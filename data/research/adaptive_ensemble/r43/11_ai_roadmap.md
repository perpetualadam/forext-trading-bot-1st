# R.43 AI learning and adaptive-strategy roadmap

No model was trained. Research observations stay disconnected from production trading. Nothing in this roadmap promotes a strategy or an AI model.

The stages stay separate:

1. Descriptive market-structure research. R.40–R.42 are in this stage. They describe swings, lines, levels, and ranges. They do not approve a trade.
2. Offline economic evaluation. This needs fresh bid/ask data, a verified GBP contract, and the blueprint in `10_evaluation_blueprint.md`. It is not started.
3. Supervised-learning experiments. These may use only the development partition, after an economic question is pre-registered. R.36 and R.37 already found no model that qualified on the exposed year. That result stands.
4. Independent validation. One holdout read, after the protocol hash. A model that was tuned on the holdout is not independent.
5. Operational risk and broker-contract verification. Account product, stake, margin, financing, and NAV are required before any size is meaningful. They are not model outputs.
6. A deployment decision. This remains a later human authorisation. Research completion does not deploy.

A later research system could record, on the development partition only:

- Market-structure observations and their availability times.
- Regime labels from the frozen R.39 definitions.
- Strategy eligibility and an explicit abstention.
- Hypothetical outcomes under the pre-registered cost model.
- An error analysis that separates a bad forecast from a correct abstention.
- Probabilities that are calibrated on development data and then left alone.
- Drift checks that compare later development windows with the fitting window.
- The model version, feature hash, and protocol hash beside every score.

Those records are not written to the production journal. They do not call the ensemble, the RL gate, or the order path. `UNAVAILABLE` remains the RL result until a verified unique learned action exists, and this stage does not create one.
