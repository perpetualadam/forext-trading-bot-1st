# R.43 contract and data provenance schema

This schema is a design for a later read-only verification record. R.43 did not fill it from a broker and did not fetch a webpage.

Two sensitivity classes are required:

- `PUBLIC_DOCUMENTATION`: a broker document that explains a product. It does not prove this account can use the product.
- `ACCOUNT_SPECIFIC`: a field returned for this account. It is sensitive. A later record may store the field name, the value, and the retrieval time, and must not store an API token.

Suggested record:

| Field | Meaning |
| --- | --- |
| `record_id` | Local identifier. Not an order id |
| `sensitivity` | `PUBLIC_DOCUMENTATION` or `ACCOUNT_SPECIFIC` |
| `broker_environment` | The environment named in the later authorisation |
| `account_product_type` | Spread-bet, CFD, or spot, as returned. Empty if the source does not say |
| `instrument_id` | Broker identifier |
| `local_symbol` | Research name such as `EUR_USD`, if a mapping exists |
| `quote_currency` | Quote currency returned by the source |
| `pip_location` | Decimal place or pip size returned by the source |
| `price_precision` | Display precision returned by the source |
| `trading_available` | Tradable flag at the source timestamp |
| `minimum_stake_or_size` | Minimum and increment. Units must be named |
| `margin_parameters` | Margin rate, leverage cap, closeout fields. Absent fields stay null |
| `financing_rules` | Rate, time, and direction convention. Null if the source does not give them |
| `source_timestamp_utc` | When the source says the fact was current |
| `retrieved_at_utc` | When the later stage stored it |
| `source_document_or_endpoint` | Document title or endpoint path. No credential |
| `verification_method` | `account_read` or `public_document` |
| `proves_account_access` | True only for `ACCOUNT_SPECIFIC` |
| `unknown_fields` | List of checklist items this record does not answer |

Rules:

- A public document sets `proves_account_access` false.
- Missing NAV, pip value, financing, or minimum stake stays null. It is not estimated.
- The record does not contain an order, a trade decision, or a profit result.
- The later stage writes these records under its own evidence directory. It does not write production state.
