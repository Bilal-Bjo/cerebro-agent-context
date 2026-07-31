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

The public v0.2 CLI does not automate history rewriting.

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

## Prompt injection

Cerebro notes are agent instructions and context. A malicious writer can attempt prompt injection
inside a note even when the frontmatter is valid.

Mitigations:

- restrict who can write the brain;
- require human review for changes;
- keep current authority concise;
- preserve repository and runtime evidence as higher authority;
- do not grant tools merely because a note asks for them;
- treat historical content as untrusted evidence.

## Responsible disclosure

Do not open a public issue containing a vulnerability that could put users at immediate risk.
Follow the private reporting instructions in [SECURITY.md](../SECURITY.md).
