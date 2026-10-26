# R.40 learning-journal architecture

The R.35 journal and the R.36–R.38 supervised path can store a later market-structure study. R.40 does not add fields to the journal and does not train a model.

A future offline record, once a stage is authorised to apply `r40.structure.v1`, can keep:

- Market context: instrument, timeframe, source-file hash, and the H4 state visible at the decision time.
- Confirmed swing points, each with pivot time and confirmation time.
- Trendline identity, the two swings that define it, and the time the line became available.
- Range state and the reaction candles that completed the range.
- Breakout state and, when a later candle qualifies, failed-breakout state.
- Strategy eligibility as a research label, with `NO_TRADE` when the state is `UNCERTAIN` or the candle is missing.
- The decision or the abstention, and the data-quality status.
- A hypothetical outcome only in a stage that is authorised to evaluate one. R.40 records none.
- A failure reason drawn from the existing mistake taxonomy when an evaluation exists.
- Confidence only when it is a probability from a model that was trained under a frozen protocol. Otherwise the field stays unavailable.
- Model and protocol identifiers, including `r40.structure.v1` and the source hashes.

The research package remains `RESEARCH_ONLY`. A journal row cannot set `Strategy.active`, cannot authorise a live order, and cannot replace the quant stub or the RL gate. Both of those stay fail-closed.

Promotion of any later structure rule or model requires three separate steps: an offline test on data that was not used to design it, a written result under the validation rules in `11_validation_requirements.md`, and an explicit approval. The software does not apply that approval by itself, and it does not edit its own rules from a loss.
