STAGE 14 TE OPERATIONAL RETIREMENT
----------------------------------
Trading Economics subscription cancellation is recorded as an operational
status change. Historical TE observations, evidence, hashes, adapter code,
tests, and probe artifacts are preserved. No replacement provider was
chosen. No CPI observation was created.

PROVIDER ACCEPTANCE REQUIREMENTS
--------------------------------
A future consensus provider must support, for the relevant release:

A. Genuine externally published market/economist consensus.
B. Distinction between Consensus, proprietary Forecast, Previous, and Actual
   where applicable.
C. Clear component semantics. CPI requires headline_mom, headline_yoy,
   core_mom, core_yoy.
D. Point-in-time observation.
E. Evidence that can be preserved with provenance.
F. Permitted access method.
G. No requirement to bypass access restrictions.
H. No automatic averaging across providers.
I. Provider-specific vintages remain separate.
J. observed_at_utc < T0 for consensus use.

CONSENSUS VS MODEL FORECAST
---------------------------
A proprietary provider forecast is NOT automatically a consensus.
A model forecast is NOT a consensus.
A nowcast is NOT a consensus.
A single economist forecast is NOT automatically a market consensus.
The source must characterize the value as a survey, poll, median/mean
consensus, or equivalent aggregated expectation with sufficiently clear
semantics. Do not infer consensus merely because a number appears before
release.

KNOWN PROVIDER STATUS
---------------------
- Trading Economics: CONSENSUS_PROVIDER, OPERATIONAL_RETIRED_SUBSCRIPTION_CANCELLED, not live, not approved.
- Forex Factory: CONSENSUS_PROVIDER candidate historically, PROBED_NOT_REGISTERED, not approved.
- BLS official: OFFICIAL_ACTUAL_PROVIDER, not a market-consensus provider.
- FRB official: OFFICIAL_ACTUAL_PROVIDER, not a market-consensus provider.
- manual_operator: ingest method, not a publisher.
- Econoday / Reuters / FactSet / Dow Jones / Bloomberg: registered, disabled, not promoted.

CPI `usd_cpi_2026-10-14` is registered with an active checkpoint schedule and
PROVIDER_PENDING / NONE_APPROVED. The scheduler may still evaluate timing and
record NO_ENABLED_SOURCE. A due checkpoint with no genuine evidence becomes
MISSED_NOT_OBSERVED. Consensus=null is never manufactured.
