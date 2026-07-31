from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .core import (
    CURRENT_STATUSES,
    SENSITIVITIES,
    Brain,
    CerebroError,
    Note,
    _safe_evidence_path,
    parse_frontmatter,
)

TASK_FILE = "cerebro-task.json"
PROPOSAL_FIELDS = {
    "schema_version",
    "id",
    "project",
    "type",
    "target",
    "sensitivity",
    "sources",
    "tags",
    "supersedes",
    "summary",
    "read_when",
    "title",
    "body",
    "requested_authority",
    "evidence_paths",
}
REQUESTED_AUTHORITIES = {"owner-accepted", "source-bound"}
TARGET_PREFIXES = {"decisions", "runbooks", "incidents", "research"}
DEFAULT_CURRENT_STATUS = {
    "state": "current",
    "reference": "active",
    "decision": "accepted",
    "runbook": "active",
    "incident": "open",
    "research": "current",
}


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    base_commit: str
    repository_root: Path
    started_at: str


def _git(cwd: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise CerebroError("Git task provenance is unavailable")
    return completed.stdout.strip()


def repository_root(cwd: Path) -> Path:
    raw = _git(cwd, "rev-parse", "--show-toplevel")
    root = Path(raw).resolve()
    if not root.is_dir():
        raise CerebroError("Git repository root is unavailable")
    return root


def task_record_path(cwd: Path) -> Path:
    root = repository_root(cwd)
    raw = _git(root, "rev-parse", "--git-path", TASK_FILE)
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return Path(os.path.abspath(path))


def _atomic_json(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise CerebroError(f"refusing symlinked state file: {path}")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
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


def init_task(cwd: Path, task_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", task_id):
        raise CerebroError("task id must contain lowercase letters, digits, hyphens, or underscores")
    root = repository_root(cwd)
    if _git(root, "status", "--porcelain"):
        raise CerebroError("task-init requires a clean Git worktree")
    base_commit = _git(root, "rev-parse", "HEAD")
    payload = {
        "schema_version": 1,
        "task_id": task_id,
        "base_commit": base_commit,
        "repository_root": str(root),
        "started_at": datetime.now(UTC).isoformat(),
    }
    _atomic_json(task_record_path(root), payload)
    return payload


def load_task(cwd: Path) -> TaskRecord | None:
    path = task_record_path(cwd)
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise CerebroError("task provenance file must be a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CerebroError("task provenance file is invalid") from exc
    expected = {
        "schema_version",
        "task_id",
        "base_commit",
        "repository_root",
        "started_at",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise CerebroError("task provenance file has an invalid schema")
    root = repository_root(cwd)
    if (
        payload.get("schema_version") != 1
        or payload.get("repository_root") != str(root)
        or not isinstance(payload.get("task_id"), str)
        or not re.fullmatch(
            r"[a-z0-9]+(?:[-_][a-z0-9]+)*",
            str(payload.get("task_id", "")),
        )
        or not re.fullmatch(r"[0-9a-f]{40}", str(payload.get("base_commit", "")))
        or not isinstance(payload.get("started_at"), str)
    ):
        raise CerebroError("task provenance file does not match this repository")
    try:
        started = datetime.fromisoformat(payload["started_at"])
    except ValueError as exc:
        raise CerebroError("task provenance file has an invalid timestamp") from exc
    if started.tzinfo is None:
        raise CerebroError("task provenance file has an invalid timestamp")
    return TaskRecord(
        task_id=payload["task_id"],
        base_commit=payload["base_commit"],
        repository_root=root,
        started_at=payload["started_at"],
    )


def _changed_paths(root: Path, task: TaskRecord) -> set[str]:
    if (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", task.base_commit, "HEAD"],
            cwd=root,
            capture_output=True,
            check=False,
        ).returncode
        != 0
    ):
        raise CerebroError("task base is not an ancestor of the current commit")
    commands = [
        ("diff", "--name-only", f"{task.base_commit}..HEAD", "--"),
        ("diff", "--cached", "--name-only", "--"),
        ("diff", "--name-only", "--"),
        ("ls-files", "--others", "--exclude-standard"),
    ]
    changed: set[str] = set()
    for command in commands:
        changed.update(line for line in _git(root, *command).splitlines() if line)
    return changed


def assess_source_provenance(cwd: Path, evidence_paths: list[str]) -> dict[str, Any]:
    normalized: list[str] = []
    for raw in evidence_paths:
        safe = _safe_evidence_path(raw)
        if safe is None:
            raise CerebroError("evidence paths must be normalized project-relative paths")
        normalized.append(safe)
    task = load_task(cwd)
    if task is None:
        return {
            "eligible": False,
            "reason": "missing task metadata",
            "task_id": None,
            "base_commit": None,
            "touched_evidence": normalized,
        }
    changed = _changed_paths(task.repository_root, task)
    touched = sorted(set(normalized) & changed)
    return {
        "eligible": not touched,
        "reason": "evidence was touched in this task" if touched else "independent task provenance",
        "task_id": task.task_id,
        "base_commit": task.base_commit,
        "touched_evidence": touched,
    }


def load_proposal(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CerebroError(f"{path}: proposal must be a regular JSON file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CerebroError(f"{path}: invalid proposal JSON") from exc
    if not isinstance(payload, dict) or set(payload) != PROPOSAL_FIELDS:
        raise CerebroError(
            f"{path}: proposal must contain exactly {', '.join(sorted(PROPOSAL_FIELDS))}"
        )
    if payload["schema_version"] != 1:
        raise CerebroError(f"{path}: proposal schema_version must be 1")
    for field in ("id", "project", "type", "target", "summary", "read_when", "title", "body"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise CerebroError(f"{path}: {field} must be a non-empty string")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", payload["id"]):
        raise CerebroError(f"{path}: id must be a lowercase kebab-case slug")
    if payload["type"] not in CURRENT_STATUSES:
        raise CerebroError(f"{path}: unsupported proposal note type")
    if payload["sensitivity"] not in SENSITIVITIES:
        raise CerebroError(f"{path}: invalid sensitivity")
    for field in ("sources", "tags", "supersedes", "evidence_paths"):
        if not isinstance(payload[field], list) or not all(
            isinstance(item, str) for item in payload[field]
        ):
            raise CerebroError(f"{path}: {field} must be a list of strings")
    if not payload["sources"]:
        raise CerebroError(f"{path}: sources must not be empty")
    if payload["requested_authority"] not in REQUESTED_AUTHORITIES:
        raise CerebroError(f"{path}: requested_authority is invalid")
    if payload["requested_authority"] == "source-bound" and not payload["evidence_paths"]:
        raise CerebroError(f"{path}: source-bound proposals require evidence_paths")
    _safe_target(payload["target"])
    return payload


def _safe_target(raw: str) -> Path:
    safe = _safe_evidence_path(raw)
    if safe is None or not safe.endswith(".md"):
        raise CerebroError("proposal target must be a normalized Markdown path")
    path = Path(safe)
    if safe not in {"State.md", "Agent Map.md"} and (
        not path.parts or path.parts[0] not in TARGET_PREFIXES
    ):
        raise CerebroError("proposal target is outside the governed project note paths")
    return path


def check_proposal(brain: Brain, cwd: Path, path: Path) -> dict[str, Any]:
    proposal = load_proposal(path)
    project = brain.resolve(cwd)
    if proposal["project"] != project.id:
        raise CerebroError("proposal project does not match the resolved project")
    requested = str(proposal["requested_authority"])
    if requested == "source-bound":
        provenance = assess_source_provenance(cwd, list(proposal["evidence_paths"]))
        eligible = bool(provenance["eligible"])
    else:
        provenance = {
            "eligible": False,
            "reason": "owner confirmation is interactive",
            "task_id": None,
            "base_commit": None,
            "touched_evidence": [],
        }
        eligible = False
    return {
        "schema_version": 1,
        "proposal": proposal["id"],
        "project": project.id,
        "requested_authority": requested,
        "automatic_promotion_eligible": eligible,
        "provenance": provenance,
    }


def _json_line(key: str, value: Any) -> str:
    return f"{key}: {json.dumps(value, separators=(',', ':'), sort_keys=True)}\n"


def _render_note(
    brain: Brain,
    cwd: Path,
    proposal: dict[str, Any],
    authority: str,
    accepted_at: str,
    existing: Note | None,
) -> str:
    project = brain.resolve(cwd)
    created = (
        str(existing.metadata["created"])
        if existing is not None
        else datetime.now(UTC).date().isoformat()
    )
    today = datetime.now(UTC).date().isoformat()
    if authority == "source-bound":
        task = load_task(cwd)
        if task is None:
            raise CerebroError("source-bound promotion requires task metadata")
        promotion: dict[str, str] = {
            "method": "task-provenance",
            "accepted_at": accepted_at,
            "task_id": task.task_id,
            "base_commit": task.base_commit,
        }
        verification = [
            brain.hash_evidence(project, cwd, path)
            for path in proposal["evidence_paths"]
        ]
    else:
        promotion = {
            "method": "interactive-owner-confirmation",
            "accepted_at": accepted_at,
        }
        verification = []
    status = DEFAULT_CURRENT_STATUS[str(proposal["type"])]
    role_line = (
        "role: agent-map\n"
        if proposal["type"] == "reference" and proposal["target"] == "Agent Map.md"
        else ""
    )
    rendered = (
        "---\n"
        "schema_version: 2\n"
        f"id: {proposal['id']}\n"
        f"project: {proposal['project']}\n"
        f"type: {proposal['type']}\n"
        f"status: {status}\n"
        f"authority: {authority}\n"
        + _json_line("promotion", promotion)
        + role_line
        + f"created: {created}\n"
        + f"updated: {today}\n"
        + f"last_verified: {today}\n"
        + f"sensitivity: {proposal['sensitivity']}\n"
        + _json_line("sources", proposal["sources"])
    )
    if verification:
        rendered += _json_line("verification", verification)
    rendered += (
        _json_line("tags", proposal["tags"])
        + _json_line("supersedes", proposal["supersedes"])
        + _json_line("summary", proposal["summary"])
        + _json_line("read_when", proposal["read_when"])
        + "---\n\n"
        + f"# {proposal['title'].strip()}\n\n"
        + proposal["body"].strip()
        + "\n"
    )
    return str(rendered)


def apply_proposal(
    brain: Brain,
    cwd: Path,
    proposal_path: Path,
    *,
    input_fn: Callable[[str], str] = input,
) -> dict[str, Any]:
    if brain.validate():
        raise CerebroError("brain must validate before applying a proposal")
    proposal = load_proposal(proposal_path)
    project = brain.resolve(cwd)
    if proposal["project"] != project.id:
        raise CerebroError("proposal project does not match the resolved project")
    authority = str(proposal["requested_authority"])
    if authority == "source-bound":
        provenance = assess_source_provenance(cwd, list(proposal["evidence_paths"]))
        if not provenance["eligible"]:
            raise CerebroError(
                f"source-bound promotion requires review: {provenance['reason']}",
                exit_code=3,
            )
    else:
        typed = input_fn(
            f"Type {proposal['id']} to confirm owner acceptance; anything else cancels: "
        )
        if typed != proposal["id"]:
            raise CerebroError("owner acceptance was not confirmed", exit_code=3)

    relative = _safe_target(str(proposal["target"]))
    target = project.path / relative
    cursor = project.path
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise CerebroError("proposal target contains a symlink")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise CerebroError("proposal target cannot be a symlink")
    existing: Note | None = None
    previous: bytes | None = None
    if target.exists():
        if not target.is_file():
            raise CerebroError("proposal target must be a regular file")
        previous = target.read_bytes()
        existing = parse_frontmatter(target)
        if (
            existing.id != proposal["id"]
            or existing.project != proposal["project"]
            or existing.note_type != proposal["type"]
        ):
            raise CerebroError("proposal cannot replace a different note identity")

    accepted_at = datetime.now(UTC).isoformat()
    rendered = _render_note(brain, cwd, proposal, authority, accepted_at, existing)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        issues = Brain(brain.root).validate()
        if issues:
            raise CerebroError(f"proposal produced invalid brain: {issues[0].render()}")
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            target.write_bytes(previous)
        raise
    return {
        "schema_version": 1,
        "status": "applied",
        "proposal": proposal["id"],
        "authority": authority,
        "path": str(target.relative_to(brain.root)),
        "commit_message": f"accept: {proposal['id']} as {authority}",
    }
