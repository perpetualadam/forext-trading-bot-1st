# R.34 ML prediction contract

Module: `forex_bot/research/ml_prediction.py`. `RESEARCH_ONLY` is true. The production ensemble does not import it and does not register it as a voter.

`validate_prediction` accepts one supplied payload. It does not create a prediction.

An approved row requires:

- model id, version, feature-schema version, instrument, and timeframe
- a 64-character artifact hash
- a timezone-aware prediction time that is not after the evaluation time and not older than the supplied maximum age
- status `approved`
- validation status `validated_offline`
- direction `BUY` or `SELL`
- a finite confidence from 0 through 1
- probabilities, when present, that sum to 1 and have that direction as the unique maximum

`abstain` and `unavailable` must not carry a direction. A non-finite value, a stale timestamp, an unvalidated approval, or a hash that is not 64 hex characters is rejected. An artifact hash alone is not treated as validation.
