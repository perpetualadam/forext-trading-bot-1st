# Recommended R.45 direction

Do not start R.45 from this stage.

If a later authorisation names one step, name route A only: accept a user-supplied redacted product or instrument sheet, with account numbers and balances removed, and record it under the schema in `10_contract_schema.md`. Do not request credentials or statements. Do not treat a redacted sheet as account permission by itself.

Route B, a public-document read, needs its own authorisation and still cannot prove this account's permissions. Route C, an account read, stays unauthorised. Do not combine A, B, and C. Do not download candles or evaluate a strategy in that stage.

Leave the R.42 range rule unchanged. Do not repair the USD-versus-GBP accounting conflict inside a contract-review stage.
