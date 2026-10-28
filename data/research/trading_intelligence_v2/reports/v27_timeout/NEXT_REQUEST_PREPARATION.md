# Fresh proposal only — do not execute

Previous request `36c7d101ab3f4fe3ae3889408735bdc7` is consumed; HTTP outcome is unknown. All existing grant, journal, claim and response evidence is preserved. No executable grant has been created for the next proposal.

Fresh proposal: `427f86a87ffa4f418a5bdb0583b0e41c`.

Local source seal: `b2cb71b596f432ba8b411a3bdcd2976cef617337486ecb3f2510aaed22dae3b3`.

`authorises_execution` is false. Original seal and proposal are preserved as *.before_timeout_fix.json. The existing reviewed archive mechanism refuses because the consumed session still occupies its fixed state slots. A new ID alone does not make it runnable. No marker has been moved or removed, and no alternate archive/session path or reset mechanism has been introduced. A separately approved evidence-preserving session rollover design is required before another grant can be issued.

Separate publication approval is also required for the local real-session authority/controller/worker timing changes. This report and the input-helper commit do not grant either publication or execution approval.

Future exact phrases, for review only:

1. `I CONFIRM ACCOUNT ENTITLEMENT AND PRIVATE RESEARCH RETENTION`
2. `I ACCEPT ONE NON-ACCOUNT ENDPOINT CONNECTIVITY CHECK`
3. `CONFIRM ONE HISTORICAL EUR_USD REQUEST b2cb71b596f4 427f86a87ffa4f418a5bdb0583b0e41c`

Affirm applicable account permissions explicitly; endpoint support and account-specific retrieval/retention conditions remain unverified. A timeout is never permission to retry.

The unchanged scope is LIVE GET api-fxtrade.oanda.com/v3/instruments/EUR_USD/candles; M5/MBA; 2026-09-02T10:00:00Z through 10:49:59Z; smooth=false, includeFirst=true, count omitted; one attempt, zero retries, no redirects, pagination or fallback; validated storage only C:\TradingResearchData\OANDA. Production trading remains NO-GO.
