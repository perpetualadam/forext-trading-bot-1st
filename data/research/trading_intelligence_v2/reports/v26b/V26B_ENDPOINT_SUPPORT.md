# V2.6B Endpoint Support

Reviewed2026-10-27 using public documentation only:
https://developer.oanda.com/rest-live-v20/development-guide/
https://developer.oanda.com/rest-live-v20/instrument-ep/
https://developer.oanda.com/rest-live-v20/pricing-ep/
https://raw.githubusercontent.com/oanda/v20-openapi/master/yaml/v20.yaml

The Development Guide identifies api-fxtrade.oanda.com as the live REST host.
The instrument endpoint page returns404. The current Pricing page documents
GET /v3/accounts/{accountID}/instruments/{instrument}/candles. The official legacy
OpenAPI3.0.25 still describes GET /v3/instruments/{instrument}/candles.
That is not sufficient evidence of current live support. A404 documentation page
also does not establish service retirement. No API host was probed.

Status: CURRENT_NON_ACCOUNT_SUPPORT_UNCONFIRMED.
Design conflict: current account-specific documentation cannot authorise widening
the existing non-account-only allowlist. Provider confirmation is required for
this exact route and its current parameters/limits. No fallback is implemented.
Public source retrieval statuses and available raw SHA256 hashes: public_sources.json.

No authenticated requests. Production remains NO-GO.
