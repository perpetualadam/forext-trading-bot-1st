# R.47 future GBP risk-engine acceptance criteria

These criteria are research-only. They are not implemented and they do not authorise a trade. A future engine fails closed on every row. A pass is a recorded input, not an order.

| Criterion | Required behaviour |
| --- | --- |
| Stake and units | No trade while the size field's meaning is unknown. Quantity 1 on this ticket is not that meaning. |
| GBP pip value | No trade while the unrounded GBP value of one pip, at a stated size, is unknown. A display of 0.00 GBP is not zero risk and is not a usable pip value. |
| Conversion | No trade while the quote-to-GBP conversion is missing, stale, or replaced by a constant. The 1.35 fallback is forbidden in that engine. |
| Minimum and increment | No trade while the instrument minimum and the size step are unverified. A displayed 1 is not the minimum. An increment of 1 is not assumed. |
| Margin | No trade while the instrument margin rule and the closeout rule are unknown. A displayed 0.03 GBP is not the rule. |
| Stops | No trade while the minimum stop distance, slippage behaviour, and guaranteed-stop terms required for the order type are unknown. |
| Financing | No trade while financing on the intended hold cannot be represented conservatively, including a Wednesday or holiday multiple when the hold can include one. An unknown rate is not zero. |
| Risk budget | No trade while the risk budget is not an explicit GBP amount supplied for that decision. The historical 97.15 figures are not that budget. |
| Position clamp | No trade under an implicit unlimited size. A configuration that leaves `MAX_POSITION_UNITS` without a positive clamp does not satisfy this criterion. Satisfying it requires a verified step and a GBP risk cap, not a copied units-available figure. |
| Currency reconciliation | No trade while broker-reported transaction currency and P&L currency have not been reconciled to GBP for that account. |
| Fail closed | Any missing input, stale conversion, mismatched currency, or unverified instrument returns no order. The engine does not substitute balance for NAV, USD for GBP, or a rounded zero for a pip value. |

OANDA One closeout and financing rules are not acceptance inputs for the reported v20 profile.
