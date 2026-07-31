# Differential suite v2 records

These are the exact structured records from the 2026-07-31 differential run. They contain final
answers, deterministic scores, context-gate status, latency, token counts, and cost. They contain no
prompts, transcripts, hidden reasoning, standard output, or standard error.

## Files

- `differential-exploratory-10x.jsonl`: 160 records, SHA-256
  `61ca5f4fcc4ce9d54e27cdc9d9987d314a87c7d8aab94f1e3aec9f044a70823f`.
- `agents-current-corrected-10x.jsonl`: 40 records, SHA-256
  `5151d32a0019e87f07d9a2b36fb6d6b41281340536db886cfd5434db43247349`.

The exploratory file exposed a benchmark bug: its mechanically rendered maintained-AGENTS
condition appended a generic instruction to re-check repository sources, including on a packet
whose dossier explicitly says the fact is owned outside the repository. That biased five of ten
history-separation responses toward `insufficient`.

The renderer was corrected by removing that sentence. Only the affected 40-call
`agents_current` arm was rerun. The published v2 comparison therefore uses:

- `repository`, stale `agents`, and `cerebro` from the 160-record exploratory file;
- `agents_current` from the 40-record corrected file.

No original record was deleted or rewritten.

Reproduce the two components:

```bash
python -m evaluation.cli summarize \
  --input evaluation/results/v2/differential-exploratory-10x.jsonl \
  --conditions repository,agents,cerebro \
  --json

python -m evaluation.cli summarize \
  --input evaluation/results/v2/agents-current-corrected-10x.jsonl \
  --conditions agents_current \
  --json
```
