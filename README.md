<div align="center">

# Cerebro

### Verified operational context for coding agents

**Local-first · Git-backed · Vendor-neutral · Explicitly current**

[![CI](https://github.com/Bilal-Bjo/cerebro-agent-context/actions/workflows/ci.yml/badge.svg)](https://github.com/Bilal-Bjo/cerebro-agent-context/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](#project-status)

</div>

## TL;DR

**Cerebro is a strict, Git-backed project memory for coding agents.** It keeps project state,
decisions, and rules in local Markdown, makes age and evidence failures visible, and keeps history
out of current context by default. The engineering is tested; the workflow benefit is still being
measured against repository-only and `AGENTS.md` baselines.

**Want it?** Open a project and paste the
[setup prompt](prompts/setup-cerebro.md) into your coding agent.

**Want the proof instead of the pitch?** Read the
[evaluation harness](evaluation/README.md). Its scenarios deliberately include cases Cerebro v0.2
handles well and cases where it fails.

**What changed in v0.2?** Cerebro now closes the loop: an agent can check current memory before
work, decide after work whether anything is genuinely worth remembering, and bind important claims
to the SHA-256 of the repository files that prove them. If a checked file changes, verified context
fails closed instead of serving the old claim.

Coding agents can remember things. The harder problem is deciding what they are still allowed to
trust.

Cerebro is a small, inspectable context layer for coding agents. It stores compact operational
knowledge as Markdown, versions it with Git, separates current authority from historical evidence,
and fails closed when important context has gone stale.

It works with any agent that can run a command and read JSON—including Codex, Claude Code, local
agents, CI jobs, and custom harnesses.

```bash
cerebro context --cwd "$PWD" --require-fresh --verify-evidence --json
```

That command answers more than “what might be relevant?” It answers:

- Which project does this working directory belong to?
- Which notes are current authority?
- When was each claim last verified?
- Has any required context expired?
- Is this information restricted?
- Is an old incident a current fact or merely historical evidence?
- Where did the claim come from?

> Cerebro is not a vector database and not an automatic transcript collector. It is a governed,
> human-readable source of operational context.

## Why Cerebro exists

Persistent memory creates a new failure mode: an agent can confidently recall something that was
true six months ago and dangerously wrong today.

Most memory systems optimize for recall:

```text
conversation → extract memory → retrieve similar memory → inject into prompt
```

Cerebro optimizes for authority:

```text
current source/runtime
        ↓ verifies
typed operational note
        ↓ checks freshness + sensitivity + status
bounded project context
        ↓
agent
```

The distinction matters:

| Question | Ordinary memory | Cerebro |
|---|---|---|
| “Is this relevant?” | Similarity or recency | Project routing and optional text search |
| “Is this still true?” | Usually implicit | `last_verified`, type TTLs, and `expires_at` |
| “Is this current authority?” | Often mixed together | Typed statuses and default-current rules |
| “Can I inspect it?” | Depends on the store | Plain Markdown and JSON |
| “Who changed it?” | Product-specific | Git history |
| “Can history leak into current context?” | Possible | History requires explicit `--history` |
| “Can restricted notes appear accidentally?” | Product-specific | Restricted access requires `--restricted` |
| “Can secrets live here?” | Sometimes | Credential-shaped note values are rejected |

## What is included

Cerebro v0.2 provides:

- a dependency-free Python CLI;
- project resolution from a working-directory path;
- one current State and one Agent Map per project;
- typed notes for decisions, runbooks, incidents, research, references, and state;
- required provenance through `sources`;
- freshness windows by note type;
- explicit expiration through `expires_at`;
- stale and non-current exclusion by default;
- fail-closed `--require-fresh` retrieval;
- optional project-file SHA-256 evidence with fail-closed `--verify-evidence` retrieval;
- explicit, labelled historical retrieval;
- restricted project and note gates;
- stable note IDs and duplicate-ID validation;
- non-echoing detection of common credential-shaped values;
- JSON output for agent and automation integration;
- a completely fictional Northstar Shop example;
- behavioral tests for the trust boundary;
- a reusable reconciliation skill and copy-paste prompt that reject transcripts and low-value
  memory.

## Quick start

### Set up Cerebro with an AI agent

Open the project you want Cerebro to understand, then paste the
[universal setup prompt](prompts/setup-cerebro.md) into Codex, Claude Code, or another capable
coding agent.

The prompt guides the agent through a safe, source-backed setup:

- install the public CLI through a user-scoped method;
- initialize or reuse a private local brain;
- register the current project exactly once;
- build its first State and Agent Map from inspected repository evidence;
- add task-boundary instructions without replacing existing agent rules;
- add the strict after-work reconciliation loop;
- validate freshness-required retrieval;
- create local Git history without configuring or pushing a remote.

It explicitly forbids secrets, raw transcripts, blind overwrites, global permission changes, and
automatic publication.

### 1. Install from source

Python 3.11 or newer is required.

```bash
git clone https://github.com/Bilal-Bjo/cerebro-agent-context.git
cd cerebro-agent-context
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Confirm the CLI:

```bash
cerebro --version
```

### 2. Explore the safe fictional example

The repository includes a complete synthetic brain for a fictional storefront. It contains no
real account, infrastructure, customer, credential, or private repository data.

```bash
export CEREBRO_HOME="$PWD/examples/northstar-shop/brain"

cerebro validate
cerebro projects
cerebro context \
  --cwd "$PWD/examples/northstar-shop/workspace" \
  --require-fresh \
  --verify-evidence
```

Search current authority:

```bash
cerebro search "payment callbacks" --project northstar-shop
```

Inspect an intentionally stale note:

```bash
cerebro search "intentionally stale" \
  --project northstar-shop \
  --include-stale
```

Retrieve historical evidence explicitly:

```bash
cerebro search "earlier checkout worker" \
  --project northstar-shop \
  --history
```

History is returned with:

```text
HISTORY — UNVERIFIED
```

It never silently becomes current authority.

### 3. Create your own brain

```bash
cerebro init --brain ~/.cerebro

cerebro scaffold my-project \
  --brain ~/.cerebro \
  --name "My Project" \
  --root ~/code/my-project
```

This creates:

```text
~/.cerebro/
├── cerebro.json
├── history/
│   └── my-project/
└── projects/
    └── my-project/
        ├── project.json
        ├── Agent Map.md
        ├── State.md
        ├── decisions/
        ├── incidents/
        ├── research/
        └── runbooks/
```

Initialize Git yourself so ownership and remote policy remain explicit:

```bash
cd ~/.cerebro
git init
git add cerebro.json projects history
git commit -m "Initialize Cerebro"
```

Do not commit credentials, cookies, exported sessions, private keys, tokens, customer data, or
unreviewed transcripts.

### 4. Close the memory loop

After meaningful work, use the [reconciliation prompt](prompts/reconcile-cerebro.md) or install the
reusable [`cerebro-reconcile` skill](skills/cerebro-reconcile/SKILL.md). The agent first applies a
strict durable-value gate. It updates nothing when the result is temporary, already obvious in
source, or unlikely to change a future action.

The loop is deliberately asymmetric:

```text
before work: verify and read current authority
after work:  remember only durable, proven changes
```

## The note model

Every current note is Markdown with small YAML-compatible frontmatter:

```markdown
---
schema_version: 1
id: checkout-recovery-runbook
project: northstar-shop
type: runbook
status: active
created: 2026-01-15
updated: 2026-01-15
last_verified: 2026-01-15
sensitivity: internal
sources: ["run://northstar-shop/recovery-drill-2026-01"]
tags: ["checkout", "recovery"]
supersedes: []
summary: "Recovery procedure for orders left in a pending state."
read_when: "Read before recovering a pending checkout."
---

# Checkout Recovery Runbook

1. Confirm the order exists.
2. Inspect the provider event by its nonsecret identifier.
3. Run reconciliation in dry-run mode.
4. Apply only when observed state matches.
```

The frontmatter parser intentionally supports a small, predictable subset: scalar values and
inline JSON arrays. This keeps the CLI dependency-free and the format easy to inspect.

### Authority types

| Type | Current status | Typical purpose | Default freshness |
|---|---|---|---:|
| `state` | `current` | Bounded present-tense project truth | 30 days |
| `reference` | `active` | Agent Map, glossary, or stable routing | 90 days |
| `decision` | `accepted` | Durable architectural or operational choice | 3,650 days |
| `runbook` | `active` | Repeatable recovery or operating procedure | 90 days |
| `incident` | `open`, `monitoring` | Bounded unresolved operational event | 14 days |
| `research` | `current` | Time-sensitive sourced findings | 30 days |

Projects must contain exactly one `state/current` note and exactly one `reference` note with
`role: agent-map`.

Non-current statuses—including `stale`, `expired`, `superseded`, `rejected`, `resolved`, and
`historical`—are excluded from normal retrieval.

### Freshness

Freshness is computed from:

1. `expires_at`, when explicitly present; otherwise
2. `last_verified` plus the configured TTL for the note type.

The root `cerebro.json` controls TTLs:

```json
{
  "schema_version": 1,
  "projects_dir": "projects",
  "freshness_days": {
    "state": 30,
    "reference": 90,
    "runbook": 90,
    "incident": 14,
    "research": 30
  }
}
```

Without `--require-fresh`, stale authority is omitted and the context response reports its status.
With `--require-fresh`, Cerebro exits with code `3` before returning stale authority. It exits with
code `4` when required current authority is restricted and explicit access was not provided.

### Executable evidence

Freshness answers “when was this checked?” File evidence can additionally answer “has the source
that proved this claim changed?”

Generate a check from the registered project checkout:

```bash
cerebro evidence hash \
  --cwd ~/code/api \
  --path pyproject.toml \
  --json
```

Copy the returned object into a note:

```yaml
verification: [{"kind":"file-sha256","path":"pyproject.toml","sha256":"<digest>"}]
```

Then require both time freshness and file evidence at the task boundary:

```bash
cerebro context \
  --cwd ~/code/api \
  --require-fresh \
  --verify-evidence \
  --json
```

Evidence paths must be normalized, project-relative regular files. Absolute paths, parent
traversal, symlinks, missing files, malformed hashes, and mismatches fail closed. A note may declare
at most eight checks. Checks compare exact bytes; repositories shared across operating systems
should declare a consistent text policy such as `* text=auto eol=lf` in `.gitattributes`.

### Provenance

Every note requires at least a `sources` list field. A source is a locator, not a secret:

```yaml
sources: ["repo://shop@4b3c2d1", "run://shop/recovery-drill-2026-01"]
```

Useful source conventions include:

- `repo://` for a repository, path, or revision;
- `run://` for a reproducible test or operational check;
- `issue://` for an issue identifier;
- `audit://` for a review artifact;
- `https://` for an authoritative public page;
- `cerebro://` for another stable Cerebro note or project.

Cerebro does not contact arbitrary source locators automatically. The locator tells a human or
agent where the claim must be revalidated. Only explicit project-file `file-sha256` checks are
executable in v0.2.

## CLI reference

### `cerebro init`

Create an empty brain:

```bash
cerebro init --brain ~/.cerebro
```

### `cerebro scaffold`

Register a project root and create its initial State and Agent Map:

```bash
cerebro scaffold api \
  --name "Public API" \
  --root ~/code/api
```

### `cerebro projects`

List registered projects:

```bash
cerebro projects --json
```

### `cerebro resolve`

Resolve a working directory using the longest registered root:

```bash
cerebro resolve --cwd ~/code/api --json
```

### `cerebro context`

Return bounded project context:

```bash
cerebro context --cwd "$PWD" --require-fresh --verify-evidence --json
```

Important flags:

- `--project <id>` selects an explicit project.
- `--query <text>` narrows non-routing context.
- `--require-fresh` fails when current authority is stale.
- `--verify-evidence` fails when a declared project-file hash no longer matches.
- `--include-stale` includes stale notes with warnings.
- `--history` includes labelled historical evidence.
- `--restricted` explicitly allows restricted content.

### `cerebro search`

Search current notes:

```bash
cerebro search "deployment recovery" --project api --json
```

Search is intentionally lexical in v0.2. For small operational brains, deterministic text search
is easier to audit than an embedding pipeline. Vector retrieval should be added only after an
evaluation shows that text retrieval is insufficient.

### `cerebro evidence hash`

Create a non-executable SHA-256 verification object for one project-relative regular file:

```bash
cerebro evidence hash --cwd ~/code/api --path pyproject.toml --json
```

The command never hashes paths outside the registered project root and never executes note-provided
commands.

### `cerebro show`

Open one note by stable ID:

```bash
cerebro show checkout-recovery-runbook
```

Stale notes require `--allow-stale`. Restricted notes require `--restricted`.

### `cerebro validate`

Validate project manifests, metadata, relationships, duplicate IDs, dates, symlink policy, and
credential-shaped note values:

```bash
cerebro validate --json
```

### `cerebro doctor`

Run a compact machine-readable health check:

```bash
cerebro doctor --json
```

## Agent integration

Add this task-boundary rule to your agent instructions:

```markdown
## Begin every task with Cerebro

Before planning or editing:

1. Fast-forward the Cerebro repository with normal Git safety.
2. Run `cerebro context --cwd "$PWD" --require-fresh --verify-evidence --json`.
3. Read the returned State and Agent Map.
4. Treat repository source, tests, and runtime output as more authoritative than Cerebro.
5. Never store credentials, sessions, cookies, private keys, or raw transcripts in Cerebro.
6. After nontrivial work, use the `cerebro-reconcile` skill or reconciliation prompt. Update only
   compact, proven context that will change a future action; otherwise update nothing.
```

For Codex, place it in `AGENTS.md`.

For Claude Code, place it in `CLAUDE.md`, or import a shared file:

```markdown
@AGENTS.md
```

See [Agent integrations](docs/integrations.md) for complete examples and failure handling.

## Security model

Cerebro assumes its content may be placed directly into an agent’s context window. Therefore:

- secrets are forbidden, even in a private Git repository;
- history is treated as evidence, not authority;
- restricted content requires an explicit retrieval flag;
- symlinked notes and history are rejected;
- secret findings identify the path and line but do not echo the detected value;
- source URLs containing user information are rejected;
- current code and runtime evidence outrank remembered notes.

The built-in scanner is a guardrail, not a replacement for a dedicated secret scanner. Public or
shared deployments should also run a tool such as Gitleaks over both the current tree and reachable
Git history.

Read [Security and trust model](docs/security.md) before putting real operational context into a
brain.

## Design principles

1. **Current is a status, not a folder name.** A note becomes authority only when its type, status,
   verification date, and sensitivity permit it.
2. **History must be requested.** Old evidence never silently competes with present truth.
3. **Source wins over memory.** Code, tests, runtime output, and owning services correct Cerebro.
4. **Plain text is a feature.** People must be able to inspect, diff, review, and repair the brain.
5. **Fail closed at task boundaries.** Missing or stale authority should stop consequential work.
6. **Keep the brain small.** Store durable operational knowledge, not transcripts or task exhaust.
7. **Vendor neutrality matters.** The same verified context should work across agent runtimes.

See [Architecture](docs/architecture.md) for the retrieval and trust model.

## What Cerebro is not

Cerebro is not:

- a password manager or secrets vault;
- a transcript archive;
- a replacement for repository documentation or tests;
- a source-code index;
- an embedding service;
- an autonomous truth-discovery engine;
- a guarantee that a written claim is correct;
- a synchronization service;
- a hosted product.

It makes authority visible and machine-checkable. Humans and agents are still responsible for
verifying claims against their owning sources.

## Project status

Cerebro is an alpha release extracted as a clean public implementation from a privately proven
workflow. The public repository uses fresh Git history and completely synthetic examples.

The v0.2 acceptance surface is covered by automated tests. Its context benefit is not yet proven:
the repository now includes a repeatable three-condition evaluation, and long-term workflow value
still needs real-world soak.

### Roadmap

- JSON Schema files for editor integration.
- Exact-path Git publication with conflict detection.
- Pluggable project resolvers for Git remotes and monorepos.
- Optional MCP server exposing read-only context tools.
- Run and publish the retrieval evaluation before any trust-model or vector-search expansion.
- Signed release artifacts and PyPI publishing.
- Expanded Windows path and terminal testing.

## Development

Run the test suite without writing bytecode:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src \
python3 -m unittest discover -s tests -v
```

Validate the bundled example:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src \
python3 -m cerebro_context validate \
  --brain examples/northstar-shop/brain
```

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md), keep fixtures synthetic,
and include executable proof for behavior changes.

## License

Licensed under the [Apache License 2.0](LICENSE).

Copyright 2026 Bilal Bahjaoui.
