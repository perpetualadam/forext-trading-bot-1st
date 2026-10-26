# R.44 contract-fact schema

Research-only. Unknown fields stay null. This stage does not fill them. The schema has no credential, account id, or personal balance.

| Field | Rule |
| --- | --- |
| `instrument_id` | Broker name if known. Local `EUR_USD` style only as `local_symbol`. |
| `local_symbol` | One of the six research names. |
| `broker` | Null until a source says so for the fact being stored. |
| `environment` | `practice` or `live`, from the source, or null. |
| `product_type` | Spread-bet, CFD, or spot, from the source, or null. |
| `account_currency` | From the source, or null. |
| `quote_currency` | From the source, or null. |
| `pip_location` | Decimal or pip size from the source, or null. |
| `price_precision` | From the source, or null. |
| `stake_or_size_convention` | Named unit, or null. |
| `minimum_size` | Null if absent. |
| `size_increment` | Null if absent. |
| `margin_requirement` | Null if absent. |
| `stop_restrictions` | Null if absent. |
| `financing_terms` | Null if absent. |
| `conversion_method` | Null if absent. |
| `source_type` | `USER_REDACTED_DOCUMENT`, `PUBLIC_DOCUMENT`, or `ACCOUNT_READ`. |
| `source_timestamp_utc` | When the source says the fact was current. |
| `verification_timestamp_utc` | When the later stage stored it. |
| `verification_scope` | Which checklist rows this record covers. |
| `provenance_id` | Local id. Not an order id and not an account id. |
| `verification_status` | `UNVERIFIED` until a later stage sets a narrower status. `ACCOUNT_VERIFIED` only after an approved account read. |
| `unresolved_caveats` | List of blockers this record leaves open. |

A public source sets `verification_status` to a public-document status and leaves account permission unresolved. A code default is not a row in this schema.
