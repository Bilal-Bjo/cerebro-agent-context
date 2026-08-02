# Changelog

All notable changes to Cerebro will be documented here.

## Unreleased

- Add bounded `agent-owned` authority so internal operational lessons can promote automatically
  without owner confirmation, while preventing them from declaring evidence, superseding notes,
  replacing stronger authority, or impersonating owner decisions.
- Add schema v2 authority classes: `owner-accepted`, `source-bound`, and non-authoritative
  `proposal`, while keeping schema v1 readable as labelled legacy authority.
- Add clean task-base Git provenance and refuse source-bound automatic promotion when an evidence
  path was committed, staged, unstaged, or created during the task.
- Add exact structured proposal checking and atomic application. Owner authority requires exact
  interactive note-ID confirmation.
- Add an owner-only, preregistered 14-day soak recorder with explicit unrated handling and no
  prompt, transcript, note-content, or credential collection.
- Add an isolated, deterministic evaluation harness comparing repository-only, `AGENTS.md`, and
  Cerebro context across ten synthetic failure modes.
- Record false task-boundary blocks separately from relevant evidence failures.
- Add a safe-mode model runner with tool isolation, no session persistence, structured output, and
  per-call budget enforcement.
- Publish the frozen 90-run initial comparison and change recommended task-boundary behavior so age
  warns by default while declared evidence failures still block.
- Commit the exact structured v1 result records and add a versioned v2 suite with a
  maintained-current `AGENTS.md` upper-bound condition and age-warning regression coverage.
- Publish the ten-repeat v2 differential records, preserve a discovered baseline-renderer bias,
  and report the corrected result: maintained-current `AGENTS.md` tied Cerebro on answer accuracy.

## 0.2.0 — 2026-07-31

- Add fail-closed project-file SHA-256 evidence generation and verification.
- Add a strict after-work reconciliation skill and copy-paste prompt.
- Update the universal setup prompt and agent integrations to use the complete before/after memory
  loop.
- Keep remote creation, pushes, credential handling, and transcript collection outside the public
  workflow.

## 0.1.0 — 2026-07-31

Initial public alpha:

- dependency-free Python CLI;
- typed, source-backed Markdown notes;
- path-based project resolution;
- freshness and explicit-expiration gates;
- current, stale, historical, and restricted retrieval boundaries;
- validation and health checks;
- synthetic Northstar Shop example;
- behavioral test suite;
- Codex, Claude Code, architecture, and security documentation.
- universal, safety-aware setup prompt linked from the README.
