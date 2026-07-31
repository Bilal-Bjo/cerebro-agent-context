---
name: cerebro-reconcile
description: Reconcile completed work into Cerebro without storing transcripts or duplicating source code. Use after nontrivial work, when current memory is wrong or incomplete, or when a durable decision, state change, runbook, incident correction, or research result should change a future agent's actions.
---

# Cerebro Reconcile

Keep Cerebro useful by remembering only compact, reusable project truth.

## Reconcile

1. Confirm the task is complete enough to support durable claims.
2. Confirm task provenance was recorded before edits:

   ```text
   cerebro task init --cwd <project-checkout> --id <short-task-id> --json
   ```

   If it was not, do not invent a base. Source-bound automatic promotion is unavailable and the
   candidate requires owner review.
3. Resolve and read current authority from the actual project checkout:

   ```text
   cerebro resolve --cwd <project-checkout> --json
   cerebro context --cwd <project-checkout> --verify-evidence --json
   ```

   If resolution, restricted access, validation, or evidence verification fails, report that
   boundary instead of guessing. Inspect age warnings; stale notes are excluded rather than treated
   as current authority.
4. Update memory only when the result is likely to change a future action and at least one of these
   is true:

   - authoritative project state changed;
   - the user made a durable decision or preference;
   - a repeatable runbook was proven;
   - an incident cause, correction, or prevention rule was established;
   - source-backed research changed a decision;
   - existing Cerebro authority was proven wrong, stale, or incomplete.

5. Classify each candidate:

   - `source-bound`: a derived fact independently proven by small owning files the agent did not
     change since the recorded task base;
   - `owner-accepted`: a durable decision or claim that requires exact interactive owner
     confirmation;
   - `reject`: inference, duplicate source facts, temporary state, or task exhaust that should not
     become current authority.

   Inference never becomes current authority. Never grant authority by editing frontmatter
   directly.
6. Prefer correcting the existing note that owns the subject. Otherwise choose the narrowest
   appropriate type: State, decision, runbook, incident, or research. Do not create a task log.
7. Write one exact structured proposal using the schema in
   [`prompts/reconcile-cerebro.md`](../../prompts/reconcile-cerebro.md), then run:

   ```text
   cerebro proposal --brain <brain-path> check \
     --cwd <project-checkout> \
     --file <proposal.json> \
     --json
   ```

   Apply a source-bound proposal only when `automatic_promotion_eligible` is true. For
   owner-accepted authority, require the owner to type the exact note ID; never simulate, pre-fill,
   pipe, or bypass confirmation. Apply with `cerebro proposal --brain <brain-path> apply ...`.
8. Inspect the brain's Git status before applying. Preserve unrelated changes. Run
   `cerebro validate --json`, inspect the exact diff, and commit only the intended note paths when
   the brain already has a safe local Git workflow.
9. Do not create a remote, push, change authentication, or publish automatically. Remote policy
   belongs to the brain owner.
10. Re-run context with `--verify-evidence`, inspect age warnings, and confirm the corrected
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
