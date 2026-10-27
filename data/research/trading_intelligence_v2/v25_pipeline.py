"""Fixed research policies, entire portfolio replays, no archive fitting."""
from collections import Counter,defaultdict
from dataclasses import replace
import gzip
import hashlib
import json
import math
from .core import Config, STRATEGIES, periods, ResearchRejected
from .study import acquire,write
from .adapters import Existing
from .mtf_features import prepare,Provider,Policy as EntryPolicy
from .decision_quality import Pricing
from .cost_aware_policies import POLICIES,fit_selector,Split
from .frequency_diagnostics import Frequency,counterfactual,opportunity_summary
from .v25_adapter import Evaluator
from .v25_engine import run as replay
from .v24_engine import run as frozen_replay
from .cost_ledger import reconcile
from .mtf_statistics import daily_pnl,interval,holm


def totals(trades,folds):
    n=len(trades); gross=sum(t['gross_account'] for t in trades); net=sum(t['net_account'] for t in trades)
    gains=sum(max(0,t['net_account']) for t in trades); losses=-sum(min(0,t['net_account']) for t in trades)
    turnover=sum(2*t['units'] if t['pair'].startswith('USD_') else
                 t['units']*(t['entry_price']+t['exit_price']) for t in trades)
    return dict(trades=n,gross_account=gross,net_account=net,
        gross_expectancy=gross/n if n else None,net_expectancy=net/n if n else None,
        average_r=sum(t['net_r'] for t in trades)/n if n else None,
        win_rate=sum(t['net_account']>0 for t in trades)/n if n else None,
        profit_factor=gains/losses if losses else None,costs=gross-net,
        average_cost=(gross-net)/n if n else None,
        exposure_position_seconds=sum(t['duration_seconds'] for t in trades),
        turnover_usd=turnover,
        maximum_fold_drawdown=max((x['metrics']['max_drawdown_account'] for x in folds),default=None))


