from __future__ import annotations

import argparse
import json
import random
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .model import (
    ContextResult,
    EvaluationError,
    build_cerebro_context,
    materialize_repository,
    prompt_for_condition,
    response_schema,
)
from .runner import load_runner, run_prompt
from .scoring import score_run, summarize
from .suites import load_suite, load_suite_packets

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKETS = ROOT / "evaluation" / "packets"


def _selected(raw: str | None) -> set[str] | None:
    return {item.strip() for item in raw.split(",") if item.strip()} if raw else None


def _conditions(raw: str, allowed: tuple[str, ...]) -> tuple[str, ...]:
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    unknown = sorted(set(values) - set(allowed))
    if unknown or not values or len(set(values)) != len(values):
        raise EvaluationError(
            f"conditions must be unique values from {', '.join(allowed)}"
        )
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
    validate.add_argument("--suite", choices=("v1", "v2"), default="v1")
    validate.add_argument("--packets")
    validate.add_argument("--json", action="store_true")

    run = sub.add_parser("run", help="Run bounded model evaluations")
    run.add_argument("--suite", choices=("v1", "v2"), default="v1")
    run.add_argument("--packets")
    run.add_argument("--runner", type=Path, required=True)
    run.add_argument("--conditions")
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument("--seed", type=int, default=20260731)
    run.add_argument("--max-runs", type=int, default=45)
    run.add_argument("--output", type=Path, required=True)

    summary = sub.add_parser("summarize", help="Summarize bounded JSONL results")
    summary.add_argument("--input", type=Path, action="append", required=True)
    summary.add_argument(
        "--conditions",
        help="Optional comma-separated condition filter for composable exact result files",
    )
    summary.add_argument("--json", action="store_true")
    return parser


def cmd_validate(args: argparse.Namespace) -> int:
    suite = load_suite(ROOT, args.suite)
    packets = load_suite_packets(suite, _selected(args.packets))
    results: list[dict[str, Any]] = []
    for packet in packets:
        with tempfile.TemporaryDirectory(prefix="cerebro-eval-") as temporary:
            temporary_root = Path(temporary)
            workspace = temporary_root / "workspace"
            materialize_repository(packet, workspace)
            context = build_cerebro_context(
                packet,
                temporary_root / "brain",
                workspace,
                require_fresh=suite.cerebro_require_fresh,
            )
            actual_warning_ids = (
                tuple(
                    warning["id"]
                    for warning in context.payload.get("warnings", [])
                    if "id" in warning
                )
                if context.payload is not None
                else ()
            )
            results.append(
                {
                    "id": packet.packet_id,
                    "cerebro_status": context.status,
                    "expected_status": packet.expected.cerebro_status,
                    "status_matches": context.status == packet.expected.cerebro_status,
                    "warning_ids": actual_warning_ids,
                    "expected_warning_ids": packet.expected.warning_ids,
                    "warnings_match": set(actual_warning_ids)
                    == set(packet.expected.warning_ids),
                }
            )
    payload = {
        "status": (
            "ok"
            if all(
                item["status_matches"] and item["warnings_match"] for item in results
            )
            else "failed"
        ),
        "suite": suite.suite_id,
        "packets": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{payload['status']}: {len(results)} packet(s)")
        for item in results:
            print(
                f"{item['id']}: {item['cerebro_status']} "
                f"(expected {item['expected_status']}; "
                f"warnings {'match' if item['warnings_match'] else 'mismatch'})"
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
    suite = load_suite(ROOT, args.suite)
    packets = load_suite_packets(suite, _selected(args.packets))
    conditions = (
        _conditions(args.conditions, suite.conditions)
        if args.conditions
        else suite.conditions
    )
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
                require_fresh=suite.cerebro_require_fresh,
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
    selected = _selected(args.conditions)
    payload = summarize(
        record
        for path in args.input
        for record in _load_records(path)
        if selected is None or record.get("condition") in selected
    )
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
