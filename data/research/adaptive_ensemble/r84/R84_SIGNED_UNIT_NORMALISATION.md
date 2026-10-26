# R.84 signed-unit normalisation

`_signed_reduction_magnitude` in `forex_bot/broker_close_evidence.py` converts one TradeReduce quantity to a non-negative `Decimal`. It does not use `abs` on the raw value as a blanket conversion.

Accepted:

- Fill negative and TradeReduce negative, as in the full-close example. The magnitude is the positive counterpart of that signed value. The original signed text is returned as `signed_reduction_units`.
- Fill negative and TradeReduce positive. This is the schema sentence "reduced by" a positive count, which the existing R.82 and R.83 fixtures use. The fill sign has already passed the long-close check.
- Fill positive and TradeReduce positive, as in the partial-close example and a short close.

Rejected:

- Fill positive and TradeReduce negative. `CloseReadError("negative_closed_units")`. This pair is not in either official example and is not the positive schema reading.
- A non-finite value, including `NaN` and `Infinity`.
- A non-numeric or empty quantity.
- A zero quantity does not become a full confirmation. It returns `CLOSE_RECONCILIATION_REQUIRED`.

The fill magnitude must equal the sum of the reduction magnitudes. A disagreement is `fill_reduction_mismatch`, not a confirmation. A reduction larger than the requested units is `unit_mismatch`. The normalised magnitude is never negative.
