# Evidence contract

Every document this executable writes uses `evidence_class` `SYNTHETIC_TEST_ONLY` and `account_specific_api_evidence` `NOT_PRODUCED`.

`broker_pricing` is `SYNTHETIC_FIXTURE`. `authentication` is `NOT_PERFORMED`. `account_verified` is `NO`. `live_connection` is `DISABLED`.

These statuses are fixed. This stage does not resolve them:

| Fact | Status |
| --- | --- |
| Account home currency | `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED` |
| GBP conversion suitability | `NOT_VERIFIED` |
| Spread-bet stake-to-unit mapping | `NOT_VERIFIED` |
| GBP pip value | `NOT_VERIFIED` |
| Financing | `NOT_VERIFIED` |
| Token permissions | `UNKNOWN` |
| Executable trade sizing | `NOT_CALCULATED` |
| Strategy profitability | `NOT_ESTABLISHED` |
| Quote staleness rule | `NOT_DEFINED` |
| Account summary | `NOT_AUTHORISED` |

## Fields a successful synthetic row may contain

| Field | Meaning |
| --- | --- |
| `instrument`, `type`, `pip_location`, `display_precision`, `minimum_trade_size`, `margin_rate` | Copied from the synthetic instruments fixture. `type` `CURRENCY` is not a spread-bet decision. |
| `financing_long_rate`, `financing_short_rate` | Copied rates from the fixture. The document financing status stays `NOT_VERIFIED`. The rates are not a GBP cost. |
| `time`, `bid`, `ask`, `tradeable` | Copied from the synthetic price fixture. The timestamp is not checked for age. |
| `spread_pips` | Calculated as `(ask - bid) / 10**pipLocation`. It is a fixture width, not a broker spread. |
| `positive_units_factor`, `negative_units_factor`, `account_gain_factor`, `account_loss_factor` | Copied when present. Missing values are `NOT_RETURNED`. They are not copied across one another. |
| `quoted_conversion_currency` | The fixture currency, or `AMBIGUOUS`, or `NOT_RETURNED`. |
| `quoted_conversion_currency_is_account_home` | Always `NO`. |
| `gbp_conversion_suitability` | Always `NOT_VERIFIED`. |
| `quote_usable` | `YES` only when `tradeable` is true and the other price checks pass. |
| `quote_staleness_rule` | Always `NOT_DEFINED`. |

The synthetic placeholder `SYNTHETIC-ACCOUNT-R55B2-NOT-REAL` is an input to the planner and a label in this research directory. It is not an OANDA account. The saved evidence omits it, omits the synthetic token, and omits a full account URL.

No row is an authentication result, a live price, a confirmed GBP model, an executable size, or evidence that a strategy is profitable. Practice trading and live trading are not ready.
