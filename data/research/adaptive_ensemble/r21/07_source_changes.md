# Source changes

Application file modified: `forex_bot/bot_loop.py`.

`database.py` and `orders.py` were not modified. Their hashes match the R.20 baseline.

## Selector

`_authoritative_strategy` interprets the selector result. After `select_strategy` or `select_deterministic` returns, the shared iteration uses that result only. A null, malformed, unknown, or inactive result returns before vote, RL, sizing, reservation, and the inert adapter. A different caller-supplied name is stored as `supplied_strategy_ignored`.

The lookback already preferred the selector lookback. The decision id and order metadata now receive the selected name rather than the supplied fallback.

## Ambiguous order

`_held` updates a still-`PENDING` local order to `UNRESOLVED`. It still calls `note_unconfirmed_exposure` and `restore_unresolved_intent`. It does not call `persist_unresolved_order`.

## Tests

`tests/test_r21_selector_and_order_state.py` is new. R.14 through R.20 fixtures that invoked the selector and depended on the `scalp` fallback now pass an eligibility map. The `bot_loop.py` hash pin in the R.8, R.10, and R.11 suites is `081314246ce22fa092d6f7de9ef8f84760bf87e086f5838e763fb08d7f34f55f`.

No strategy algorithm, weight, sizing formula, broker endpoint, account id, or risk threshold was changed. No production strategy was activated.
