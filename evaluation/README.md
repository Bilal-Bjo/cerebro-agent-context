# Cerebro evaluation harness

This harness tests whether Cerebro improves bounded project decisions compared with two simpler
baselines:

1. repository snapshot only;
2. repository snapshot plus an `AGENTS.md`-style instruction;
3. repository snapshot plus context produced by the current Cerebro CLI.

It exists to falsify the project’s value, not to manufacture a benchmark win. Until repeated runs
and real-work soak show a useful improvement, Cerebro should be treated as careful infrastructure
with an unproven workflow benefit.

## What is measured

The ten synthetic packets cover:

- stale instructions contradicted by current repository files;
- durable decisions not represented in source;
- cross-repository ownership;
- an age-expired global State note blocking a repository-answerable task;
- a valid file hash attached to a semantically unsupported claim;
- duplicated package-version drift;
- durable user preferences;
- secret-storage boundaries;
- recovery runbook sequencing;
- separation of current authority from history.

Each packet declares exact answer options, accepted sources, known stale answers, the context status
produced by v0.2, and whether a block is relevant to the task. Scoring is deterministic—there is no
LLM judge.

The summary reports completion, answer accuracy, source accuracy, overall accuracy, stale-answer
adoption, context-gate accuracy, false blocks, latency, token use (including cache tokens), and cost
when the runner exposes them.

## Isolation and privacy

The example runner uses Claude in safe mode with:

- project and user instruction loading disabled by safe mode;
- all tools disabled;
- no session persistence;
- a fresh process for every condition;
- a strict JSON output schema;
- a per-run spending cap.

The model receives only the packet’s synthetic repository snapshot and the context for its assigned
condition. It cannot inspect your working tree, Cerebro clone, shell, or credentials.

Result files contain the final structured answer, scores, context gate status, and aggregate usage
metrics. The harness does not store prompts, transcripts, hidden reasoning, standard output, or
standard error. Keep result files outside the repository unless you have reviewed them for
publication.

## Validate without calling a model

From the repository root:

```bash
python -m evaluation.cli validate
python -m unittest tests.test_evaluation -v
```

Validation materializes every synthetic repository and brain in a temporary directory, then checks
that current Cerebro produces the packet’s declared current-or-blocked status.

## Run a bounded pilot

Review `evaluation/runners/claude-safe.example.json` before use. The bundled configuration caps each
call at $0.15, so this nine-call pilot has a maximum configured spend of $1.35:

```bash
python -m evaluation.cli run \
  --runner evaluation/runners/claude-safe.example.json \
  --packets stale-queue-backend,decision-continuity,semantic-hash-trap \
  --conditions repository,agents,cerebro \
  --repeats 1 \
  --max-runs 9 \
  --output /tmp/cerebro-pilot.jsonl
```

Summarize an existing result file:

```bash
python -m evaluation.cli summarize \
  --input /tmp/cerebro-pilot.jsonl
```

## Run the comparison

One run is a smoke test, not evidence. The initial comparison repeats all three conditions three
times across all ten packets. With the example runner, the configured maximum is $13.50:

```bash
python -m evaluation.cli run \
  --runner evaluation/runners/claude-safe.example.json \
  --conditions repository,agents,cerebro \
  --repeats 3 \
  --max-runs 90 \
  --output /tmp/cerebro-evaluation.jsonl
```

Use the same model and runner configuration for every condition. Preserve the seed and raw result
file when comparing code revisions. Do not tune packets after looking at condition-level results
without recording that the benchmark changed.

## Interpretation rules

- A win on synthetic packets does not prove long-term personal value.
- A one-repeat pilot is directional only.
- Same-model variance can swamp small differences.
- Packet authors know the expected answer; model processes do not.
- The harness tests bounded context injection, not note-writing quality or maintenance effort.
- The current packets intentionally expose both strengths and failures in v0.2.
- A real verdict also needs a time-boxed workflow soak measuring corrections, repeated
  explanations, wrong assumptions, task-boundary blocks, and upkeep time.

If Cerebro cannot materially beat repository-only and `AGENTS.md`-only baselines after accounting
for false blocks and maintenance cost, simplify it or stop using it.
