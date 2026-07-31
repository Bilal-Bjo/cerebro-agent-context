---
schema_version: 1
id: northstar-shop-state
project: northstar-shop
type: state
status: current
created: 2026-01-15
updated: 2026-01-15
last_verified: 2026-01-15
sensitivity: internal
sources: ["repo://northstar-shop@4b3c2d1", "run://northstar-shop/test-suite"]
tags: ["checkout", "payments", "release"]
supersedes: []
summary: "Current authority for the fictional Northstar Shop service."
read_when: "Read before changing checkout, payments, deployment, or recovery behavior."
---

# Northstar Shop State

Northstar Shop is a fictional storefront used to demonstrate Cerebro without exposing a real
company, account, repository, or infrastructure environment.

## Current system

- The service is a Python web application with a PostgreSQL database.
- Checkout creates an order before requesting payment authorization.
- The application source and tests remain authoritative for implementation details.
- Production deployment uses immutable release identifiers.

## Known constraint

Payment callbacks may be delivered more than once. Handlers must remain idempotent by provider
event identifier.

## Verification

The fake source revision and test-run locator above demonstrate provenance syntax. They do not
refer to a reachable private system.
