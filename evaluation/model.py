from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cerebro_context.core import Brain, CerebroError

CONDITIONS = ("repository", "agents", "cerebro")
CURRENT_STATUSES = {
    "state": "current",
    "reference": "active",
    "decision": "accepted",
    "runbook": "active",
    "incident": "open",
    "research": "current",
}


class EvaluationError(Exception):
    """A governed evaluation configuration or execution error."""


@dataclass(frozen=True)
class Expected:
    answer: str
    sources: tuple[str, ...]
    forbidden_answers: tuple[str, ...]
    cerebro_status: str
    block_relevant: bool


@dataclass(frozen=True)
class Packet:
    packet_id: str
    title: str
    task: str
    answer_options: tuple[str, ...]
    repository_files: dict[str, str]
    agents_context: str
    cerebro: dict[str, Any]
    expected: Expected
    path: Path


@dataclass(frozen=True)
class ContextResult:
    status: str
    payload: dict[str, Any] | None
    error_category: str | None
    error_code: int | None


def _safe_relative_path(raw_path: Any) -> str:
    if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path:
        raise EvaluationError("packet file paths must be non-empty POSIX paths")
    path = Path(raw_path)
    if path.is_absolute() or raw_path.startswith("~") or ".." in path.parts:
        raise EvaluationError(f"unsafe packet file path: {raw_path}")
    normalized = path.as_posix()
    if normalized in {"", "."} or normalized.startswith("./"):
        raise EvaluationError(f"packet file path must be normalized: {raw_path}")
    return normalized


def _require_keys(data: dict[str, Any], required: set[str], label: str) -> None:
    missing = required - data.keys()
    if missing:
        raise EvaluationError(f"{label} is missing: {', '.join(sorted(missing))}")


