"""Complete multi-timeframe offline pipeline, sharing the existing M5 fill engine."""
from collections import Counter,defaultdict
from dataclasses import asdict,replace
import gzip
import hashlib
import json
import math
import statistics

from .core import PAIRS,STRATEGIES,Config,ResearchRejected,periods
from .adapters import Existing
from .engine import run as replay,metrics
from .study import acquire,digest,write,grouped
from .mtf_features import Policy,Provider,prepare
from .mtf_selector import fit,select_hold,validate_fit
from .mtf_statistics import daily_pnl,interval,holm


def purged(fold,seconds):
    if type(seconds) is not int or seconds<0: raise ResearchRejected('invalid_purge')
    f=dict(fold)
    for phase in ('train','validation'):
        start,end=f[phase]
        if start>=end-seconds: raise ResearchRejected('purge_exhausted_partition')
        f[phase]=(start,end-seconds)
    return f


def summarize(trades,initial=20000):
    m=metrics(trades,initial=initial)
    m.update(spread_cost_account=sum(t.get('spread_cost_account',0) for t in trades),
             slippage_cost_account=sum(t.get('slippage_cost_account',0) for t in trades),
             commission_account=sum(t.get('commission_account',0) for t in trades),
             average_spread=statistics.fmean(t['spread_reference'] for t in trades) if trades else None,
             average_stop_distance=statistics.fmean(t['stop_distance'] for t in trades) if trades else None,
             average_target_distance=statistics.fmean(t['target_distance'] for t in trades) if trades else None,
             buy_trades=sum(t['direction']=='BUY' for t in trades),sell_trades=sum(t['direction']=='SELL' for t in trades))
    return m


