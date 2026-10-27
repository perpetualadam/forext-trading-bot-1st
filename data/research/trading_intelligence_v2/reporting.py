"""Render substantive research reports from executed results, never templates of claims."""
import json
from .core import PAIRS, STRATEGIES, iso
from .study import write


def number(x): return 'UNDEFINED' if x is None else f'{x:.6f}'


def line(r):
    m=r['metrics']
    return (f"{r['pair']} / {r['strategy']} / {r['policy']} / protection={r['protection']} / stress={r['stress']}: "
            f"n={m['trades']}, expectancy R={number(m['expectancy_r'])}, net USD={number(m['net_account'])}, "
            f"PF={number(m['profit_factor'])}.")


def generate(package,summary,frozen):
    reports=package/'reports'
    common=('\n\nStatus: TIV2_OFFLINE_RESEARCH_PARTIALLY_VERIFIED. Production remains NO-GO. '
            'All results are hypothetical archived-data replay, never broker fills. '
            'The 29-day archive and short OOS windows do not establish statistical significance or live profitability.\n')
    def report(name,title,text):
        (reports/(name+'.md')).write_text('# '+title+'\n\n'+text+common,encoding='utf-8')
    agg=summary['aggregate']
    baseline=[r for r in agg if r['pair']!='PORTFOLIO' and r['policy']=='baseline' and not r['protection']]
    positive=[r for r in baseline if (r['metrics']['expectancy_r'] or 0)>0]
    filtered_positive=[r for r in agg if r['pair']!='PORTFOLIO' and r['policy']!='baseline' and not r['protection'] and (r['metrics']['expectancy_r'] or 0)>0]
    quality=frozen['data_quality']
    original=summary['original_sl_tp_benchmark']['aggregate']
    original_base=[r for r in original if not r['protection']]
    original_positive=[r for r in original_base if (r['metrics']['expectancy_r'] or 0)>0]
    regime_pairs=[]
    for a in baseline:
        b=next(r for r in agg if r['pair']==a['pair'] and r['strategy']==a['strategy'] and r['policy']=='spread' and not r['protection'])
        c=next(r for r in agg if r['pair']==a['pair'] and r['strategy']==a['strategy'] and r['policy']=='regime_spread' and not r['protection'])
        if b['metrics']['expectancy_r'] is not None and c['metrics']['expectancy_r'] is not None:
            regime_pairs.append(c['metrics']['expectancy_r']-b['metrics']['expectancy_r'])
    report('TIV2_ARCHITECTURE','Offline architecture',
        'Baseline main at '+frozen['configuration']['baseline_head']+'. Three pre-existing scheduler files were modified and preserved without content access. '
        'Existing untracked exposure proposal/reports were excluded. No operational sources changed.\n\n'
        'Reachable production decision chain: bot_loop._evaluate_impl -> strategy_meta.select_strategy -> compute_indicators -> '
        'nn_pred/sequence features -> AIEnsemble.vote -> RL entry gate -> risk checks/OrderIntent -> execution adapter. '
        'The six strategy names select families and parameters; direction in that path is AI/RL dependent. '
        'strategy_meta legacy weighted selection is stochastic; this study uses the existing shadow hybrid_family and deterministic select_name_argmax, '
        'with train-only weights. That is a research router comparison, not a faithful replay of the stochastic operational selector.\n\n'
        'Integrated research call path: run.py isolation -> study.acquire archive verification -> core.features causal arrays -> '
        'adapters.Existing pinned source definitions -> engine.run chronological replay -> training/validation selection -> frozen OOS A/B -> reporting.generate. '
        'The package uses stdlib and does not import production module bodies. AST extraction reuses reviewed function dependencies; '
        'module-global configuration is replaced with documented fixed research defaults. No model artifacts or account state loaded. '
        'Existing backtest.py imports operational config/broker paths and was not invoked. Existing shadow and adaptive_ensemble archives supply reusable rules/data, '
        'not live ownership or recovery authority. Forecast nn_pred has a noisy live-price fallback and a sequence backtest mode; neither is a validated fold-bound forecast model here.')
    qlines=[]
    for p,q in quality['primary'].items():
        qlines.append(f"- {p}: {q['rows']} rows, {q['start']} to {q['end']}; gaps={len(q['gaps'])}; invalid={len(q['errors'])}; "
                      f"off-precision bid/ask values={q['off_precision_values']}; SHA256 {q['sha256']}; {q['raw_link']}.")
    report('TIV2_DATA_QUALITY','Historical data quality',
        'Primary data: existing adaptive_ensemble/g3 OANDA candle archive. Read locally only; no acquisition requests. '
        f"Manifest SHA256 {quality['manifest_sha256']}. All {quality['raw_pages']} raw-page hashes and every normalized complete candle value matched. "
        'This verifies internal chain consistency, not independent broker attestation or untouched research history. '
        'Manifest itself labels duration INSUFFICIENT_INDEPENDENT_DURATION and does not promote validation readiness.\n\n'+'\n'.join(qlines)+
        '\n\nUTC-aware timestamps, M5 alignment, strict order, duplicate rejection, completed flags, positive finite OHLC, high/low consistency, '
        'uncrossed observed bid/ask, instrument precision (JPY three decimals/0.01 pip, others five/0.0001) checked. '
        'Spread is observed, not interpolated. Incomplete rows are explicitly excluded and logged; invalid rows abort. '
        'No sorting, interpolation or silent price repairs. Gap lists are in outputs/data_quality.json; warm-up resets after every gap. '
        'The prior September 2025–August 2026 six-pair archive was also validated for quality, but excluded from profitability evidence because previously examined '
        'and its acquisition chain was not reverified. Exact older hashes and ranges are in the compact study_summary.json and frozen_inputs.json.')
    report('TIV2_STRATEGY_INVENTORY','Strategy inventory',
        'Evaluated actual shadow.signals.signal_from_arrays definitions for scalp, trend, mean_reversion, swing_trend, swing_mean_reversion and swing_breakout. '
        'Trend/scalp use MA direction and price confirmation; mean reversion uses outer Bollinger bands; breakout uses prior 20 highs/lows excluding the current bar. '
        'Momentum and MA strategies overlap and are not independent evidence. There is no additional standalone strategy implementation invented here. '
        'These are existing shadow rules, explicitly distinct from live AI directions. All six pairs were replayed separately before portfolio runs. '
        'The quantitative AI stub is retired/unavailable, not replaced with fake directional votes. '
        'Profit protection uses the original operational function definitions unchanged; AI and RL use pure extracted abstention paths. '
        'Source definitions and AST/raw hashes: reuse_manifest.json and study_summary.json. Indicator adapter implements warmed-up fixed MA/ATR/BB formulas '
        'from indicators.py without importing pandas; operational early adaptive-length warm-up is deliberately not reproduced.')
    report('TIV2_MARKET_REGIMES','Causal regime evaluation',
        'Fixed before evaluation: abs(MAfast-MAslow)/ATR >=0.5 TREND, <=0.15 RANGE, otherwise UNCERTAIN. '
        'Mean-reversion entries require RANGE; others TREND. Spread-only and regime+spread policies require prior completed-bar spread/ATR <=0.25. '
        'ATR relative to the past 250 valid ATR median gives HIGH >1.5x, LOW <0.67x, otherwise NORMAL; '
        'five-bar price change >=1 ATR tags STRONG momentum. These latter tags are diagnostics, not extra fitted filters. '
        'Breakout tags are the existing causal breakout signal; no ADX or redundant feature search. '
        'No full-sample fitting; uncertain regimes abstain. Thresholds are fixed hypotheses, not validated production parameters.\n\n'+
        '\n'.join('- '+line(r) for r in agg if r['pair']=='PORTFOLIO' and not r['stress'])+
        f'\n\nAdding regime to spread filtering increases sample R expectancy in {sum(x>0 for x in regime_pairs)} of {len(regime_pairs)} comparable pair/strategy cells; '
        'this is an exploratory cell count with dependent trades, not a significance claim. '
        'Per-pair comparisons are in study_summary.json; matched accepted/rejected baseline trade outcomes are in outputs/metrics.json. '
        'Actual filtered replays change trade availability and capital, so matched-entry outcomes are reported separately; rejected signals are not assigned fabricated trade outcomes. '
        'No claim that this beats the actual live selector is supported by shadow-rule results.')
    report('TIV2_BACKTEST_METHODOLOGY','Replay methodology',
        'All signal features use bar i-1, available at open i. Phases: current opening quotes, opening exits, entries, stop-first intrabar exits, '
        'closing quotes, time/protection decisions, MTM. Intrabar profits cannot fund earlier opening entries. '
        'BUY enters ask plus slippage and exits bid minus slippage; SELL reverses. Both stop and target touched => stop first. '
        'Adverse stop gaps fill at opening executable quote; favorable target gaps get no improvement. Missing-interval held exposure gets a conservative stop/open-worse fill; '
        'unpriceable conversions or end exposure invalidate the run. This conservative gap rule is a model assumption, not a known broker fill. '
        'Sizing includes worst planned stop loss, exit slippage and roundtrip commissions in account currency; gap losses can exceed planned risk.\n\n'
        'USD research account 10,000; per-trade risk 0.25%, total planned risk 2%, six positions, two same-USD-direction slots, leverage 20, '
        '80% margin capacity, stop=max(2 ATR,4 pips), target=2R, max hold 12 M5 bars. Daily flatten at 20:55 UTC and no subsequent entries until UTC midnight. '
        'The ATR geometry is a declared research assumption. A separate original-default geometry benchmark reuses trading.sl_tp_distance_for_entry with cleared environment '
        '(USE_ATR_STOPS defaults false, SL_FALLBACK_PIPS=20, TP_RISK_REWARD=2). This is a source-default benchmark, not verification of current production settings. '
        'It was added after the initial study to satisfy the original-geometry comparison, without fitting parameters; those comparisons remain exploratory. '
        'Base slippage 0.2 pip per side; stress 0.5. Commission 3 account units/100k per side; conservative 1bp notional/day funding on date crossing. '
        'These are declared assumptions, not retrieved broker terms. Fixed UTC sessions are descriptive and not DST-aware exchange calendars. '
        'FX conversion uses causal observed bid/ask graph: assets liquidated at bid/ask inverse and liabilities valued at adverse side. '
        'Quotes older than 300 seconds or from the future cannot be used. USD_JPY pip is 0.01; raw cross-currency units never summed.\n\n'
        'Metrics: account-currency and R expectancy, PF, net/gross/cost, win/loss, exposure duration, consecutive losses, MTM drawdown and daily Sharpe/Sortino only with >=20 observations. '
        'Aggregated separate-fold returns divide by two independent 10,000 capitals; aggregate MTM drawdown/Sharpe undefined. Per-run MTM metrics remain available. '
        'OHLC cannot reveal tick sequence, liquidity or fill latency; this simulator makes explicit assumptions, not a broker execution guarantee.')
    foldtext='\n'.join(f"- Fold {f['fold']}: train {[iso(t) for t in f['train']]}; validation {[iso(t) for t in f['validation']]}; test {[iso(t) for t in f['test']]}." for f in summary['folds'])
    report('TIV2_WALK_FORWARD_RESULTS','Walk-forward results',foldtext+
        '\n\nHalf-open chronological intervals. Two expanding training windows; nonoverlapping OOS tests; fold-one test may become fold-two validation only after its time. '
        'Full causal history is permitted for warm-up, but signals/fits never see future rows. Each simulation starts flat and closes at its partition boundary. '
        'Selection requires >=20 train and >=20 validation trades and positive R expectancy in both; largest validation R expectancy wins with alphabetical ties. '
        'No eligible strategy => abstain. Train-only nonnegative expectancy weights feed the shadow hybrid. Frozen selections are persisted before each OOS run. '
        'Final 20% was not used to tune parameters in this study; this is not an assertion that the archive was never examined by prior researchers.\n\n'+
        '\n'.join(f"- Fold {s['fold']} {s['pair']}: selected {s['selected'] or 'ABSTAIN'}." for s in summary['selection']))
    report('TIV2_STRATEGY_COMPARISON','Strategy comparison after costs',
        'Combined nonoverlapping OOS ATR-research geometry baseline point estimates (no protection):\n\n'+'\n'.join('- '+line(r) for r in baseline)+
        '\n\nPositive point-estimate combinations: '+(', '.join(r['pair']+'/'+r['strategy'] for r in positive) or 'none')+
        '. Positive filtered point estimates (exploratory, not selected using test results):\n\n'+'\n'.join('- '+line(r) for r in filtered_positive)+
        '\n\nThese do not establish profitability: short sample, dependent strategies/pairs, multiple comparisons, assumed costs and uncertain archive independence. '
        'Compact per-fold and per-policy metrics are in study_summary.json; full groupings by regime/session/pair are in outputs/metrics.json. No superiority claim for any strategy is warranted.\n\n'
        'Separate original source-default SL/TP benchmark (20-pip stop / 40-pip target), unchanged source function:\n\n'+
        '\n'.join(f"- {r['pair']}/{r['strategy']}: n={r['metrics']['trades']}, R={number(r['metrics']['expectancy_r'])}, net USD={number(r['metrics']['net_account'])}." for r in original_base)+
        '\n\nOriginal-default positive sample combinations: '+(', '.join(r['pair']+'/'+r['strategy'] for r in original_positive) or 'none')+'. No reliable profitability claim follows.')
    report('TIV2_AI_RL_ASSESSMENT','AI and RL ablations',
        json.dumps(summary['availability'],indent=2)+
        '\n\nQuantitative shadow alone and +regime have executed replays. +AI, +RL and combined strict gates all abstain (zero approved trades; expectancy undefined), '
        'because no fold-bound trained, verified, calibrated model was supplied. The actual empty AI ensemble returns no_voters, retired quant stub returns quant_stub_removed, '
        'and RLAgent without persisted_ok returns UNAVAILABLE. This does not prove no production model exists: production stores and credentials were intentionally not accessed. '
        'Persistence code exists in decision_repair/rl_store.py; existence of its schema does not establish this study has a trained leakage-free policy. '
        'No external voter/API calls, model training, invented predictions or confidence calibration claims. Measurable incremental AI/RL value: not established.')
    pp=[]
    original_pp=[]
    for a in original_base:
        b=next(r for r in original if r['pair']==a['pair'] and r['strategy']==a['strategy'] and r['protection'])
        x,y=a['metrics']['expectancy_r'],b['metrics']['expectancy_r']
        original_pp.append(f"- {a['pair']}/{a['strategy']}: A R={number(x)}, B R={number(y)}, B-A={number(y-x if x is not None and y is not None else None)}; nA={a['metrics']['trades']}, nB={b['metrics']['trades']}.")
    for a in baseline:
        b=next(r for r in agg if r['pair']==a['pair'] and r['strategy']==a['strategy'] and r['policy']=='baseline' and r['protection'])
        x,y=a['metrics']['expectancy_r'],b['metrics']['expectancy_r']
        pp.append(f"- {a['pair']}/{a['strategy']}: A R={number(x)}, B R={number(y)}, B-A={number(y-x if x is not None and y is not None else None)}; nA={a['metrics']['trades']}, nB={b['metrics']['trades']}.")
    report('TIV2_PROFIT_PROTECTION_COMPARISON','Original profit protection A/B',
        'A: original source-default SL/TP geometry (20/40 pips). B: same geometry with unchanged original 67% activation, ATR14*0.5 giveback (original clamps 0.5..30 pips), '
        '4-pip missing-ATR fallback and monotonic ratchet, BUY/SELL and JPY-aware. No alternative C is justified by this short sample. '
        'Completed-bar favorable extreme updates MFE; original protection compares executable close; requested software exit executes at the next open. '
        'SL/TP takes precedence. No retroactive favorable threshold fill and no broker trailing amendment. '
        'A completed-bar simulation cannot establish live monitoring equivalence.\n\n'+'\n'.join(original_pp)+
        '\n\nSecondary controlled ATR-research geometry A/B (not the default operational geometry):\n\n'+'\n'.join(pp))
    report('TIV2_PORTFOLIO_RISK','Portfolio risk',
        '\n'.join('- '+line(r) for r in agg if r['pair']=='PORTFOLIO')+
        '\n\nPortfolio replay orders simultaneous candidates alphabetically for reproducibility; this introduces a declared allocation priority. '
        'Independent pair returns are never simply summed to represent a financed portfolio. USD directions counted separately; opposing directions do not net away gross risk. '
        'Conservative bid/ask account conversions, cash-risk caps, maximum slots, margin and MTM drawdown enforced. '
        'USD slot concentration is a coarse correlation control, not a fitted covariance/stress model. Broker observations, quarantine and unknown live exposure are absent, '
        'and never treated as simulated managed positions. No live portfolio risk totals inferred. Concentration diagnostics by pair/regime/session and MTM drawdown per run are recorded.')
    report('TIV2_TEST_RESULTS','Verification commands and evidence',
        'Run synthetic contract tests: `python -I -S -B data/research/trading_intelligence_v2/run.py --tests`. '
        'Run full archived study: `python -I -S -B data/research/trading_intelligence_v2/run.py --evaluate`. '
        'Run existing coordinator: `python -I -S -B offline_exposure/run_checks.py`. '
        'Exact executed local test results are recorded in verification.json after checks; synthetic returns are never profit evidence. '
        'Hosted feature-specific CI runs the isolated synthetic suite; it does not download or commit datasets. '
        'Existing full CI historical failures remain visible; local checks do not imply overall CI green.\n\n'
        f"Executed study scenarios={len(summary['results'])+len(summary['original_sl_tp_benchmark']['results'])}; deterministic record SHA256 {summary['records_sha256']}; "
        f"frozen-input SHA256 {summary['frozen_inputs_sha256']}. Full compressed candidate/trade records and per-fold frozen selections are generated under ignored outputs/. "
        'Reproduction requires the existing archive and unchanged pinned definitions. Committed compact metrics retain all scenario summaries but no market dataset.')
    report('TIV2_REMAINING_RISKS','Remaining evidence gaps',
        '29 trading days is insufficient independent duration, with only approximately 10 OOS days total. Archive hash consistency is not independent provenance attestation. '
        'Prior inspection and multiple-comparison risks remain. Shadow signals do not reproduce AI/RL production direction. '
        'No trained fold-bound AI/RL artifact, calibration or leakage audit exists for these ablations. '
        'OHLC intrabar ordering, latency, liquidity, slippage tails, contract-specific margin/funding and holiday calendars remain approximate. '
        'No statistical significance, tick-level PP equivalence, cross-process coordinator safety or production fill quality is established. '
        'Regime and spread thresholds need preregistered longer independent evaluation; no parameter was tuned to final OOS results here. '
        'The wrapper seal mismatch remains separate and unchanged.')
    report('TIV2_INTEGRATION_PLAN','Later operational integration proposal',
        'Current integration is research-only through run.py --evaluate. No bot_loop, strategy_meta, risk gate, broker adapter, profit_protection or ownership changes. '
        'Next proposed improvement is an observation-only decision-quality diagnostic using the same causal spread/ATR and regime tags, '
        'after a longer preregistered independent study. This could attach reasons to candidates before OrderIntent creation, without granting broker authority. '
        'Do not activate selection/filter changes based on this report. First obtain longer provenance-attested data, broker-cost/FX validation, '
        'tick replay for protection, calibrated fold-bound model artifacts if applicable, and targeted operational integration approval/tests. '
        'Operational R.86 wrapper reconciliation requires its own source/seal review. No recovery implementation or R.88 begun.')
    report('TIV2_FINAL_DECISION','Research decision',
        'TIV2_OFFLINE_RESEARCH_PARTIALLY_VERIFIED. Integrated executable offline pipeline and deterministic correctness tests implemented. '
        'Which strategies demonstrate positive OOS expectancy? No unfiltered ATR-research geometry pair/strategy combination is positive across combined OOS tests. '
        'The original source-default geometry has '+str(len(original_positive))+' positive sample combinations, individually listed in TIV2_STRATEGY_COMPARISON. '
        'Exploratory filtered positive point estimates are listed in TIV2_STRATEGY_COMPARISON; none establishes a reliable profitable edge. '
        'Does regime filtering improve the existing selector? Shadow-rule policy comparisons are measurable, but the actual AI/RL selector was not replayed; operational improvement is unproven. '
        'Do AI/RL add value? Not established; unavailable models abstain. '
        'Does original protection improve expectancy? Pair/strategy A/B deltas are mixed or sample-dependent as recorded; no universal benefit is assumed. '
        'Suitable now: offline validators, causal diagnostics and replay instrumentation. Production filters, router changes and model gates remain research-only. '
        'No trading activation is authorised or performed.')
    # Compact committed evidence: full per-regime/session and matched-trade audit remain in ignored outputs/metrics.json.
    compact={k:v for k,v in summary.items() if k not in ('results','filter_audit','selection')}
    compact['results']=[{k:v for k,v in r.items() if k not in ('by_regime','by_session','by_pair')} for r in summary['results']]
    compact['selection']=[dict(fold=s['fold'],pair=s['pair'],selected=s['selected'],weights=s['weights']) for s in summary['selection']]
    write(reports/'study_summary.json',dict(summary=compact,inputs=frozen))
