# V2.5 Data Coverage

No independent historical dataset was acquired. Existing V23 importer and
source-permission checks were inspected. Public provider documentation was
rechecked 2026-10-27; no archive was downloaded:
- FXCM: https://github.com/fxcm/MarketData/blob/master/CandleData/README.md ;
  personal-use archive subject to EULA; applicable project rights unresolved.
- Dukascopy Europe: https://www.dukascopy.com/europe/english/legal-pages/terms-of-use/ ;
  project database-use permission not established.
The user's earlier clarification confirms no FXCM permission. No protected
service was scraped, no EULA form submitted and no broker API contacted.

Only the 29-trading-day previously examined six-pair M5 archive was replayed,
with study.acquire verifying existing provenance hashes. Exact source provenance,
aggregation gaps and fold times are in ignored outputs/v25/input_manifest.json.
Earlier local 12-month candles were previously examined and lack the required
verified acquisition chain; they are not relabelled independent data.

Missing prerequisite: >=12 months (prefer24–36) M5 or finer observed bid/ask for
EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF, reviewed automated-use and
derived-publication rights, provider identity, UTC/completion conventions, original
hashes, gap/duplicate/precision checks, full research-exposure review and controlled
first access. The V23 importer remains the ingestion contract; no fabricated asks.

Research only. Production remains NO-GO.
