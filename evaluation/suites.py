from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .model import EvaluationError, Packet, load_packets


def render_agents_current(dossier: str) -> str:
    return "## Maintained project context\n\n" f"{dossier.strip()}"


@dataclass(frozen=True)
class EvaluationSuite:
    suite_id: str
    packets_dir: Path
    conditions: tuple[str, ...]
    cerebro_require_fresh: bool
    packets: dict[str, dict[str, Any]]
    differential_packets: tuple[str, ...]
    path: Path


def load_suite(root: Path, suite_id: str) -> EvaluationSuite:
    path = root / "evaluation" / "suites" / f"{suite_id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"{path}: invalid suite JSON") from exc
    expected = {
        "schema_version",
        "id",
        "packets_dir",
        "conditions",
        "cerebro_require_fresh",
        "packets",
        "differential_packets",
        "method",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise EvaluationError(f"{path}: suite schema is invalid")
    if payload["schema_version"] != 1 or payload["id"] != suite_id:
        raise EvaluationError(f"{path}: suite identity is invalid")
    packet_dir_raw = payload["packets_dir"]
    if not isinstance(packet_dir_raw, str) or Path(packet_dir_raw).is_absolute():
        raise EvaluationError(f"{path}: packets_dir must be repository-relative")
    packets_dir = (root / packet_dir_raw).resolve()
    try:
        packets_dir.relative_to(root.resolve())
    except ValueError as exc:
        raise EvaluationError(f"{path}: packets_dir escapes the repository") from exc
    conditions = payload["conditions"]
    allowed = {"repository", "agents", "agents_current", "cerebro"}
    if (
        not isinstance(conditions, list)
        or not conditions
        or not all(isinstance(item, str) and item in allowed for item in conditions)
        or len(set(conditions)) != len(conditions)
    ):
        raise EvaluationError(f"{path}: conditions are invalid")
    packet_overrides = payload["packets"]
    if not isinstance(packet_overrides, dict):
        raise EvaluationError(f"{path}: packets must be an object")
    differential = payload["differential_packets"]
    if not isinstance(differential, list) or not all(
        isinstance(item, str) for item in differential
    ):
        raise EvaluationError(f"{path}: differential_packets must be strings")
    if not isinstance(payload["cerebro_require_fresh"], bool):
        raise EvaluationError(f"{path}: cerebro_require_fresh must be a boolean")
    if not isinstance(payload["method"], dict):
        raise EvaluationError(f"{path}: method must be an object")
    return EvaluationSuite(
        suite_id=suite_id,
        packets_dir=packets_dir,
        conditions=tuple(conditions),
        cerebro_require_fresh=payload["cerebro_require_fresh"],
        packets=packet_overrides,
        differential_packets=tuple(differential),
        path=path,
    )


def load_suite_packets(
    suite: EvaluationSuite,
    selected: set[str] | None = None,
) -> list[Packet]:
    packets = load_packets(suite.packets_dir, selected)
    ids = {packet.packet_id for packet in packets}
    unknown = set(suite.packets) - {
        packet.packet_id for packet in load_packets(suite.packets_dir)
    }
    if unknown:
        raise EvaluationError(
            f"{suite.path}: unknown packet overrides: {', '.join(sorted(unknown))}"
        )
    configured: list[Packet] = []
    for packet in packets:
        override = suite.packets.get(packet.packet_id, {})
        if not isinstance(override, dict):
            raise EvaluationError(
                f"{suite.path}: packet override for {packet.packet_id} must be an object"
            )
        allowed = {
            "maintenance_dossier",
            "cerebro_status",
            "warning_ids",
            "agents_current_sources",
        }
        if set(override) - allowed:
            raise EvaluationError(
                f"{suite.path}: unsupported override for {packet.packet_id}"
            )
        dossier = override.get("maintenance_dossier")
        if "agents_current" in suite.conditions and (
            not isinstance(dossier, str) or not dossier.strip()
        ):
            raise EvaluationError(
                f"{suite.path}: {packet.packet_id} needs a maintenance dossier"
            )
        warning_ids = override.get("warning_ids", [])
        if not isinstance(warning_ids, list) or not all(
            isinstance(item, str) for item in warning_ids
        ):
            raise EvaluationError(
                f"{suite.path}: warning_ids for {packet.packet_id} must be strings"
            )
        cerebro_status = override.get(
            "cerebro_status", packet.expected.cerebro_status
        )
        if cerebro_status not in {"current", "blocked"}:
            raise EvaluationError(
                f"{suite.path}: invalid cerebro_status for {packet.packet_id}"
            )
        current_sources = override.get("agents_current_sources")
        condition_sources: dict[str, tuple[str, ...]] | None = None
        if current_sources is not None:
            if not isinstance(current_sources, list) or not all(
                isinstance(item, str) and item for item in current_sources
            ):
                raise EvaluationError(
                    f"{suite.path}: agents_current_sources must be non-empty strings"
                )
            condition_sources = {
                "agents_current": tuple(current_sources),
            }
        expected = replace(
            packet.expected,
            cerebro_status=cerebro_status,
            warning_ids=tuple(warning_ids),
            condition_sources=condition_sources,
        )
        configured.append(
            replace(
                packet,
                agents_current_context=(
                    render_agents_current(dossier)
                    if isinstance(dossier, str)
                    else None
                ),
                expected=expected,
            )
        )
    missing_differential = set(suite.differential_packets) - ids
    if selected is None and missing_differential:
        raise EvaluationError(
            f"{suite.path}: unknown differential packets: "
            f"{', '.join(sorted(missing_differential))}"
        )
    return configured
