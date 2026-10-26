# R.34 research decision-journal schema

Module: `forex_bot/research/decision_journal.py`. `RESEARCH_ONLY` is true. `validate_journal_record` checks one in-memory row and writes nothing. There is no collector, database writer, or retraining hook.

A row records the decision time, instrument, timeframe, feature and model versions, artifact hash, prediction, probabilities, acceptance or abstention, spread, market condition, risk rejection reason, later return, prediction error, whether that outcome was evaluable, and the data and model provenance.

`prediction_error` and `adverse_outcome` are separate. A row may have prediction error 0 and `adverse_outcome` true: the direction matched and the later result was still adverse. A positive prediction error records a poor directional prediction. If `outcome_evaluable` is false, the return, the error, and the adverse flag must be empty.
