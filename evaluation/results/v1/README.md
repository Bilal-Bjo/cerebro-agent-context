# Frozen v1 structured results

These are the exact structured records used for the 90-run table in
[`evaluation/RESULTS.md`](../../RESULTS.md). They contain synthetic answers, citations, bounded
rationales, context status, scores, latency, token counts, and cost. They do not contain prompts,
transcripts, hidden reasoning, standard output, standard error, credentials, or repository data
outside the committed synthetic packets.

The run was collected in two independently bounded batches:

| File | Runs | SHA-256 |
|---|---:|---|
| `full-sweep-1x.jsonl` | 30 | `268d68b6033f2ce49b3e33244653131f560cfb93102c85e3f3fdfdb8665e75ab` |
| `full-sweep-2x.jsonl` | 60 | `6426fdfa2d0a0353b8e3aa6ef56f74be829283c6083a6c6f57927a20c1f02070` |

Reproduce the aggregate:

```bash
python -m evaluation.cli summarize \
  --input evaluation/results/v1/full-sweep-1x.jsonl \
  --input evaluation/results/v1/full-sweep-2x.jsonl \
  --json
```

The v1 packets and method remain frozen. New policy and baseline work belongs to suite `v2`; never
rewrite these records or reinterpret them as results from the warning-first policy.
