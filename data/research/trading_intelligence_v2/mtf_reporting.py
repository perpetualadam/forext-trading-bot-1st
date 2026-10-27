"""Executed multi-timeframe evidence, kept separate from immutable TIV2 reports."""
import json
from .core import PAIRS,STRATEGIES,iso
from .study import write


def fmt(value): return 'UNDEFINED' if value is None else f'{value:.6f}'


def describe(row):
    m=row['metrics']
    return (f"{row['pair']} / {row['strategy']} / {row['label']}: trades={m['trades']}, "
            f"R expectancy={fmt(m['expectancy_r'])}, PF={fmt(m['profit_factor'])}, net USD={fmt(m['net_account'])}, "
            f"net return={fmt(m['net_return_fraction'])}.")


def generate(package,frozen,s):
    reports=package/'reports/mtf'
    caveat=('\n\nClassification: TIV22_MTF_RESEARCH_PARTIALLY_VERIFIED. Production NO-GO. '
            'Archived-market replay, not broker fills. This 29-day archive was already examined during TIV2; '
            'these are chronologically out-of-fit comparisons, not a fresh independently untouched dataset. '
            'No reliable profitability or operational advantage is established.\n')
    def report(name,title,text):
        (reports/(name+'.md')).write_text('# '+title+'\n\n'+text+caveat,encoding='utf-8')
    rows=s['aggregate']; ordinary=[r for r in rows if not r['protection'] and not r['stress']]
    fixed=[r for r in ordinary if r['pair']!='PORTFOLIO' and r['label'] in ('M5','M15','H1','H4')]
    conf=[r for r in ordinary if r['pair']!='PORTFOLIO' and r['label'] not in ('M5','M15','H1','H4')]
    adaptive=[r for r in rows if r['label']=='ADAPTIVE']
    examples=[]
    for pair,strategy,label in [('USD_JPY','swing_breakout','E_M15_H1'),('EUR_USD','swing_trend','H4')]:
        ex=next(r for r in ordinary if r['pair']==pair and r['strategy']==strategy and r['label']==label)
        fold_rows=[r for r in s['results'] if r['phase']=='test' and r['pair']==pair and r['label']==label
                   and r['policy'].split(':')[1]==strategy and not r['protection'] and not r['stress']]
        examples.append(describe(ex)+' Fold R values '+', '.join(fmt(r['metrics']['expectancy_r']) for r in fold_rows)+'.')
    report('MTF_ARCHITECTURE','Research architecture',
        'Baseline main '+frozen['config']['baseline_head']+'. Existing three scheduler modifications and untracked exposure documents/reports were preserved. '
        'No scheduler contents, credentials, journals, model stores, broker endpoints or operational execution modules were accessed by the runner. '
        'Original TIV2 reports and machine summary are read-only in MTF mode.\n\n'
        'Executable path: run.py --mtf-evaluate -> original study.acquire (local archive verification) -> timeframes.aggregate -> '
        'mtf_features.prepare/Provider -> unchanged shadow rule definitions through Existing -> existing engine.run M5 event phases -> '
        'mtf_selector training and validation veto -> frozen OOS comparison -> mtf_statistics -> mtf_reporting. '
        'Engine extension accepts completed signal bundles and per-position holding limits; fill ordering, FX, cash risk, USD slots, margin and exit rules are shared. '
        'Optional hook defaults preserve the original path. No parallel fill simulator, operational selector or broker management authority was added. '
        'M5-only native execution is checked against every matching original baseline test cell before results are accepted.')
    coverage=[]
    for p,tfq in frozen['aggregation'].items():
        for tf,q in tfq.items():
            if tf=='D1': coverage.append(f"- {p} D1: {q['status']}; {q['reason']}."); continue
            coverage.append(f"- {p} {tf}: {q['complete_bars']} complete bars; {len(q['unavailable'])} unavailable buckets; "
                            f"warmed 50/100 observations={q['warmed_50']}/{q['warmed_100']}.")
    report('MTF_DATA_COVERAGE','Historical coverage',
        'Six original instruments: verified local G3 archive, September 1–October 9 2026, 29 trading days. '
        'Every normalized candle matches its raw archived complete candle, and all 36 raw-page SHA256 values match the acquisition manifest. '
        'This proves archive-chain consistency, not independent provenance attestation. '
        'The September 2025–August 2026 archive exists and is quality-checked by acquire, but was previously examined and its acquisition chain is unverified here; '
        'it is excluded from performance comparisons. No new data downloads or invented market prices.\n\n'+'\n'.join(coverage)+
        '\n\nExact normalized, raw-page manifest and older archive hashes/ranges are preserved in outputs/mtf/frozen_inputs.json and data_quality.json. '
        'Dataset hashes are also included in MTF_SOURCE_HASHES.txt. Gaps are never interpolated; every excluded bucket and reason is recorded. '
        'H4/D1 evidence is explicitly data-limited; zero trades following warm-up refusal is not a successful strategy result.')
    report('MTF_TIMEFRAME_AGGREGATION','Aggregation and availability',
        'M5=300, M15=900, H1=3600, H4=14400 seconds, aligned to UTC epoch multiples. '
        'Each higher bar requires every ordered completed M5 source bar in its half-open window; duplicate/malformed/out-of-order inputs reject. '
        'Mid, bid and ask each use first open, maximum high, minimum low, last close. Missing rows and partial edge windows make a bucket unavailable; no synthetic prices. '
        'Completion equals start+duration. At 10:35 the 10:00–11:00 H1 final values are inaccessible; at exactly 11:00 the completed bar is usable '
        'under the explicitly assumed zero publication delay. Context expires after one full timeframe interval without a newer completed bar.\n\n'
        'D1 never defaults to UTC midnight. Its API requires explicit reviewed UTC session windows, convention and evidence, handles 23/24/25-hour windows, '
        'and does not independently authenticate a supplied calendar. Synthetic calendar tests prove coverage arithmetic, not New York timezone/DST calendar correctness. '
        'No validated calendar is supplied for this study, so D1 performance is disabled. '
        '[OANDA candle parameters](https://developer.oanda.com/rest-live-v20/pricing-ep/) specify daily alignment settings and a New York default; '
        '[granularity definitions](https://developer.oanda.com/rest-live-v20/instrument-df/) classify H4 as day-aligned. '
        'Our UTC H4 is a declared research alignment and is not asserted equivalent to default broker H4. '
        'No authenticated broker requests were made.\n\n'
        'Higher-timeframe features reuse warmed-up 50/100-bar MA/ATR/Bollinger formulas with the appropriate interval. '
        'A documented continuity hypothesis retains indicator history across Friday-evening to Sunday-evening/Monday-early gaps of 24–72 hours; '
        'other gaps reset warm-up. This retains observed history only, never fills prices; weekend-containing outages may still affect inference. '
        'M5 retains the original reset-on-any-gap rule unchanged.')
    report('MTF_STRATEGY_RESULTS','Independent timeframe comparisons',
        'All six existing shadow families were evaluated on all four entry timeframes. These are explicit shadow rules, not live AI/RL signals. '
        'Scalp on H1/H4 is an exploratory transfer of the existing rule, not an assertion of suitability. '
        'Identical data/test windows and base costs. Holding candidates are 4/12 entry bars for M15/H1/H4, fitted using train/validation only; '
        'M5 stays at the original 12 M5 bars. If no holding candidate passes conservative train+validation requirements, the preregistered 4-bar fallback is labelled unvalidated.\n\n'+
        '\n'.join('- '+describe(r) for r in fixed)+
        '\n\nThese are separate simulations, not a financed combined portfolio. Combined returns use two independently reset 10,000 USD fold capitals. '
        'Combined MTM drawdown is undefined; per-fold MTM drawdown is recorded in the machine summary. '
        'Signal counts/BUY-SELL distribution, average spreads, entry/exit/stop/target/holding details are in outputs/mtf/metrics.json and records.jsonl.gz.')
    report('MTF_CONFIRMATION_RESULTS','Higher-timeframe confirmation',
        'A=M5 native baseline; B=M5+M15; C=M5+H1; D=M5+H4; E=M15+H1; F=H1+H4; G=M5 entry with M15/H1/H4 context quorum two. '
        'Context uses completed 50-bar fast/slow MA difference divided by ATR: >=0.5 BUY, <=-0.5 SELL, otherwise WAIT. '
        'BUY/SELL opposition returns CONFLICT; any missing/stale/unwarmed context returns INSUFFICIENT_DATA; neutral WAIT may coexist with two agreeing directional votes. '
        'No universal directional agreement is required, but missing values never silently become agreement. Entry direction must match the context result. '
        'Raw candidate direction, context states, availability and rejection reason are recorded.\n\n'+
        '\n'.join('- '+describe(r) for r in conf)+
        '\n\nPaired daily comparisons against each matching M5 strategy/cost/protection cell are in comparisons.json. '
        'Fewer trades or lower losses does not establish a profitable trading advantage; missing-context abstention is reported separately from verified confirmation.')
    report('MTF_ADAPTIVE_SELECTION','Adaptive selection',
        'Candidate entry timeframes M5/M15/H1/H4 and existing strategy names use the same execution model. '
        'A train-only map conditions on causal M5 regime and volatility; entry-timeframe signals must be newly completed. '
        'Each context needs >=10 closed training trades and positive mean R minus 1.96*standard-error score. '
        'Highest positive score wins with deterministic policy-key tie break, not trade count or highest cash return. '
        'This penalty is a selection heuristic, not a valid significance interval. A pair-level validation replay then needs >=20 trades and a positive penalized score; '
        'otherwise its entire map abstains. Maps are immutable during test. No recent test outcomes update routing. '
        'Adaptive fits use independent timeframe candidates only; confirmation policies are separate fixed comparisons, not additionally searched.\n\n'+
        '\n'.join(f"- Fold {x['fold']}: train rules={len(x['train_rules'])}; validation-approved rules={len(x['final_rules'])}." for x in s['selections'])+
        '\n\n'+'\n'.join('- '+describe(r) for r in adaptive)+
        '\n\nActual selected context rules, holding choices and approval/fallback status are in selected_policies.json. '
        'An all-abstain model is not labelled profitable or a successful active selector.')
    report('MTF_WALK_FORWARD_RESULTS','Chronological walk-forward',
        '\n'.join(f"- Fold {f['fold']}: train {[iso(t) for t in f['train']]}; validation {[iso(t) for t in f['validation']]}; test {[iso(t) for t in f['test']]}." for f in frozen['selection_partitions'])+
        '\n\nThe original TIV2 nonoverlapping test windows remain identical across candidates. Train/validation end 48 hours before the next partition '
        '(maximum candidate holding horizon: 12 H4 bars). Every replay starts and ends flat; no training/validation trade enters a test account. '
        'The purge is deliberately conservative with daily flattening; it reduces an already short fitting sample. '
        'Causal indicator warm-up may read earlier observed history, never future labels. '
        'Training weights/context maps and validation holding choices are persisted before each test begins. '
        'The final 20% is chronologically held out of this fit, but had already been examined in TIV2; no new untouched final period is available. '
        f"All {s['baseline_equivalent_cells']} normal-cost M5 baseline cells matched original metrics exactly. "
        'Results are exploratory, not independent confirmation.')
    stress=[]
    for r in fixed:
        v=next(x for x in rows if x['label']==r['label'] and x['strategy']==r['strategy'] and x['pair']==r['pair'] and x['stress'] and not x['protection'])
        stress.append(f"- {r['pair']}/{r['strategy']}/{r['label']}: base net={fmt(r['metrics']['net_account'])}; stressed net={fmt(v['metrics']['net_account'])} USD.")
    report('MTF_TRANSACTION_COSTS','Execution and costs',
        'Shared TIV2 engine: opening quotes -> opening exits -> entries -> conservative stop-first intrabar -> closing quotes -> software-exit decisions -> MTM. '
        'Signals never fill before completion, BUY pays ask plus slippage and SELL bid minus slippage. '
        'Base/stress slippage 0.2/0.5 pip per side; commission 3 account units per 100k base units per side. '
        'Funding, gap/stop/target handling, daily 20:55 UTC flatten, one-position-per-pair, six maximum positions, two same-USD-direction slots, '
        '0.25% per-trade and 2% planned portfolio risk, leverage 20 and 80% margin capacity are unchanged research assumptions. '
        'Maximum holding varies by entry timeframe, chosen from train/validation only; this is explicitly part of the candidate policy. '
        'Currency conversion uses causal observed bid/ask, 300-second maximum age, adverse liability conversion and correct 0.01 JPY pip. '
        'Actual broker costs/latency/liquidity are unverified. Spread/slippage/commission are separately recorded in account currency; '
        'conversion residual explains nonlinear bid/ask conversion versus gross/net accounting. No raw cross-currency units are summed.\n\n'+
        '\n'.join(stress))
    pp=[]
    for r in [x for x in rows if x['pair']!='PORTFOLIO' and not x['stress'] and not x['protection']]:
        b=next(x for x in rows if x['label']==r['label'] and x['strategy']==r['strategy'] and x['pair']==r['pair'] and not x['stress'] and x['protection'])
        a,z=r['metrics']['expectancy_r'],b['metrics']['expectancy_r']
        pp.append(f"- {r['pair']}/{r['strategy']}/{r['label']}: ordinary R={fmt(a)}, protection R={fmt(z)}, delta={fmt(z-a if a is not None and z is not None else None)}.")
    report('MTF_PROFIT_PROTECTION','Original protection comparison',
        'Operational profit_protection.py is unchanged and reused via pinned definitions: 67% original TP-distance activation, '
        'ATR14*0.5 giveback, original clamps, four-pip fallback, monotonic ratchet, BUY/SELL symmetry and JPY pip handling. '
        'ATR14 remains the causal M5 management ATR used by the original replay, regardless of entry timeframe; higher-timeframe ATR sizes entries only. '
        'No exit configuration is selected using test results. Completed-bar MFE/close decisions execute at the next M5 open after SL/TP checks, '
        'not at a retrospectively favorable protection threshold. This is local software protection, not a broker trailing stop. '
        'Controlled ATR-research entry geometry matches TIV2; the separate original-default 20-pip entry benchmark remains preserved in the original reports.\n\n'+
        '\n'.join(pp))
    report('MTF_AI_RL_COMPATIBILITY','AI and RL compatibility',
        json.dumps(s['availability'],indent=2)+
        '\n\nExisting ensemble vote dictionaries can structurally carry feature keys, but no trained/versioned fold-bound multi-timeframe voter is verified. '
        'The RL tabular state key/schema has no verified MTF policy mapping or persisted artifact for this study. '
        'No model store/credentials were read. Actual empty ensemble and unverified RL return unavailable; they abstain. '
        'AI/RL incremental value and feature compatibility are unproven; no fabricated probabilities, model retraining or operational integration.')
    report('MTF_STATISTICAL_ASSESSMENT','Uncertainty and multiple comparisons',
        'Comparisons pair daily marked-equity P/L divided by initial capital on exactly matching pair/fold dates and cost/protection settings. '
        'Entry times/trade counts differ, so trade-level R samples are not falsely treated as paired independent observations. '
        'Moving-block bootstrap resamples adjacent two-trading-day blocks within each fold, with 2,000 deterministic replicates. '
        'Fewer than eight daily observations or a fold shorter than two days returns an undefined interval. '
        'These are unadjusted percentile intervals, not simultaneous family intervals; they are illustrative because short samples cannot establish block length, stationarity, exchangeability or coverage. '
        'Block sign-flip p-values likewise require unverified symmetry/block independence. '
        f"Holm adjustments include the complete {len(s['comparisons'])}-comparison family, including unavailable comparisons; "
        'no reliable advantage is claimed even if an exploratory adjusted value is small. '
        'No statistically reliable M15/H1/H4, confirmation or adaptive superiority follows from this archive. '
        'H4 warm-up gaps and low trade counts further limit interpretation. Full numerical intervals/p-values are in comparisons.json. '
        'Positive PF or a handful of wins cannot establish profitability.')
    report('MTF_TEST_RESULTS','Executable verification',
        'Commands: `python -I -S -B data/research/trading_intelligence_v2/run.py --mtf-tests`; '
        '`python -I -S -B data/research/trading_intelligence_v2/run.py --tests`; '
        '`python -I -S -B offline_exposure/run_checks.py`; '
        '`python -I -S -B data/research/trading_intelligence_v2/run.py --mtf-evaluate`. '
        'Tests use synthetic prices solely for correctness. Executed local counts/runtime results and source-integrity checks are in verification.json. '
        f"Archived replay completed {s['scenario_count']} scenarios and {s['baseline_equivalent_cells']} exact baseline-cell checks. "
        f"Deterministic gzip records SHA256 {s['records_sha256']}; frozen input SHA256 {s['frozen_inputs_sha256']}. "
        'Feature-specific hosted job runs isolated MTF tests, while existing TIV2/coordinator and historical full-suite jobs remain visible. '
        'Publication and exact-SHA CI conclusions are reported after pushing, never inferred from local passes.')
    report('MTF_INTEGRATION_STATUS','Integration boundary and portfolio controls',
        'Integrated only in run.py --mtf-evaluate/--mtf-tests, sharing the original replay via an optional completed-decision provider. '
        'Production strategy selection, broker execution, risk/ownership/recovery/gates and source seals are untouched. '
        'Fixed trend portfolios on M5/M15/H1/H4 use preregistered fallback holding limits as financed comparison controls, not validation-approved adaptive exits. '
        'Adaptive portfolio routes its frozen validated context map; it may abstain. These portfolios, unlike sums of standalone pair runs, share capital, '
        'USD-direction/risk/margin limits and deterministic alphabetical allocation. No simulated exposure is given broker authority.\n\n'+
        '\n'.join('- '+describe(r) for r in rows if r['pair']=='PORTFOLIO')+
        '\n\nNext proposal: longer provenance-attested independent data, preregistered clock/session convention and cost/tick validation before any operational MTF diagnostics or filter proposal. '
        'Do not deploy these selection/confirmation rules. No recovery implementation or R.88.')
    positive=[r for r in fixed if r['label']!='M5' and (r['metrics']['expectancy_r'] or 0)>0]
    report('MTF_FINAL_DECISION','V2.2 decision',
        'TIV22_MTF_RESEARCH_PARTIALLY_VERIFIED. Completed-candle M5/M15/H1/H4 engine, fixed confirmation policies, '
        'train/validation adaptive routing, purge, shared realistic replay and uncertainty reporting are implemented. '
        f"There are {len(positive)} higher-timeframe positive base-cost independent sample cells; none is a verified profitable strategy. "
        'Does M15/H1/H4 outperform M5? Cell-level exploratory comparisons are recorded; reliable superiority is unproven. '
        'Does H1/H4 confirmation improve M5? Effects are pair/strategy dependent and confounded by unavailable context; no dependable benefit established. '
        'Does adaptive selection outperform fixed timeframes on unseen data? No independent untouched dataset exists; abstention or a positive temporal point estimate is not such proof. '
        'Does confirmation improve original protection? The controlled ordinary/protected A/B grid is reported without choosing a winner on test data. '
        'Investigate only combinations with nontrivial normal/stress trade counts and stable fold signs on a newly preregistered archive; '
        'reject production deployment, model-confidence claims, D1 inference without a calendar, and profitability claims from tiny samples. '
        'No holding policy passed train+validation approval and both adaptive maps were empty, so no candidate is approved for advancement. '
        'For further diagnostic work, these examples show why an aggregate positive should not be promoted:\n\n'+
        '\n'.join('- '+e for e in examples)+
        '\n\nThese examples are post-hoc diagnostics, not selected policies or tuned parameters. '
        'Reject the USD_JPY M15 swing-mean-reversion positive point estimate as robust evidence because stress costs reverse its sign; '
        'reject USD_CHF H4 swing conclusions where the 100-bar warm-up yields no eligible observations. '
        'The next improvement is a preregistered longer independent dataset and clock/cost validation, not another search on this test period. '
        'Stop after V2.2; no production activation.')
    hashes=[]
    for name,h in frozen['source_hashes'].items(): hashes.append(f'{h}  {name}')
    hashes.append(f"{frozen['config_sha256']}  mtf_config.json")
    hashes.append(f"{frozen['baseline_summary_sha256']}  original reports/study_summary.json (preserved)")
    for path,record in frozen['reused_sources'].items(): hashes.append(f"{record['raw_sha256']}  {path}")
    for p,q in frozen['data_quality']['primary'].items(): hashes.append(f"{q['sha256']}  {q['source_path']}")
    hashes.append(f"{s['records_sha256']}  outputs/mtf/records.jsonl.gz")
    (reports/'MTF_SOURCE_HASHES.txt').write_text('\n'.join(hashes)+'\n')
    write(reports/'selected_policies.json',s['selections']); write(reports/'comparisons.json',s['comparisons'])
    keys=('trades','win_rate','expectancy_r','profit_factor','net_return_fraction','net_account','max_drawdown_fraction',
          'average_win','average_loss','average_duration_seconds','spread_cost_account','slippage_cost_account')
    slim=[{**{k:v for k,v in r.items() if k!='metrics'},'metrics':{k:r['metrics'].get(k) for k in keys}} for r in rows]
    fold_metrics=[dict(fold=r['fold'],label=r['label'],pair=r['pair'],policy=r['policy'],protection=r['protection'],stress=r['stress'],
                       signal_count=r['signal_count'],metrics={k:r['metrics'].get(k) for k in keys},
                       peak_entry_allocation=r['metrics']['peak_entry_allocation'])
                  for r in s['results'] if r['phase']=='test']
    write(reports/'metrics_summary.json',dict(classification=s['classification'],aggregate=slim,
        fold_results=fold_metrics,scenario_count=s['scenario_count'],baseline_equivalent_cells=s['baseline_equivalent_cells'],
        records_sha256=s['records_sha256'],frozen_inputs_sha256=s['frozen_inputs_sha256']))
