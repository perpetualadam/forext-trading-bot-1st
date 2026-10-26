# R.43 ranked next-stage options

These options are separate. The next authorisation should name one of them. R.43 does not start any of them.

## C. Read-only OANDA GBP spread-betting contract verification

Purpose: learn whether this account is a GBP spread-betting account and what stake, pip value, margin, financing, and instrument identifiers apply to the existing six names.

Prerequisites: a later authorisation, a read-only account scope, and the checklist in `06_contract_checklist.md`.

Risks: a live read can touch account metadata. The later client must not call order endpoints. Logs must not keep tokens.

Research value: high. GBP economic results and spread-bet sizing are blocked until this exists. Candle history cannot answer it.

Approvals: explicit read-only account authorisation. No order permission.

Without credentials: the checklist and the schema. Nothing account-specific.

With account access: the provenance records. Still no orders and no strategy test.

Stop: if the account is not the expected product, stop. If an existing pair is not tradable, record that and do not invent a substitute. Do not continue into a candle download in the same stage.

## A. Controlled acquisition of fresh bid/ask data for the six existing pairs

Purpose: obtain candles outside the exposed year so a later study is not another pass over R.29–R.42.

Prerequisites: option C, or an explicit statement that the download is research-only and cannot support a GBP claim until C exists. A frozen instrument list, time range, and holdout cut.

Risks: mixing practice and live, interpolating gaps, or letting a development script read the holdout.

Research value: high for any later market study. Low if the contract is incompatible and the candles cannot be valued in GBP.

Approvals: explicit candle-read authorisation. No order permission.

Without credentials: the architecture in `08_acquisition_architecture.md` only.

With account access: raw files, hashes, and a quality report. No strategy evaluation.

Stop: after the manifest. A short download that ends near the G.3 length stays `INSUFFICIENT_COVERAGE` and is not evaluated.

## B. Controlled acquisition for a small number of additional pairs

Purpose: test whether a new currency, NZD first, adds anything the six USD pairs do not already show.

Prerequisites: A and C for the existing six, plus eligibility for the new name. No synthesised cross prices.

Risks: treating a correlated cross as an independent sample, and spending the first fresh sample on an unverified instrument.

Research value: secondary. It does not repair the exposed year.

Approvals: a separate instrument list. NZD_USD only, if a single name is chosen.

Without credentials: the feasibility table.

With account access: one pair's candles and contract fields. No ranking by profit.

Stop: if the account cannot trade the name, stop. Do not add the other five shortlist names in that stage.

## D. Independent market-structure strategy evaluation

Purpose: ask whether a frozen structure rule has a cost-aware result on data that was not used to design it.

Prerequisites: A with a protected holdout, C with financing and stake rules, and the blueprint in `10_evaluation_blueprint.md`. The R.42 range rule stays unchanged.

Risks: too few confirmed ranges, correlated pairs counted as independent trials, and repeated holdout looks.

Research value: this is the question the programme is pointing at. It is not available yet.

Approvals: one evaluation authorisation naming the protocol hash.

Without credentials: nothing economic can be finished. The blueprint can be written, and it has been.

With account access: still wait until the data and the contract record exist.

Stop: one pre-registered run. `INSUFFICIENT_EVENTS` is an acceptable stop. A loss stays a loss. Do not widen the reach tolerance.

## Sequence

The practical next stage is C. Account product, stake, and financing decide whether a later candle file can support a GBP result. A follows C, limited to the existing six pairs and stopped at the quality manifest. D waits for both. B waits until the six-pair path is unblocked, and then only for NZD_USD.
