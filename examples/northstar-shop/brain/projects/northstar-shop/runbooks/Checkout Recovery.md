---
schema_version: 2
id: checkout-recovery-runbook
project: northstar-shop
type: runbook
status: active
authority: owner-accepted
promotion: {"accepted_at":"2026-01-15T00:00:00+00:00","method":"interactive-owner-confirmation"}
created: 2026-01-15
updated: 2026-01-15
last_verified: 2026-01-15
sensitivity: internal
sources: ["run://northstar-shop/recovery-drill-2026-01"]
tags: ["checkout", "recovery"]
supersedes: []
summary: "Recovery procedure for orders left in a pending checkout state."
read_when: "Read when diagnosing or recovering a pending checkout."
---

# Checkout Recovery Runbook

1. Confirm the order exists and record its immutable identifier.
2. Inspect the payment provider event by its nonsecret event identifier.
3. Replay the idempotent reconciliation command in dry-run mode.
4. Apply the transition only when the dry-run matches the provider state.
5. Verify the order, audit event, and customer-visible status.

This is a synthetic procedure. It intentionally contains no live command, endpoint, or credential.
