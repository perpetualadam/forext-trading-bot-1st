"""Generate honest offline evidence. No authenticated acquisition or performance."""
from pathlib import Path
from .core import PAIRS,iso,timestamp
from .oanda_history import Plan,acquire
from .oanda_history_manifest import encoded,digest
from .oanda_history_integration import load_dataset,verify_policy_seal
from .history_fixtures import Virtual,T
from .mtf_features import prepare


def run(root,package):
    out=package/'outputs/v26';reports=package/'reports/v26'
    out.mkdir(parents=True,exist_ok=True);reports.mkdir(parents=True,exist_ok=True)
    v=Virtual();plan=Plan(T,T+60*300,PAIRS,batch_candles=50)
    manifest=acquire(plan,v.transport(),out/'offline_demo',retrieved=lambda:T+86400)
    data,provenance=load_dataset(out/'offline_demo');frames,_,_=prepare(data)
    policy_hash=verify_policy_seal()
    synthetic=dict(source='INVENTED_FIXTURES_NOT_MARKET_DATA',authenticated_requests=0,
        network_requests=0,synthetic_http_calls=len(v.calls),synthetic_candles=manifest['candle_count'],
        fixture_manifest_sha256=digest(encoded(manifest)),policy_seal=policy_hash,
        aggregation={p:{tf:len(b) for tf,b in bytf.items()} for p,bytf in frames.items()},
        validation_failures=[],resume_reuses_hash_verified_batches=True)
    (reports/'synthetic_verification.json').write_bytes(encoded(synthetic))
    proposal=Plan(timestamp('2023-09-01T00:00:00Z'),timestamp('2025-09-01T00:00:00Z'))
    acquisition=dict(status='AUTHENTICATED_RETRIEVAL_NOT_AUTHORISED',executed='NOT_EXECUTED',
        actual_new_candles=0,actual_new_coverage=None,proposed_environment='practice_NOT_CONFIRMED',
        proposed_host='api-fxpractice.oanda.com',approved_endpoint='/v3/instruments/{instrument}/candles',
        instruments=list(PAIRS),from_utc=iso(proposal.start),to_utc_exclusive=iso(proposal.end),
        primary='M5',price='MBA',batch_candles=1000,planned_windows=len(proposal.batches()),
        maximum_attempts_per_window=3,request_spacing_seconds=1,disk_budget_bytes=2*1024**3,
        storage='NOT_APPROVED_FOR_AUTHENTICATED_DATA: workspace is under OneDrive; review protected local location and applicable rights',
        blocking_reviews=['Explicit Permission B','Intended environment/token match without inspecting credentials now',
            'Applicable jurisdiction/account API usage terms and derived-result permissions',
            'Current support and per-path request ceiling for the exact non-account endpoint',
            'Credential source/redaction review and protected archive location'],
        independent_strategy_results='NOT_EXECUTED',walk_forward_results='NOT_EXECUTED')
    (reports/'acquisition_plan.json').write_bytes(encoded(acquisition))
    docs={
    'EXECUTIVE_SUMMARY': f'''TIV26_READ_ONLY_DOWNLOADER_VERIFIED — offline synthetic verification only.

Standalone GET-only transport, bounded range acquisition, strict MBA validation,
hash-verified atomic batch storage, resume and existing research integration are
implemented. No operational source changed. AUTHENTICATED_RETRIEVAL_NOT_AUTHORISED.
Actual acquisition, independent strategy results and walk-forward results are
NOT_EXECUTED. New historical candles acquired:0. Synthetic fixtures are not market
data. The offline demonstration contains{manifest['candle_count']} invented candles.

The exact non-account candle path appears in OANDA's legacy official OpenAPI;
its former instrument endpoint documentation returns404. Current pricing docs
describe an account-specific path which this transport explicitly refuses.
Current non-account endpoint availability/ceiling must be confirmed before B.
Applicable account terms, environment, credentials and storage are unreviewed.
No test result or API document authorises trading.''',
    'OANDA_CLIENT_AUDIT': '''Read forex_bot/oanda_client.py as source only; never imported it.
Imports oandapyV20, pandas and forex_bot.config. Configuration optionally invokes
load_dotenv, so importing it is unsuitable for this isolated stage. No .env or
credential values were read. build_api selects live/practice from runtime config;
the standalone module does not inherit that selection.

fetch_ohlcv_range requests mid-only M candles, chunks by configured granularity,
drops duplicates then sorts, and returnsNone on request failure. These behaviours
cannot establish strict bid/ask provenance or coverage. Latest fetch_ohlcv uses
one candle request and can retain optional quote fields. The same API instance
and generic wrapper also support account summary/pricing reads. No write endpoint
is imported by the historical range function itself, but generic SDK/configuration
coupling makes direct reuse unsuitable for the narrow transport contract.

_oanda_request uses bounded retries for429/gateway/transport failures, jitter,
and the shared rate limiter. Defaults15s connection/read timeouts, configurable
500/5000 page sizes and shared10RPS are operational settings; none was changed.
The new implementation reuses validators and replay functions, not this client,
its account state, environment settings or operational execution adapter.''',
    'READ_ONLY_TRANSPORT': '''CandleTransport validates method, exact hostname, instrument path and all
query parameters BEFORE invoking its sender. Only GET and six fixed instrument
candle paths are allowed. No account ID is accepted. Both official hosts are
fixed; chosen environment must match the host. No arbitrary URL, port override,
userinfo, query token, encoded path, account-specific route or write method.

Real backend is lazy stdlib HTTPS with certificate validation, fixed GET, bounded
body and no redirect-following library. It does not inherit HTTP proxy environment
configuration. Three attempts maximum; >=1s between serial requests;15s socket
timeout and30s loop deadline, subject to OS DNS/connection timing. No claim of
hard real-time DNS cancellation. Redirects fail, including same-host redirects.
429/5xx retries honour a bounded Retry-After; >60s fails rather than retrying early.

No credential loader or authenticated CLI is provided. In-memory token only after
explicit scoped Approval flags, including terms, endpoint support and credential
review. No such approval exists in this session. Token never enters a URL, repr,
progress record, manifest or response archive. Backend errors and non200 bodies
are discarded/redacted. Synthetic sender tests and mocked stdlib HTTP exercise
the transport without contacting OANDA. The injected sender is a trusted test
seam, not a security boundary against malicious Python code.''',
    'API_DOCUMENTATION': '''Public primary sources reviewed2026-10-27:
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
terms and exact endpoint support must be reviewed before authenticated retrieval.''',
    'DATA_ACQUISITION_PLAN': f'''NOT_EXECUTED. Proposed scope for a later explicit Permission B review:
2023-09-01T00:00Z <= candle start <2025-09-01T00:00Z, six existing FX instruments,
M5 and unsmoothed MBA. Mid is requested from the source so no midpoint extrema
need fabrication. Derive M15/H1/H4 once; D1 disabled. Practice host is proposed,
not confirmed. Live host use would require its own explicit scope approval.

{len(proposal.batches())} deterministic windows at1000 candle intervals, at most3 attempts
each, >=1 second spacing and2GiB logical-byte budget. Actual market availability,
response sizes, permissions, endpoint support and coverage are unknown. Individual
requests use from=start and to=end-1 second, includeFirst=true, no count. This
assigns each aligned candle to one half-open window without relying on whether
the API's end bound is inclusive. Any returned out-of-range start is refused.

Before any authenticated request: confirm exact route and intended environment,
applicable market-data/API terms, safe credential access, protected storage and
explicit approval of this concrete scope. Current workspace is under OneDrive;
ignored Git status alone does not prevent cloud sync. No authenticated archive
location has been approved. Credentials are neither requested nor inspected now.''',
    'BATCHING_AND_RESUME': '''Plan is immutable, M5 aligned, <=3*366 days, <=5000 intervals/window,
<=20,000 windows total. Pagination advances fixed requested windows, never the
last returned candle, so empty replies cannot create infinite loops or masquerade
as coverage. Cancellation is checked before requests, while pacing/backoff and
between batches. A request already in progress is bounded by socket/deadline
behaviour, not instantly cancellable. Progress callbacks contain safe counts.

OS nonblocking writer locks serialize archive publication; closing releases the
lock, including OS process cleanup. Windows uses msvcrt, POSIX flock. No PID-file
stale-owner guessing. Tests cover lock exclusion and interruption; cross-host
filesystems, power loss and hard process-kill durability were not tested.

Raw envelope atomically stores original response bytes as base64, original
retrieval time and public request range. Normalized rows retain decimal lexemes.
Commit record is published LAST with hashes of both artifacts. Resume verifies
hashes, schema, range, retrieval evidence and canonical rows. Durable orphan raw
can finish without refetching. Partial/ambiguous staging stops for review; nothing
is deleted or trusted as complete. Different committed content cannot overwrite
immutable batches. Progress is a rebuildable index, not completeness authority.
fsync plus replace is used; POSIX also syncs the parent directory. Windows and
network/cloud filesystem power-loss semantics remain a deployment review item.''',
    'DATA_VALIDATION': '''Strict JSON rejects duplicate keys, nonstandard NaN/Infinity and unexpected
response/candle fields. Require exact instrument, M5, explicit boolean completion,
integer volume and all observed mid/bid/ask OHLC components. Finite positive
decimal strings allow at most12 fractional digits; original lexemes are retained,
never rounded to a guessed display precision. Instrument precision metadata is
not fetched, so this lexical ceiling is a research validation policy.

Require low<=open/close<=high and comparable bid<=ask. Timestamps normalize to
UTC, must align M5, and reject nonzero fractional nanoseconds rather than truncate.
Reject duplicate/disordered/out-of-range candles before publication. Incomplete
candles are counted and excluded; completed timestamps must precede retrieval.
No sorting, deduplication, interpolation, invented asks or silent invalid-row repair.

Every missing run, including empty windows, is recorded. Weekend-containing gaps
are not certified closures; holiday/calendar evidence remains unknown. No empty
response establishes requested historical completeness. Invalid raw/error bodies
are not archived because arbitrary unexpected fields could echo credentials.
Only validated candle-schema responses become raw evidence. Synthetic checks
exercise gaps, weekends, cross quotes, malformed OHLC and incomplete exclusion.''',
    'DATA_PROVENANCE': '''Actual acquisition NOT_EXECUTED; new market candles0. Small tracked
acquisition_plan.json and synthetic_verification.json distinguish plans/fixtures
from real provenance. Full invented archives stay in ignored outputs/v26.

Real schema records provider, transport mode, environment, public endpoint,
instrument, granularity, MBA, ranges, retrieval time, returned/valid/incomplete
counts, first/last candles, missing-run references, raw/envelope/normalized/commit
SHA256 and limitations. Per-batch commit files contain exact validation reports;
the small final manifest references and hashes them. No token, account ID, HTTP
headers or private URL is serialized. TLS/source assertions and local hashes
are not independent provider attestations or signatures against local tampering.

Large raw and normalized data are excluded from Git. Store confines writes to
research outputs/v26, rejects path escapes and links/junctions, limits logical
disk bytes and uses immutable data publication. Concurrent malicious filesystem
replacement, ACL security, OneDrive/cloud replication and media-failure integrity
are not proven. A protected location/usage review is required before Permission B.''',
    'INDEPENDENT_PERIODS': '''The previously examined29-trading-day archive spans candle starts
2026-09-01T00:00:00Z through2026-10-09T07:00:00Z, last completion07:05Z across
all six pairs. Earlier local history2025-09-01 through2026-08-31 was also examined.
Conservative exclusion interval is[2025-09-01T00:00Z,2026-10-09T07:05Z).

Classification supports PREVIOUSLY_EXAMINED, OVERLAPPING,
INDEPENDENT_UNTOUCHED and PROVENANCE_UNVERIFIED. New download time does not
change a known period's overlap. The proposed2023–2025 range avoids the recorded
exclusion interval but is NOT declared independent: complete research-history,
controlled first access, provenance and rights evidence remain missing. Human
attestations alone do not establish their truth. Mixed overlapping datasets fail
the strongest evaluation gate; a separately validated nonoverlapping dataset
must be supplied. No downloaded period or independent coverage exists yet.''',
    'RESEARCH_INTEGRATION': f'''load_dataset verifies archive commits and original raw bytes, reconstructs
existing core.Bar values and reuses historical_quality and mtf_features.prepare.
The older V23 public-source importer deliberately refuses OANDA URLs; it was not
weakened. The new adapter verifies this dedicated archive contract instead.
Synthetic integration exercises all six pairs and M15/H1/H4 aggregation.

Guarded evaluate_independent reuses v25_engine, Evaluator, Provider, fixed policy
definitions and existing execution accounting. It refuses synthetic input,
unreviewed market closures, insufficient coverage, overlapping or unproven history.
Policy source seal: {policy_hash}. Immutable first-performance-inspection receipt
precedes feature/performance evaluation and blocks a second first-access claim.
No operational loop, broker execution module, strategy/sizing/SL/TP change or new
backtester was introduced. Actual independent evaluation remains NOT_EXECUTED.''',
    'STRATEGY_RESULTS': '''NOT_EXECUTED. No authenticated historical retrieval or independent dataset
exists. No frozen-policy expectancy, trade count, win rate, drawdown or improvement
is fabricated. Synthetic candles validate engineering only and are explicitly
rejected as independent market evidence. V2.5 diagnostics remain preserved and
are not relabelled as V2.6 independent results. Unknown pricing remains unknown.
The fixed-policy integration is an offline foundation, not independently verified
adaptive selection or an operational promotion decision.''',
    'WALK_FORWARD_RESULTS': '''NOT_EXECUTED. Future data must pass provenance, coverage/closure and
independence gates before an irreversible local first-inspection receipt is
written. The frozen adapter uses existing expanding chronological partitions,
causal warm-up and nonoverlapping final test windows; fixed policies are not
selected using test outcomes. Adaptive selection abstains until independent
training/validation is supported. Existing purged-selector lifecycle tests are
reused, including rejection of test-outcome tuning. There is no fitted model,
untouched final result, confidence interval or independent performance conclusion
in this stage. Full future study reporting remains conditional on legitimate data.''',
    'COST_ASSUMPTIONS': '''Historical MBA candles are quotes, not execution receipts. They do not
establish actual filled spread, latency/slippage, commission, financing, conversion
markup or account-specific quality. Frozen V25 scenarios remain observed-bid/ask
only; hypothetical0.5 pip/side with commission3 account units/100k base units/side;
and original0.2 pip/side commission3 control. No scenario is selected by profit.
Current pricing-plan applicability remains unverified. V24 conversion/funding
and intrabar attribution limitations remain. No pricing or profit-protection
parameter was changed; the operational raw protection hash is checked by the seal.''',
    'TEST_RESULTS': '''All tests are synthetic HTTP or filesystem fixtures. Command:
python -I -S -B data/research/trading_intelligence_v2/v26_run.py --tests
Offline demonstration/report command: same runner --offline-check.
Both install the audit barrier before importing project modules. Socket events,
operational imports, credentials, journals, subprocesses and writes outside this
stage's research outputs/reports are blocked. No authenticated OANDA request occurs.

Targeted tests exercise allowlists before send, redirects, token redaction, scoped
approval refusal, mocked HTTPS backend, rate/retry/timeout budgets, cancellation,
JSON/price/time validation, partial publication, original retrieval-time resume,
hash tampering, writer exclusion, six-pair aggregation and independence gates.
Executed results and earlier-version regressions are recorded in test_results.json;
cross-platform findings and raw source preservation are in verification.json.
Hosted outcomes are recorded separately after publication. Historical full-suite
failures remain visible; overall CI must not be described as green if they persist.''',
    'REMAINING_LIMITATIONS': '''Authenticated retrieval is NOT authorised and NOT executed. Exact current
non-account route support/limits, applicable account/division/API terms, intended
host, secure credential method and approved storage remain unresolved. The
workspace is cloud-synced; Git ignore is not an archive permission or security
control. No claim that offline tests verify actual server behaviour or data rights.

No new market coverage, verified holiday calendar, complete history or independent
strategy evidence. Hashes establish local consistency, not provider signatures.
Real TLS, DNS, rate limits, availability and long-range completeness remain untested.
Storage tests cover controlled interruption, not power loss, hostile path races,
network filesystems or cross-host locking. Ambiguous staging intentionally requires
review. Offline integration is tested with fixtures; full independent research and
adaptive-performance reporting require actual sufficient authorised data.
No operational trading integration or production readiness is authorised.''',
    'FINAL_DECISION': '''TIV26_READ_ONLY_DOWNLOADER_VERIFIED — the classification covers the offline
implementation and executed synthetic checks only. Authenticated retrieval:
AUTHENTICATED_RETRIEVAL_NOT_AUTHORISED. Market acquisition, independent strategy
results and walk-forward results: NOT_EXECUTED. Actual new historical data:0.

The transport's read-only restrictions are independent of the trading bot. This
does not prove that the exact legacy endpoint currently serves this account.
It cannot create/close/modify trades through its allowed request interface.
No policy improvement on genuinely independent data is established.

Recommended next step is review of the concrete acquisition plan and all six
Permission B prerequisites, including exact endpoint support and a protected,
rights-compatible archive location. Explicit approval is required before any
authenticated request; no credential values should be pasted into chat.
Stop after V2.6. Production remains NO-GO.'''
    }
    for name,body in docs.items():
        (reports/('V26_'+name+'.md')).write_text('# V2.6 '+name.replace('_',' ').title()+'\n\n'+body+
            '\n\nProduction remains NO-GO.\n',encoding='utf-8')
    hashes={p.name:digest(p.read_bytes().replace(b'\r\n',b'\n')) for p in package.glob('*.py')}
    (reports/'V26_SOURCE_HASHES.txt').write_text('SHA256 LF-normalized research source; not operational raw seals\n'+
        '\n'.join(k+' '+h for k,h in sorted(hashes.items()))+'\n')
    print('OFFLINE_CHECK synthetic candles',manifest['candle_count'],'actual acquired 0; no authenticated requests')
