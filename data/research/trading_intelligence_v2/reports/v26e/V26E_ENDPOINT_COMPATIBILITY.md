# Endpoint and usage evidence — reviewed 2026-10-28

The operational SDK source and repository calls use
`GET /v3/instruments/{instrument}/candles`. The request does not contain an
account ID. OANDA's [legacy OpenAPI 3.0.25](https://raw.githubusercontent.com/oanda/v20-openapi/master/yaml/separate/v20_instrument.yaml)
documents this path, MBA price combinations, temporal bounds, smoothing and
includeFirst; count is omitted when both bounds are supplied. Its specification
licence is not a licence to retain or redistribute market data.

The [current instrument page](https://developer.oanda.com/rest-live-v20/instrument-ep/)
returned 404 during review. The current [pricing page](https://developer.oanda.com/rest-live-v20/pricing-ep/)
documents `/v3/accounts/{accountID}/instruments/{instrument}/candles`, including an
account identifier and an additional units parameter. Documentation of that route
does not verify current OEL LIVE support for the selected non-account route.
Neither route was contacted. The account-specific alternative is refused by the
adapter and unchanged one-shot guard; it needs separate endpoint approval.

The [development guide](https://developer.oanda.com/rest-live-v20/development-guide/)
lists `api-fxtrade.oanda.com` for authenticated fxTrade REST. The [UK troubleshooting guide](https://help.oanda.com/uk/en/faqs/rest-v20-api-troubleshooting-guide.htm)
distinguishes historical base pricing from account-group live pricing. No
interchangeability or equivalence to execution prices is assumed.

`ENDPOINT_SUPPORT_UNVERIFIED` — repository/SDK and legacy contract verified;
current non-account OEL availability, account entitlement and connectivity remain
unverified. There was no API-host probe, support contact or automatic substitution.

The [OANDA Europe Limited agreement, April 2026](https://legal.oanda.com/?code=api_licence_agreement&language=en)
conditions personal/own use in section 4. Section 18.6 describes internal research
and analysis; sections 18.1–18.2 restrict third-party access and retransmission.
Section 17.4 addresses return/destruction on termination. This public document
does not independently establish the user's applicable account terms, intended
retention duration, bulk historical permissions or public derived-data rights.

`USAGE_PERMISSION_NOT_FULLY_ESTABLISHED`. Before activation, resolve current
non-account route support, applicable account/territory entitlement, retention
scope and any proposed disclosure. No private agreement or credentials were read.
