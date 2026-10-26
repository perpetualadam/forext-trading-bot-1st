# Decision-record schema

`details.risk_decision` is built by `_build_risk_decision` for every result. It is JSON serialisable and deterministic for fixed inputs.

Fields:

- `decision_id`: instrument, direction, injected timestamp, and strategy.
- `context`: `isolated_test` or `production`.
- `instrument`, `direction`, `timestamp`, `strategy`.
- `account_evidence`, `market_data_evidence`, `exposure_hold`.
- `portfolio_risk`, `gross_notional`, `unit_limit`, `daily_loss`, `drawdown`.
- `spread`, `quote_freshness`, `lookback`, `margin_evidence`.
- `mandatory_gates`, `disabled_gates`, `missing_evidence`, `unapproved_policies`, `not_implemented`.
- `blocking_reasons`: every non-pass that is not an optional disabled gate or a documented not-applicable gate.
- `production_eligible`.
- `synthetic_contract`: `completed` only when the inert adapter was invoked.
- `reservation_attempted`, `inert_adapter_invoked`, `production_adapter_invoked`.

The record does not copy the account payload. Building a record does not reserve, create an order, or change live-permission state. A missing record is not treated as eligibility: a decision with unevaluated mandatory gates has `production_eligible` false.
