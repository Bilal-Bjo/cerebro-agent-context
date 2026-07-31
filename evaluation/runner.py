from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import EvaluationError


@dataclass(frozen=True)
class RunnerConfig:
    name: str
    parser: str
    command: tuple[str, ...]
    timeout_seconds: int


@dataclass(frozen=True)
class RunnerResult:
    response: dict[str, str] | None
    exit_code: int
    error_category: str | None
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None


def load_runner(path: Path) -> RunnerConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"{path}: invalid runner configuration") from exc
    if not isinstance(data, dict):
        raise EvaluationError(f"{path}: runner configuration must be an object")
    expected = {"schema_version", "name", "parser", "command", "timeout_seconds"}
    if set(data) != expected:
        raise EvaluationError(f"{path}: runner configuration must contain exactly {sorted(expected)}")
    if data["schema_version"] != 1:
        raise EvaluationError(f"{path}: runner schema_version must be 1")
    if not isinstance(data["name"], str) or not data["name"]:
        raise EvaluationError(f"{path}: runner name must be non-empty")
    if data["parser"] not in {"claude-json", "direct-json"}:
        raise EvaluationError(f"{path}: unsupported runner parser")
    command = data["command"]
    if not isinstance(command, list) or not command or not all(
        isinstance(item, str) for item in command
    ):
        raise EvaluationError(f"{path}: runner command must be a non-empty string list")
    timeout = data["timeout_seconds"]
    if not isinstance(timeout, int) or not 10 <= timeout <= 600:
        raise EvaluationError(f"{path}: timeout_seconds must be between 10 and 600")
    config = RunnerConfig(
        name=data["name"],
        parser=data["parser"],
        command=tuple(command),
        timeout_seconds=timeout,
    )
    validate_runner_safety(config)
    return config


def _option_value(command: tuple[str, ...], option: str) -> str | None:
    try:
        index = command.index(option)
    except ValueError:
        return None
    return command[index + 1] if index + 1 < len(command) else None


def validate_runner_safety(config: RunnerConfig) -> None:
    if config.parser == "claude-json":
        forbidden = {
            "-c",
            "-r",
            "--add-dir",
            "--agent",
            "--agents",
            "--append-system-prompt",
            "--append-system-prompt-file",
            "--chrome",
            "--dangerously-skip-permissions",
            "--mcp-config",
            "--plugin-dir",
            "--plugin-url",
            "--resume",
            "--continue",
            "--settings",
            "--system-prompt",
            "--system-prompt-file",
        }
        if any(
            item == option or item.startswith(f"{option}=")
            for item in config.command
            for option in forbidden
        ):
            raise EvaluationError(
                f"{config.name}: runner contains a contamination-prone option"
            )
        if Path(config.command[0]).name != "claude":
            raise EvaluationError(f"{config.name}: Claude runner executable must be claude")
        required = {"claude", "--safe-mode", "--print", "--no-session-persistence"}
        if not required.issubset(set(config.command)):
            raise EvaluationError(
                f"{config.name}: Claude runner must use safe mode and no session persistence"
            )
        if _option_value(config.command, "--tools") != "":
            raise EvaluationError(f"{config.name}: Claude runner must disable all tools")
        if _option_value(config.command, "--output-format") != "json":
            raise EvaluationError(f"{config.name}: Claude runner must emit JSON")
        budget = _option_value(config.command, "--max-budget-usd")
        try:
            parsed_budget = float(budget) if budget is not None else 0.0
        except ValueError as exc:
            raise EvaluationError(f"{config.name}: invalid Claude budget") from exc
        if not 0 < parsed_budget <= 1:
            raise EvaluationError(f"{config.name}: per-run budget must be between $0 and $1")


def _parse_structured(value: Any) -> dict[str, str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise EvaluationError("runner did not return structured JSON") from exc
    if not isinstance(value, dict):
        raise EvaluationError("runner structured output must be an object")
    if set(value) != {"answer", "source", "rationale"}:
        raise EvaluationError("runner output must contain exactly answer, source, and rationale")
    if not all(isinstance(value[key], str) for key in value):
        raise EvaluationError("runner output fields must be strings")
    return {key: value[key] for key in ("answer", "source", "rationale")}


def _parse_claude(payload: Any) -> tuple[dict[str, str], int | None, int | None, float | None]:
    if not isinstance(payload, dict):
        raise EvaluationError("Claude output wrapper must be an object")
    structured = payload.get("structured_output", payload.get("result"))
    response = _parse_structured(structured)
    usage = payload.get("usage", {})
    input_tokens: int | None = None
    if isinstance(usage, dict):
        input_parts = [
            usage.get("input_tokens"),
            usage.get("cache_creation_input_tokens"),
            usage.get("cache_read_input_tokens"),
        ]
        present_parts = [part for part in input_parts if isinstance(part, int)]
        input_tokens = sum(present_parts) if present_parts else None
    output_tokens = usage.get("output_tokens") if isinstance(usage, dict) else None
    cost = payload.get("total_cost_usd")
    return (
        response,
        input_tokens,
        output_tokens if isinstance(output_tokens, int) else None,
        float(cost) if isinstance(cost, (int, float)) else None,
    )


def run_prompt(
    config: RunnerConfig,
    prompt: str,
    schema: dict[str, Any],
    *,
    cwd: Path | None = None,
) -> RunnerResult:
    command = list(config.command)
    if config.parser == "claude-json":
        command.extend(["--json-schema", json.dumps(schema, separators=(",", ":"))])
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=config.timeout_seconds,
            check=False,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return RunnerResult(
            response=None,
            exit_code=124,
            error_category="timeout",
            latency_ms=round((time.monotonic() - started) * 1000),
            input_tokens=None,
            output_tokens=None,
            cost_usd=None,
        )
    latency_ms = round((time.monotonic() - started) * 1000)
    if completed.returncode != 0:
        return RunnerResult(
            response=None,
            exit_code=completed.returncode,
            error_category="runner_nonzero_exit",
            latency_ms=latency_ms,
            input_tokens=None,
            output_tokens=None,
            cost_usd=None,
        )
    try:
        payload = json.loads(completed.stdout)
        if config.parser == "claude-json":
            response, input_tokens, output_tokens, cost = _parse_claude(payload)
        else:
            response = _parse_structured(payload)
            input_tokens = None
            output_tokens = None
            cost = None
    except (json.JSONDecodeError, EvaluationError, ValueError):
        return RunnerResult(
            response=None,
            exit_code=completed.returncode,
            error_category="invalid_structured_output",
            latency_ms=latency_ms,
            input_tokens=None,
            output_tokens=None,
            cost_usd=None,
        )
    return RunnerResult(
        response=response,
        exit_code=completed.returncode,
        error_category=None,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
    )
