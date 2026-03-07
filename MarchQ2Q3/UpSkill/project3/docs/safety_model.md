# Safety Model

## Overview

The agent enforces a three-layer safety model before any fix is applied.

## Layer 1: Forbidden SQL Patterns

These patterns are never allowed in auto-generated fixes:

| Pattern | Reason |
|---------|--------|
| `DROP TABLE` | Destructive, irreversible |
| `DROP DATABASE` | Destructive, irreversible |
| `TRUNCATE` | Removes all data without WHERE |
| `DELETE FROM` (no WHERE) | Removes all data |
| `GRANT` | Privilege escalation |
| `REVOKE` | Privilege removal |
| `ALTER ROLE` | Security-sensitive |

## Layer 2: Protected Tables

These tables cannot be modified by auto-fixes:

- `users`
- `accounts`
- `payments`
- `audit_log`
- `credentials`
- `secrets`
- `permissions`

Any ALTER, UPDATE, DELETE, or INSERT targeting these tables triggers escalation.

## Layer 3: Risk Tier Classification

| Tier | Criteria | Action |
|------|----------|--------|
| **Low** | SELECT-only, comments, test files | Auto-approve |
| **Medium** | UPDATE/INSERT with WHERE clause | Auto-approve |
| **High** | ALTER TABLE, CREATE, DDL | Require approval |
| **Critical** | Any modification to protected tables | Block + escalate |

## Escalation

When a fix fails safety checks or exceeds retry limits, the agent:

1. Logs the failure with full context
2. Sends a Slack escalation message
3. Does NOT create a PR
4. Records the escalation in the agent run history
