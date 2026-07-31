---
schema_version: 2
id: northstar-shop-agent-map
project: northstar-shop
type: reference
status: active
authority: owner-accepted
promotion: {"accepted_at":"2026-01-15T00:00:00+00:00","method":"interactive-owner-confirmation"}
role: agent-map
created: 2026-01-15
updated: 2026-01-15
last_verified: 2026-01-15
sensitivity: internal
sources: ["cerebro://project/northstar-shop"]
tags: ["routing", "agents"]
supersedes: []
summary: "Entry map for agents working on the fictional Northstar Shop."
read_when: "Read at the beginning of every Northstar Shop task."
---

# Northstar Shop Agent Map

Start with [[Northstar Shop State]].

- Read [[Payment Idempotency Decision]] before changing payment callbacks.
- Read [[Checkout Recovery Runbook]] before diagnosing stuck orders.
- Treat anything under the history partition as unverified evidence.
- Revalidate code claims against the repository and executable tests.
