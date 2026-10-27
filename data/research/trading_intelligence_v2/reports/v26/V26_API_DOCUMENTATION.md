# V2.6 Api Documentation

Public primary sources reviewed2026-10-27:
- https://raw.githubusercontent.com/oanda/v20-openapi/master/yaml/v20.yaml
  Legacy official spec3.0.25 defines the approved non-account instrument path,
  price components, time bounds, smooth and includeFirst; count is omitted when
  both bounds are supplied. No numeric ceiling is specified there.
- https://developer.oanda.com/rest-live-v20/pricing-ep/
  Current account-specific candle documentation gives maximum5000. That path is
  NOT allowed. Research caps windows at5000 and defaults1000 conservatively;
  the exact non-account current ceiling remains unverified.
- https://developer.oanda.com/rest-live-v20/development-guide/
  Documents the two REST hosts and connection/request ceilings; one serial
  request/second is the stricter local choice, not a global cross-process limiter.
- https://developer.oanda.com/rest-live-v20/instrument-df/
  Defines observed mid/bid/ask OHLC, timestamp, volume and explicit completion.
- https://developer.oanda.com/rest-live-v20/authentication/
  Describes bearer-token authentication. No token was obtained or read.
- https://www.oanda.com/assets/documents/383/OEM_OANDA_API_Licence_v2_11.2020.pdf
  Public OEL licence distinguishes internal research from redistribution.
  Applicability to this user/account and derived publication is NOT established.

The instrument-ep URL returned404; no fallback API call was made. A public API
spec/code licence is not a market-data usage grant. Applicable division/platform
terms and exact endpoint support must be reviewed before authenticated retrieval.

Production remains NO-GO.
