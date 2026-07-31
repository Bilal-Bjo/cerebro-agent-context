from __future__ import annotations

import argparse
import json
import random
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .model import (
    CONDITIONS,
    ContextResult,
    EvaluationError,
    build_cerebro_context,
    load_packets,
    materialize_repository,
    prompt_for_condition,
    response_schema,
)
from .runner import load_runner, run_prompt
from .scoring import score_run, summarize

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKETS = ROOT / "evaluation" / "packets"


def _selected(raw: str | None) -> set[str] | None:
    return {item.strip() for item in raw.split(",") if item.strip()} if raw else None


def _conditions(raw: str) -> tuple[str, ...]:
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    unknown = sorted(set(values) - set(CONDITIONS))
    if unknown or not values or len(set(values)) != len(values):
        raise EvaluationError("conditions must be unique repository, agents, or cerebro values")
    return values


def _load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise EvaluationError(f"{path}: result records must be objects")
                records.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"{path}: invalid result JSONL") from exc
    return records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evaluation.cli",
        description="Run isolated Cerebro context evaluations.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Validate packets and generated Cerebro contexts")
    validate.add_argument("--packets-dir", type=Path, default=DEFAULT_PACKETS)
    validate.add_argument("--packets")
    validate.add_argument("--json", action="store_true")

    run = sub.add_parser("run", help="Run bounded model evaluations")
    run.add_argument("--packets-dir", type=Path, default=DEFAULT_PACKETS)
    run.add_argument("--packets")
    run.add_argument("--runner", type=Path, required=True)
    run.add_argument("--conditions", default="repository,agents,cerebro")
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument("--seed", type=int, default=20260731)
    run.add_argument("--max-runs", type=int, default=45)
    run.add_argument("--output", type=Path, required=True)

    summary = sub.add_parser("summarize", help="Summarize bounded JSONL results")
    summary.add_argument("--input", type=Path, required=True)
    summary.add_argument("--json", action="store_true")
    return parser


def cmd_validate(args: argparse.Namespace) -> int:
    packets = load_packets(args.packets_dir, _selected(args.packets))
    results: list[dict[str, Any]] = []
    for packet in packets:
        with tempfile.TemporaryDirectory(prefix="cerebro-eval-") as temporary:
            temporary_root = Path(temporary)
            workspace = temporary_root / "workspace"
            materialize_repository(packet, workspace)
            context = build_cerebro_context(packet, temporary_root / "brain", workspace)
            results.append(
                {
                    "id": packet.packet_id,
                    "cerebro_status": context.status,
                    "expected_status": packet.expected.cerebro_status,
                    "status_matches": context.status == packet.expected.cerebro_status,
                }
            )
    payload = {
        "status": "ok" if all(item["status_matches"] for item in results) else "failed",
        "packets": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{payload['status']}: {len(results)} packet(s)")
        for item in results:
            print(
                f"{item['id']}: {item['cerebro_status']} "
                f"(expected {item['expected_status']})"
            )
    return 0 if payload["status"] == "ok" else 2


def _make_record(
    *,
    runner_name: str,
    packet_id: str,
    condition: str,
    repetition: int,
    context: ContextResult | None,
    response: dict[str, str] | None,
    scores: dict[str, Any],
    exit_code: int,
    error_category: str | None,
    latency_ms: int,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_usd: float | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "recorded_at": datetime.now(UTC).isoformat(),
        "runner": runner_name,
        "packet": packet_id,
        "condition": condition,
        "repetition": repetition,
        "cerebro_context": (
            {
                "status": context.status,
                "error_category": context.error_category,
                "error_code": context.error_code,
            }
            if context is not None
            else None
        ),
        "response": response,
        "scores": scores,
        "metrics": {
            "exit_code": exit_code,
            "error_category": error_category,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
        },
    }


def cmd_run(args: argparse.Namespace) -> int:
    if not 1 <= args.repeats <= 10:
        raise EvaluationError("repeats must be between 1 and 10")
    if not 1 <= args.max_runs <= 500:
        raise EvaluationError("max-runs must be between 1 and 500")
    if args.output.exists():
        raise EvaluationError(f"refusing to overwrite existing results: {args.output}")
    packets = load_packets(args.packets_dir, _selected(args.packets))
    conditions = _conditions(args.conditions)
    jobs = [
        (packet, condition, repetition)
        for packet in packets
        for condition in conditions
        for repetition in range(1, args.repeats + 1)
    ]
    if len(jobs) > args.max_runs:
        raise EvaluationError(
            f"planned {len(jobs)} runs exceeds --max-runs {args.max_runs}"
        )
    random.Random(args.seed).shuffle(jobs)
    runner = load_runner(args.runner)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for packet, condition, repetition in jobs:
        with tempfile.TemporaryDirectory(prefix="cerebro-eval-") as temporary:
            temporary_root = Path(temporary)
            workspace = temporary_root / "workspace"
            materialize_repository(packet, workspace)
            context = build_cerebro_context(
                packet,
                temporary_root / "brain",
                workspace,
            )
            prompt = prompt_for_condition(
                packet,
                condition,
                context if condition == "cerebro" else None,
            )
            result = run_prompt(runner, prompt, response_schema(packet), cwd=workspace)
            scores = score_run(
                packet,
                condition,
                context if condition == "cerebro" else None,
                result,
            )
            record = _make_record(
                runner_name=runner.name,
                packet_id=packet.packet_id,
                condition=condition,
                repetition=repetition,
                context=context if condition == "cerebro" else None,
                response=result.response,
                scores=scores,
                exit_code=result.exit_code,
                error_category=result.error_category,
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=result.cost_usd,
            )
            records.append(record)
            with args.output.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
            print(
                f"{packet.packet_id}/{condition}/{repetition}: "
                f"{'complete' if result.response else result.error_category}"
            )
    print(json.dumps(summarize(records), indent=2, sort_keys=True))
    return 0 if all(record["response"] is not None for record in records) else 3


def cmd_summarize(args: argparse.Namespace) -> int:
    payload = summarize(_load_records(args.input))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"runs: {payload['runs']}")
        for condition, metrics in payload["conditions"].items():
            print(
                f"{condition}: overall={metrics['overall_accuracy']} "
                f"stale={metrics['stale_adoption_rate']} "
                f"false_blocks={metrics['false_blocks']}"
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return cmd_validate(args)
        if args.command == "run":
            return cmd_run(args)
        if args.command == "summarize":
            return cmd_summarize(args)
        raise EvaluationError(f"unsupported command: {args.command}")
    except EvaluationError as exc:
        print(f"cerebro-eval: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
