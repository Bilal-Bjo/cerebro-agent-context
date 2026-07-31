# Initial evaluation results

Date: 2026-07-31  
Frozen harness commit: `a25b339`  
Runner: Claude Code 2.1.220, `sonnet` alias, safe mode, tools disabled  
Samples: 10 packets × 3 conditions × 3 independent processes = 90 runs  
Completion: 90/90  
Recorded model cost: $1.48

An earlier nine-call exploratory pilot was used to correct cache-token accounting and strengthen the
age-only false-block packet. The 90 runs below started only after packets, scoring, and runner
isolation were frozen in Git.

## Strict preregistered scores

| Condition | Answer accuracy | Answer + accepted source | Stale-answer adoption | False age blocks |
|---|---:|---:|---:|---:|
| Repository only | 16/30 (53.3%) | 12/30 (40.0%) | 0/30 | n/a |
| Repository + `AGENTS.md` | 18/30 (60.0%) | 12/30 (40.0%) | 9/30 (30.0%) | n/a |
| Repository + Cerebro | 30/30 (100%) | 29/30 (96.7%) | 0/30 | 3/30 |

The sole Cerebro source miss cited `src/worker.py` for the correct River answer instead of the
preregistered `config/queue.toml`. Both files in the synthetic snapshot support that answer. The
table preserves the strict preregistered score instead of changing accepted sources after seeing
the result.

## What the result supports

- Cerebro reliably supplied durable decisions and cross-repository facts absent from the snapshot.
- Current repository evidence overrode stale `AGENTS.md` and Cerebro claims in these packets.
- Separating current State from history prevented the historical provider from leaking into the
  answer.
- A valid SHA-256 attached to the wrong semantic claim did not beat a directly contradictory live
  status file. That success came from source precedence, not from the hash proving the prose.
- Age-only strict freshness produced a false task-boundary block in every repetition of its packet.
- File-evidence mismatch produced the intended block in every repetition of its packet.

## What it does not prove

- The packets are synthetic and deliberately exercise situations where durable project context can
  help. They do not measure note-writing quality or upkeep.
- Three samples per packet reveal gross instability, not statistical significance.
- The runner used one model alias on one day.
- The harness supplies a blocked context result to the model alongside the repository snapshot.
  A wrapper that aborts the entire task on a nonzero context exit would be less resilient.
- This is not evidence that Cerebro improves Bilal’s actual workflow over weeks.

## Decisions from this evaluation

1. Recommend age as a visible warning and keep stale notes out of returned context. Reserve
   `--require-fresh` for tasks where age alone truly must block.
2. Keep access, schema, path, and declared evidence failures blocking.
3. Describe file hashes as byte-change detectors, never as proof that prose is true.
4. Require reconciliation candidates to distinguish accepted decisions, derived facts, and
   unverified inference. Do not auto-accept a derived fact from files the agent changed in the same
   task.
5. Defer live-service adapters until a measured real-work failure requires one.
6. Run a time-boxed personal workflow soak before making a “game changer” claim.

The raw structured result files are intentionally not committed. They contain no prompts or
transcripts, but publishing them was not needed to support these aggregate claims.
