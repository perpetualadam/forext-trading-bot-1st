# V2.8 observed data quality

Read-only inspection: session d57f728a858243dca8cfc1cc39ecba44, protected archive C:\TradingResearchData\OANDA\sessions\d57f728a858243dca8cfc1cc39ecba44.

Genuine acquired OANDA data: ten EUR_USD M5 candles, 2026-09-02 10:00 through 10:45 UTC candle starts, covering the approved 10:00-10:49:59 window. All complete; bid, ask and midpoint OHLC present. No duplicate, disordered, off-grid, missing or off-precision observations. Existing strict revalidation PASS. Decimal prices preserved; no rounding, filling, sorting or fabricated observations. Closing spread 1.5-1.6 pips, EUR_USD pip size 0.0001; USD_JPY uses 0.01 in the unchanged quality engine.

Raw SHA-256: c85586c61f8ef676a954398e9336226f530506654ff1507794958ecb05834145

Validated SHA-256: 6da41d6470778b2fe8bd9c6c2bcef00c459cc2ac63c03649fd0baf7874f21539

Both match durable manifest. Session request/manifest binding and claimed-grant result hash match; journal SESSION_CONSUMED, attempts 1, DONE, worker exited. Evidence unchanged. No response status line is archived: HTTP 200 follows from the sealed transport rejecting every other status, not from a stored header. No new request made.

Historical candles are not stale because retrieval occurred later. Their completion timestamps must precede retrieval; current live-price freshness is a different check. Weekend-containing gaps remain unverified closure candidates, not fabricated candles; holidays require reviewed calendar evidence. Unexpected jumps and spread distributions require larger-sample/regime analysis; ten candles cannot establish absence of market anomalies. No inference about future fills, slippage or commissions from quote bars.

New offline import_bundle accepts only a reviewed, hash-bound non-synthetic OANDA candle bundle, revalidates its derivative and returns the existing research schema/Bar representation. It imports bytes only, never opens broker connections or modifies archive files. Callers read through existing protected Archive; they must not treat caller-supplied hashes as provider signatures. Generic licensed importer and six-instrument checks are unchanged. Rights review is mandatory; no expanded rights attestation was invented for this sample. The known connectivity request can never become independent through review flags. Unexamined dates need complete research-history and controlled-first-access evidence; merely choosing older dates does not establish independence.
