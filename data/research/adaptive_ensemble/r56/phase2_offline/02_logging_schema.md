# R.56 phase 2 logging schema

Schema version: `r56.phase2.1`.

Each file is one JSON object. Unknown input keys are not copied. Output keys must belong to the allowlist in `diagnostic_writer.py`. A secret literal found in the serialised object blocks that object and writes `SENSITIVE_OUTPUT_BLOCKED` instead.

## Envelope

| Field | Meaning |
| --- | --- |
| `schema_version` | `r56.phase2.1` |
| `collected_at` | UTC time supplied by the logger clock, `YYYY-MM-DDTHH:MM:SSZ` |
| `data_source` | `SYNTHETIC_TEST_ONLY` or `SUPPLIED_DOCUMENT` |
| `session_id` | `r56-` plus 32 hex characters from `uuid4`. Not derived from an account id |
| `record_kind` | `account_summary`, `pricing`, `sizing`, or `failure` |
| `outcome` | `DIAGNOSTIC_RECORDED` or `REJECTED` |
| `missing_evidence` | Stable codes for absent broker evidence |
| `validation_warnings` | Stable codes. Field names that may contain secrets are not included |
| `executable_order` | `NOT_PRODUCED` |

## Account summary

Broker strings are preserved. Floats and booleans are `incorrect_type` and become `NOT_RETURNED`.

| Field | When absent or unreadable |
| --- | --- |
| `home_currency` | `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED` |
| `home_currency_is_gbp` | `true`, `false`, or `UNVERIFIED` |
| `account_type` | `NOT_RETURNED` |
| `balance`, `nav`, `margin_available` | `NOT_RETURNED` |
| `margin_used` | `NOT_RETURNED`, and `margin_used_operational_capture` is `NOT_PARSED_BY_OPERATIONAL_CLIENT` |
| `unrealised_pl` | `NOT_RETURNED`. When present, the capture note says `account_core` parses it and the summary snapshot drops it |
| `account_reporting_timestamp` | `NOT_RETURNED` |
| `account_id_present` | boolean |
| `account_id_logged` | always `false` |
| `account_identity_verified` | always `false` |

## Pricing

| Field | Rule |
| --- | --- |
| `bid`, `ask` | Original first-level price strings, or `NOT_RETURNED` |
| `bid_levels`, `ask_levels` | Count of levels. Extra levels set `additional_levels_not_used` and are not priced |
| `spread_price` | Decimal difference, or `NOT_CALCULATED` |
| `spread_price_source` | `BOT_CALCULATED` or `UNVERIFIED` |
| `spread_pips` | `NOT_CALCULATED` |
| `quote_timestamp` | Original string when it matches a bounded RFC3339 pattern, otherwise `NOT_RETURNED` |
| `quote_freshness` | `QUOTE_FRESHNESS_NOT_VERIFIED` |
| `tradeable` | Boolean from the document, or `NOT_RETURNED`. Missing tradeable is not inferred from `status` |
| `home_conversion` | `HOME_CONVERSION_NOT_VERIFIED`, or a nested object when the supplied document contains the research field names |
| `home_conversion_operational_request` | `NOT_REQUESTED` |

The nested conversion object may contain `positive_units_factor`, `negative_units_factor`, and `home_conversions` entries of `currency`, `account_gain`, and `account_loss`. Positive and negative factors are not copied onto each other.

## Sizing

| Field | Rule |
| --- | --- |
| `instrument`, `proposed_api_units`, `stop_distance`, `risk_budget`, `account_currency`, `calculated_pip_value`, `margin_estimate` | Supplied decimal or instrument string, or `NOT_SUPPLIED` |
| `*_source` | Caller label if it is an allowed source, otherwise `UNVERIFIED` |
| `gbp_pip_value_status` | `UNVERIFIED` |
| `stake_to_unit_mapping` | `NOT_VERIFIED` |
| `sizing_formula_status` | `NOT_REUSED` |
| `order_payload` | `NOT_PRODUCED` |

## Failure

`outcome` is `REJECTED`. `error_code` is one of `EMPTY_RESPONSE`, `MALFORMED_JSON`, `REJECTED_DOCUMENT`, `EXCEPTION_CONTAINED`, `SENSITIVE_OUTPUT_BLOCKED`, `INVALID_CLASSIFICATION`, `SESSION_ID_REJECTED`, `ALLOWLIST_REJECTED`. Exception text is not a field.
