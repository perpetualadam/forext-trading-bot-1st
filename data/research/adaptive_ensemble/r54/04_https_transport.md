# HTTPS transport used by the session

`session_main.run_session` does not contain a second request builder. After the preview, it calls the pinned R.53 function `run_synthetic`, which calls `transmit`.

The transport that function prepares is:

- Host `api-fxtrade.oanda.com`, port `443`.
- TLS context from `ssl.create_default_context` with `CERT_REQUIRED` and hostname checks left on.
- Timeout `5.0` seconds. Retries `0`. Redirects are not followed.
- Method `GET` only. Body is `None`. Streaming is off.
- Paths are only `/v3/accounts/{accountID}/instruments` and `/v3/accounts/{accountID}/pricing`.
- Both queries list only `EUR_USD,GBP_USD,AUD_USD,USD_CAD,USD_CHF,USD_JPY`.
- The pricing query also sets `includeHomeConversions=true`.
- Any other host, method, path, or query key is rejected before a client object is created.
- Only HTTP 200 is accepted. A redirect status does not read a body.
- The body read is capped at 1,048,576 bytes.
- `close()` runs on completion and on failure.
- `http.client.HTTPSConnection`, `http.client.HTTPConnection`, and subclasses are refused before construction.

R.54 did not open a real TLS connection. The offline tests pass a fake client class into `run_session`. The default entry point never calls `run_session`.
