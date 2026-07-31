# Architecture

Cerebro is a file-backed context compiler. It turns a small, typed Markdown corpus into bounded
JSON suitable for an agent context window.

## Components

```text
working directory
       │
       ▼
project resolver ───────► project.json
       │
       ▼
current-note loader ────► Markdown + frontmatter
       │
       ├── structural validation
       ├── authority promotion validation
       ├── status filtering
       ├── freshness calculation
       ├── optional file evidence
       ├── sensitivity gate
       └── lexical query
       │
       ▼
context document ───────► human text or stable JSON
```

Historical paths are a separate input. They are read only when `--history` is present and every
result is labelled `partition: history`, `current: false`, and `warning: unverified historical
evidence`.

## Authority order

Cerebro is deliberately subordinate to live evidence:

1. Current source, tests, runtime output, and the owning service or API.
2. Current Cerebro State, accepted decisions, active runbooks, open incidents, and current
   research.
3. Explicitly requested historical evidence.

If live evidence contradicts Cerebro, the agent should follow the live evidence and update the
relevant note through a normal reviewed Git change.

## Project resolution

Each `project.json` contains one or more filesystem roots. `cerebro resolve` finds every root that
contains the target working directory and selects the longest match.

This permits:

- one brain to serve many repositories;
- a more specific nested project to override a broad workspace registration;
- deterministic resolution without reading agent conversation history.

Equal-length ambiguous matches fail instead of guessing.

## Note lifecycle

A note is current authority only when:

- its type is supported;
- its status is current for that type;
- schema v2 records `owner-accepted` or `source-bound` authority rather than `proposal`;
- its promotion metadata satisfies the selected authority class;
- its freshness window has not expired;
- its `expires_at` date, when present, has not passed;
- every declared project-file SHA-256 check matches when evidence verification is required;
- its sensitivity is allowed by the retrieval request;
- the note and project both pass validation.

Changing a note from `current` to `stale` preserves the evidence without allowing it into default
context. `supersedes` provides stable lineage between note IDs.

## Why lexical search

The public alpha uses deterministic, case-insensitive lexical search. Operational brains should
remain compact, and exact terms are inspectable during debugging.

An embedding backend adds ranking opacity, dependencies, model drift, cost, and potential data
movement. Cerebro’s roadmap requires a retrieval evaluation before accepting those tradeoffs.

## Write and promotion model

The CLI scaffolds a brain and project partitions. Ongoing authoritative changes flow through an
exact structured proposal:

```text
clean Git task base
        ↓
candidate proposal
        ↓
source-bound ── compare evidence paths with task diff
        │
        └────── owner-accepted ── exact interactive confirmation
        ↓
atomic note write + whole-brain validation
```

For `source-bound`, task provenance covers committed changes since the base, staged changes,
unstaged changes, and untracked files. If any evidence path appears in that union, automatic
promotion refuses. Missing task metadata and dirty preflight states route to review.

`owner-accepted` is a different trust mechanism, not a fallback an agent may silently choose. The
CLI requires the owner to type the exact note ID. `proposal` never appears in current context.

Cerebro reports an intended commit message but does not commit, push, configure remotes, or publish.

## Compatibility

The JSON surface is intended for agents and automation. It includes:

- `schema_version`;
- project identity;
- generation time;
- current/stale status;
- authority class and promotion metadata;
- whether history was included;
- ordered documents;
- explicit warnings.

Human output is a presentation layer over the same governed selection.
