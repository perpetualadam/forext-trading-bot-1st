# Research journal

Each historical bar can become one research decision. Without a trained model the row records:

- A deterministic SHA-256 research decision id.
- Instrument, timeframe, and decision timestamp.
- Source dataset hash and feature-schema version.
- Feature validity, spread, and volatility when the feature row is valid.
- `prediction_status = prediction_unavailable`.
- Direction, probabilities, confidence, and model artifact are null or the documented unavailable sentinel.
- Decision `abstained`, rejection reason `prediction_unavailable`.
- Outcome timestamp, directional midpoint outcome, and evaluability when the horizon is present.
- Hypothetical cost-adjusted decision outcome stays null because no side was chosen.
- Mistake class `insufficient_information` or `unevaluable_outcome`.

The full id list is hashed. Three validated sample rows are stored in `10_demonstration.json`. The historical CSV is not copied.
