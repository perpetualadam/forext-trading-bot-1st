"""Cost verification against previously examined data; never broker execution."""
from .study import acquire, write
from .core import Config, periods, ResearchRejected
from .mtf_features import prepare
from .adapters import Existing
from .v24_engine import run as replay


def run(root, package):
    out = package/'outputs/v24'
    out.mkdir(parents=True, exist_ok=True)
    data, provenance = acquire(root)
    frames, packs, coverage = prepare(data)
    raw = {p: packs[p]['M5'] for p in data}
    folds = periods(sorted({b.t for bars in data.values() for b in bars}))
    existing = Existing(root)
    from .engine import run as frozen_replay
    results = [frozen_replay(data, raw, existing, f['test'], cost_breakdown=True) for f in folds]
    baseline = dict(trades=sum(len(r['trades']) for r in results),
                    gross=sum(r['metrics']['gross_account'] for r in results),
                    net=sum(r['metrics']['net_account'] for r in results),
                    spread=sum(t['spread_cost_account'] for r in results for t in r['trades']),
                    slippage=sum(t['slippage_cost_account'] for r in results for t in r['trades']),
                    commission=sum(t['commission_account'] for r in results for t in r['trades']),
                    funding=sum(t['funding_assumption_account'] for r in results for t in r['trades']),
                    conversion_residual=sum(t['conversion_cost_residual'] for r in results for t in r['trades']))
    import math
    if baseline['trades'] != 829 or not math.isclose(baseline['gross'], -108.118650558, abs_tol=1e-6) or not math.isclose(baseline['net'], -6204.763853417, abs_tol=1e-6):
        raise ResearchRejected('M5_BASELINE_NOT_REPRODUCED')
    if not (out/'initial_baseline.json').exists():
        write(out/'initial_baseline.json', dict(baseline=baseline, folds=folds, provenance=provenance))
    print(baseline, flush=True)

    from dataclasses import replace
    import gzip
    import hashlib
    import json
    from .core import STRATEGIES
    from .mtf_features import Policy, Provider
    from .cost_ledger import reconcile
    scenarios = {
        'A_MID_THEORETICAL': (0, 0, 0),
        'B_OBSERVED_ONLY': (1, 0, 0),
        'C_OBSERVED_SLIP_02': (1, .2, 0),
        'D_HYPOTHETICAL_3_PER_100K_SIDE': (1, .2, 3),
        'E_STRESS_2X_SPREAD_1_PIP_SIDE': (2, 1, 3),
        'F_US_CORE_7_COMPARATOR_NOT_UK_PLAN': (1, .2, 7),
    }
    write(out/'protocol.json',dict(scenarios=scenarios,folds=folds,account='USD',
        prior_data='PREVIOUSLY_EXAMINED_29_TRADING_DAYS',
        geometry='UNCHANGED_ATR_RESEARCH',
        scope='All six strategies M5 portfolio; trend portfolio M15 H1 H4; two unchanged test folds',
        source_sha256_lf={p.name:hashlib.sha256(p.read_text().replace('\r\n','\n').encode()).hexdigest()
                          for p in package.glob('*.py')}))
    all_results=[]; ledger_samples=[]; bridge=[]; total_ledgers=0; max_residual=0
    policies=[Policy('M5',name,12) for name in STRATEGIES]
    policies += [Policy(tf,'trend',4) for tf in ('M15','H1','H4')]
    with (out/'cost_ledger.jsonl.gz').open('wb') as binary:
        with gzip.GzipFile(filename='',fileobj=binary,mode='wb',mtime=0) as stream:
            for label,(factor,slip,fee) in scenarios.items():
                transformed={p:[replace(b, **{key:(getattr(b,bid)+getattr(b,ask))/2
                    + sign*factor*(getattr(b,ask)-getattr(b,bid))/2
                    for bid,ask in [('bo','ao'),('bh','ah'),('bl','al'),('bc','ac')]
                    for key,sign in [(bid,-1),(ask,1)]}) for b in bars] for p,bars in data.items()}
                if factor == 1:
                    transformed = data  # Preserve source floats exactly, no reconstructive rounding.
                for pol in policies:
                    rows=[]; marks=[]; fold_summary=[]
                    for f in folds:
                        provider=Provider(frames,packs,existing,pol,None)
                        cfg=replace(Config(),slippage_pips=slip,commission_per_100k_side=fee)
                        r=replay(transformed,raw,existing,f['test'],strategy=pol.strategy,
                            config=cfg,decision_provider=None if pol.entry=='M5' else provider,
                            cost_breakdown=True,cost_trace=True)
                        if label.startswith('D_') and pol.entry=='M5' and pol.strategy=='trend':
                            original=results[f['fold']-1]
                            if r['metrics']!=original['metrics']: raise ResearchRejected('trace_changed_baseline_metrics')
                            if r['equity']!=original['equity']: raise ResearchRejected('trace_changed_equity')
                            for a,b in zip(r['trades'],original['trades']):
                                if {k:v for k,v in a.items() if k!='cost_trace'}!=b:
                                    raise ResearchRejected('trace_changed_baseline_trade')
                        sums={k:0.0 for k in ('gross_account','net_account','spread_attribution_account',
                            'slippage_attribution_account','commission_account','financing_account')}
                        for i,t in enumerate(r['trades']):
                            ledger=reconcile(t)
                            total_ledgers+=1
                            max_residual=max(max_residual,abs(ledger['reconciliation_residual']),abs(ledger['gross_residual']))
                            ledger.update(scenario=label,fold=f['fold'],strategy=pol.strategy,timeframe=pol.entry)
                            ledger['trade_id']=hashlib.sha256(json.dumps([label,f['fold'],pol.key,i,ledger['trade_id']]).encode()).hexdigest()
                            stream.write((json.dumps(ledger,sort_keys=True,allow_nan=False)+'\n').encode())
                            if label.startswith('D_') and pol.entry=='M5' and pol.strategy=='trend':
                                bridge.append(ledger)
                                if not any(x['instrument']==ledger['instrument'] and x['direction']==ledger['direction'] for x in ledger_samples):
                                    ledger_samples.append(ledger)
                            for k in sums: sums[k]+=ledger[k]
                        n=len(r['trades'])
                        fold_summary.append(dict(fold=f['fold'],trades=n,**sums,
                            max_drawdown_account=r['metrics']['max_drawdown_account'],
                            rejected=r['metrics']['rejections']))
                        rows.extend(r['trades']); marks.append(r['metrics']['max_drawdown_account'])
                    n=len(rows); gross=sum(t['gross_account'] for t in rows); net=sum(t['net_account'] for t in rows)
                    gains=sum(max(0,t['net_account']) for t in rows); losses=-sum(min(0,t['net_account']) for t in rows)
                    identities=[(t['pair'],t['direction'],t['entry_time'],t['exit_time'],t['exit_reason']) for t in rows]
                    all_results.append(dict(scenario=label,strategy=pol.strategy,timeframe=pol.entry,
                        trades=n,gross_account=gross,net_account=net,gross_expectancy=gross/n if n else None,
                        net_expectancy=net/n if n else None,cost_per_trade=(gross-net)/n if n else None,
                        total_cost=gross-net,profit_factor=gains/losses if losses else None,
                        max_drawdown_by_fold=marks,maximum_fold_drawdown=max(marks),
                        break_even_cost_per_trade=gross/n if n else None,
                        break_even_interpretation='Fixed-path average allowable debit; negative means no nonnegative cost is viable',
                        spread_per_trade=sum(f['spread_attribution_account'] for f in fold_summary)/n if n else None,
                        slippage_per_trade=sum(f['slippage_attribution_account'] for f in fold_summary)/n if n else None,
                        commission_per_trade=sum(f['commission_account'] for f in fold_summary)/n if n else None,
                        path_sha256=hashlib.sha256(json.dumps(identities).encode()).hexdigest(),folds=fold_summary))
                print('V24 completed',label,flush=True)
    reference={(r['strategy'],r['timeframe']):r for r in all_results if r['scenario'].startswith('D_')}
    for r in all_results:
        ref=reference[r['strategy'],r['timeframe']]
        r['entry_exit_path_matches_baseline']=r['path_sha256']==ref['path_sha256']
        r['financial_comparison']='FULL_REPLAY_INCLUDING_RESIZING_NOT_ADDITIVE_COUNTERFACTUAL'
    reconciliation=dict(baseline=baseline,ledger_records=total_ledgers,maximum_residual_account=max_residual,
        waterfall={k:sum(t[k] for t in bridge) for k in ('gross_account','spread_attribution_account',
            'slippage_attribution_account','commission_account','financing_account','net_account')},
        ledger_sha256=hashlib.sha256((out/'cost_ledger.jsonl.gz').read_bytes()).hexdigest())
    write(out/'reconciliation.json',reconciliation)
    write(out/'sensitivity.json',all_results)
    reports=package/'reports/v24'; reports.mkdir(parents=True,exist_ok=True)
    write(reports/'reconciliation.json',reconciliation)
    write(reports/'sensitivity.json',all_results)
    write(reports/'cost_ledger_examples.json',ledger_samples)
    from .v24_reporting import generate
    generate(package,reconciliation,all_results)
    print('V24 ledger records',total_ledgers,'max residual',max_residual,flush=True)
