# Cerebro evaluation harness

This harness tests whether Cerebro improves bounded project decisions compared with simpler
baselines:

1. repository snapshot only;
2. repository snapshot plus a deliberately stale `AGENTS.md` instruction;
3. repository snapshot plus a mechanically rendered, maintained-current `AGENTS.md`;
4. repository snapshot plus context produced by the current Cerebro CLI.

The benchmark is versioned. Suite `v1` is the frozen original three-condition comparison and keeps
its strict freshness behavior. Suite `v2` adds the maintained-current upper bound and uses the
v0.3 warning-first age policy. Results from different suites must not be pooled.

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

Each packet declares exact answer options, condition-specific accepted sources, known stale
answers, the expected context status and warning IDs, and whether a block is relevant to the task.
Scoring is deterministic—there is no LLM judge.

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
standard error. Exact reviewed v1 records are committed under `evaluation/results/v1/`; keep new
result files outside the repository until they have been reviewed for publication.

## Validate without calling a model

From the repository root:

```bash
python -m evaluation.cli validate --suite v1
python -m evaluation.cli validate --suite v2
python -m unittest tests.test_evaluation -v
```

Validation materializes every synthetic repository and brain in a temporary directory, then checks
that current Cerebro produces the packet’s declared current-or-blocked status.

## Run a bounded pilot

Review `evaluation/runners/claude-safe.example.json` before use. The bundled configuration caps each
call at $0.15, so this twelve-call pilot has a maximum configured spend of $1.80:

```bash
python -m evaluation.cli run \
  --suite v2 \
  --runner evaluation/runners/claude-safe.example.json \
  --packets stale-queue-backend,decision-continuity,semantic-hash-trap \
  --conditions repository,agents,agents_current,cerebro \
  --repeats 1 \
  --max-runs 12 \
  --output /tmp/cerebro-pilot.jsonl
```

Summarize an existing result file:

```bash
python -m evaluation.cli summarize --input /tmp/cerebro-pilot.jsonl
```

## Run the comparison

One run is a smoke test, not evidence. The frozen v1 comparison repeated all three conditions three
times across all ten packets. Its two exact result files can be reproduced with:

```bash
python -m evaluation.cli summarize \
  --input evaluation/results/v1/full-sweep-1x.jsonl \
  --input evaluation/results/v1/full-sweep-2x.jsonl
```

For v2, start with the four differential packets named in `evaluation/suites/v2.json`, use all four
conditions, and repeat each arm enough to expose same-model variance. Use the same model and runner
configuration for every condition. Preserve the seed and exact result file when comparing code
revisions. Do not tune packets after looking at condition-level results without creating a new
suite version.

The completed ten-repeat differential result, including the preserved renderer correction, is in
[`RESULTS_V2.md`](RESULTS_V2.md).

## Interpretation rules

- A win on synthetic packets does not prove long-term personal value.
- A one-repeat pilot is directional only.
- Same-model variance can swamp small differences.
- Packet authors know the expected answer; model processes do not.
- The harness tests bounded context injection, not note-writing quality or maintenance effort.
- The maintained-current `AGENTS.md` condition is an upper bound. It tests equally available
  current facts, not the human cost of keeping that file current.
- The packets were designed around Cerebro failure modes; the honest differential metrics are
  stale adoption and false blocks, not the headline accuracy gap.
- A real verdict also needs a time-boxed workflow soak measuring corrections, repeated
  explanations, wrong assumptions, task-boundary blocks, and upkeep time.

If Cerebro cannot materially beat repository-only and `AGENTS.md`-only baselines after accounting
for false blocks and maintenance cost, simplify it or stop using it.
