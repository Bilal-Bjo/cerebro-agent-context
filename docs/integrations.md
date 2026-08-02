# Agent integrations

Cerebro works at the task boundary: resolve the current project, validate freshness, then place the
returned documents into the agent’s working context.

## Codex

Add the following to `AGENTS.md`:

```markdown
## Cerebro

Before every task:

1. Update the Cerebro repository with a fast-forward-only Git operation.
2. On a clean worktree, run `cerebro task init --cwd "$PWD" --id <task-id> --json`.
3. Run `cerebro context --cwd "$PWD" --verify-evidence --json`.
4. Read the returned State and Agent Map before planning or editing.
5. Inspect `status` and `warnings`. Stale notes are excluded; evidence, validation, access, and
   resolution failures remain blocking.
6. Source, tests, runtime output, and owning services outrank Cerebro.
7. Never write credentials, cookies, sessions, private keys, customer data, or transcripts to the
   brain.
8. After nontrivial work, use the `cerebro-reconcile` skill or reconciliation prompt. Submit
   structured proposals. Use bounded `agent-owned` authority for ordinary agent learning and
   reserve `owner-accepted` for actual owner decisions; never grant note authority by editing
   frontmatter directly.
```

The exact Git update command belongs to your environment. Do not place a token in the instruction
file or command line.

## Claude Code

Claude Code can use the same rules through `CLAUDE.md`:

```markdown
@AGENTS.md
```

Or copy the bounded Cerebro rule directly into `CLAUDE.md`.

## Shell task boundary

A simple read-only wrapper can make the boundary explicit:

```bash
#!/usr/bin/env bash
set -euo pipefail

cerebro context \
  --cwd "${1:-$PWD}" \
  --verify-evidence \
  --json
```

Keep authentication in the Git client or credential manager that owns it. Do not interpolate a
credential into this wrapper.

## Custom agent harness

Call the CLI as a subprocess and reject nonzero exit codes:

```python
import json
import subprocess

result = subprocess.run(
    [
        "cerebro",
        "context",
        "--cwd",
        "/workspace/project",
        "--verify-evidence",
        "--json",
    ],
    check=True,
    capture_output=True,
    text=True,
)

context = json.loads(result.stdout)
```

Exit code `3` indicates a strict freshness or declared evidence failure. Ordinary age staleness is
reported in `status` and `warnings` when `--require-fresh` is omitted; stale notes are not returned.
Use strict freshness only when age alone must be a release gate.

Exit code `4` indicates that required current authority is restricted. Do not add `--restricted`
automatically; obtain the appropriate authorization for that task.

## After-work reconciliation

Use the repository's [`cerebro-reconcile` skill](../skills/cerebro-reconcile/SKILL.md) when your
agent runtime supports reusable skills. Otherwise paste the
[reconciliation prompt](../prompts/reconcile-cerebro.md) after meaningful work.

Both paths apply the same gate:

- correct an existing note before creating a new one;
- remember only durable facts that will change a future action;
- bind important claims to small project files only when task provenance proves the agent did not
  change those files;
- publish bounded internal agent-process lessons automatically as `agent-owned`;
- require exact interactive owner confirmation only for claims that represent the owner's
  decisions or commitments;
- validate and inspect the exact diff;
- do nothing when no claim passes the gate;
- never push or change remote policy automatically.

## CI

Validate the brain as part of its own repository checks:

```bash
cerebro validate --brain . --json
```

If the brain is private, run validation only in a trusted CI environment. Do not upload the vault
as an artifact unless that is explicitly allowed by its data policy.

## Restricted partitions

Do not add `--restricted` to a global wrapper. The flag exists to make access visible at the call
site.

Prefer a separate task or explicit user authorization before retrieving restricted context.
