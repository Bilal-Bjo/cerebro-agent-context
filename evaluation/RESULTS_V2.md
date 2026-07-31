# Differential evaluation v2

## Result

On the four preregistered differential packets, a maintained-current `AGENTS.md` matched Cerebro's
answer accuracy: both reached 40/40. Cerebro eliminated the stale adoption seen in the deliberately
stale `AGENTS.md` arm and produced zero false blocks under the warning-first age policy. It did not
beat a perfectly maintained `AGENTS.md` on answer accuracy.

| Condition | Answer accuracy | Overall accuracy | Stale adoption | False blocks |
|---|---:|---:|---:|---:|
| Repository only | 30/40 (75.0%) | 30/40 (75.0%) | 0/40 | n/a |
| Stale `AGENTS.md` | 30/40 (75.0%) | 30/40 (75.0%) | 6/40 (15.0%) | n/a |
| Maintained-current `AGENTS.md` | 40/40 (100%) | 40/40 (100%) | 0/40 | n/a |
| Cerebro v0.3 | 40/40 (100%) | 38/40 (95.0%) | 0/40 | 0/40 |

Cerebro's two overall misses were source-attribution misses on `stale-queue-backend`: the answers
were correct (`river`), but the model cited `src/worker.py`, which was deliberately left outside
the preregistered accepted-source set. The scorer and records were not changed after inspection.

Total effective comparison cost was $2.66: $2.04 for the three retained arms in the exploratory
file plus $0.63 for the corrected maintained-AGENTS arm. The superseded exploratory maintained
arm cost $0.77 and remains committed for auditability.

## Method

- Four differential packets: stale queue backend, irrelevant expired State, semantically
  unsupported hash, and current-versus-history separation.
- Four conditions, ten independent processes per packet and condition.
- One model and runner configuration, tool-free safe mode, no session persistence.
- Maintained `AGENTS.md` rendered mechanically from a neutral maintenance dossier containing
  project truth but no answer options, accepted-source list, forbidden answers, or scoring rules.
- Deterministic scoring with no LLM judge.
- Cerebro warning-first age behavior; broken declared evidence still blocks.

## Honest interpretation

This result rejects the dramatic claim that Cerebro inherently gives better answers than a
complete, current `AGENTS.md`. It does not—at least on these packets.

The value hypothesis is narrower: Cerebro may make that quality easier to sustain by separating
history, routing projects, binding selected claims to byte changes, and making stale adoption
visible. This synthetic evaluation cannot measure maintenance burden, note-writing correctness, or
long-term personal utility. The preregistered 14-day soak remains the decisive personal test.

See [the exact records](results/v2/README.md) and [suite definition](suites/v2.json).
