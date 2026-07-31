# Cerebro reconciliation prompt

Paste the prompt below into a coding agent after meaningful work when you want it to decide whether
Cerebro needs a compact update. If your agent supports skills, use
[`skills/cerebro-reconcile/SKILL.md`](../skills/cerebro-reconcile/SKILL.md) instead.

```text
Reconcile the work just completed into Cerebro only if it produced reusable project truth.

First resolve the current project and read its existing State and Agent Map with freshness and
evidence checks enabled. Current source, tests, runtime output, and the owning service outrank
Cerebro. Stop and report any resolution, freshness, access, or evidence failure instead of
guessing.

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

Write only claims proven during this task. If an important claim depends on a stable repository
file, run:

cerebro evidence hash \
  --cwd <project-checkout> \
  --path <project-relative-file> \
  --json

Add the returned verification object to the note's verification array. Use no more than eight
small, directly relevant regular files.

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
     --require-fresh \
     --verify-evidence \
     --json

If nothing passes the durable-value gate, make no Cerebro change and say so briefly.
```
