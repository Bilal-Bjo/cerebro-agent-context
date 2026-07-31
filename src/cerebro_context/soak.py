from __future__ import annotations

import json
import os
import statistics
import tempfile
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from .core import Brain, CerebroError

RATINGS = {"yes", "no", "unrated"}
DEFAULT_DAYS = 14
DEFAULT_MIN_RATED_TASKS = 20
DEFAULT_MAX_FALSE_BLOCK_RATE = 0.05
DEFAULT_MAX_REPEATED_EXPLANATION_RATE = 0.10
DEFAULT_MAX_CORRECTION_RATE = 0.10
DEFAULT_MAX_MEDIAN_UPKEEP_SECONDS = 60


def default_state_dir() -> Path:
    configured = os.environ.get("CEREBRO_SOAK_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path("~/.local/state/cerebro-soak").expanduser()


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise CerebroError("soak state directory must be a regular directory")
    os.chmod(path, 0o700)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _ensure_private_directory(path.parent)
    if path.exists() and path.is_symlink():
        raise CerebroError("soak state files cannot be symlinks")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def init_soak(
    state_dir: Path,
    *,
    days: int = DEFAULT_DAYS,
    min_rated_tasks: int = DEFAULT_MIN_RATED_TASKS,
    max_false_block_rate: float = DEFAULT_MAX_FALSE_BLOCK_RATE,
    max_repeated_explanation_rate: float = DEFAULT_MAX_REPEATED_EXPLANATION_RATE,
    max_correction_rate: float = DEFAULT_MAX_CORRECTION_RATE,
    max_median_upkeep_seconds: int = DEFAULT_MAX_MEDIAN_UPKEEP_SECONDS,
) -> dict[str, Any]:
    if not 1 <= days <= 90:
        raise CerebroError("soak days must be between 1 and 90")
    if min_rated_tasks < 1:
        raise CerebroError("minimum rated tasks must be positive")
    for label, value in (
        ("false block", max_false_block_rate),
        ("repeated explanation", max_repeated_explanation_rate),
        ("correction", max_correction_rate),
    ):
        if not 0 <= value <= 1:
            raise CerebroError(f"maximum {label} rate must be between 0 and 1")
    if max_median_upkeep_seconds < 0:
        raise CerebroError("maximum median upkeep seconds cannot be negative")
    _ensure_private_directory(state_dir)
    config_path = state_dir / "config.json"
    events_path = state_dir / "events.jsonl"
    if config_path.exists() or events_path.exists():
        raise CerebroError("soak state already exists; refusing to rewrite preregistered gates")
    started = datetime.now(UTC)
    payload = {
        "schema_version": 1,
        "started_at": started.isoformat(),
        "ends_on": (started.date() + timedelta(days=days)).isoformat(),
        "thresholds": {
            "minimum_rated_tasks": min_rated_tasks,
            "maximum_false_block_rate": max_false_block_rate,
            "maximum_repeated_explanation_rate": max_repeated_explanation_rate,
            "maximum_correction_rate": max_correction_rate,
            "maximum_median_upkeep_seconds": max_median_upkeep_seconds,
        },
        "method": {
            "control_condition": "none",
            "automatic_fields": [
                "context_outcome",
                "context_exit_code",
                "warnings",
                "evidence",
                "documents",
                "latency_ms",
            ],
            "owner_rated_fields": [
                "correction_needed",
                "repeated_explanation",
                "false_block",
                "useful_context",
                "upkeep_seconds",
            ],
            "missing_ratings": "unrated and excluded from success denominators",
        },
    }
    _atomic_json(config_path, payload)
    descriptor = os.open(events_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    return payload


def _context_category(exc: CerebroError) -> str:
    message = str(exc).casefold()
    if "evidence" in message:
        return "evidence_block"
    if "restricted" in message:
        return "access_block"
    if "stale" in message or "expired" in message:
        return "age_block"
    if "validation" in message:
        return "validation_block"
    return "unavailable"


def _validate_rating(value: str, label: str) -> str:
    if value not in RATINGS:
        raise CerebroError(f"{label} must be yes, no, or unrated")
    return value


def record_soak(
    brain: Brain,
    cwd: Path,
    state_dir: Path,
    *,
    correction_needed: str = "unrated",
    repeated_explanation: str = "unrated",
    false_block: str = "unrated",
    useful_context: str = "unrated",
    upkeep_seconds: int | None = None,
) -> dict[str, Any]:
    config_path = state_dir / "config.json"
    events_path = state_dir / "events.jsonl"
    if not config_path.is_file() or not events_path.is_file():
        raise CerebroError("soak is not initialized")
    if config_path.is_symlink() or events_path.is_symlink():
        raise CerebroError("soak state files cannot be symlinks")
    ratings = {
        "correction_needed": _validate_rating(correction_needed, "correction-needed"),
        "repeated_explanation": _validate_rating(
            repeated_explanation, "repeated-explanation"
        ),
        "false_block": _validate_rating(false_block, "false-block"),
        "useful_context": _validate_rating(useful_context, "useful-context"),
    }
    if upkeep_seconds is not None and upkeep_seconds < 0:
        raise CerebroError("upkeep seconds cannot be negative")

    started = time.monotonic()
    project_id: str | None = None
    try:
        project = brain.resolve(cwd)
        project_id = project.id
        payload = brain.context(
            project,
            verify_evidence=True,
            cwd=cwd,
        )
        context_outcome = str(payload["status"])
        context_exit_code = 0
        warnings = len(payload.get("warnings", []))
        evidence = payload.get("evidence", {})
        evidence_status = str(evidence.get("status", "unknown"))
        evidence_checks = int(evidence.get("checks", 0))
        evidence_failures = len(evidence.get("failures", []))
        documents = len(payload.get("documents", []))
    except CerebroError as exc:
        context_outcome = _context_category(exc)
        context_exit_code = exc.exit_code
        warnings = 0
        evidence_status = "blocked"
        evidence_checks = 0
        evidence_failures = 1 if context_outcome == "evidence_block" else 0
        documents = 0
    event = {
        "schema_version": 1,
        "event_id": str(uuid.uuid4()),
        "recorded_at": datetime.now(UTC).isoformat(),
        "project": project_id,
        "condition": "cerebro-required",
        "automatic": {
            "context_outcome": context_outcome,
            "context_exit_code": context_exit_code,
            "warnings": warnings,
            "evidence_status": evidence_status,
            "evidence_checks": evidence_checks,
            "evidence_failures": evidence_failures,
            "documents": documents,
            "latency_ms": round((time.monotonic() - started) * 1000),
        },
        "owner_rated": {
            **ratings,
            "upkeep_seconds": upkeep_seconds,
        },
    }
    encoded = (json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n").encode()
    descriptor = os.open(
        events_path,
        os.O_APPEND | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        with os.fdopen(descriptor, "ab", closefd=False) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    return event


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CerebroError(f"{path}: invalid soak state") from exc
    if not isinstance(payload, dict):
        raise CerebroError(f"{path}: soak state must be an object")
    return payload


def _load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise TypeError
            if (
                set(event)
                != {
                    "schema_version",
                    "event_id",
                    "recorded_at",
                    "project",
                    "condition",
                    "automatic",
                    "owner_rated",
                }
                or event.get("schema_version") != 1
                or event.get("condition") != "cerebro-required"
                or not isinstance(event.get("automatic"), dict)
                or not isinstance(event.get("owner_rated"), dict)
            ):
                raise TypeError
            events.append(event)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise CerebroError(f"{path}: invalid soak events") from exc
    return events


def _rated_rate(events: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [
        event.get("owner_rated", {}).get(field)
        for event in events
        if event.get("owner_rated", {}).get(field) in {"yes", "no"}
    ]
    yes = sum(value == "yes" for value in values)
    return {
        "yes": yes,
        "rated": len(values),
        "unrated": len(events) - len(values),
        "rate": round(yes / len(values), 4) if values else None,
    }


def summarize_soak(state_dir: Path) -> dict[str, Any]:
    config = _load_json(state_dir / "config.json")
    events = _load_events(state_dir / "events.jsonl")
    thresholds = config.get("thresholds", {})
    metrics = {
        field: _rated_rate(events, field)
        for field in (
            "correction_needed",
            "repeated_explanation",
            "false_block",
            "useful_context",
        )
    }
    upkeep = [
        event.get("owner_rated", {}).get("upkeep_seconds")
        for event in events
        if isinstance(event.get("owner_rated", {}).get("upkeep_seconds"), int)
    ]
    median_upkeep = statistics.median(upkeep) if upkeep else None
    rated_tasks = min(
        metrics["correction_needed"]["rated"],
        metrics["repeated_explanation"]["rated"],
        metrics["false_block"]["rated"],
    )
    try:
        duration_complete = datetime.now(UTC).date() >= date.fromisoformat(
            str(config["ends_on"])
        )
        minimum_rated_tasks = int(thresholds["minimum_rated_tasks"])
        maximum_false_block_rate = float(thresholds["maximum_false_block_rate"])
        maximum_repeated_explanation_rate = float(
            thresholds["maximum_repeated_explanation_rate"]
        )
        maximum_correction_rate = float(thresholds["maximum_correction_rate"])
        maximum_median_upkeep_seconds = int(
            thresholds["maximum_median_upkeep_seconds"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CerebroError("soak configuration is invalid") from exc
    gates = {
        "duration_complete": duration_complete,
        "minimum_rated_tasks": rated_tasks
        >= minimum_rated_tasks,
        "false_block_rate": (
            metrics["false_block"]["rate"] is not None
            and metrics["false_block"]["rate"]
            <= maximum_false_block_rate
        ),
        "repeated_explanation_rate": (
            metrics["repeated_explanation"]["rate"] is not None
            and metrics["repeated_explanation"]["rate"]
            <= maximum_repeated_explanation_rate
        ),
        "correction_rate": (
            metrics["correction_needed"]["rate"] is not None
            and metrics["correction_needed"]["rate"]
            <= maximum_correction_rate
        ),
        "median_upkeep_seconds": (
            median_upkeep is not None
            and median_upkeep
            <= maximum_median_upkeep_seconds
        ),
    }
    return {
        "schema_version": 1,
        "status": "passed" if all(gates.values()) else "open",
        "started_at": config["started_at"],
        "ends_on": config["ends_on"],
        "events": len(events),
        "rated_tasks": rated_tasks,
        "metrics": metrics,
        "median_upkeep_seconds": median_upkeep,
        "gates": gates,
        "limitations": [
            "There is no uninstrumented control condition.",
            "Owner-rated fields are judgments; missing ratings never count as success.",
            "The soak establishes personal utility only after its duration and sample gates close.",
        ],
    }
