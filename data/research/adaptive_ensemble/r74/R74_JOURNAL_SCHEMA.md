# R.74 Journal Schema

Schema version: 1. Source: `SCHEMA_SQL` in `forex_bot/close_journal.py` lines 24–68.

## `schema_meta`

One row, `id = 1`.

- `schema_version`
- `bootstrapped_at`
- `closes_authorised`

An unsupported version raises `unsupported_schema` and does not submit.

## `close_operations`

- `operation_id` primary key
- `position_instance_id`
- `position_generation`
- `account_binding` (SHA-256 hex, not the account id)
- `instrument`
- `trade_id`
- `direction`
- `original_units`, `requested_units`, `confirmed_units`, `remaining_units` as exact decimal text, or NULL when unknown
- `submission_state`
- `confirmation_state`
- `submission_intent`
- `owner_token`
- `transaction_ids` as a comma-separated list
- `attempt_count`
- `created_at`, `updated_at`
- `error_classification`
- `recovery_status`
- `schema_version`

Invalid unit text raises `invalid_units`. It is not stored as zero.

## Uniqueness

```sql
CREATE UNIQUE INDEX one_unresolved_close
    ON close_operations(account_binding, instrument, trade_id)
    WHERE confirmation_state NOT IN ('CLOSE_REJECTED_CONFIRMED', 'CLOSE_FINALISED');
```

`CLOSE_FULLY_CONFIRMED`, `CLOSE_PARTIALLY_CONFIRMED`, `CLOSE_OUTCOME_AMBIGUOUS`, and `CLOSE_RECONCILIATION_REQUIRED` still occupy the index. A confirmed rejection or a finalised delete releases it.

Preexisting blockers use NULL unit columns and `error_classification = preexisting_broker_position`. They are not a claim that zero units were closed.
