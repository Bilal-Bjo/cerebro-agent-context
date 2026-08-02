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

Task provenance must have been recorded before edits with:

cerebro task init --cwd <project-checkout> --id <short-task-id> --json

If that did not happen, do not invent a base commit. Source-bound automatic promotion is
unavailable. Bounded agent-owned learning is also unavailable until the next clean task boundary;
do not route ordinary agent learning to owner confirmation as a fallback.

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

Classify every candidate:

- source-bound candidate: a derived fact independently proven by small owning files the agent did
  not create or change since the recorded task base;
- agent-owned candidate: a bounded internal runbook, agent-process incident, or research synthesis
  that should change future agent behavior without claiming external proof or owner approval;
- owner-accepted candidate: only a claim that explicitly represents the owner's approved
  preference, commitment, or consequential business decision;
- reject: inference, duplicate source facts, temporary state, or task exhaust.

Ordinary agent learning must not require the owner to babysit Cerebro. Prefer `agent-owned` for
corrections and prevention rules discovered through the agent's work. It is limited to internal
notes directly under `runbooks/`, `incidents/`, or `research/`; requires `agent-learning` and
`audit://agent/...` provenance; and cannot supersede notes, declare evidence, or replace stronger
authority. Inference never becomes current authority. Do not edit note frontmatter directly to
grant authority. For a surviving candidate, write one JSON file with exactly this shape:

{
  "schema_version": 1,
  "id": "stable-note-id",
  "project": "resolved-project-id",
  "type": "runbook",
  "target": "runbooks/Prevention Rule.md",
  "sensitivity": "internal",
  "sources": ["audit://agent/project-task"],
  "tags": ["agent-learning", "bounded"],
  "supersedes": [],
  "summary": "One compact claim.",
  "read_when": "When this claim changes a future action.",
  "title": "Human title",
  "body": "Compact Markdown body.",
  "requested_authority": "agent-owned",
  "evidence_paths": []
}

Allowed targets are State.md, Agent Map.md, or a Markdown file under decisions/, runbooks/,
incidents/, or research/. For `agent-owned`, use internal sensitivity, a direct target in the
partition matching its type, `agent-learning`, at least one `audit://agent/...` source, and empty
`supersedes` and `evidence_paths`. Use `owner-accepted` with an empty evidence list only for actual
owner authority.

Check it before applying:

cerebro proposal --brain <brain-path> check \
  --cwd <project-checkout> \
  --file <proposal.json> \
  --json

For source-bound proposals, apply only when automatic_promotion_eligible is true. The CLI compares
every evidence path with the recorded base and creates the hashes itself. Apply bounded
agent-owned proposals automatically when automatic_promotion_eligible is true; never ask the owner
to type an ID for the agent's own learning. For owner-accepted proposals, ask the owner to run or
explicitly approve the interactive apply; never simulate, pre-fill, pipe, or bypass the exact-ID
confirmation.

Apply an eligible proposal:

cerebro proposal --brain <brain-path> apply \
  --cwd <project-checkout> \
  --file <proposal.json> \
  --json

Use no more than eight small, directly relevant evidence files. A matching hash proves unchanged
bytes, not that the note's prose follows from those bytes.

Before applying, inspect the brain's Git status and preserve unrelated changes. Never store
transcripts, hidden reasoning, credentials, cookies, sessions, private keys, OAuth state, customer
data, logs, databases, copied source code, guesses, temporary plans, or one-off commands.

After editing:

1. Run cerebro validate --brain <brain-path> --json.
2. Inspect the exact diff and the CLI-provided commit message.
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
