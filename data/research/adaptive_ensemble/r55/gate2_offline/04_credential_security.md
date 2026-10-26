# Credential security

Real OANDA credentials were not requested, read, or stored. `.env` and production configuration were not opened. The process did not read `os.environ`.

The preview is fixed text. It shows host `api-fxtrade.oanda.com`, port 443, the two path patterns, `includeHomeConversions=true`, and this warning: a GET-only client does not make the token read-only, and the token may be allowed to trade. The preview has no account identifier and no token.

`CONFIRM PREVIEW` is required before `SyntheticProvider.issue`. Any other answer stops first. Cancellation before credentials also skips `issue`. Cancellation after the handle exists and before the first request constructs nothing and erases the handle. `str` and `repr` of the handle are `REDACTED`. After `erase`, asking for the token raises `R55G2_REJECTED`.

`hidden_input_available` is false. `read_real_credential` raises `R55G2_REAL_CREDENTIAL_INPUT_NOT_AUTHORISED`. There is no `getpass` and no `input` call.

The synthetic pair is `SYNTHETIC-ACCOUNT-R55G2-NOT-REAL` and `SYNTHETIC-TOKEN-R55G2-NOT-REAL`. Tests put that token in a reader exception and in a response field. The exception text, the returned document, and the written file did not contain it. The evidence writer rejects a document that contains the synthetic token, the synthetic account identifier, `Bearer`, `Authorization`, a URL, `ACCOUNT_VERIFIED`, or `1.35`.

The handle lives in process memory until `finally` erases it. A debugger, crash dump, or another local program can still read that memory. This stage does not claim the token is safe from local inspection.

Token permission remains `UNKNOWN`. No order, trade, or position method is implemented.
