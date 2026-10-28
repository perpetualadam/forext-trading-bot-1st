# Endpoint and permissions — reviewed 2026-10-28

Source-only findings: forex_bot/oanda_client.py:367 and :443 construct
InstrumentsCandles(instrument=..., params=...). The previously inspected installed
SDK 0.7.2 maps that class to GET v3/instruments/{instrument}/candles. The public
[official specification 3.0.25](https://raw.githubusercontent.com/oanda/v20-openapi/master/yaml/separate/v20_instrument.yaml)
also defines this non-account GET and MBA/from/to/smooth/includeFirst parameters;
count is omitted when both bounds are provided. Its software licence does not
grant market-data rights.

The [development guide](https://developer.oanda.com/rest-live-v20/development-guide/)
identifies api-fxtrade.oanda.com as the authenticated fxTrade REST host. The
[former instrument documentation](https://developer.oanda.com/rest-live-v20/instrument-ep/)
returned 404 during this review. Current [pricing documentation](https://developer.oanda.com/rest-live-v20/pricing-ep/)
describes GET /v3/accounts/{accountID}/instruments/{instrument}/candles. That is a
different contract, with an account identifier and units parameter; it is not
approved as a replacement.

Evidence states:

- Official specification: non-account route documented.
- Current web documentation: account-specific route described; current support
  for the selected non-account route is not established by this evidence.
- Observed working in this account: not verified in this stage; code is not a receipt.
- Account entitlement: not verified; no credentials, account records or probes used.

`ENDPOINT_SUPPORT_NOT_RUNTIME_VERIFIED`

The [OEL legal hub](https://www.oanda.com/uk-en/legal/) links the
[April 2026 OANDA Europe Limited API agreement](https://legal.oanda.com/?code=api_licence_agreement&language=en).
Sections 4 and 18.6 support own/internal research use subject to the agreement;
18.1–18.2 restrict third-party access and retransmission. Section 17.4 imposes
return/destruction obligations at termination. These are conditional permissions,
not an account-specific entitlement or an explicit perpetual-retention grant.

Assessment: one EUR/USD historical request for private research, secure local
storage, no third-party access, redistribution or resale is consistent with the
internal-use purpose. Applicability and exact retention rights remain unresolved.
Future multi-year acquisition needs a separate bulk-access/archival review.

Questions prepared for OANDA, **not sent**:

1. Does the applicable OEL LIVE account support the non-account
   /v3/instruments/EUR_USD/candles route for this bounded M5/MBA request?
2. Do its applicable terms permit this single private research retrieval and
   secure local retention of raw and validated candles? For how long, with what
   copy, attribution, backup and deletion obligations?
3. What separate permission or limits apply to future multi-year retrieval,
   archival retention and publication of derived research without raw data?

No conclusion about connectivity or personal account rights is inferred from
public documentation, a token variable name or a successful synthetic fixture.
