# Agent integrations

Cerebro works at the task boundary: resolve the current project, validate freshness, then place the
returned documents into the agent’s working context.

## Codex

Add the following to `AGENTS.md`:

```markdown
## Cerebro

Before every task:

1. Update the Cerebro repository with a fast-forward-only Git operation.
2. Run `cerebro context --cwd "$PWD" --require-fresh --verify-evidence --json`.
3. Read the returned State and Agent Map before planning or editing.
4. If project resolution or freshness fails, report the boundary failure instead of guessing.
5. Source, tests, runtime output, and owning services outrank Cerebro.
6. Never write credentials, cookies, sessions, private keys, customer data, or transcripts to the
   brain.
7. After nontrivial work, use the `cerebro-reconcile` skill or reconciliation prompt. Remember only
   compact, proven changes that will affect a future action.
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
  --require-fresh \
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
        "--require-fresh",
        "--verify-evidence",
        "--json",
    ],
    check=True,
    capture_output=True,
    text=True,
)

context = json.loads(result.stdout)
```

Exit code `3` indicates that requested authority is stale or non-current. Treat it as a context
release gate, not as an empty search result.

Exit code `4` indicates that required current authority is restricted. Do not add `--restricted`
automatically; obtain the appropriate authorization for that task.

## After-work reconciliation

Use the repository's [`cerebro-reconcile` skill](../skills/cerebro-reconcile/SKILL.md) when your
agent runtime supports reusable skills. Otherwise paste the
[reconciliation prompt](../prompts/reconcile-cerebro.md) after meaningful work.

Both paths apply the same gate:

- correct an existing note before creating a new one;
- remember only durable facts that will change a future action;
- bind important claims to small project files when deterministic evidence helps;
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
