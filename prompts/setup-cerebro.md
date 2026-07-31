# Universal Cerebro setup prompt

Copy everything inside the prompt block into a capable coding agent while your intended project is
open. It is designed for Codex, Claude Code, and other agents that can inspect files and run shell
commands.

The prompt defaults to:

- the current repository as the first Cerebro project;
- `~/.cerebro` as the private brain;
- the public `v0.3.0` release of Cerebro;
- local Git history without creating or pushing a remote.

Change those defaults in the first paragraph before pasting if needed.

```text
Set up Cerebro for the project currently open in this workspace.

Use these defaults unless the local environment proves they are unsuitable:

- Cerebro brain: ~/.cerebro
- Cerebro release: v0.3.0 from
  https://github.com/Bilal-Bjo/cerebro-agent-context
- First project root: the current Git repository root, or the current working directory when this
  is not a Git repository
- Project name and ID: derive them from current repository metadata; make the ID lowercase
  kebab-case

The observable end state is:

1. The `cerebro` CLI is installed through a user-scoped, reversible method.
2. The brain exists and is a local Git repository.
3. The current project is registered exactly once.
4. Its State and Agent Map contain compact facts verified from current source, configuration,
   tests, and runtime output.
5. The project’s agent instructions contain a task-boundary Cerebro rule without overwriting
   existing instructions.
6. `cerebro validate` passes.
7. `cerebro context --cwd <project-root> --verify-evidence --json` resolves the project, returns
   current State and Agent Map, reports age warnings, and verifies declared file evidence.

Safety and authority rules:

- Inspect before changing anything.
- Never use `cerebro init --force`.
- If the brain already exists, validate and reuse it. Do not replace its configuration, project
  partitions, notes, or Git history.
- If the current project is already registered, do not create a duplicate. Verify its root and
  update notes only when current source proves that an existing claim is wrong or stale.
- Preserve unrelated working-tree changes and all existing AGENTS.md and CLAUDE.md content.
- Do not initialize Git inside the project if it is not already a Git repository. Cerebro’s own
  brain may be initialized as a separate local Git repository.
- Do not create a GitHub repository, configure a remote, publish, or push the brain. Mention a
  private remote as an optional later step only.
- Never read, copy, store, print, or move passwords, tokens, private keys, cookies, browser
  sessions, OAuth state, recovery codes, environment-secret values, credential files, customer
  records, or raw conversation transcripts.
- Do not copy credential-bearing Git remote URLs into notes. Remove URL user information and use a
  nonsecret repository locator.
- Do not install a password helper or change authentication configuration.
- Do not change global Git identity, global agent permissions, shell startup files, or system
  Python. If one of those becomes necessary, stop and report the exact gate.
- Current repository source, tests, runtime output, and owning services are more authoritative
  than Cerebro. Do not invent missing project facts.
- Keep current notes small. Put code architecture, commands, and implementation detail in the
  project repository rather than duplicating them into Cerebro.

Perform the setup:

A. Preflight

1. Resolve the absolute project root.
2. Inspect its Git status without changing it.
3. If it is a clean Git worktree, record the setup task base before any edit:

   cerebro task init --cwd <absolute-project-root> --id setup-cerebro --json

   If it is dirty or not a Git repository, do not invent provenance. Initial notes will require
   explicit owner acceptance.
4. Read the smallest authoritative set of project files needed to understand purpose, runtime,
   build/test commands, major boundaries, and current operational state. Prefer README files,
   manifests, lockfiles, checked-in configuration, tests, and the installed tool versions.
5. Check for AGENTS.md and CLAUDE.md before editing either.
6. Check whether `cerebro` is already installed and record `cerebro --version`.
7. Inspect the brain path. If `~/.cerebro/cerebro.json` exists, run:

   cerebro doctor --brain ~/.cerebro --json
   cerebro projects --brain ~/.cerebro --json

   Stop on an unhealthy brain instead of trying to repair or replace it implicitly.

B. Install the public CLI only when it is missing

Use the first suitable user-scoped option already supported by the machine:

1. `uv tool install` from the Git tag:

   uv tool install "git+https://github.com/Bilal-Bjo/cerebro-agent-context.git@v0.3.0"

2. `pipx install` from the Git tag:

   pipx install "git+https://github.com/Bilal-Bjo/cerebro-agent-context.git@v0.3.0"

3. a dedicated virtual environment under the user’s local application-data directory, plus a
   user-local launcher.

Do not use sudo, modify system Python, or silently edit a shell profile. After installation,
verify:

cerebro --version

If the executable is not on PATH, use its resolved absolute path for the remainder of the setup
and report the PATH limitation in the handoff.

C. Initialize or reuse the brain

When `~/.cerebro/cerebro.json` does not exist, run:

cerebro init --brain ~/.cerebro

When it already exists, do not run init again.

Run validation before adding the project:

cerebro validate --brain ~/.cerebro --json

D. Register the current project exactly once

First try:

cerebro resolve --brain ~/.cerebro --cwd <absolute-project-root> --json

If it resolves to the intended project, reuse that partition.

If it does not resolve, ensure the derived project ID is not already used, then run:

cerebro scaffold <project-id> \
  --brain ~/.cerebro \
  --name "<project-name>" \
  --root <absolute-project-root>

Do not select a similarly named project by guesswork.

E. Replace scaffold prose through governed proposals

Edit only the new project partition under:

~/.cerebro/projects/<project-id>/

Keep the generated stable IDs. Do not grant authority by editing frontmatter directly. Prepare one
exact proposal JSON per note using the schema in the public reconciliation prompt, check it with
`cerebro proposal ... check`, then apply it with `cerebro proposal ... apply`.

Request `source-bound` authority only when task initialization succeeded and every evidence file
was untouched since that base. Otherwise request `owner-accepted` and stop for the owner's exact-ID
interactive confirmation.

The State proposal should contain compact present-tense authority covering:

- what the project is and who or what owns its source of truth;
- its verified runtime or platform;
- the verified build, test, or validation commands an agent needs to begin work;
- a short map of major components or boundaries;
- current constraints or known release gates;
- exact nonsecret source locators.

The Agent Map proposal should contain a short routing document covering:

- “Read State first”;
- which repository files are authoritative for architecture, setup, commands, and tests;
- when future decisions, runbooks, incidents, or research notes should be created;
- that historical content requires explicit retrieval;
- that live source and runtime evidence correct Cerebro.

Do not fill either note with generic advice, guessed architecture, transient task details, a
transcript, or copied secrets. If a material fact cannot be verified, omit it or label the
verification gate rather than presenting it as current.

For source-bound notes, put one or more directly supporting project-relative files in the
proposal's `evidence_paths`, then run:

cerebro proposal --brain ~/.cerebro check \
  --cwd <absolute-project-root> \
  --file <proposal.json> \
  --json

Cerebro—not the agent—checks task provenance and creates verification hashes during apply. Use at
most eight small, directly relevant regular files. Do not bind a note to generated files,
dependencies, logs, databases, secret-bearing configuration, or broad directories.

F. Add the task-boundary rule

Preserve all existing instructions. Add the following bounded section to the project-root
AGENTS.md only when an equivalent rule is not already present:

## Cerebro task boundary

Before planning or editing:

1. On a clean worktree, run `cerebro task init --cwd "$PWD" --id <task-id> --json`.
2. Run `cerebro context --brain ~/.cerebro --cwd "$PWD" --verify-evidence --json`.
3. Read the returned State and Agent Map.
4. Inspect status and warnings. Stale notes are excluded; if resolution, validation, evidence, or
   restricted access fails, report the exact boundary failure instead of guessing.
5. Current source, tests, runtime output, and owning services outrank Cerebro.
6. Never store credentials, cookies, sessions, private keys, customer data, or raw transcripts in
   Cerebro.
7. After nontrivial work, use the reconciliation prompt or skill to submit a structured proposal.
   Never grant authority by editing note frontmatter directly.
8. Prefer correcting an existing note. Never create task logs, copy source code, or remember
   temporary plans merely because work occurred.

If AGENTS.md does not exist, create it with only this section.

For Claude Code:

- If CLAUDE.md already imports AGENTS.md, make no change.
- If CLAUDE.md exists without that import, preserve its content and add `@AGENTS.md` only when
  Claude Code import syntax is appropriate for the repository.
- If CLAUDE.md does not exist, create it containing only `@AGENTS.md`.

Do not duplicate the full rule in both files.

G. Validate the complete setup

Run:

cerebro validate --brain ~/.cerebro --json
cerebro doctor --brain ~/.cerebro --json
cerebro resolve --brain ~/.cerebro --cwd <absolute-project-root> --json
cerebro context \
  --brain ~/.cerebro \
  --cwd <absolute-project-root> \
  --verify-evidence \
  --json

Verify from the actual JSON that:

- validation and doctor are healthy;
- the intended project ID resolved;
- status and age warnings are visible, and stale notes were excluded;
- every declared evidence check passed;
- history was not included;
- the expected State and Agent Map are present;
- no restricted content was requested implicitly.

H. Give the brain local history

If `~/.cerebro/.git` does not exist:

1. Initialize a `main` branch inside `~/.cerebro`.
2. Stage only `cerebro.json` and the intended project partition.
3. Inspect the staged diff.
4. Commit with a concise message such as `Initialize Cerebro for <project-name>`.

If the brain is already a Git repository:

1. Inspect its status and existing changes.
2. Stage only the files created or intentionally updated for this setup.
3. Do not include unrelated changes.
4. Commit only when identity is already configured and the exact staged diff is safe.

Never configure a remote or push as part of this prompt.

I. Final handoff

Report:

- Cerebro version and resolved executable;
- brain path;
- project ID and root;
- files created or changed in the brain and project;
- validation, doctor, resolution, and context results;
- the local brain commit, if created;
- any skipped commit, PATH issue, existing-brain conflict, or human gate;
- the optional next step of creating a private remote, clearly marked as not performed.

Do not claim success unless the freshness-required context command passed and returned the intended
State and Agent Map.
```

## After setup

The setup prompt intentionally does not publish the brain. If you later create a remote, make it
private, scan the complete local history first, and review exactly what will be pushed.
