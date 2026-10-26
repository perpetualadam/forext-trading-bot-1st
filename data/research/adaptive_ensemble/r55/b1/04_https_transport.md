# HTTPS transport

`transport.py` is an allowlisted GET sender. Importing it does not open a connection, and it does not enable a live OANDA session.

The normal `--offline` command passes only the built-in `SyntheticTransport`. A class attribute is not accepted as proof that an arbitrary class is network-free. `transmit` checks the prepared request through the pinned R.53 allowlist, builds a certificate-verifying TLS context, and then calls the class it was given:

- Host `api-fxtrade.oanda.com`, port `443`, timeout `5.0` seconds.
- Certificate mode `CERT_REQUIRED` and hostname verification left on.
- Method `GET`, body empty, no stream, no redirect, no retry.
- Only the instruments and pricing templates, the six pairs, and `includeHomeConversions=true` on pricing.
- HTTP statuses other than 200 do not read a body.
- The read is capped at 1,048,576 bytes.
- Failures become fixed classifications. The original exception text is dropped.
- `close()` runs on completion and on failure.

The offline command passes `SyntheticTransport`, which returns fixture payloads and does not open a socket. `run_live`, `mode="live"`, and the live client classes are rejected before a callback or a client object is created. `transmit` also refuses `HTTPSConnection`, `HTTPConnection`, and their subclasses. Refusing those classes does not prove that some other class cannot open a socket. The executable therefore accepts only `SyntheticTransport`. Test stand-ins use a separate function that `launch` and `run_offline` do not call. Those tests run under a network-denial fixture covering socket creation, name lookup, and connection attempts. That fixture is a testing safeguard, not a general security sandbox.
