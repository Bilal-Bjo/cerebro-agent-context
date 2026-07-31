from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from .model import ContextResult, Packet
from .runner import RunnerResult


def score_run(
    packet: Packet,
    condition: str,
    context: ContextResult | None,
    result: RunnerResult,
) -> dict[str, Any]:
    response = result.response or {}
    answer = response.get("answer")
    source = response.get("source")
    answer_correct = answer == packet.expected.answer
    source_correct = source in packet.expected.sources_for(condition)
    stale_adoption = answer in packet.expected.forbidden_answers
    if condition == "cerebro" and context is not None:
        context_status = context.status
        context_gate_correct = context.status == packet.expected.cerebro_status
        false_block = context.status == "blocked" and not packet.expected.block_relevant
    else:
        context_status = "not_applicable"
        context_gate_correct = None
        false_block = False
    return {
        "answer_correct": answer_correct,
        "source_correct": source_correct,
        "overall_correct": answer_correct and source_correct,
        "stale_adoption": stale_adoption,
        "context_status": context_status,
        "context_gate_correct": context_gate_correct,
        "false_block": false_block,
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def summarize(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_records = list(records)
    for record in all_records:
        groups[str(record["condition"])].append(record)
    conditions: dict[str, Any] = {}
    for condition, items in sorted(groups.items()):
        completed = [item for item in items if item["response"] is not None]
        scores = [item["scores"] for item in completed]
        gate_scores = [
            item["scores"]
            for item in items
            if item["scores"]["context_gate_correct"] is not None
        ]
        input_tokens = [
            item["metrics"]["input_tokens"]
            for item in items
            if item["metrics"]["input_tokens"] is not None
        ]
        output_tokens = [
            item["metrics"]["output_tokens"]
            for item in items
            if item["metrics"]["output_tokens"] is not None
        ]
        costs = [
            item["metrics"]["cost_usd"]
            for item in items
            if item["metrics"]["cost_usd"] is not None
        ]
        conditions[condition] = {
            "runs": len(items),
            "completed": len(completed),
            "completion_rate": _rate(len(completed), len(items)),
            "answer_accuracy": _rate(
                sum(bool(score["answer_correct"]) for score in scores), len(scores)
            ),
            "source_accuracy": _rate(
                sum(bool(score["source_correct"]) for score in scores), len(scores)
            ),
            "overall_accuracy": _rate(
                sum(bool(score["overall_correct"]) for score in scores), len(scores)
            ),
            "stale_adoption_rate": _rate(
                sum(bool(score["stale_adoption"]) for score in scores), len(scores)
            ),
            "context_gate_accuracy": _rate(
                sum(bool(score["context_gate_correct"]) for score in gate_scores),
                len(gate_scores),
            ),
            "context_blocks": sum(
                score["context_status"] == "blocked" for score in gate_scores
            ),
            "false_blocks": sum(bool(score["false_block"]) for score in gate_scores),
            "latency_ms_mean": (
                round(sum(item["metrics"]["latency_ms"] for item in items) / len(items))
                if items
                else None
            ),
            "input_tokens": sum(input_tokens) if input_tokens else None,
            "output_tokens": sum(output_tokens) if output_tokens else None,
            "cost_usd": round(sum(costs), 6) if costs else None,
        }
    return {
        "schema_version": 1,
        "runs": len(all_records),
        "conditions": conditions,
        "limitations": [
            "Small pilots are directional and do not establish statistical significance.",
            "Synthetic packets test bounded failure modes, not long-term maintenance burden.",
            "Real-use soak evidence remains required before claiming personal impact.",
        ],
    }
