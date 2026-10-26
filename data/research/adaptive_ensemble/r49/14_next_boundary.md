# Next authorisation boundary

Do not start the next stage from this one.

The prepared procedure is `08_manual_procedure.md`. A later stage may approve that procedure and only then add one HTTPS send inside the same allowlist. That stage is not R.49, and it is not started here.

Until that approval, do not type the token, do not run the prompts, and do not connect. The next stage must still forbid orders, candle downloads, stored account identifiers, and repairs to the USD path. It must run from a window you open outside Cursor.

Leave `MAX_POSITION_UNITS` and the R.42 range rule unchanged.
