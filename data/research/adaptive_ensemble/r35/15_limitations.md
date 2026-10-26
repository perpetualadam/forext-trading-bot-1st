# Limitations

- No model was trained. Every demonstration row is `prediction_unavailable`.
- Hypothetical labels are not executed trades and are not a profitability result.
- The EUR_USD M5 year was already used in R.29–R.33. Its chronological split is not an untouched final test.
- Labels use the decision bar's close and a later close. That differs from the R.30 simulator, which enters on a later bar.
- Outcome windows overlap. The evaluation embargo is a future-model rule; it does not delete the overlapping labels.
- Volume is the source column when it is finite. It is not independently audited as trade volume.
- Session codes are fixed UTC hour buckets.
- No scaler, encoder, or imputer is fit.
