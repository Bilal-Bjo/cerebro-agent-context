# Changelog

All notable changes to Cerebro will be documented here.

## Unreleased

- Add an isolated, deterministic evaluation harness comparing repository-only, `AGENTS.md`, and
  Cerebro context across ten synthetic failure modes.
- Record false task-boundary blocks separately from relevant evidence failures.
- Add a safe-mode model runner with tool isolation, no session persistence, structured output, and
  per-call budget enforcement.
- Publish the frozen 90-run initial comparison and change recommended task-boundary behavior so age
  warns by default while declared evidence failures still block.
- Add explicit accept/review/reject reconciliation proposals and prohibit automatic acceptance of
  facts derived from files changed by the agent in the same task.

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
