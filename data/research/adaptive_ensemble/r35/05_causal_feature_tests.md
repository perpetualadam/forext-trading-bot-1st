# Causal feature checks

`tests/test_r35_learning_foundation.py` checks:

- Warm-up rows before 20 completed bars are not feature-valid.
- A later suffix does not change an earlier causal feature row.
- `leaky_future_return` copies the next midpoint return into the current row and fails the same prefix check.

Features use the current completed candle and earlier completed candles. Rolling windows end at that candle. There is no global normalisation.