def run(root,package):
    out=package/'outputs/v25'; reports=package/'reports/v25'
    out.mkdir(parents=True,exist_ok=True); reports.mkdir(parents=True,exist_ok=True)
    protocol=(package/'v25_experiment.json').read_bytes().replace(b'\r\n',b'\n')
    protocol_hash=hashlib.sha256(protocol).hexdigest()
    if protocol_hash!=(package/'v25_experiment.sha256').read_text().strip():
        raise ResearchRejected('V25_PROTOCOL_CHANGED')
    spec=json.loads(protocol)
    if spec['policies']['B']['spread_atr_max']!=POLICIES[1].spread_atr_limit or spec['policies']['C']['cost_target_max']!=POLICIES[2].cost_target_limit:
        raise ResearchRejected('THRESHOLD_PROTOCOL_MISMATCH')
    write(out/'prerun_protocol.json',dict(protocol=spec,sha256=protocol_hash,
        source_sha256_lf={p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in package.glob('*.py')}))
    data,provenance=acquire(root)
    frames,packs,coverage=prepare(data)
    raw={p:packs[p]['M5'] for p in data}; existing=Existing(root)
    folds=periods(sorted({b.t for bars in data.values() for b in bars}))
    write(out/'input_manifest.json',dict(provenance=provenance,folds=folds,coverage=coverage,
        mode='EXPLORATORY_PREVIOUSLY_EXAMINED_NO_FITTING',protocol_sha256=protocol_hash))
    pricing=(Pricing(),Pricing('HYPOTHETICAL_STRESS',.5,3),Pricing('HYPOTHETICAL_BASELINE',.2,3))
    results=[]; baselines={}; daily={}; comparisons=[]; max_residual=0; ledger_count=0
    schemas=Counter(); quality_bins=[]; trade_digest=hashlib.sha256()
    with (out/'decision_records.jsonl.gz').open('wb') as binary:
        with gzip.GzipFile(filename='',fileobj=binary,mode='wb',mtime=0) as stream:
            def emit(kind,scenario,row):
                rawrow=(json.dumps(dict(kind=kind,scenario=scenario,record=row),sort_keys=True,allow_nan=False)+'\n').encode()
                stream.write(rawrow)
                if kind in ('trade','ledger'): trade_digest.update(rawrow)
            def execute(price,tf,strategy,policy,protection=False):
                nonlocal ledger_count,max_residual
                scenario=dict(pricing=price.name,timeframe=tf,strategy=strategy,policy=policy.name,protection=protection)
                key=(price.name,tf,strategy,protection)
                closed=[]; ds=[]; frows=[]; candidate_counts=Counter(); freq_counts=Counter(); frequency_groups=Counter()
                for f in folds:
                    frequency=Frequency(); decisions=[]
                    def record(kind,row):
                        row=dict(row)  # Diagnostics must not mutate the engine's stored candidate.
                        frequency.record(kind,row)
                        if kind=='candidate':
                            decisions.append(dict(row)); candidate_counts['signals']+=1
                            candidate_counts['portfolio_accepted']+=int(row['accepted'])
                            candidate_counts['status_'+row['quality_decision']['status']]+=1
                        emit(kind,dict(scenario,fold=f['fold']),row)
                    pol=EntryPolicy(tf,strategy,spec['hold'][tf])
                    provider=Provider(frames,packs,existing,pol,None)
                    evaluator=Evaluator(policy,price,frames,packs,tf)
                    cfg=replace(Config(),slippage_pips=price.slippage_pips_side,
                        commission_per_100k_side=price.commission_account_per_100k_side)
                    r=replay(data,raw,existing,f['test'],strategy=strategy,protection=protection,config=cfg,
                        decision_provider=None if tf=='M5' else provider,decision_evaluator=evaluator,
                        record=record,cost_breakdown=True,cost_trace=True)
                    if policy.name in ('A_BASELINE','E_EXACT_VOTES'):
                        frozen=frozen_replay(data,raw,existing,f['test'],strategy=strategy,protection=protection,config=cfg,
                            decision_provider=None if tf=='M5' else Provider(frames,packs,existing,pol,None),
                            cost_breakdown=True,cost_trace=True)
                        if frozen['metrics']!=r['metrics'] or frozen['equity']!=r['equity']:
                            raise ResearchRejected('UNCHANGED_BASELINE_METRICS_FAILED')
                        for observed,old in zip(r['trades'],frozen['trades']):
                            if {k:v for k,v in observed.items() if k!='quality_decision'}!=old:
                                raise ResearchRejected('UNCHANGED_BASELINE_TRADE_FAILED')
                    for t in r['trades']:
                        l=reconcile(t); ledger_count+=1
                        max_residual=max(max_residual,abs(l['reconciliation_residual']),abs(l['gross_residual']))
                        emit('ledger',dict(scenario,fold=f['fold']),l)
                        schemas[l['exit_quote_status']]+=1
                    frows.append(dict(fold=f['fold'],metrics=r['metrics']))
                    ds.append(daily_pnl(r['equity'])); closed.extend(r['trades'])
                    freq_counts.update(frequency.counts); frequency_groups.update(frequency.groups)
                    if policy.name=='A_BASELINE':
                        baselines[key+(f['fold'],)]=(r['trades'],decisions)
                    ref,refc=baselines[key+(f['fold'],)]
                    cf=counterfactual(decisions,ref,refc)
                    for row in cf: emit('baseline_counterfactual',dict(scenario,fold=f['fold']),row)
                    for name,value in opportunity_summary(cf).items():
                        if type(value) in (int,float): candidate_counts['opportunity_'+name]+=value
                    if policy.name=='A_BASELINE' and not protection:
                        idx={(t['pair'],t['entry_time'],t['direction']):t for t in r['trades']}
                        bins=defaultdict(list)
                        for d in decisions:
                            t=idx.get((d['pair'],d['signal_time'],d['direction']))
                            if not t: continue
                            m=d['quality_decision']['metrics']
                            for field,value in [('session',d['session']),('regime',d['regime']),('volatility',d['volatility']),
                                ('spread_atr','GT_025' if m['spread_atr']>.25 else 'LE_025'),
                                ('cost_target','GT_025' if m['cost_target']>.25 else 'LE_025')]:
                                bins[(field,value)].append(t)
                        for (field,value),trades in bins.items():
                            quality_bins.append(dict(**scenario,fold=f['fold'],field=field,value=value,**totals(trades,[])))
                summary=dict(**scenario,**totals(closed,frows),folds=frows,candidates=dict(candidate_counts),
                    frequency=dict(freq_counts),frequency_groups=[dict(pair=k[0],strategy=k[1],timeframe=k[2],
                        session=k[3],regime=k[4],volatility=k[5],weekday=k[6],spread_bin=k[7],signals=v)
                        for k,v in sorted(frequency_groups.items())])
                n=candidate_counts['signals']; summary['acceptance_rate']=len(closed)/n if n else None
                summary['rejected_candidates']=n-len(closed)
                summary['by_instrument']={p:totals([t for t in closed if t['pair']==p],[]) for p in data}
                summary['by_regime']={x:totals([t for t in closed if t['regime']==x],[]) for x in sorted({t['regime'] for t in closed})}
                summary['by_session']={x:totals([t for t in closed if t['session']==x],[]) for x in sorted({t['session'] for t in closed})}
                summary['by_holding_seconds']={label:totals([t for t in closed if lo<=t['duration_seconds']<hi],[])
                    for label,lo,hi in [('LT_1H',0,3600),('1H_TO_4H',3600,14400),('GE_4H',14400,10**10)]}
                results.append(summary); daily[key+(policy.name,)]=ds
                return summary
            for price in pricing[:2]:
                for tf in spec['timeframes']:
                    for policy in POLICIES[:5]: execute(price,tf,'trend',policy)
                    execute(price,tf,'trend',POLICIES[0],True)
                    print('V25 completed',price.name,tf,flush=True)
            for tf in spec['timeframes']: execute(pricing[2],tf,'trend',POLICIES[0])
            for strategy in STRATEGIES:
                if strategy!='trend': execute(pricing[0],'M5',strategy,POLICIES[0])
    control=next(r for r in results if r['pricing']=='HYPOTHETICAL_BASELINE' and r['timeframe']=='M5')
    if control['trades']!=829 or not math.isclose(control['net_account'],-6204.7638534165835,abs_tol=1e-8):
        raise ResearchRejected('ORIGINAL_M5_CONTROL_NOT_REPRODUCED')
    for price in pricing[:2]:
        for tf in spec['timeframes']:
            key=(price.name,tf,'trend',False)
            ref=daily[key+('A_BASELINE',)]
            for policy in POLICIES[1:5]:
                alternative=daily[key+(policy.name,)]
                differences=[]
                for a,b in zip(ref,alternative):
                    if set(a)!=set(b): raise ResearchRejected('UNPAIRED_DATES')
                    differences.append([b[d]-a[d] for d in sorted(a)])
                comparisons.append(dict(pricing=price.name,timeframe=tf,policy=policy.name,
                    statistics=interval(differences,seed=25,repeats=2000)))
    holm(comparisons)
    summary=dict(classification='TIV25_COST_AWARE_RESEARCH_PARTIALLY_VERIFIED',
        protocol_sha256=protocol_hash,results=results,comparisons=comparisons,
        quality_bins=quality_bins,ledger_records=ledger_count,max_ledger_residual=max_residual,
        trade_ledger_digest=trade_digest.hexdigest(),records_sha256=hashlib.sha256((out/'decision_records.jsonl.gz').read_bytes()).hexdigest(),
        adaptive_status='ABSTAIN_NO_FRESH_INDEPENDENT_TRAINING_VALIDATION',
        combined_policy='DISABLED_NO_FRESH_VALIDATION',equivalence='E has one predicate vote per entry; no proven redundant trades removed',
        mode='EXPLORATORY_PREVIOUSLY_EXAMINED_NO_FITTING',exit_quote_status=dict(schemas))
    write(out/'full_summary.json',summary)
    write(reports/'performance.json',{k:v for k,v in summary.items() if k not in ('results','quality_bins')})
    write(reports/'policy_comparison.json',[{k:v for k,v in r.items() if k not in ('frequency_groups','folds','by_instrument','by_regime','by_session','by_holding_seconds')} for r in results])
    write(reports/'entry_quality.json',quality_bins)
    from .entry_quality_reporting import generate
    generate(package,summary)
    print('V25 complete',len(results),'scenarios,',ledger_count,'ledger records;',summary['records_sha256'],flush=True)
