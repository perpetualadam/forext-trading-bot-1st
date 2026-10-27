"""Substantive diagnostics generated from executed results, never independent-data claims."""
import json
import statistics
from .study import write
from .historical_sources import SOURCES
from .historical_import import SCHEMA


def f(value): return 'UNDEFINED' if value is None else f'{value:.6f}'


def line(row):
    return (f"{row['pair']}/{row['label']}/{row['strategy']}: n={row['trades']}, gross R={f(row['gross_expectancy_R'])}, "
            f"net R={f(row['net_expectancy_R'])}, cost class={row['cost_class']}.")


def generate(package,spec,receipt,s):
    folder=package/'reports/v23'
    caveat=('\n\nTIV23_RESEARCH_PARTIALLY_VERIFIED. Production remains NO-GO. '
            'No new independent archive was acquired. Existing data is PREVIOUSLY_EXAMINED; these diagnostics are exploratory, '
            'not independent validation, policy optimisation or proof of future profitability.\n')
    def report(name,title,text): (folder/(name+'.md')).write_text('# '+title+'\n\n'+text+caveat,encoding='utf-8')
    normal=[r for r in s['aggregates'] if not r['protection'] and not r['stress']]
    fixed=[r for r in normal if r['label'] in spec['timeframes'] and r['pair']!='PORTFOLIO']
    portfolio=[r for r in s['aggregates'] if r['pair']=='PORTFOLIO']
    st=[r for r in s['signal_overlap'] if r['strategy_a']=='scalp' and r['strategy_b']=='trend']
    report('V23_EXECUTIVE_SUMMARY','V2.3 research outcome',
        'Built a strict licensed-data importer, explicit independence gate, preregistered frozen replay, strategy-overlap matrix and trade-level loss diagnostics. '
        'User confirmed no applicable provider permission and directed importer/exploratory work; no new download was attempted. '
        f"Executed {s['scenario_count']} controlled scenarios with {s['baseline_checks']} matching V2.2 baseline cells. "
        'The original strategies, fills, risk, holding, costs and profit protection are unchanged; diagnostic observation never feeds candidate selection. '
        'Results describe existing shadow rules, not live AI/RL trading directions. '
        'No independent conclusions about timeframe superiority or profit protection are available. '
        'Full strategy-specific gross/net results and overlap measurements follow; do not choose winners from this examined period.')
    source_lines=[]
    for name,r in SOURCES.items():
        source_lines.append(f"- {name}: {r['status']}. {r['limitation']} [Provider documentation]({r['documentation']}); [terms/evidence]({r['terms']}).")
    report('V23_DATA_SOURCE_REVIEW','Public source review and acquisition decision',
        '\n'.join(source_lines)+
        '\n\nNo authenticated broker endpoint, protected-service scrape, account registration, legal-form submission or dependency installation was used. '
        'This is a project-specific permission gap, not a conclusion that these providers prohibit every form of research. '
        'The user selected the importer-only fallback. Future public acquisition needs independently verified provider identity, applicable rights permitting '
        'automated local research and derived-result publication, documented schema/timezone/completion semantics and a bounded retrieval plan. '
        'Suggested upper bounds for a separately reviewed workflow: one request at a time, at most one per second, 15-second timeout, '
        'one retry, 64 MiB/file and 512 MiB total, no redirects to authenticated services, no OANDA hosts. These bounds are proposals; no downloader is active.')
    report('V23_DATA_PROVENANCE','Exposure labels and data provenance',
        'Four labels are distinct: PREVIOUSLY_EXAMINED, NEWLY_ACQUIRED_BUT_OVERLAPPING, INDEPENDENT_UNTOUCHED, PROVENANCE_UNVERIFIED. '
        'A later download does not erase date overlap. Known exposure conservatively covers September 2025 through October 9 2026, '
        'including earlier Stage E/G and TIV2/TIV2.2. Earlier dates are not automatically untouched: complete research-history review and '
        'controlled-first-access evidence are required. Reviewed metadata is an auditable human assertion, not cryptographic provider authentication. '
        'The importer verifies exact raw file hashes and instrument/time/quote identity; it cannot independently prove a dishonest manifest is truthful.\n\n'
        'Current source: archived G3 OANDA candles, read locally only; 29 trading days, all six pairs, normalized values matched to 36 raw-page hashes by the existing acquire routine. '
        'The older 12-month archive is previously examined and lacks a reverified acquisition chain; excluded from performance. '
        'Raw original files are not modified. Existing and new local inspection receipts add dates to the independence gate before performance starts, '
        'including interrupted runs. Repeated imported evaluation requires explicit --allow-reproduction and is labelled exploratory; '
        'it cannot be presented as another untouched first pass. No new archive has qualified as independent in this task.')
    report('V23_DATA_QUALITY','Importer and quality checks',
        'Supported import schema: OBSERVED_M5_BID_ASK_MID_V1 CSV with columns '+', '.join(SCHEMA)+'. '
        'Every row needs literal true completion, an instrument matching the manifest, an aware start timestamp normalized to UTC, '
        'finite positive midpoint/bid/ask OHLC and uncrossed quotes. M5 alignment, strict ordering and duplicate rejection apply within and across files. '
        'Files are consumed in manifest order; disorder is never silently sorted or deduplicated. Malformed/extra/missing fields reject the import. '
        'Ask and midpoint OHLC must be supplied from observed quotes; bid-only minute files are not silently given assumed asks or synthetic midpoint extrema. '
        'Other source formats require a separately documented adapter.\n\n'
        'Original decimal lexemes are preserved in original CSV files and hashed; replay uses the existing IEEE-754 Bar representation. '
        'No decimal rounding, interpolation or price repair. Off-instrument-grid precision is reported rather than silently rounded. '
        'Weekend-containing gaps are labelled; only explicit reviewed calendar windows qualify as documented holidays. Other gaps remain unexplained outage/unverified holiday. '
        'Observed market closure is not inferred from an invented holiday calendar. Full gap/coverage results are in outputs/v23/data_quality.json. '
        'D1 remains disabled because no reviewed daily-session calendar is supplied. Historical coverage was not expanded.')
    report('V23_INDEPENDENT_EVALUATION_PROTOCOL','Frozen first-evaluation protocol',
        f"Canonical experiment SHA256: `{s['experiment_sha256']}`. Specification: v23_experiment.json and v23_experiment.sha256, frozen before evaluation under this version. "
        'Initial preregistration 292c96c3bdc0a4242061f27743fbb43c111042e49842b2f8ed84f21c72a24aff preceded the first V23 replay and is retained in protocol_history/. '
        'A diagnostic-only amendment corrects zero-gross classification; no strategy, execution, exit, cost, holding or selection parameter changed. No independent data has been examined. '
        'It pins research source text (LF-normalized for checkout portability), existing strategy definitions via the pinned adapter, execution parameters, '
        'holding rules, hypotheses, metrics, costs and candidate grid. These research fingerprints do not replace or alter any operational raw source seal. '
        'The runner verifies pins before data loading/replay and writes a dataset/spec-bound inspection receipt before examining strategy results.\n\n'
        'Fixed policies: M5 holds 12 M5 bars; M15/H1/H4 hold 4 entry bars, the existing predeclared unvalidated fallback. '
        'Ordinary/protected exits and normal/stressed costs are compared; B–G confirmations use unchanged V2.2 rules. '
        'No new indicator, adaptive fit, threshold search, exit optimisation or AI/RL training occurs. Existing unapproved adaptive maps remain unavailable. '
        'Existing core.periods supplies chronological train/validation/test splits and two nonoverlapping test windows; earlier data is used for causal warm-up only. '
        'Every replay starts/ends flat, and no training position crosses into test. Previously examined final windows are not called newly untouched. '
        'First independent use requires a licensed manifest, verified provenance, full prior-exposure review, no date overlap and controlled first access. '
        'The current mode is '+s['mode']+'.')
    overlap_lines=[]
    for r in st:
        overlap_lines.append(f"- {r['pair']}/{r['timeframe']}: common-ready={r['eligible']}, BUY same={r['buy_agreement']}, SELL same={r['sell_agreement']}, "
            f"opposed={r['opposite_direction']}, joint WAIT={r['joint_abstention']}, scalp-only={r['only_a']}, trend-only={r['only_b']}, "
            f"active conditional agreement={f(r['conditional_direction_agreement'])}.")
    report('V23_STRATEGY_OVERLAP','Redundancy and distinctness',
        'Scalp and trend call the same existing signal_from_arrays dispatcher, but have separate branches. '
        'Trend permits close >= fast MA for BUY (<= for SELL); scalp requires strict > (<). '
        'They are not mathematically equivalent: at close==fast with fast>slow, trend buys and scalp waits. '
        'A deterministic counterexample executes the actual pinned functions. When both act, their directions cannot oppose under those conditions. '
        'No diversification benefit follows merely from different strategy names. Swing-trend shares the trend branch but uses a different lookback.\n\n'+
        '\n'.join(overlap_lines)+
        '\n\nThe complete 360-cell pairwise matrix covers every strategy pair/timeframe/instrument at common eligible decision timestamps, '
        'requiring available executable M5 opens, the original session rules and both feature warm-ups. '
        'Joint abstention is reported separately and excluded from active-agreement denominators. A zero-signal denominator is undefined, never perfect agreement. '
        'Previous-only timing matches are bounded to one native bar. Same-time signal reference prices coincide by construction; actual fill differences and '
        'matched trade-R correlations are separately recorded in trade_overlap.json. Correlation is undefined for tiny/constant samples. '
        'Identical signals/trades are not independent experiments. Do not delete either operational strategy in this task.')
    report('V23_TRADE_FAILURE_DIAGNOSIS','Loss evidence and limitations',
        'Every closed trade is saved with a stable dataset/spec/scenario-bound ID, price, direction, timeframe, strategy, causal entry H1/H4 context, '
        'regime/volatility, stop/target geometry, holding/exit, gross/net/risk/R/costs and source-quality information. '
        'Labels may coexist: negative gross outcome, costs overwhelming positive gross, spread > one quarter ATR, stop within one entry bar, '
        'stop inside one ATR, target >=4 ATR, entry against known higher trend, observed later context reversal, timeout/session/fold flatten, '
        'volatility/stagnation tags, breakout stop-out, protection giveback, gaps and undetermined causal contribution. '
        'They are hypotheses and observed conditions, not a causal allocation of each loss. Thresholds are preregistered diagnostics and never entry filters.\n\n'
        'A losing gross exit can reflect direction, entry timing or exit rules. A wide target being reached rarely does not by itself establish it is too distant. '
        'Stop-placement causality requires a separately frozen counterfactual; none is optimised here. '
        'OHLC cannot establish intrabar excursion ordering: the exit bar contributes only to upper MFE/MAE bounds for intrabar exits; '
        'completed held bars and known execution endpoints supply lower bounds. Opening/data gaps have unknown upper path bounds. '
        'No exact MFE/MAE is fabricated from full exit-bar extrema. Post-entry context observations are explicitly post-trade diagnostics, not selection features. '
        'Detailed counts by policy are in failure_counts.json; sums of contributing tags can exceed the number of trades.')
    report('V23_GROSS_NET_COST_ANALYSIS','Signal/exit outcomes versus execution friction',
        '\n'.join('- '+line(r) for r in fixed)+
        '\n\nGross is the existing replay midpoint-reference P/L for the realised executed policy, not a separate ideal frictionless strategy replay. '
        'Stops are anchored to executable entries and costs can change trade paths; gross expectancy is not a pure forecast-accuracy statistic. '
        'Negative gross plus negative net means transaction costs alone cannot explain the result under these exits. '
        'Positive gross but negative net identifies cost-overwhelmed realised trades, not a proven scalable edge. '
        'Spread, slippage, commission, funding and FX-conversion residual reconcile gross minus net in account currency. '
        'Turnover is converted to USD for these six USD-leg pairs, never a sum of unrelated currency units. '
        'Trade frequency and holding duration are recorded; fewer trades alone does not demonstrate better predictions.')
    report('V23_TIMEFRAME_COMPARISON','Unchanged multi-timeframe replay',
        '\n'.join('- '+line(r) for r in portfolio if not r['protection'] and not r['stress'])+
        '\n\nThese are financed six-pair fixed-trend controls with shared capital/risk constraints, not sums of standalone pair returns. '
        'Compare R expectancy, gross-positive realised outcomes, per-trade costs and holding durations alongside total P/L. '
        'Different frequencies/holding limits are part of the unchanged policy; smaller cumulative losses do not establish better predictive accuracy. '
        'confirmation_diagnosis.json groups baseline executed trades by agreeing/opposing/WAIT/missing H1/H4 context and retains their realised outcomes. '
        'It measures which baseline executed winners/losers a condition would reject, not outcomes of all unexecuted candidates. '
        'Actual confirmation replays are reported separately because altered capital and availability affect later opportunities. '
        'H4 sparse/zero warm-up cells remain data-limited; no independent timeframe conclusion is available.')
    pp_lines=[]
    for r in s['protection_pairs']:
        if r['label'] not in spec['timeframes'] or r['pair']=='PORTFOLIO' or r['stress']: continue
        pp_lines.append(f"- {r['pair']}/{r['label']}/{r['strategy']}: matched={r['matched']}, improved={r['protection_improved']}, reduced={r['protection_reduced']}, "
           f"unchanged={r['unchanged']}, mean delta R={f(r['mean_matched_R_difference'])}, activations={r['activation_observed']}/{r['protected_trades']}.")
    report('V23_PROFIT_PROTECTION_DIAGNOSIS','Original protection: matched trades',
        'The operational implementation is unchanged: 67% TP-distance trigger, causal M5 ATR14*0.5 giveback, four-pip fallback, original clamps, '
        'monotonic ratchet, BUY/SELL and JPY handling. A passive wrapper delegates the actual source and records its disposable simulation state; '
        'unit parity and unchanged replay metrics check that observation changes no decision. '
        'Activation means observed activation at completed-bar management time, not reconstructed tick activation. '
        'SL/TP can end a bar before management is called, so potential intrabar triggers are not invented. '
        'Original software close executes next open; no broker trailing-stop, breakeven or partial close.\n\n'+
        '\n'.join(pp_lines)+
        '\n\nPairs match instrument, entry time and direction within the same frozen policy/cost grid; duplicate identities reject. '
        'Unmatched trade counts are reported because protection changes capital/re-entry opportunities. '
        'Matched subsets are descriptive, not an unbiased causal estimate of total-policy improvement. '
        'Captured signed/positive price movement, bounded giveback and activation by volatility/regime/session are in protection_pairs.json and cohorts.json. '
        'No independent-data protection effect is established and no 67%/ATR parameter was tuned.')
    report('V23_STATISTICAL_ASSESSMENT','Dependence, uncertainty and multiplicity',
        'Strategies and policy variants overlap substantially; raw trade counts are not independent sample sizes. '
        'Comparisons use paired daily marked-equity P/L by fold, two-trading-day moving-block bootstrap (2,000 seeded replicates) and '
        f"Holm adjustment across {len(s['comparisons'])} comparisons. Unadjusted bootstrap intervals are illustrative, not validated simultaneous confidence intervals. "
        'Block independence, stationarity and symmetry assumptions are not verified in this short archive; no formal significance or calibrated probability is claimed. '
        'Insufficient/constant data produces undefined values. Matched trade-R correlations and PP differences remain descriptive. '
        'Unchanged folds expose positive-to-negative reversals rather than hiding them in aggregate values. '
        'No strategy is promoted based on a positive aggregate estimate or lower turnover. Independent assessment remains incomplete.')
    report('V23_TEST_RESULTS','Commands and verification',
        '`python -I -S -B data/research/trading_intelligence_v2/run.py --v23-tests` runs synthetic correctness tests. '
        '`python -I -S -B data/research/trading_intelligence_v2/run.py --v23-evaluate --exploratory` reproduces the examined-archive diagnostics. '
        'For a separately reviewed archive: `python -I -S -B data/research/trading_intelligence_v2/run.py --v23-evaluate --manifest '
        'data/research/trading_intelligence_v2/inputs/v23/approved_manifest.json`. '
        'After recorded inspection, add --allow-reproduction to label a rerun explicitly; default strict mode refuses overlap. '
        'Without a mode/manifest the runner fails clearly. All datasets remain outside Git by ignore rules; raw archives are never overwritten. '
        f"Executed scenarios={s['scenario_count']}; unchanged baseline checks={s['baseline_checks']}; trade stream SHA256={s['trades_sha256']}. "
        'Local check results and source integrity are in verification.json. Hosted feature-specific checks and full-suite comparison are verified against the published SHA after pushing. '
        'Historical full CI failures remain visible; local checks do not imply overall CI green.')
    report('V23_INTEGRATION_STATUS','Offline integration and publication boundary',
        'The importer, frozen-spec gate, existing replay, passive protection observer, post-trade diagnosis, overlap matrix and reporting are exercised by one runner command. '
        'New modules are historical_sources/import/quality/manifest, strategy_overlap, trade_diagnostics and v23_pipeline/reporting. '
        'Only run.py gains dispatch and narrower V23 output permissions; existing engine/core/timeframe/strategy code is unchanged. '
        'Original TIV2/TIV2.2 reports are read-only in V23 mode. The initial three scheduler modifications are preserved without content reads. '
        'No operational selection, sizing, stops/targets, broker risk/ownership/recovery/credentials/gates/permits or production state were modified. '
        'Existing AI/RL availability remains unavailable/abstaining; no trained fold-bound MTF artifact or causal compatibility is established, and none was loaded or trained. '
        'Research-only commit/push and dedicated CI follow the user policy; datasets/streams and unrelated work are excluded.')
    report('V23_REMAINING_LIMITATIONS','What remains unknown',
        'Missing independent dataset: all six pairs, at least 12 months (preferably 24–36), M5 or finer underlying observed bid/ask quotes, '
        'source-derived midpoint OHLC or ticks from which correct extrema can be verified, aware UTC start times, explicit completion, original archives, '
        'file hashes and complete chronology; documented legal permission for this research and derived-result publication. '
        'The strict importer currently accepts the normalized observed M5 CSV schema; provider-specific tick/M1 adapters are not silently invented. '
        'Need full prior-design/training exposure review and controlled first-access evidence, not just acquisition date. '
        'Need broker-realistic liquidity/cost/tick-order evidence, independently validated calendars and enough H4/volatility-regime observations. '
        'Exact intrabar MFE/MAE, causal stop/target/timeout contributions, future diversification benefit, active adaptive selection and independent protection impact remain unknown. '
        'Public-source download permission remains unconfirmed by user instruction; no archive acquisition or dependency installation occurred.')
    report('V23_FINAL_DECISION','Decision and next research step',
        'TIV23_RESEARCH_PARTIALLY_VERIFIED. The independently useful importer and diagnostic pipeline are implemented and tested; '
        'historical expansion and independent performance verification are incomplete. '
        'Why do the evaluated rules lose? Per-strategy gross/net evidence distinguishes negative realised gross outcomes from cost-overwhelmed positive outcomes. '
        'This does not uniquely attribute losses to predictions, stop placement or holding constraints; those causal contributions remain undetermined. '
        'Scalp/trend are almost the same MA rule except exact-equality boundaries, not proven independent information. '
        'Does H1/H4 improve per-trade expectancy or merely reduce frequency? Both per-trade and frequency/cost results are recorded, but no independent advantage is established. '
        'Does original protection improve independent outcomes? Unknown: no independent archive was acquired. '
        'Prioritise licensed independent history, deduplicated research evidence and targeted exit/cost diagnosis before adding indicators or ML. '
        'Deprioritise treating scalp/trend as separate diversification evidence and promoting sparse, stress-sensitive or fold-unstable positives. '
        'Do not delete strategies, optimise this examined archive or integrate these hypotheses into production. Stop after V2.3.')
    hashes=[f"{s['experiment_sha256']}  canonical v23_experiment.json"]
    hashes.extend(f'{h}  LF-normalized {name}' for name,h in spec['source_hashes'].items())
    if 'primary' in receipt['provenance']:
        hashes.extend(f"{q['sha256']}  {q['source_path']}" for q in receipt['provenance']['primary'].values())
    else: hashes.extend(f"{q['sha256']}  {q['path']}" for q in receipt['provenance']['files'])
    hashes.append(f"{s['trades_sha256']}  outputs/v23/trades.jsonl.gz")
    (folder/'V23_SOURCE_HASHES.txt').write_text('\n'.join(hashes)+'\n')
    for name,key in [('signal_overlap','signal_overlap'),('trade_overlap','trade_overlap'),('cost_analysis','aggregates'),
                     ('failure_counts','failures'),('protection_pairs','protection_pairs'),('confirmation_diagnosis','confirmation_diagnosis')]:
        write(folder/(name+'.json'),s[key])
    # Large cohort/full-run evidence stays in ignored outputs; compact published metrics are derived summaries.
    write(package/'outputs/v23/cohorts.json',s['cohorts'])
    write(folder/'statistics.json',s['comparisons'])
    write(folder/'result_manifest.json',dict(classification=s['classification'],mode=s['mode'],independence=s['independence'],
          scenarios=s['scenario_count'],unchanged_baseline_checks=s['baseline_checks'],
          experiment_sha256=s['experiment_sha256'],trades_sha256=s['trades_sha256']))
