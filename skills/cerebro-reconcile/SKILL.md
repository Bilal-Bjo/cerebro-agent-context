---
name: cerebro-reconcile
description: Reconcile completed work into Cerebro without storing transcripts or duplicating source code. Use after nontrivial work, when current memory is wrong or incomplete, or when a durable decision, state change, runbook, incident correction, or research result should change a future agent's actions.
---

# Cerebro Reconcile

Keep Cerebro useful by remembering only compact, reusable project truth.

## Reconcile

1. Confirm the task is complete enough to support durable claims.
2. Resolve and read current authority from the actual project checkout:

   ```text
   cerebro resolve --cwd <project-checkout> --json
   cerebro context --cwd <project-checkout> --verify-evidence --json
   ```

   If resolution, restricted access, validation, or evidence verification fails, report that
   boundary instead of guessing. Inspect age warnings; stale notes are excluded rather than treated
   as current authority.
3. Update memory only when the result is likely to change a future action and at least one of these
   is true:

   - authoritative project state changed;
   - the user made a durable decision or preference;
   - a repeatable runbook was proven;
   - an incident cause, correction, or prevention rule was established;
   - source-backed research changed a decision;
   - existing Cerebro authority was proven wrong, stale, or incomplete.

4. Before editing, classify each candidate and emit one compact proposal:

   - `accept`: an explicitly accepted user/owner decision, or a derived fact independently proven by
     an owning source the agent did not change in this task;
   - `review`: a plausible claim that needs user acceptance or independent verification, including
     facts derived from files the agent created or changed in this task;
   - `reject`: inference, duplicate source facts, temporary state, or task exhaust that should not
     become current authority.

   Include the claim, class (`decision`, `derived`, or `inference`), owning source, whether the agent
   changed that source, target note, and reason. Only `accept` proposals may be written
   automatically. Inference never becomes current authority.
5. Prefer correcting the existing note that owns the subject. Otherwise choose the narrowest
   appropriate type: State, decision, runbook, incident, or research. Do not create a task log.
6. Write only claims proven by current source, tests, runtime output, or the owning service. When a
   stable repository file directly supports an important claim, generate a bounded check:

   ```text
   cerebro evidence hash \
     --cwd <project-checkout> \
     --path <project-relative-file> \
     --json
   ```

   Copy the returned `verification` object into the note's `verification` array. Use no more than
   eight small, directly relevant regular files. A matching hash proves unchanged bytes, not that
   the note's prose is true.
7. Inspect the brain's Git status before editing. Preserve unrelated changes. Edit only the
   resolved project partition, run `cerebro validate --json`, inspect the exact diff, and commit
   only the intended note paths when the brain already has a safe local Git workflow.
8. Do not create a remote, push, change authentication, or publish automatically. Remote policy
   belongs to the brain owner.
9. Re-run context with `--verify-evidence`, inspect age warnings, and confirm the corrected
   authority is returned.

## Refuse low-value memory

Do not store:

- chat transcripts, hidden reasoning, task narration, or status chatter;
- facts already cheap and authoritative in project source;
- guesses, temporary plans, one-off commands, or unresolved hypotheses;
- credentials, cookies, sessions, private keys, OAuth state, customer data, logs, or databases;
- copied source code or broad repository summaries;
- a new note merely to prove reconciliation happened.

If nothing passes the durable-value gate, make no Cerebro change.
