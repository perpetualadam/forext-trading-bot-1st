# Redaction

Synthetic values stay in the test process. They are absent from `06_synthetic_session.json`, from exception text, and from the default launch output.

Checked behaviour:

- The written session file does not contain the synthetic token or the synthetic account identifier.
- It does not contain `Bearer`, `Authorization`, `https://`, or raw bid liquidity.
- A document that contains the token is refused, and the destination file is not created.
- Redirect and rejection exceptions use the fixed code `R51_REJECTED` or `R51_LIVE_TRANSPORT_DISABLED`.
- Launch prints one fixed sentence. Arguments are not printed.
- `future_credential_entry` raises before any prompt.

The fake connection may see the authorisation header and the path in memory so the test can check them. Those objects are not written.
