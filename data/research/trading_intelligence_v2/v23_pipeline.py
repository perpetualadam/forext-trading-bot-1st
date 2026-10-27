"""Frozen unchanged-policy replay connected to importer, overlap and diagnostics."""
from collections import Counter,defaultdict
from dataclasses import asdict,replace
import gzip
import hashlib
import json
import statistics
from itertools import combinations

from .core import PAIRS,STRATEGIES,Config,ResearchRejected,periods
from .study import acquire,digest,write
from .adapters import Existing
from .engine import run as replay
from .mtf_features import prepare,Policy,Provider
from .timeframes import DURATIONS
from .mtf_statistics import daily_pnl,interval,holm
from .historical_import import import_dataset
from .historical_manifest import verify_spec,canonical_digest,KNOWN_EXPOSURE
from .strategy_overlap import matrix,paired
from .trade_diagnostics import ProtectionObserver,diagnose,cost_summary


def run(root,package,*,exploratory=False,manifest=None,allow_reproduction=False):
    out=package/'outputs/v23'; reports=package/'reports/v23'
    out.mkdir(exist_ok=True); reports.mkdir(exist_ok=True)
    spec=json.loads((package/'v23_experiment.json').read_text())
    expected=(package/'v23_experiment.sha256').read_text().strip()
    verify_spec(spec,expected,package)
    if asdict(Config())!=spec['execution']: raise ResearchRejected('frozen_execution_configuration_changed')
    existing=Existing(root)
    if exploratory:
        data,provenance=acquire(root)
        labels={p:'PREVIOUSLY_EXAMINED' for p in PAIRS}; mode='EXPLORATORY_PREVIOUSLY_EXAMINED'
    else:
        if manifest is None: raise ResearchRejected('approved_dataset_manifest_required')
        prior=list(KNOWN_EXPOSURE)
        for path in (out/'inspection_receipts').glob('*.json'):
            record=json.loads(path.read_text())
            prior.extend(tuple(x) for x in record['coverage_intervals'])
        data,provenance=import_dataset(json.loads(manifest.read_text()),manifest.parent,
                                      independent_required=not allow_reproduction,prior_intervals=tuple(prior))
        labels=provenance['independence']; mode='FIRST_EVALUATION_CONDITIONAL_ON_REVIEWED_ATTESTATIONS'
        if allow_reproduction: mode='EXPLICIT_EXPLORATORY_IMPORTED_DATA_REPRODUCTION'
    frames,packs,coverage=prepare(data)
    for q in coverage.values():
        q['D1']=dict(status='UNAVAILABLE',reason='Disabled by frozen V23 protocol; reviewed daily-session calendar not supplied')
    rawpacks={p:packs[p]['M5'] for p in PAIRS}; times={p:[b.t for b in bars] for p,bars in data.items()}
    folds=periods(sorted({b.t for bars in data.values() for b in bars}))
    receipt=dict(mode=mode,labels=labels,experiment_sha256=expected,provenance=provenance,folds=folds,
                 source_pin_scheme='SHA256_LF_TEXT_RESEARCH_FILES_NOT_OPERATIONAL_SEALS',sources=spec['source_hashes'])
    write(out/'prerun_receipt.json',receipt)  # BEFORE outcomes: binds exact inputs/protocol.
    inspection=out/'inspection_receipts'; inspection.mkdir(exist_ok=True)
    dataset_id=canonical_digest({p:[(b.t,b.bo,b.bh,b.bl,b.bc,b.ao,b.ah,b.al,b.ac,b.o,b.h,b.l,b.c) for b in bars] for p,bars in data.items()})
    inspection_record=dict(dataset_id=dataset_id,experiment_sha256=expected,
         coverage_intervals=[[bars[0].t,bars[-1].t+300] for bars in data.values()],
         inspection_started=True,mode=mode)
    receipt_path=inspection/(dataset_id+'-'+expected+'.json')
    if receipt_path.exists() and json.loads(receipt_path.read_text())!=inspection_record:
        # Reproduction must not rewrite a previous first-access receipt.
        receipt_path=inspection/(dataset_id+'-'+expected+'-reproduction.json')
    if not receipt_path.exists(): write(receipt_path,inspection_record)
    write(out/'data_quality.json',dict(provenance=provenance,aggregation=coverage))
    overlap=matrix(frames,packs,existing,[f['test'] for f in folds])
    totals=defaultdict(list); results=[]; daily=defaultdict(dict); baseline_checks=0
    baseline=json.loads((package/'reports/mtf/metrics_summary.json').read_text())['fold_results'] if exploratory else []
    baseline_index={(r['fold'],r['label'],r['pair'],r['policy'],r['protection'],r['stress']):r for r in baseline}
    with (out/'trades.jsonl.gz').open('wb') as binary:
        with gzip.GzipFile(filename='',mode='wb',fileobj=binary,mtime=0) as stream:
            def execute(f,pol,pair,label,protection,stress):
                nonlocal baseline_checks
                scenario=dict(fold=f['fold'],label=label,strategy=pol.strategy,pair=pair or 'PORTFOLIO',
                              policy=pol.key,protection=protection,stress=stress,mode=mode)
                counts=Counter(); closed=[]; observer=ProtectionObserver(existing)
                native=pol.entry=='M5' and not pol.contexts and pol.hold==12
                def record(kind,row):
                    if kind==('candidate' if native else 'mtf_signal'): counts['signals']+=1
                    if kind!='trade': return
                    p=row['pair']; key=(p,row['entry_time'],row['strategy'])
                    annotated=diagnose(row,pol.entry,data[p],frames[p],packs[p],observer.events.get(key,()),times[p],
                                       holding_limit_seconds=pol.hold*DURATIONS[pol.entry],fold_end=f['test'][1])
                    annotated['trade_id']=canonical_digest([dataset_id,expected,scenario,p,row['entry_time'],row['direction']])
                    closed.append(annotated)
                    stream.write((json.dumps(dict(scenario=scenario,independence=labels[p],trade=annotated),sort_keys=True,allow_nan=False)+'\n').encode())
                provider=Provider(frames,packs,observer,pol,record)
                cfg=replace(Config(),slippage_pips=spec['costs']['stress_slippage']) if stress else Config()
                r=replay(data,rawpacks,observer,f['test'],strategy=pol.strategy,config=cfg,
                         instruments=[pair] if pair else None,protection=protection,
                         decision_provider=None if native else provider,cost_breakdown=True,record=record)
                if len(closed)!=len(r['trades']): raise ResearchRejected('diagnostic_trade_count_mismatch')
                key=(label,pol.strategy,pair or 'PORTFOLIO',protection,stress)
                totals[key].extend(closed); daily[key][f['fold']]=daily_pnl(r['equity'])
                ref=baseline_index.get((f['fold'],label,pair or 'PORTFOLIO',pol.key,protection,stress))
                if ref is not None:
                    for k,v in ref['metrics'].items():
                        if r['metrics'].get(k)!=v: raise ResearchRejected('unchanged_replay_regression:'+k)
                    baseline_checks+=1
                results.append(dict(**scenario,signals=counts['signals'],metrics=r['metrics'],costs=cost_summary(closed)))
            for f in folds:
                print('V23 frozen replay fold',f['fold'],mode,flush=True)
                for pair in PAIRS:
                    for name in STRATEGIES:
                        candidates=[(tf,Policy(tf,name,spec['holding'][tf])) for tf in spec['timeframes']]
                        candidates.extend((label,Policy(entry,name,spec['holding'][entry],tuple(context),quorum))
                                          for label,entry,context,quorum in spec['confirmation'])
                        for label,pol in candidates:
                            for protection in (False,True):
                                for stress in (False,True): execute(f,pol,pair,label,protection,stress)
                    print(' diagnosed',pair,flush=True)
                for tf in spec['timeframes']:
                    for protection in (False,True):
                        for stress in (False,True):
                            execute(f,Policy(tf,'trend',spec['holding'][tf]),None,'PORTFOLIO_'+tf,protection,stress)
    aggregates=[]; failures=[]; protection_pairs=[]; trade_overlap=[]; comparisons=[]; cohorts=[]
    for key,trades in totals.items():
        label,name,pair,prot,stress=key
        base=dict(label=label,strategy=name,pair=pair,protection=prot,stress=stress)
        aggregates.append(dict(**base,**cost_summary(trades)))
        for field in ('regime','volatility','session'):
            for value in sorted({t[field] for t in trades}):
                group=[t for t in trades if t[field]==value]
                cohorts.append(dict(**base,dimension=field,value=value,**cost_summary(group),
                   activation_observed=sum(t['protection_activation_observed'] is True for t in group),
                   mean_giveback_lower_pips=statistics.fmean(t['giveback_lower_pips'] for t in group)))
        tagcounts=Counter(tag for t in trades for tag in t['diagnostic_tags'])
        failures.append(dict(**base,trades=len(trades),tags=dict(tagcounts),
                             excursion_status=dict(Counter(t['excursion_status'] for t in trades)),
                             exits=dict(Counter(t['exit_diagnostic'] for t in trades))))
        if not prot:
            protected=totals[(label,name,pair,True,stress)]
            comparison=paired(trades,protected)
            diffs=comparison.pop('paired_net_R_differences')
            protection_pairs.append(dict(**base,**comparison,protection_improved=sum(d>1e-12 for d in diffs),
                protection_reduced=sum(d< -1e-12 for d in diffs),unchanged=sum(abs(d)<=1e-12 for d in diffs),
                mean_matched_R_difference=statistics.fmean(diffs) if diffs else None,
                protected_trades=len(protected),activation_observed=sum(t['protection_activation_observed'] is True for t in protected),
                mean_captured_price_pips=statistics.fmean(t['captured_price_move_pips'] for t in protected) if protected else None,
                mean_positive_captured_price_pips=statistics.fmean(max(0,t['captured_price_move_pips']) for t in protected) if protected else None,
                mean_giveback_lower_pips=statistics.fmean(t['giveback_lower_pips'] for t in protected) if protected else None))
    for pair in PAIRS:
        for tf in spec['timeframes']:
            for a,b in combinations(STRATEGIES,2):
                p=paired(totals[(tf,a,pair,False,False)],totals[(tf,b,pair,False,False)])
                p.pop('paired_net_R_differences')
                trade_overlap.append(dict(pair=pair,timeframe=tf,strategy_a=a,strategy_b=b,**p))
    for key,values in daily.items():
        label,name,pair,prot,stress=key
        if label in ('M5','PORTFOLIO_M5'): continue
        refkey=('PORTFOLIO_M5','trend',pair,prot,stress) if pair=='PORTFOLIO' else ('M5',name,pair,prot,stress)
        groups=[]
        for f,ds in sorted(values.items()):
            ref=daily[refkey][f]
            if set(ds)!=set(ref): raise ResearchRejected('unpaired_calendar_dates')
            groups.append([ds[d]-ref[d] for d in sorted(ds)])
        comparisons.append(dict(label=label,strategy=name,pair=pair,protection=prot,stress=stress,
                                statistics=interval(groups,seed=spec['statistics']['seed'],repeats=spec['statistics']['replicates'])))
    holm(comparisons)
    # Baseline executed trades grouped by known causal context; no invented outcomes for unexecuted signals.
    confirmation_diagnosis=[]
    for key,trades in totals.items():
        label,name,pair,prot,stress=key
        if label!='M5' or prot or stress or pair=='PORTFOLIO': continue
        for tf in ('H1','H4'):
            bins=defaultdict(list)
            for t in trades:
                state=t['higher_context_at_entry'][tf]
                bucket='AGREES' if state==t['direction'] else ('OPPOSES' if state in ('BUY','SELL') else state)
                bins[bucket].append(t)
            confirmation_diagnosis.append(dict(pair=pair,strategy=name,context=tf,
                interpretation='matched baseline executed-entry outcomes; not counterfactual filtered portfolios',
                bins={k:cost_summary(v) for k,v in bins.items()}))
    summary=dict(classification='TIV23_RESEARCH_PARTIALLY_VERIFIED',mode=mode,independence=labels,
                 experiment_sha256=expected,scenario_count=len(results),baseline_checks=baseline_checks,
                 aggregates=aggregates,failures=failures,protection_pairs=protection_pairs,
                 signal_overlap=overlap,trade_overlap=trade_overlap,comparisons=comparisons,
                 cohorts=cohorts,
                 confirmation_diagnosis=confirmation_diagnosis,results=results,availability=existing.availability(),
                 trades_sha256=digest(out/'trades.jsonl.gz'))
    write(out/'metrics.json',summary)
    from .v23_reporting import generate
    generate(package,spec,receipt,summary)
    print('V23 complete',len(results),'scenarios;',baseline_checks,'unchanged baseline cells; trade hash',summary['trades_sha256'],flush=True)