def load_packet(path: Path) -> Packet:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"{path}: invalid packet JSON") from exc
    if not isinstance(raw, dict):
        raise EvaluationError(f"{path}: packet must be an object")
    _require_keys(
        raw,
        {
            "schema_version",
            "id",
            "title",
            "task",
            "answer_options",
            "repository_files",
            "agents_context",
            "cerebro",
            "expected",
        },
        str(path),
    )
    if raw["schema_version"] != 1:
        raise EvaluationError(f"{path}: schema_version must be 1")
    for key in ("id", "title", "task", "agents_context"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise EvaluationError(f"{path}: {key} must be a non-empty string")
    answer_options = raw["answer_options"]
    if (
        not isinstance(answer_options, list)
        or len(answer_options) < 2
        or not all(isinstance(item, str) and item for item in answer_options)
        or len(set(answer_options)) != len(answer_options)
    ):
        raise EvaluationError(f"{path}: answer_options must contain unique strings")
    files = raw["repository_files"]
    if not isinstance(files, dict) or not files:
        raise EvaluationError(f"{path}: repository_files must be a non-empty object")
    repository_files: dict[str, str] = {}
    for raw_file, content in files.items():
        safe_file = _safe_relative_path(raw_file)
        if not isinstance(content, str):
            raise EvaluationError(f"{path}: repository file values must be strings")
        repository_files[safe_file] = content
    cerebro = raw["cerebro"]
    if not isinstance(cerebro, dict):
        raise EvaluationError(f"{path}: cerebro must be an object")
    _require_keys(cerebro, {"state", "agent_map"}, f"{path}: cerebro")
    expected_raw = raw["expected"]
    if not isinstance(expected_raw, dict):
        raise EvaluationError(f"{path}: expected must be an object")
    _require_keys(
        expected_raw,
        {
            "answer",
            "sources",
            "forbidden_answers",
            "cerebro_status",
            "block_relevant",
        },
        f"{path}: expected",
    )
    answer = expected_raw["answer"]
    sources = expected_raw["sources"]
    forbidden = expected_raw["forbidden_answers"]
    cerebro_status = expected_raw["cerebro_status"]
    block_relevant = expected_raw["block_relevant"]
    if answer not in answer_options:
        raise EvaluationError(f"{path}: expected answer is not an answer option")
    if not isinstance(sources, list) or not sources or not all(
        isinstance(item, str) and item for item in sources
    ):
        raise EvaluationError(f"{path}: expected sources must be non-empty strings")
    if not isinstance(forbidden, list) or not all(isinstance(item, str) for item in forbidden):
        raise EvaluationError(f"{path}: forbidden_answers must be strings")
    if cerebro_status not in {"current", "blocked"}:
        raise EvaluationError(f"{path}: cerebro_status must be current or blocked")
    if not isinstance(block_relevant, bool):
        raise EvaluationError(f"{path}: block_relevant must be a boolean")
    return Packet(
        packet_id=raw["id"],
        title=raw["title"],
        task=raw["task"],
        answer_options=tuple(answer_options),
        repository_files=repository_files,
        agents_context=raw["agents_context"],
        cerebro=cerebro,
        expected=Expected(
            answer=answer,
            sources=tuple(sources),
            forbidden_answers=tuple(forbidden),
            cerebro_status=cerebro_status,
            block_relevant=block_relevant,
        ),
        path=path,
    )


def load_packets(directory: Path, selected: set[str] | None = None) -> list[Packet]:
    packets = [load_packet(path) for path in sorted(directory.glob("*.json"))]
    if not packets:
        raise EvaluationError(f"no evaluation packets found in {directory}")
    ids = [packet.packet_id for packet in packets]
    duplicates = sorted({packet_id for packet_id in ids if ids.count(packet_id) > 1})
    if duplicates:
        raise EvaluationError(f"duplicate packet ids: {', '.join(duplicates)}")
    if selected is not None:
        missing = sorted(selected - set(ids))
        if missing:
            raise EvaluationError(f"unknown packet ids: {', '.join(missing)}")
        packets = [packet for packet in packets if packet.packet_id in selected]
    return packets


def materialize_repository(packet: Packet, workspace: Path) -> None:
    workspace.mkdir(parents=True)
    for relative, content in packet.repository_files.items():
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")


def _json_line(key: str, value: Any) -> str:
    return f"{key}: {json.dumps(value, separators=(',', ':'), sort_keys=True)}\n"


def _render_note(
    packet: Packet,
    spec: dict[str, Any],
    *,
    note_id: str,
    note_type: str,
    status: str,
    role: str | None = None,
) -> str:
    if not isinstance(spec, dict):
        raise EvaluationError(f"{packet.packet_id}: note specifications must be objects")
    summary = spec.get("summary")
    body = spec.get("body")
    if not isinstance(summary, str) or not summary:
        raise EvaluationError(f"{packet.packet_id}: note summary must be non-empty")
    if not isinstance(body, str) or not body:
        raise EvaluationError(f"{packet.packet_id}: note body must be non-empty")
    today = datetime.now(UTC).date().isoformat()
    last_verified = spec.get("last_verified", today)
    if not isinstance(last_verified, str):
        raise EvaluationError(f"{packet.packet_id}: last_verified must be a string")
    metadata = (
        "---\n"
        "schema_version: 1\n"
        f"id: {note_id}\n"
        f"project: {packet.packet_id}\n"
        f"type: {note_type}\n"
        f"status: {status}\n"
    )
    if role:
        metadata += f"role: {role}\n"
    metadata += (
        f"created: {last_verified}\n"
        f"updated: {last_verified}\n"
        f"last_verified: {last_verified}\n"
        "sensitivity: internal\n"
        + _json_line("sources", [f"repo://evaluation/{packet.packet_id}"])
    )
    verification_specs = spec.get("verification", [])
    if verification_specs:
        if not isinstance(verification_specs, list):
            raise EvaluationError(f"{packet.packet_id}: verification must be a list")
        checks: list[dict[str, str]] = []
        for verification in verification_specs:
            if not isinstance(verification, dict):
                raise EvaluationError(f"{packet.packet_id}: verification entries must be objects")
            path = _safe_relative_path(verification.get("path"))
            sha256_of = verification.get("sha256_of")
            if not isinstance(sha256_of, str):
                raise EvaluationError(
                    f"{packet.packet_id}: verification sha256_of must be text"
                )
            checks.append(
                {
                    "kind": "file-sha256",
                    "path": path,
                    "sha256": hashlib.sha256(sha256_of.encode()).hexdigest(),
                }
            )
        metadata += _json_line("verification", checks)
    metadata += (
        "tags: []\n"
        "supersedes: []\n"
        + _json_line("summary", summary)
        + _json_line("read_when", "Read for this bounded evaluation task.")
        + "---\n\n"
        + body.strip()
        + "\n"
    )
    return metadata


def materialize_brain(packet: Packet, root: Path, workspace: Path) -> None:
    projects = root / "projects" / packet.packet_id
    history = root / "history" / packet.packet_id
    for directory in (
        projects / "decisions",
        projects / "runbooks",
        projects / "incidents",
        projects / "research",
        history,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    freshness = {
        "state": 365000,
        "reference": 365000,
        "decision": 365000,
        "runbook": 365000,
        "incident": 365000,
        "research": 365000,
        **packet.cerebro.get("freshness_days", {}),
    }
    (root / "cerebro.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "projects_dir": "projects",
                "freshness_days": freshness,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (projects / "project.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": packet.packet_id,
                "name": packet.title,
                "roots": [str(workspace)],
                "sensitivity": "internal",
                "history_paths": [f"history/{packet.packet_id}"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (projects / "State.md").write_text(
        _render_note(
            packet,
            packet.cerebro["state"],
            note_id=f"{packet.packet_id}-state",
            note_type="state",
            status="current",
        ),
        encoding="utf-8",
    )
    (projects / "Agent Map.md").write_text(
        _render_note(
            packet,
            packet.cerebro["agent_map"],
            note_id=f"{packet.packet_id}-agent-map",
            note_type="reference",
            status="active",
            role="agent-map",
        ),
        encoding="utf-8",
    )
    notes = packet.cerebro.get("notes", [])
    if not isinstance(notes, list):
        raise EvaluationError(f"{packet.packet_id}: notes must be a list")
    for index, spec in enumerate(notes):
        if not isinstance(spec, dict):
            raise EvaluationError(f"{packet.packet_id}: note specifications must be objects")
        note_type = spec.get("type")
        if note_type not in CURRENT_STATUSES:
            raise EvaluationError(f"{packet.packet_id}: invalid note type {note_type}")
        note_id = spec.get("id", f"{packet.packet_id}-{note_type}-{index}")
        if not isinstance(note_id, str) or not note_id:
            raise EvaluationError(f"{packet.packet_id}: note id must be a string")
        directory = projects / {
            "decision": "decisions",
            "runbook": "runbooks",
            "incident": "incidents",
            "research": "research",
            "reference": "research",
            "state": "research",
        }[note_type]
        (directory / f"{index:02d}-{note_id}.md").write_text(
            _render_note(
                packet,
                spec,
                note_id=note_id,
                note_type=note_type,
                status=str(spec.get("status", CURRENT_STATUSES[note_type])),
            ),
            encoding="utf-8",
        )
    history_specs = packet.cerebro.get("history", [])
    if not isinstance(history_specs, list):
        raise EvaluationError(f"{packet.packet_id}: history must be a list")
    for index, spec in enumerate(history_specs):
        note_id = str(spec.get("id", f"{packet.packet_id}-history-{index}"))
        (history / f"{index:02d}-{note_id}.md").write_text(
            _render_note(
                packet,
                spec,
                note_id=note_id,
                note_type="log",
                status="historical",
            ),
            encoding="utf-8",
        )


def build_cerebro_context(packet: Packet, root: Path, workspace: Path) -> ContextResult:
    materialize_brain(packet, root, workspace)
    try:
        brain = Brain(root)
        issues = brain.validate()
        if issues:
            raise EvaluationError(
                f"{packet.packet_id}: generated brain failed validation: {issues[0].render()}"
            )
        payload = brain.context(
            brain.project(packet.packet_id),
            query="",
            require_fresh=True,
            verify_evidence=True,
            cwd=workspace,
        )
        return ContextResult(
            status="current",
            payload=payload,
            error_category=None,
            error_code=None,
        )
    except CerebroError as exc:
        return ContextResult(
            status="blocked",
            payload=None,
            error_category=str(exc),
            error_code=exc.exit_code,
        )


def _repository_block(packet: Packet) -> str:
    chunks: list[str] = []
    for path, content in sorted(packet.repository_files.items()):
        chunks.append(f"--- {path} ---\n{content.rstrip()}")
    return "\n\n".join(chunks)


def _bounded_context_payload(context: ContextResult) -> dict[str, Any]:
    if context.payload is None:
        return {
            "status": context.status,
            "error_category": context.error_category,
            "error_code": context.error_code,
        }
    return {
        "status": context.status,
        "project": context.payload["project"],
        "evidence": context.payload.get("evidence"),
        "warnings": context.payload.get("warnings", []),
        "documents": [
            {
                "id": document["id"],
                "type": document["type"],
                "summary": document["summary"],
                "content": document.get("content", ""),
            }
            for document in context.payload["documents"]
        ],
    }


def prompt_for_condition(
    packet: Packet,
    condition: str,
    context: ContextResult | None,
) -> str:
    if condition not in CONDITIONS:
        raise EvaluationError(f"unknown condition: {condition}")
    if condition == "repository":
        additional = "No additional project context was supplied."
    elif condition == "agents":
        additional = f"AGENTS.md:\n{packet.agents_context.strip()}"
    else:
        if context is None:
            raise EvaluationError("Cerebro condition requires generated context")
        additional = "Cerebro task-boundary result:\n" + json.dumps(
            _bounded_context_payload(context),
            indent=2,
            sort_keys=True,
        )
    options = ", ".join(packet.answer_options)
    return f"""You are evaluating one bounded software-project decision.

Current repository files outrank additional project context when they directly disagree. Do not
invent facts outside the supplied snapshot. Return only the requested structured result and no
hidden reasoning.

TASK
{packet.task}

ALLOWED ANSWERS
{options}

REPOSITORY SNAPSHOT
{_repository_block(packet)}

ADDITIONAL PROJECT CONTEXT
{additional}

Return:
- answer: exactly one allowed answer
- source: one repository path, `cerebro:<note-id>`, `agents:AGENTS.md`, or `insufficient`
- rationale: at most 30 words
"""


def response_schema(packet: Packet) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "answer": {"type": "string", "enum": list(packet.answer_options)},
            "source": {"type": "string"},
            "rationale": {"type": "string", "maxLength": 240},
        },
        "required": ["answer", "source", "rationale"],
    }
