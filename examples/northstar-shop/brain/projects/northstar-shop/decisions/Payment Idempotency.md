---
schema_version: 2
id: payment-idempotency-decision
project: northstar-shop
type: decision
status: accepted
authority: owner-accepted
promotion: {"accepted_at":"2026-01-15T00:00:00+00:00","method":"interactive-owner-confirmation"}
created: 2026-01-15
updated: 2026-01-15
last_verified: 2026-01-15
sensitivity: internal
sources: ["repo://northstar-shop/docs/adr/004-payment-idempotency.md"]
tags: ["payments", "idempotency"]
supersedes: []
summary: "Payment callbacks are deduplicated by provider event identifier."
read_when: "Read before changing payment callback handling or order state transitions."
---

# Payment Idempotency Decision

Every payment callback is recorded with a unique provider event identifier before its state
transition is applied. Replayed callbacks return the previously recorded result.

This decision protects order state from duplicate delivery without relying on timing assumptions.
