# Security policy

## Supported versions

Cerebro is currently an alpha project. Security fixes are applied to the latest release on the
default branch.

## Reporting a vulnerability

Please use GitHub’s private vulnerability reporting feature for this repository.

Include:

- the affected command and version;
- a minimal synthetic reproduction;
- the security consequence;
- whether the issue could expose note content or bypass freshness, history, or sensitivity gates;
- the smallest verification that would demonstrate a fix.

Do not include real credentials, private vault content, customer data, cookies, or session exports
in the report.

## Scope

High-priority security issues include:

- restricted content returned without explicit authorization;
- stale or historical content represented as current authority;
- path or symlink escape from configured partitions;
- secret values echoed in diagnostic output;
- unsafe parsing that can execute note content;
- ambiguous project resolution that silently selects the wrong authority.
