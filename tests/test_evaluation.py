from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from evaluation.cli import DEFAULT_PACKETS, main
from evaluation.model import (
    ContextResult,
    EvaluationError,
    build_cerebro_context,
    load_packet,
    load_packets,
    materialize_repository,
)
from evaluation.runner import (
    RunnerConfig,
    RunnerResult,
    load_runner,
    run_prompt,
    validate_runner_safety,
)
from evaluation.scoring import score_run, summarize

ROOT = Path(__file__).resolve().parents[1]


class EvaluationPacketTests(unittest.TestCase):
    def test_all_packets_materialize_with_expected_context_status(self) -> None:
        packets = load_packets(DEFAULT_PACKETS)
        self.assertEqual(len(packets), 10)
        for packet in packets:
            with (
                self.subTest(packet=packet.packet_id),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                workspace = root / "workspace"
                materialize_repository(packet, workspace)
                context = build_cerebro_context(packet, root / "brain", workspace)
                self.assertEqual(context.status, packet.expected.cerebro_status)

    def test_packet_paths_cannot_escape_workspace(self) -> None:
        source = json.loads(
            (DEFAULT_PACKETS / "01-stale-queue-backend.json").read_text(encoding="utf-8")
        )
        source["repository_files"] = {"../outside": "no"}
        with tempfile.TemporaryDirectory() as temporary:
            packet = Path(temporary) / "unsafe.json"
            packet.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaises(EvaluationError):
                load_packet(packet)

    def test_irrelevant_expiry_is_counted_as_false_block(self) -> None:
        packet = load_packet(DEFAULT_PACKETS / "04-irrelevant-stale-note.json")
        context = ContextResult(
            status="blocked",
            payload=None,
            error_category="stale",
            error_code=3,
        )
        result = RunnerResult(
            response={
                "answer": "3.13",
                "source": ".python-version",
                "rationale": "Repository configuration is current.",
            },
            exit_code=0,
            error_category=None,
            latency_ms=1,
            input_tokens=None,
            output_tokens=None,
            cost_usd=None,
        )
        scores = score_run(packet, "cerebro", context, result)
        self.assertTrue(scores["false_block"])
        self.assertTrue(scores["answer_correct"])


class RunnerTests(unittest.TestCase):
    def test_example_runner_is_safely_isolated(self) -> None:
        runner = load_runner(ROOT / "evaluation" / "runners" / "claude-safe.example.json")
        self.assertEqual(runner.parser, "claude-json")

    def test_unsafe_claude_runner_is_rejected(self) -> None:
        runner = RunnerConfig(
            name="unsafe",
            parser="claude-json",
            command=(
                "claude",
                "--safe-mode",
                "--print",
                "--no-session-persistence",
                "--tools",
                "",
                "--output-format",
                "json",
                "--max-budget-usd",
                "0.1",
                "--continue",
            ),
            timeout_seconds=30,
        )
        with self.assertRaises(EvaluationError):
            validate_runner_safety(runner)

    def test_direct_json_runner_returns_only_structured_result(self) -> None:
        response = {
            "answer": "river",
            "source": "config/queue.toml",
            "rationale": "Repository configuration wins.",
        }
        runner = RunnerConfig(
            name="fixture",
            parser="direct-json",
            command=(sys.executable, "-c", f"print({json.dumps(json.dumps(response))})"),
            timeout_seconds=30,
        )
        result = run_prompt(runner, "private prompt marker", {"type": "object"})
        self.assertEqual(result.response, response)
        self.assertIsNone(result.error_category)

    def test_claude_usage_counts_cache_tokens_as_input(self) -> None:
        payload = {
            "structured_output": {
                "answer": "river",
                "source": "config/queue.toml",
                "rationale": "Repository configuration wins.",
            },
            "usage": {
                "input_tokens": 2,
                "cache_creation_input_tokens": 100,
                "cache_read_input_tokens": 20,
                "output_tokens": 8,
            },
            "total_cost_usd": 0.01,
        }
        runner = RunnerConfig(
            name="claude-fixture",
            parser="claude-json",
            command=(
                sys.executable,
                "-c",
                f"print({json.dumps(json.dumps(payload))})",
                "claude",
                "--safe-mode",
                "--print",
                "--no-session-persistence",
                "--tools",
                "",
                "--output-format",
                "json",
                "--max-budget-usd",
                "0.1",
            ),
            timeout_seconds=30,
        )
        result = run_prompt(runner, "prompt", {"type": "object"})
        self.assertEqual(result.input_tokens, 122)


class EvaluationCliTests(unittest.TestCase):
    def test_one_run_writes_no_prompt_or_transcript(self) -> None:
        response = {
            "answer": "river",
            "source": "config/queue.toml",
            "rationale": "Repository configuration wins.",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner_path = root / "runner.json"
            runner_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "fixture",
                        "parser": "direct-json",
                        "command": [
                            sys.executable,
                            "-c",
                            f"print({json.dumps(json.dumps(response))})",
                        ],
                        "timeout_seconds": 30,
                    }
                ),
                encoding="utf-8",
            )
            output = root / "results.jsonl"
            with redirect_stdout(StringIO()):
                exit_code = main(
                    [
                        "run",
                        "--packets",
                        "stale-queue-backend",
                        "--conditions",
                        "repository",
                        "--runner",
                        str(runner_path),
                        "--output",
                        str(output),
                        "--max-runs",
                        "1",
                    ]
                )
            self.assertEqual(exit_code, 0)
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertNotIn("prompt", record)
            self.assertNotIn("transcript", record)
            self.assertEqual(record["response"], response)

    def test_summary_exposes_accuracy_and_false_blocks(self) -> None:
        summary = summarize(
            [
                {
                    "condition": "cerebro",
                    "response": {"answer": "3.13"},
                    "scores": {
                        "answer_correct": True,
                        "source_correct": True,
                        "overall_correct": True,
                        "stale_adoption": False,
                        "context_status": "blocked",
                        "context_gate_correct": True,
                        "false_block": True,
                    },
                    "metrics": {
                        "latency_ms": 10,
                        "input_tokens": 5,
                        "output_tokens": 3,
                        "cost_usd": 0.01,
                    },
                }
            ]
        )
        cerebro = summary["conditions"]["cerebro"]
        self.assertEqual(cerebro["overall_accuracy"], 1.0)
        self.assertEqual(cerebro["context_gate_accuracy"], 1.0)
        self.assertEqual(cerebro["false_blocks"], 1)


if __name__ == "__main__":
    unittest.main()
