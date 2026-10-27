# V2.6B Api Terms

User confirmed OANDA Europe Limited (UK); no private agreement was inspected.
Public sources reviewed2026-10-27:
https://www.oanda.com/uk-en/legal/
https://legal.oanda.com/?code=api_licence_agreement&language=en
https://legal.oanda.com/?code=terms_of_use_oel&language=en

The current public API agreement is dated April2026. Sections4.1–4.3 constrain
own-use purposes and copies;18.6 includes internal research/analysis. Sections18.1–18.2
restrict sharing/retransmission. June2026 website terms separately restrict
third-party publication of market data. These are not blanket bulk-retention grants.

- DOCUMENTED_PERMITTED, conditional on the applicable agreement: internal personal
  research/analysis. Quant backtesting and private model evaluation are an inference
  within that purpose, not an explicit unrestricted licence.
- DOCUMENTED_RESTRICTED: raw-rate redistribution/disclosure.
- APPLICABILITY_UNVERIFIED: user's applicable version and personal-v20 coverage.
- PROVIDER_CONFIRMATION_REQUIRED: multi-year local archives, retention/backups,
  copy-log obligations and external publication of derived metrics.

Questions for OANDA: Does this agreement cover this personal v20 API use? Is
24-month MBA retention for sole-user backtesting permitted, with which copy/backup
conditions? May non-reconstructive aggregate metrics be published? What route,
request cap and historical availability apply? No forms or messages were sent.

Official PDFs were readable through web extraction. Direct byte retrieval returned406;
raw PDF hashes are unavailable, explicitly recorded rather than invented.

No authenticated requests. Production remains NO-GO.