def run(root,package):
    out=package/'outputs/mtf'; reports=package/'reports/mtf'
    out.mkdir(exist_ok=True); reports.mkdir(exist_ok=True)
    config=json.loads((package/'mtf_config.json').read_text())
    data,quality=acquire(root)
    existing=Existing(root)
    frames,packs,coverage=prepare(data)
    rawpacks={p:packs[p]['M5'] for p in PAIRS}
    original=json.loads((package/'reports/study_summary.json').read_text())['summary']
    folds=periods(sorted({b.t for source in data.values() for b in source}))
    frozen=dict(config=config,execution=asdict(Config()),folds=folds,
                selection_partitions=[purged(f,config['purge_seconds']) for f in folds],
                data_quality=quality,aggregation=coverage,reused_sources=existing.sources,
                source_hashes={p.name:digest(p) for p in sorted(package.glob('*.py'))},
                config_sha256=digest(package/'mtf_config.json'),baseline_summary_sha256=digest(package/'reports/study_summary.json'))
    write(out/'frozen_inputs.json',frozen)
    write(out/'data_quality.json',dict(source=quality,aggregation=coverage))
    result_rows=[]; totals=defaultdict(list); days=defaultdict(dict); selections=[]; equivalents=0
    scenario={}; signal_counts=Counter(); sides=Counter(); signal_spreads=[]
    minimum=dict(train=10,validation=20)
    with (out/'records.jsonl.gz').open('wb') as file:
        with gzip.GzipFile(filename='',mode='wb',fileobj=file,mtime=0) as stream:
            def record(kind,row):
                if kind==('candidate' if scenario['native_M5'] else 'mtf_signal'):
                    signal_counts['signals']+=1
                    sides[row['direction']]+=1
                    signal_spreads.append(row['spread_reference'])
                stream.write((json.dumps(dict(scenario=scenario,kind=kind,record=row),sort_keys=True,allow_nan=False)+'\n').encode())

            def execute(fold,phase,policy,pair,*,protection=False,stress=False,fit_rules=None,label=None):
                nonlocal scenario,signal_counts,sides,signal_spreads,equivalents
                native=(fit_rules is None and policy.entry=='M5' and not policy.contexts and policy.hold==12)
                label=label or policy.entry
                scenario=dict(fold=fold['fold'],phase=phase,label=label,pair=pair or 'PORTFOLIO',
                              policy=policy.key if policy else 'adaptive',protection=protection,stress=stress,native_M5=native)
                signal_counts=Counter(); sides=Counter(); signal_spreads=[]
                provider=Provider(frames,packs,existing,fit_rules.policy if fit_rules is not None else policy,record)
                cfg=replace(Config(),slippage_pips=.5) if stress else Config()
                r=replay(data,rawpacks,existing,fold[phase],strategy=policy.strategy if policy else 'trend',
                         config=cfg,instruments=[pair] if pair else None,protection=protection,
                         decision_provider=None if native else provider,record=record,cost_breakdown=True)
                for t in r['trades']:
                    t.setdefault('context_key',provider.context_key(t['pair'],t['entry_time']))
                    t.setdefault('entry_timeframe','M5')
                row={**scenario,'metrics':r['metrics'],'signal_count':signal_counts['signals'],
                     'signal_sides':dict(sides),'average_signal_spread':statistics.fmean(signal_spreads) if signal_spreads else None}
                if phase=='test':
                    # One test domain for every comparison, including the original M5 baseline.
                    key=(label,policy.strategy if policy else 'ADAPTIVE',pair or 'PORTFOLIO',protection,stress)
                    totals[key].extend(r['trades'])
                    days[key][fold['fold']]=daily_pnl(r['equity'])
                    row.update(by_pair=grouped(r['trades'],'pair'),by_regime=grouped(r['trades'],'regime'),
                               by_session=grouped(r['trades'],'session'))
                    if native and not stress and pair is not None:
                        old=next(x for x in original['results'] if x['phase']=='test' and x['pair']==pair
                            and x['strategy']==policy.strategy and x['policy']=='baseline'
                            and x['protection']==protection and not x['stress'] and x['fold']==fold['fold'])
                        if old['metrics']!=r['metrics']: raise ResearchRejected('original_M5_baseline_regression')
                        equivalents+=1
                result_rows.append(row)
                return r

            for f in folds:
                fit_fold=purged(f,config['purge_seconds'])
                print('MTF fold',f['fold'],'train/validation fitting',flush=True)
                holding={}; training=[]; hold_evidence=[]
                for pair in PAIRS:
                    for tf in config['entry_timeframes']:
                        for name in STRATEGIES:
                            candidates=[]
                            for hold in config['holding_candidates_entry_bars'][tf]:
                                policy=Policy(tf,name,hold)
                                a=execute(fit_fold,'train',policy,pair)['trades']
                                b=execute(fit_fold,'validation',policy,pair)['trades']
                                training.append((pair,policy,a))
                                candidates.append((hold,a,b))
                            chosen,status=select_hold(candidates,config['fallback_holding_entry_bars'][tf])
                            if tf=='M5': chosen,status=12,'IMMUTABLE_TIV2_BASELINE'
                            holding[(pair,tf,name)]=chosen
                            hold_evidence.append(dict(pair=pair,timeframe=tf,strategy=name,holding=chosen,status=status))
                    print(' fit',pair,flush=True)
                fitted=fit(training,fit_fold['train'][1])
                validation={p:execute(fit_fold,'validation',None,p,fit_rules=fitted,label='ADAPTIVE')['trades'] for p in PAIRS}
                frozen_fit=validate_fit(fitted,validation,*fit_fold['validation'])
                selected=dict(fold=f['fold'],holding=hold_evidence,
                              train_rules=[dict(pair=p,context=k,policy=asdict(pol)) for p,k,pol in fitted.rules],
                              final_rules=[dict(pair=p,context=k,policy=asdict(pol)) for p,k,pol in frozen_fit.rules],
                              train_end=fitted.train_end,validation_end=frozen_fit.validation_end)
                selections.append(selected); write(out/f"fold_{f['fold']}_selected_policies.json",selected)
                print('MTF fold',f['fold'],'frozen; OOS evaluation',flush=True)
                for pair in PAIRS:
                    for name in STRATEGIES:
                        policies=[(tf,Policy(tf,name,holding[(pair,tf,name)])) for tf in config['entry_timeframes']]
                        policies.extend([
                            ('B_M5_M15',Policy('M5',name,12,('M15',))),
                            ('C_M5_H1',Policy('M5',name,12,('H1',))),
                            ('D_M5_H4',Policy('M5',name,12,('H4',))),
                            ('E_M15_H1',Policy('M15',name,holding[(pair,'M15',name)],('H1',))),
                            ('F_H1_H4',Policy('H1',name,holding[(pair,'H1',name)],('H4',))),
                            ('G_AGREEMENT',Policy('M5',name,12,('M15','H1','H4'),2))])
                        for label,pol in policies:
                            for protection in (False,True):
                                for stress in (False,True): execute(f,'test',pol,pair,protection=protection,stress=stress,label=label)
                    print(' OOS',pair,flush=True)
                for protection in (False,True):
                    for stress in (False,True):
                        execute(f,'test',None,None,fit_rules=frozen_fit,label='ADAPTIVE',protection=protection,stress=stress)
                        # Financed six-pair fixed-policy portfolio controls (same period/cost/risk).
                        for tf in config['entry_timeframes']:
                            pol=Policy(tf,'trend',config['fallback_holding_entry_bars'][tf])
                            execute(f,'test',pol,None,protection=protection,stress=stress,label='PORTFOLIO_'+tf)
    aggregate=[]
    for key,trades in totals.items():
        label,strategy,pair,protection,stress=key
        aggregate.append(dict(label=label,strategy=strategy,pair=pair,protection=protection,stress=stress,
                              metrics=summarize(trades)))
    comparisons=[]
    for key,fd in days.items():
        label,strategy,pair,protection,stress=key
        if label in ('M5','PORTFOLIO_M5'): continue
        baseline=('PORTFOLIO_M5','trend','PORTFOLIO',protection,stress) if pair=='PORTFOLIO' else ('M5',strategy,pair,protection,stress)
        if baseline not in days: continue
        diffs=[]
        for fold,values in sorted(fd.items()):
            ref=days[baseline][fold]
            if set(values)!=set(ref): raise ResearchRejected('unpaired_daily_comparison')
            diffs.append([values[d]-ref[d] for d in sorted(ref)])
        comparisons.append(dict(label=label,strategy=strategy,pair=pair,protection=protection,stress=stress,
                                statistics=interval(diffs,seed=config['bootstrap_seed'],repeats=config['bootstrap_repeats'])))
    holm(comparisons)
    summary=dict(classification='TIV22_MTF_RESEARCH_PARTIALLY_VERIFIED',production='NO-GO',
                 scenario_count=len(result_rows),baseline_equivalent_cells=equivalents,
                 results=result_rows,aggregate=aggregate,selections=selections,comparisons=comparisons,
                 availability=existing.availability(),records_sha256=digest(out/'records.jsonl.gz'),
                 frozen_inputs_sha256=digest(out/'frozen_inputs.json'))
    write(out/'metrics.json',summary)
    from .mtf_reporting import generate
    generate(package,frozen,summary)
    print('MTF complete:',len(result_rows),'scenarios; baseline cells',equivalents,'record hash',summary['records_sha256'],flush=True)
