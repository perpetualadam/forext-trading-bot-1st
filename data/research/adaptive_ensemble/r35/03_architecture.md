# R.35 research architecture

Offline package: `forex_bot/research/learning/`.

It is not imported by `bot_loop`, `ai_ensemble`, or the RL agent. It does not register a voter, start a collector, or fit a model.

Separated pieces:

- `data_validation.py` checks local candles and returns a copy.
- `features.py` builds causal features from completed bars.
- `labels.py` builds future outcome labels in a separate frame.
- `journal.py` writes in-memory research rows with `prediction_unavailable`.
- `mistakes.py` classifies explicit rows and leaves missing probabilities uncomputed.
- `splits.py` builds chronological folds with an embargo.
- `dataset.py` summarises one local CSV without rewriting it.
- `protocol.py` freezes the schema and protocol versions.

The R.34 validators in `ml_prediction.py` and `decision_journal.py` remain the research contracts. `prediction_status="unavailable"` allows an evaluable market outcome without an invented prediction error.
