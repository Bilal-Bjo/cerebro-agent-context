from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

__version__ = "0.3.0"

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SENSITIVITIES = {"public", "internal", "restricted"}
CURRENT_STATUSES = {
    "state": {"current"},
    "reference": {"active"},
    "decision": {"accepted"},
    "runbook": {"active"},
    "incident": {"open", "monitoring"},
    "research": {"current"},
}
ALL_STATUSES = {
    **CURRENT_STATUSES,
    "log": {"historical"},
}
NONCURRENT_STATUSES = {
    "stale",
    "expired",
    "superseded",
    "rejected",
    "resolved",
    "historical",
    "proposed",
}
AUTHORITIES = {"owner-accepted", "source-bound", "proposal"}
REQUIRED_NOTE_FIELDS = {
    "schema_version",
    "id",
    "project",
    "type",
    "status",
    "created",
    "updated",
    "last_verified",
    "sensitivity",
    "sources",
    "tags",
    "supersedes",
    "summary",
    "read_when",
}
SECRET_PATTERNS = [
    re.compile(
        r"(?i)\b(password|passwd|api[_ -]?key|access[_ -]?token|client[_ -]?secret|"
        r"private[_ -]?key|recovery[_ -]?code)\b\s*[:=]\s*[`\"']?([^\s`\"']+)"
    ),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_VERIFICATION_CHECKS = 8


class CerebroError(Exception):
    """A governed, user-facing Cerebro error."""

    def __init__(self, message: str, exit_code: int = 2):
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class Issue:
    path: str
    message: str
    line: int | None = None

    def render(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"{location}: {self.message}"


@dataclass(frozen=True)
class Note:
    path: Path
    metadata: dict[str, Any]
    body: str
    raw: str
    partition: str = "current"

    @property
    def id(self) -> str:
        return str(self.metadata.get("id", ""))

    @property
    def project(self) -> str:
        return str(self.metadata.get("project", ""))

    @property
    def note_type(self) -> str:
        return str(self.metadata.get("type", ""))

    @property
    def status(self) -> str:
        return str(self.metadata.get("status", ""))

    @property
    def sensitivity(self) -> str:
        return str(self.metadata.get("sensitivity", "internal"))

    @property
    def authority(self) -> str:
        value = self.metadata.get("authority")
        return str(value) if value is not None else "legacy-declared"

    def title(self) -> str:
        for line in self.body.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return self.id


@dataclass(frozen=True)
class Project:
    path: Path
    data: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.data["id"])

    @property
    def name(self) -> str:
        return str(self.data["name"])

    @property
    def roots(self) -> list[str]:
        return [str(item) for item in self.data.get("roots", [])]

    @property
    def sensitivity(self) -> str:
        return str(self.data.get("sensitivity", "internal"))

    @property
    def history_paths(self) -> list[str]:
        return [str(item) for item in self.data.get("history_paths", [])]


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_today() -> str:
    return utc_now().date().isoformat()


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value[0] in {'"', "'", "[", "{"}:
        try:
            if value[0] == "'":
                return value[1:-1] if value.endswith("'") else value[1:]
            return json.loads(value)
        except (json.JSONDecodeError, IndexError):
            return value.strip("\"'")
    if value in {"true", "false", "null"}:
        return {"true": True, "false": False, "null": None}[value]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def parse_frontmatter(path: Path, partition: str = "current") -> Note:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise CerebroError(f"{path}: note must be valid UTF-8") from exc
    if not raw.startswith("---\n"):
        raise CerebroError(f"{path}: missing YAML frontmatter")
    lines = raw.splitlines()
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise CerebroError(f"{path}: unclosed YAML frontmatter") from exc
    metadata: dict[str, Any] = {}
    for index, line in enumerate(lines[1:closing], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise CerebroError(f"{path}:{index}: expected 'key: value'")
        key, value = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise CerebroError(f"{path}:{index}: invalid frontmatter key")
        if key in metadata:
            raise CerebroError(f"{path}:{index}: duplicate frontmatter key '{key}'")
        metadata[key] = _parse_scalar(value)
    body = "\n".join(lines[closing + 1 :]).strip() + "\n"
    return Note(path=path, metadata=metadata, body=body, raw=raw, partition=partition)


def _parse_date(value: Any, field: str, path: Path, issues: list[Issue]) -> date | None:
    if not isinstance(value, str):
        issues.append(Issue(str(path), f"{field} must be an ISO date"))
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        issues.append(Issue(str(path), f"{field} must be an ISO date"))
        return None


def scan_secrets(note: Note) -> list[Issue]:
    issues: list[Issue] = []
    for line_number, line in enumerate(note.raw.splitlines(), start=1):
        for pattern in SECRET_PATTERNS:
            if pattern.search(line):
                issues.append(
                    Issue(
                        str(note.path),
                        "credential-shaped value is forbidden; store only a nonsecret locator",
                        line_number,
                    )
                )
                break
    return issues


def _safe_evidence_path(raw_path: Any) -> str | None:
    if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path:
        return None
    candidate = Path(raw_path)
    if candidate.is_absolute() or raw_path.startswith("~") or ".." in candidate.parts:
        return None
    normalized = candidate.as_posix()
    if normalized in {"", "."} or normalized.startswith("./"):
        return None
    return normalized


def validate_verification(note: Note) -> list[Issue]:
    checks = note.metadata.get("verification")
    if checks is None:
        return []
    if (
        not isinstance(checks, list)
        or not checks
        or len(checks) > MAX_VERIFICATION_CHECKS
    ):
        return [
            Issue(
                str(note.path),
                f"verification must contain 1..{MAX_VERIFICATION_CHECKS} checks",
            )
        ]

    issues: list[Issue] = []
    for index, check in enumerate(checks):
        label = f"verification[{index}]"
        if not isinstance(check, dict):
            issues.append(Issue(str(note.path), f"{label} must be an object"))
            continue
        expected_keys = {"kind", "path", "sha256"}
        if set(check) != expected_keys:
            issues.append(
                Issue(
                    str(note.path),
                    f"{label} must contain exactly kind, path, and sha256",
                )
            )
            continue
        if check.get("kind") != "file-sha256":
            issues.append(Issue(str(note.path), f"{label}.kind must be file-sha256"))
        if _safe_evidence_path(check.get("path")) is None:
            issues.append(
                Issue(
                    str(note.path),
                    f"{label}.path must be a normalized project-relative file path",
                )
            )
        digest = check.get("sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            issues.append(
                Issue(str(note.path), f"{label}.sha256 must be a lowercase SHA-256 digest")
            )
    return issues


def validate_authority(note: Note) -> list[Issue]:
    schema_version = note.metadata.get("schema_version")
    authority = note.metadata.get("authority")
    if schema_version == 1:
        if authority is not None or "promotion" in note.metadata:
            return [
                Issue(
                    str(note.path),
                    "schema_version 1 notes cannot declare authority or promotion; migrate to 2",
                )
            ]
        return []
    if schema_version == 2 and authority is None:
        return [Issue(str(note.path), "schema_version 2 notes require authority")]
    if not isinstance(authority, str) or authority not in AUTHORITIES:
        return [
            Issue(
                str(note.path),
                "authority must be owner-accepted, source-bound, or proposal",
            )
        ]
    if authority == "source-bound" and not note.metadata.get("verification"):
        return [Issue(str(note.path), "source-bound authority requires verification")]
    if authority == "proposal" and note.status in CURRENT_STATUSES.get(
        note.note_type, set()
    ):
        return [Issue(str(note.path), "proposal authority cannot use a current status")]

    promotion = note.metadata.get("promotion")
    if schema_version != 2 or authority == "proposal":
        return []
    if not isinstance(promotion, dict):
        return [Issue(str(note.path), f"{authority} authority requires promotion metadata")]
    expected_method = (
        "interactive-owner-confirmation"
        if authority == "owner-accepted"
        else "task-provenance"
    )
    if promotion.get("method") != expected_method:
        return [
            Issue(
                str(note.path),
                f"{authority} promotion.method must be {expected_method}",
            )
        ]
    accepted_at = promotion.get("accepted_at")
    if not isinstance(accepted_at, str):
        return [Issue(str(note.path), "promotion.accepted_at must be an ISO timestamp")]
    try:
        datetime.fromisoformat(accepted_at)
    except ValueError:
        return [Issue(str(note.path), "promotion.accepted_at must be an ISO timestamp")]

    if authority == "source-bound":
        if set(promotion) != {"method", "accepted_at", "task_id", "base_commit"}:
            return [
                Issue(
                    str(note.path),
                    "source-bound promotion must contain exactly method, accepted_at, "
                    "task_id, and base_commit",
                )
            ]
        if (
            not isinstance(promotion.get("task_id"), str)
            or not promotion["task_id"]
            or not isinstance(promotion.get("base_commit"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", promotion["base_commit"])
        ):
            return [Issue(str(note.path), "source-bound promotion metadata is invalid")]
    elif set(promotion) != {"method", "accepted_at"}:
        return [
            Issue(
                str(note.path),
                "owner-accepted promotion must contain exactly method and accepted_at",
            )
        ]
    return []


def validate_note(note: Note, expected_project: str) -> list[Issue]:
    issues: list[Issue] = []
    missing = sorted(REQUIRED_NOTE_FIELDS - note.metadata.keys())
    if missing:
        issues.append(Issue(str(note.path), f"missing fields: {', '.join(missing)}"))
        return issues

    data = note.metadata
    if data["schema_version"] not in {1, 2}:
        issues.append(Issue(str(note.path), "schema_version must be 1 or 2"))
    if not isinstance(data["id"], str) or not SLUG_RE.fullmatch(data["id"]):
        issues.append(Issue(str(note.path), "id must be a lowercase kebab-case slug"))
    if data["project"] != expected_project:
        issues.append(Issue(str(note.path), f"project must be '{expected_project}'"))
    note_type = data["type"]
    status = data["status"]
    if not isinstance(note_type, str) or note_type not in ALL_STATUSES:
        issues.append(Issue(str(note.path), f"unsupported note type '{note_type}'"))
    else:
        allowed = ALL_STATUSES[note_type] | NONCURRENT_STATUSES
        if not isinstance(status, str) or status not in allowed:
            issues.append(Issue(str(note.path), f"status '{status}' is invalid for type '{note_type}'"))
    if not isinstance(data["sensitivity"], str) or data["sensitivity"] not in SENSITIVITIES:
        issues.append(Issue(str(note.path), "sensitivity must be public, internal, or restricted"))
    for field in ("sources", "tags", "supersedes"):
        if not isinstance(data[field], list) or not all(isinstance(item, str) for item in data[field]):
            issues.append(Issue(str(note.path), f"{field} must be a list of strings"))
    for field in ("summary", "read_when"):
        if not isinstance(data[field], str) or not data[field].strip():
            issues.append(Issue(str(note.path), f"{field} must be a non-empty string"))

    created = _parse_date(data["created"], "created", note.path, issues)
    updated = _parse_date(data["updated"], "updated", note.path, issues)
    verified = _parse_date(data["last_verified"], "last_verified", note.path, issues)
    if created and updated and updated < created:
        issues.append(Issue(str(note.path), "updated cannot be earlier than created"))
    if verified and verified > utc_now().date():
        issues.append(Issue(str(note.path), "last_verified cannot be in the future"))
    if "expires_at" in data:
        _parse_date(data["expires_at"], "expires_at", note.path, issues)

    for source in data.get("sources", []):
        if re.search(r"://[^/@\s]+:[^/@\s]+@", source):
            issues.append(Issue(str(note.path), "source URLs must not contain credentials"))

    issues.extend(scan_secrets(note))
    issues.extend(validate_verification(note))
    issues.extend(validate_authority(note))
    return issues


class Brain:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.config_path = self.root / "cerebro.json"
        if not self.config_path.is_file():
            raise CerebroError(
                f"{self.config_path} does not exist; run 'cerebro init --brain {self.root}'"
            )
        self.config = self._load_json(self.config_path)
        if self.config.get("schema_version") != 1:
            raise CerebroError(f"{self.config_path}: schema_version must be 1")
        self.projects_dir = self.root / str(self.config.get("projects_dir", "projects"))
        freshness = self.config.get("freshness_days", {})
        if not isinstance(freshness, dict) or not all(
            isinstance(key, str) and isinstance(value, int) and value >= 0
            for key, value in freshness.items()
        ):
            raise CerebroError(f"{self.config_path}: freshness_days must map names to nonnegative integers")
        self.default_freshness = {
            "state": 30,
            "reference": 90,
            "decision": 3650,
            "runbook": 90,
            "incident": 14,
            "research": 30,
            **freshness,
        }

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise CerebroError(f"{path}: duplicate JSON key '{key}'")
                result[key] = value
            return result

        try:
            data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
        except CerebroError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CerebroError(f"{path}: invalid JSON") from exc
        if not isinstance(data, dict):
            raise CerebroError(f"{path}: expected a JSON object")
        return data

    def projects(self) -> list[Project]:
        if not self.projects_dir.is_dir():
            return []
        projects: list[Project] = []
        for path in sorted(self.projects_dir.glob("*/project.json")):
            if path.parent.is_symlink() or path.is_symlink():
                raise CerebroError(f"{path}: symlinked project manifests are forbidden")
            data = self._load_json(path)
            project = Project(path=path.parent, data=data)
            self._validate_project(project)
            projects.append(project)
        return projects

    def _validate_project(self, project: Project) -> None:
        data = project.data
        required = {"schema_version", "id", "name", "roots", "sensitivity", "history_paths"}
        missing = required - data.keys()
        if missing:
            raise CerebroError(f"{project.path / 'project.json'}: missing {', '.join(sorted(missing))}")
        if data["schema_version"] != 1:
            raise CerebroError(f"{project.path / 'project.json'}: schema_version must be 1")
        if not isinstance(data["id"], str) or not SLUG_RE.fullmatch(data["id"]):
            raise CerebroError(f"{project.path / 'project.json'}: invalid project id")
        if project.path.name != data["id"]:
            raise CerebroError(f"{project.path / 'project.json'}: directory must match project id")
        if not isinstance(data["name"], str) or not data["name"].strip():
            raise CerebroError(f"{project.path / 'project.json'}: name must be non-empty")
        if not isinstance(data["roots"], list) or not all(isinstance(item, str) for item in data["roots"]):
            raise CerebroError(f"{project.path / 'project.json'}: roots must be a list of paths")
        if not isinstance(data["sensitivity"], str) or data["sensitivity"] not in SENSITIVITIES:
            raise CerebroError(f"{project.path / 'project.json'}: invalid sensitivity")
        if not isinstance(data["history_paths"], list) or not all(
            isinstance(item, str) for item in data["history_paths"]
        ):
            raise CerebroError(f"{project.path / 'project.json'}: history_paths must be a list")
        for raw in data["history_paths"]:
            history_root = Path(raw).expanduser()
            if not history_root.is_absolute():
                history_root = self.root / history_root
            try:
                history_root.resolve().relative_to(self.root)
            except ValueError as exc:
                raise CerebroError(
                    f"{project.path / 'project.json'}: history paths must remain inside the brain"
                ) from exc

    def project(self, project_id: str) -> Project:
        for project in self.projects():
            if project.id == project_id:
                return project
        raise CerebroError(f"unknown project '{project_id}'")

    def resolve(self, cwd: Path) -> Project:
        target = cwd.expanduser().resolve()
        candidates: list[tuple[int, Project]] = []
        for project in self.projects():
            for raw_root in project.roots:
                root = Path(raw_root).expanduser()
                if not root.is_absolute():
                    root = self.root / root
                root = root.resolve()
                try:
                    target.relative_to(root)
                except ValueError:
                    continue
                candidates.append((len(root.parts), project))
        if not candidates:
            raise CerebroError(f"no Cerebro project resolves for {target}")
        candidates.sort(key=lambda item: item[0], reverse=True)
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            raise CerebroError(f"multiple Cerebro projects resolve for {target}")
        return candidates[0][1]

    def project_root(self, project: Project, cwd: Path) -> Path:
        target = cwd.expanduser().resolve()
        candidates: list[Path] = []
        for raw_root in project.roots:
            root = Path(raw_root).expanduser()
            if not root.is_absolute():
                root = self.root / root
            root = root.resolve()
            try:
                target.relative_to(root)
            except ValueError:
                continue
            candidates.append(root)
        if not candidates:
            raise CerebroError(
                f"{target} is outside the registered roots for project '{project.id}'"
            )
        candidates.sort(key=lambda item: len(item.parts), reverse=True)
        if len(candidates) > 1 and len(candidates[0].parts) == len(candidates[1].parts):
            raise CerebroError(f"multiple roots for project '{project.id}' match {target}")
        return candidates[0]

    @staticmethod
    def _evidence_file(project_root: Path, raw_path: Any) -> Path:
        safe_path = _safe_evidence_path(raw_path)
        if safe_path is None:
            raise CerebroError("evidence path must be a normalized project-relative file path")
        candidate = project_root / safe_path
        cursor = project_root
        for part in Path(safe_path).parts:
            cursor /= part
            if cursor.is_symlink():
                raise CerebroError(f"evidence path contains a symlink: {safe_path}")
        resolved = candidate.resolve()
        try:
            resolved.relative_to(project_root.resolve())
        except ValueError as exc:
            raise CerebroError(f"evidence path escapes the project root: {safe_path}") from exc
        if not resolved.is_file():
            raise CerebroError(f"evidence path is not a regular file: {safe_path}")
        return resolved

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def hash_evidence(self, project: Project, cwd: Path, path: str) -> dict[str, str]:
        root = self.project_root(project, cwd)
        evidence_file = self._evidence_file(root, path)
        return {
            "kind": "file-sha256",
            "path": evidence_file.relative_to(root).as_posix(),
            "sha256": self._sha256_file(evidence_file),
        }

    def verify_evidence(
        self,
        project: Project,
        cwd: Path,
        notes: Iterable[Note],
    ) -> dict[str, Any]:
        root = self.project_root(project, cwd)
        failures: list[dict[str, str]] = []
        checks = 0
        for note in notes:
            raw_checks = note.metadata.get("verification", [])
            if not isinstance(raw_checks, list):
                continue
            for check in raw_checks:
                if not isinstance(check, dict) or check.get("kind") != "file-sha256":
                    continue
                checks += 1
                path = str(check.get("path", ""))
                expected = str(check.get("sha256", ""))
                try:
                    evidence_file = self._evidence_file(root, path)
                    actual = self._sha256_file(evidence_file)
                except CerebroError as exc:
                    failures.append(
                        {"note": note.id, "path": path, "reason": str(exc)}
                    )
                    continue
                if actual != expected:
                    failures.append(
                        {
                            "note": note.id,
                            "path": path,
                            "reason": "SHA-256 mismatch",
                        }
                    )
        return {
            "status": "failed" if failures else "passed",
            "checks": checks,
            "failures": failures,
        }

    def current_notes(self, project: Project) -> list[Note]:
        notes: list[Note] = []
        for path in sorted(project.path.rglob("*.md")):
            if path.is_symlink():
                raise CerebroError(f"{path}: symlinked notes are forbidden")
            notes.append(parse_frontmatter(path))
        return notes

    def history_notes(self, project: Project) -> list[Note]:
        notes: list[Note] = []
        for raw in project.history_paths:
            history_root = Path(raw).expanduser()
            if not history_root.is_absolute():
                history_root = self.root / history_root
            if not history_root.exists():
                continue
            for path in sorted(history_root.rglob("*.md")):
                if path.is_symlink():
                    raise CerebroError(f"{path}: symlinked history is forbidden")
                notes.append(parse_frontmatter(path, partition="history"))
        return notes

    def validate(self) -> list[Issue]:
        issues: list[Issue] = []
        ids: dict[str, Path] = {}
        for project in self.projects():
            notes = self.current_notes(project)
            state_count = 0
            map_count = 0
            for note in notes:
                issues.extend(validate_note(note, project.id))
                if note.id in ids:
                    issues.append(Issue(str(note.path), f"duplicate note id also used by {ids[note.id]}"))
                else:
                    ids[note.id] = note.path
                if (
                    note.note_type == "state"
                    and note.status == "current"
                    and note.authority != "proposal"
                ):
                    state_count += 1
                if (
                    note.note_type == "reference"
                    and note.metadata.get("role") == "agent-map"
                    and note.authority != "proposal"
                ):
                    map_count += 1
            if state_count != 1:
                issues.append(Issue(str(project.path), "project must have exactly one current state note"))
            if map_count != 1:
                issues.append(Issue(str(project.path), "project must have exactly one agent-map reference"))
        return issues

    def stale_reason(self, note: Note) -> str | None:
        if note.authority == "proposal":
            return "authority is an unaccepted proposal"
        if note.status not in CURRENT_STATUSES.get(note.note_type, set()):
            return "status is not current authority"
        today = utc_now().date()
        expires_at = note.metadata.get("expires_at")
        if isinstance(expires_at, str):
            try:
                if date.fromisoformat(expires_at) < today:
                    return f"expired on {expires_at}"
            except ValueError:
                return "expires_at is invalid"
        try:
            verified = date.fromisoformat(str(note.metadata["last_verified"]))
        except (KeyError, ValueError):
            return "last_verified is invalid"
        ttl = int(self.default_freshness.get(note.note_type, 30))
        due = verified + timedelta(days=ttl)
        if due < today:
            return f"verification expired on {due.isoformat()}"
        return None

    def authorize(self, note: Note, restricted: bool) -> bool:
        return note.sensitivity != "restricted" or restricted

    def context(
        self,
        project: Project,
        *,
        query: str = "",
        include_history: bool = False,
        include_stale: bool = False,
        require_fresh: bool = False,
        restricted: bool = False,
        verify_evidence: bool = False,
        cwd: Path | None = None,
    ) -> dict[str, Any]:
        if project.sensitivity == "restricted" and not restricted:
            raise CerebroError("restricted project requires --restricted")
        all_candidates = self.current_notes(project)
        validation_issues: list[Issue] = []
        ids: set[str] = set()
        state_count = 0
        map_count = 0
        for note in all_candidates:
            validation_issues.extend(validate_note(note, project.id))
            if note.id in ids:
                validation_issues.append(
                    Issue(str(note.path), f"duplicate note id in project: {note.id}")
                )
            ids.add(note.id)
            if (
                note.note_type == "state"
                and note.status == "current"
                and note.authority != "proposal"
            ):
                state_count += 1
            if (
                note.note_type == "reference"
                and note.metadata.get("role") == "agent-map"
                and note.authority != "proposal"
            ):
                map_count += 1
        if state_count != 1:
            validation_issues.append(
                Issue(str(project.path), "project must have exactly one current state note")
            )
        if map_count != 1:
            validation_issues.append(
                Issue(str(project.path), "project must have exactly one agent-map reference")
            )
        if validation_issues:
            first = validation_issues[0].render()
            remaining = len(validation_issues) - 1
            suffix = f" (+{remaining} more)" if remaining else ""
            raise CerebroError(f"project validation failed: {first}{suffix}")
        unauthorized_authority = [
            note
            for note in all_candidates
            if not self.authorize(note, restricted)
            and note.status in CURRENT_STATUSES.get(note.note_type, set())
            and note.authority != "proposal"
        ]
        if require_fresh and unauthorized_authority:
            raise CerebroError(
                "required current authority is restricted; rerun with explicit --restricted access",
                exit_code=4,
            )
        candidates = [note for note in all_candidates if self.authorize(note, restricted)]
        stale = [(note, self.stale_reason(note)) for note in candidates if self.stale_reason(note)]
        stale_authority = [
            (note, reason)
            for note, reason in stale
            if note.status in CURRENT_STATUSES.get(note.note_type, set())
        ]
        if require_fresh and stale_authority:
            names = ", ".join(note.id for note, _ in stale_authority)
            raise CerebroError(f"current authority is stale: {names}", exit_code=3)

        authority = [
            note
            for note in candidates
            if note.status in CURRENT_STATUSES.get(note.note_type, set())
            and note.authority != "proposal"
            and self.stale_reason(note) is None
        ]
        legacy_authority = [
            note for note in authority if note.authority == "legacy-declared"
        ]
        declared_evidence = sum(
            len(note.metadata.get("verification", []))
            for note in authority
            if isinstance(note.metadata.get("verification", []), list)
        )
        if verify_evidence:
            if cwd is None:
                raise CerebroError("--verify-evidence requires a working directory")
            evidence = self.verify_evidence(project, cwd, authority)
            if evidence["failures"]:
                names = ", ".join(
                    f"{item['note']}:{item['path']}" for item in evidence["failures"]
                )
                raise CerebroError(
                    f"current authority evidence failed: {names}",
                    exit_code=3,
                )
        else:
            evidence = {
                "status": "not_checked" if declared_evidence else "not_declared",
                "checks": declared_evidence,
                "failures": [],
            }

        visible = []
        for note in candidates:
            reason = self.stale_reason(note)
            if reason and not include_stale:
                continue
            visible.append((note, reason))

        if query:
            terms = [term.casefold() for term in query.split() if term]
            visible = [
                (note, reason)
                for note, reason in visible
                if all(term in note.raw.casefold() for term in terms)
                or note.note_type in {"state", "reference"}
            ]

        documents = [
            self.serialize_note(note, stale_reason=reason, include_content=True)
            for note, reason in sorted(visible, key=lambda item: self._note_sort_key(item[0]))
        ]
        if include_history:
            documents.extend(
                self.serialize_note(note, stale_reason="unverified historical evidence", include_content=True)
                for note in self.history_notes(project)
                if self.authorize(note, restricted)
                and (not query or query.casefold() in note.raw.casefold())
            )
        return {
            "schema_version": 1,
            "generated_at": utc_now().isoformat(),
            "project": project.id,
            "project_name": project.name,
            "status": (
                "partial"
                if unauthorized_authority
                else "stale"
                if stale_authority
                else "current"
            ),
            "history_included": include_history,
            "documents": documents,
            "evidence": evidence,
            "warnings": (
                [
                    {
                        "reason": "restricted current authority omitted",
                        "count": len(unauthorized_authority),
                    }
                ]
                if unauthorized_authority
                else []
            )
            + (
                [
                    {
                        "reason": "executable evidence was not checked",
                        "count": declared_evidence,
                    }
                ]
                if declared_evidence and not verify_evidence
                else []
            )
            + (
                [
                    {
                        "reason": "legacy note has no explicit authority classification",
                        "count": len(legacy_authority),
                    }
                ]
                if legacy_authority
                else []
            )
            + [
                {"id": note.id, "reason": reason}
                for note, reason in stale
                if note.status in CURRENT_STATUSES.get(note.note_type, set())
                and note.authority != "proposal"
            ],
        }

    def search(
        self,
        query: str,
        *,
        project_id: str | None = None,
        include_history: bool = False,
        include_stale: bool = False,
        restricted: bool = False,
    ) -> list[dict[str, Any]]:
        terms = [term.casefold() for term in query.split() if term]
        if not terms:
            raise CerebroError("search query cannot be empty")
        projects = [self.project(project_id)] if project_id else self.projects()
        results: list[tuple[int, dict[str, Any]]] = []
        for project in projects:
            if project.sensitivity == "restricted" and not restricted:
                continue
            for note in self.current_notes(project):
                if not self.authorize(note, restricted):
                    continue
                reason = self.stale_reason(note)
                if reason and not include_stale:
                    continue
                haystack = note.raw.casefold()
                if not all(term in haystack for term in terms):
                    continue
                score = sum(haystack.count(term) for term in terms)
                results.append((score, self.serialize_note(note, reason, include_content=False)))
            if include_history:
                for note in self.history_notes(project):
                    haystack = note.raw.casefold()
                    if all(term in haystack for term in terms):
                        score = sum(haystack.count(term) for term in terms)
                        results.append(
                            (
                                score,
                                self.serialize_note(
                                    note, "unverified historical evidence", include_content=False
                                ),
                            )
                        )
        results.sort(key=lambda item: (-item[0], item[1]["id"]))
        return [item for _, item in results]

    def show(self, note_id: str, *, allow_stale: bool = False, restricted: bool = False) -> dict[str, Any]:
        for project in self.projects():
            for note in self.current_notes(project):
                if note.id != note_id:
                    continue
                if not self.authorize(note, restricted):
                    raise CerebroError("restricted note requires --restricted")
                reason = self.stale_reason(note)
                if reason and not allow_stale:
                    raise CerebroError(
                        f"'{note_id}' is not current authority ({reason}); use --allow-stale",
                        exit_code=3,
                    )
                return self.serialize_note(note, reason, include_content=True)
        raise CerebroError(f"unknown note '{note_id}'")

    @staticmethod
    def _note_sort_key(note: Note) -> tuple[int, str]:
        order = {
            "state": 0,
            "reference": 1,
            "decision": 2,
            "runbook": 3,
            "incident": 4,
            "research": 5,
            "log": 6,
        }
        return (order.get(note.note_type, 99), note.id)

    def serialize_note(
        self, note: Note, stale_reason: str | None, *, include_content: bool
    ) -> dict[str, Any]:
        try:
            relative = str(note.path.resolve().relative_to(self.root))
        except ValueError:
            relative = str(note.path)
        payload: dict[str, Any] = {
            "id": note.id,
            "title": note.title(),
            "project": note.project,
            "type": note.note_type,
            "status": note.status,
            "authority": note.authority,
            "partition": note.partition,
            "current": stale_reason is None,
            "last_verified": note.metadata.get("last_verified"),
            "summary": note.metadata.get("summary", ""),
            "path": relative,
        }
        if stale_reason:
            payload["warning"] = stale_reason
        if include_content:
            payload["content"] = note.body
        return payload


def init_brain(root: Path, *, force: bool = False) -> None:
    root = root.expanduser().resolve()
    config = root / "cerebro.json"
    if config.exists() and not force:
        raise CerebroError(f"{config} already exists")
    root.mkdir(parents=True, exist_ok=True)
    (root / "projects").mkdir(exist_ok=True)
    (root / "history").mkdir(exist_ok=True)
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "projects_dir": "projects",
                "freshness_days": {
                    "state": 30,
                    "reference": 90,
                    "runbook": 90,
                    "incident": 14,
                    "research": 30,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _note_template(
    *,
    note_id: str,
    project_id: str,
    note_type: str,
    status: str,
    title: str,
    summary: str,
    role: str | None = None,
) -> str:
    today = iso_today()
    role_line = f"role: {role}\n" if role else ""
    promotion = json.dumps(
        {
            "method": "interactive-owner-confirmation",
            "accepted_at": utc_now().isoformat(),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        "---\n"
        "schema_version: 2\n"
        f"id: {note_id}\n"
        f"project: {project_id}\n"
        f"type: {note_type}\n"
        f"status: {status}\n"
        "authority: owner-accepted\n"
        f"promotion: {promotion}\n"
        f"{role_line}"
        f"created: {today}\n"
        f"updated: {today}\n"
        f"last_verified: {today}\n"
        "sensitivity: internal\n"
        'sources: ["repo://current"]\n'
        "tags: []\n"
        "supersedes: []\n"
        f"summary: {json.dumps(summary)}\n"
        'read_when: "Read before working on this project."\n'
        "---\n\n"
        f"# {title}\n\n"
        "Replace this scaffold with compact, source-backed current context.\n"
    )


def scaffold_project(brain_root: Path, project_id: str, name: str, project_root: Path) -> Path:
    if not SLUG_RE.fullmatch(project_id):
        raise CerebroError("project id must be a lowercase kebab-case slug")
    brain = Brain(brain_root)
    target = brain.projects_dir / project_id
    if target.exists():
        raise CerebroError(f"project '{project_id}' already exists")
    target.mkdir(parents=True)
    for directory in ("decisions", "runbooks", "incidents", "research"):
        (target / directory).mkdir()
    history_path = brain.root / "history" / project_id
    history_path.mkdir(parents=True, exist_ok=True)
    project_data = {
        "schema_version": 1,
        "id": project_id,
        "name": name,
        "roots": [str(project_root.expanduser().resolve())],
        "sensitivity": "internal",
        "history_paths": [str(history_path.relative_to(brain.root))],
    }
    (target / "project.json").write_text(
        json.dumps(project_data, indent=2) + "\n", encoding="utf-8"
    )
    (target / "State.md").write_text(
        _note_template(
            note_id=f"{project_id}-state",
            project_id=project_id,
            note_type="state",
            status="current",
            title=f"{name} State",
            summary=f"Current operational state for {name}.",
        ),
        encoding="utf-8",
    )
    (target / "Agent Map.md").write_text(
        _note_template(
            note_id=f"{project_id}-agent-map",
            project_id=project_id,
            note_type="reference",
            status="active",
            title=f"{name} Agent Map",
            summary=f"Entry map for agents working on {name}.",
            role="agent-map",
        ),
        encoding="utf-8",
    )
    return target


def default_brain_path() -> Path:
    return Path(os.environ.get("CEREBRO_HOME", "~/.cerebro")).expanduser()


def render_human_documents(documents: Iterable[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for document in documents:
        label = "HISTORY — UNVERIFIED" if document["partition"] == "history" else document["type"].upper()
        warning = f"\nWarning: {document['warning']}" if document.get("warning") else ""
        chunks.append(
            f"[{label}] {document['title']} ({document['id']}){warning}\n"
            f"{document.get('content', document.get('summary', '')).strip()}"
        )
    return "\n\n".join(chunks)
