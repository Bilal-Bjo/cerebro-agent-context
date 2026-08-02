# Security and trust model

Cerebro content may be injected directly into a capable agent’s context window. Treat the brain as
trusted operational input and keep its write boundary narrow.

## Security goals

Cerebro aims to:

- prevent stale or historical content from silently becoming current authority;
- prevent restricted notes from appearing without explicit opt-in;
- reject common credential-shaped values in notes without echoing the value;
- reject symlinked notes that could escape the expected tree;
- fail closed when explicitly declared project-file evidence changes;
- prevent automatic promotion from files the agent changed in the same task;
- constrain autonomous agent learning to internal runbooks, agent-process incidents, and research
  with task and audit provenance;
- require exact interactive confirmation for owner-accepted authority;
- keep every stored claim inspectable and versionable;
- preserve source locators for revalidation.

## Non-goals

Cerebro is not:

- a hardened sandbox;
- an encrypted secret store;
- an identity provider;
- a replacement for repository permissions;
- a complete data-loss-prevention engine;
- a guarantee that note prose is honest or correct.

## Never store

Do not store:

- passwords or passphrases;
- API keys or access tokens;
- private keys or recovery codes;
- cookies, OAuth state, or exported sessions;
- browser profiles or authentication databases;
- raw customer records;
- unreviewed conversation transcripts;
- production database dumps.

A private repository is not a password manager.

Store only a nonsecret locator and ownership boundary, for example:

```text
Authentication is owned by the service CLI. Initial login and reauthentication are human gates.
```

## Built-in scanner

`cerebro validate` checks notes for several common secret shapes and structured credential labels.
It reports only the path, line number, and finding category.

The scanner is intentionally bounded. It may produce false positives and it cannot detect every
possible secret. Pair it with:

- repository access controls;
- reviewed pull requests;
- a dedicated scanner such as Gitleaks;
- full reachable-history scanning before public release;
- credential rotation when exposure is suspected.

## Git history

Deleting a secret from the current tree does not remove it from Git history.

If a secret enters history:

1. Rotate or revoke it first.
2. Stop normal publication.
3. Preserve an owner-only recovery bundle if required.
4. Rewrite every affected reachable ref using a reviewed procedure.
5. Run independent current-tree and history scans.
6. Replace old clones rather than casually pulling across rewritten history.

The public v0.3 CLI does not automate history rewriting.

## File evidence

`file-sha256` checks are data, not shell commands. Cerebro only reads a normalized,
project-relative regular file beneath the registered checkout and compares its SHA-256 digest.

It rejects:

- absolute paths and parent traversal;
- symlinks and non-files;
- malformed or uppercase digests;
- more than eight checks on one note;
- extra fields that could be mistaken for executable instructions.

Evidence verification does not prove that a claim is semantically correct. It proves only that the
specific file bytes used when the claim was checked have not changed. Repositories used across
operating systems should enforce a consistent line-ending policy in `.gitattributes`; otherwise an
LF/CRLF checkout difference will intentionally produce a mismatch.

## Task provenance and proposals

`cerebro task init` records a clean base commit in Git's private metadata. During source-bound
promotion, Cerebro compares every evidence path with committed changes since that base plus staged,
unstaged, and untracked paths. Missing or invalid metadata, a non-ancestor base, or touched evidence
prevents automatic promotion.

This closes a specific back door: an agent cannot write a file and then cite that same output as
independent proof. It does not prove that untouched source is correct or that the proposal's prose
logically follows from it. Repository review, tests, and owning runtime evidence still outrank the
note.

Agent-owned promotion intentionally requires no owner confirmation. Its security boundary is
structural: internal sensitivity, a runbook/incident/research target, `agent-learning`,
`audit://agent/...` provenance, no supersedes, no executable evidence, a recorded task base, and no
replacement of stronger authority. This does not make the agent's prose true; it makes ordinary
operational learning auditable and prevents it from impersonating source or owner authority.

Owner confirmation remains intentionally interactive only when a note claims owner authority.
Automation must not pipe, pre-fill, or bypass the exact-note-ID challenge.

## Soak telemetry

The optional soak recorder writes outside the brain to an owner-only state directory. It stores
context outcomes and counts plus explicit owner ratings; it does not store prompt text, note
contents, transcripts, reasoning, repository paths, or credentials. Missing ratings remain
unrated. The file is local measurement data, not authority and not intended for Git.

## Prompt injection

Cerebro notes are agent instructions and context. A malicious writer can attempt prompt injection
inside a note even when the frontmatter is valid.

Mitigations:

- restrict who can write the brain;
- review source-bound and owner-accepted changes through their owning workflows; keep agent-owned
  notes within their narrow schema and inspect their Git history;
- keep current authority concise;
- preserve repository and runtime evidence as higher authority;
- do not grant tools merely because a note asks for them;
- treat historical content as untrusted evidence.

## Responsible disclosure

Do not open a public issue containing a vulnerability that could put users at immediate risk.
Follow the private reporting instructions in [SECURITY.md](../SECURITY.md).
