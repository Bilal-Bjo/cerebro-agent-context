# Cerebro reconciliation prompt

Paste the prompt below into a coding agent after meaningful work when you want it to decide whether
Cerebro needs a compact update. If your agent supports skills, use
[`skills/cerebro-reconcile/SKILL.md`](../skills/cerebro-reconcile/SKILL.md) instead.

```text
Reconcile the work just completed into Cerebro only if it produced reusable project truth.

First resolve the current project and read its existing State and Agent Map with evidence checks
enabled. Current source, tests, runtime output, and the owning service outrank Cerebro. Stop and
report any resolution, validation, access, or evidence failure instead of guessing. Inspect age
warnings; stale notes are excluded rather than treated as current authority.

Apply this strict durable-value gate. Update Cerebro only if the result is likely to change a
future agent's action and it records one of:

- changed authoritative project state;
- a durable user decision or preference;
- a proven repeatable runbook;
- an incident cause, correction, or prevention rule;
- source-backed research that changed a decision;
- a correction to Cerebro authority proven wrong, stale, or incomplete.

Prefer correcting the existing note that owns the subject. Otherwise use the narrowest suitable
State, decision, runbook, incident, or research note. Never create a task diary.

Before editing, classify every candidate and produce a compact proposal:

- accept: an explicitly accepted user/owner decision, or a derived fact independently proven by an
  owning source the agent did not create or change in this task;
- review: a plausible claim requiring user acceptance or independent verification, including any
  fact derived from files the agent created or changed in this task;
- reject: inference, duplicate source facts, temporary state, or task exhaust.

For each proposal state: claim, class (decision, derived, or inference), owning source, whether the
agent changed that source, target note, and reason. Automatically write only accept proposals.
Inference never becomes current authority.

Write only claims proven during this task. If an important claim depends on a stable repository
file, run:

cerebro evidence hash \
  --cwd <project-checkout> \
  --path <project-relative-file> \
  --json

Add the returned verification object to the note's verification array. Use no more than eight
small, directly relevant regular files. A matching hash proves unchanged bytes, not that the note's
prose follows from those bytes.

Before editing, inspect the brain's Git status and preserve unrelated changes. Edit only the
resolved project partition. Never store transcripts, hidden reasoning, credentials, cookies,
sessions, private keys, OAuth state, customer data, logs, databases, copied source code, guesses,
temporary plans, or one-off commands.

After editing:

1. Run cerebro validate --brain <brain-path> --json.
2. Inspect the exact diff.
3. Commit only the intended note paths when the brain already has a safe local Git workflow.
4. Do not create a remote, push, change authentication, or publish automatically.
5. Re-run:

   cerebro context \
     --brain <brain-path> \
     --cwd <project-checkout> \
     --verify-evidence \
     --json

Inspect the returned status and age warnings. If nothing passes the durable-value gate, make no
Cerebro change and say so briefly.
```
