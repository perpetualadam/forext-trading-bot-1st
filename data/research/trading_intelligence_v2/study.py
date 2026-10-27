"""Reproducible archived-data study; no downloads, model stores or execution."""
from collections import Counter, defaultdict
from dataclasses import asdict, replace
import gzip
import hashlib
import json
import math
from pathlib import Path

from .core import PAIRS, STRATEGIES, Bar, Config, ResearchRejected, features, iso, periods, read_csv, timestamp
from .adapters import Existing
from .engine import Filter, metrics, run as replay


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')


def acquire(root):
    """Verify local archive chain. This function makes NO acquisition requests."""
    base=root/'data/research/adaptive_ensemble/g3'
    manifest=json.loads((base/'acquisition_manifest.json').read_text())
    raw={p:{} for p in PAIRS}
    for page in manifest['raw_pages']:
        path=root/page['path']
        if not path.resolve().is_relative_to((base/'raw').resolve()) or digest(path)!=page['sha256']:
            raise ResearchRejected('raw_archive_hash_or_path_mismatch')
        payload=json.loads(path.read_text())
        pair=page['instrument']
        if payload['instrument']!=pair or payload['granularity']!='M5':
            raise ResearchRejected('raw_archive_metadata_mismatch')
        for candle in payload['candles']:
            if candle['complete'] is not True: continue
            t=timestamp(candle['time'])
            values=tuple(float(candle[component][k]) for component in ('mid','bid','ask') for k in ('o','h','l','c'))
            if t in raw[pair] and raw[pair][t]!=values:
                raise ResearchRejected('conflicting_raw_candle')
            raw[pair][t]=values
    data,quality={},{}
    for item in manifest['quality']:
        pair=item['pair']; path=base/'normalized'/f'{pair}_M5.csv'
        if digest(path)!=item['sha256']: raise ResearchRejected('normalized_hash_mismatch')
        bars,q=read_csv(path)
        if len(bars)!=item['rows'] or len(raw[pair])!=len(bars): raise ResearchRejected('archive_completeness_mismatch')
        for b in bars:
            values=(b.o,b.h,b.l,b.c,b.bo,b.bh,b.bl,b.bc,b.ao,b.ah,b.al,b.ac)
            if values!=raw[pair].get(b.t): raise ResearchRejected('normalized_raw_value_mismatch')
        decimals=3 if pair=='USD_JPY' else 5
        q.update(raw_link='ALL_COMPLETE_CANDLES_EXACTLY_MATCH', source='local OANDA archive acquisition record; not independently attested',
                 precision_decimals=decimals,
                 off_precision_values=sum(abs(x*10**decimals-round(x*10**decimals))>1e-6 for b in bars for x in (b.bo,b.bh,b.bl,b.bc,b.ao,b.ah,b.al,b.ac)),
                 source_path=str(path.relative_to(root)).replace('\\','/'))
        data[pair],quality[pair]=bars,q
    if set(data)!=set(PAIRS): raise ResearchRejected('six_pairs_required')
    older={}
    for pair in PAIRS:
        _,q=read_csv(root/'data/historical'/f'{pair}_M5.csv')
        q['research_use']='QUALITY_ONLY: previously examined; acquisition chain not verified here'
        older[pair]=q
    return data,dict(primary=quality,previously_examined=older,
                     manifest_sha256=digest(base/'acquisition_manifest.json'),raw_pages=len(manifest['raw_pages']),
                     duration_status=manifest['duration_status'],complete_trading_days=manifest['complete_trading_days'])


def selection(train, validation, minimum=20):
    eligible=[name for name in STRATEGIES if train[name]['trades']>=minimum and validation[name]['trades']>=minimum
              and train[name]['expectancy_r']>0 and validation[name]['expectancy_r']>0]
    return sorted(eligible,key=lambda n:(-validation[n]['expectancy_r'],n))[0] if eligible else None


def grouped(trades,key):
    buckets=defaultdict(list)
    for t in trades: buckets[t[key]].append(t)
    return {k:metrics(v) for k,v in sorted(buckets.items())}


def run(root, package):
    output=package/'outputs'; reports=package/'reports'; output.mkdir(exist_ok=True); reports.mkdir(exist_ok=True)
    config_record=json.loads((package/'study_config.json').read_text())
    existing=Existing(root)
    data,quality=acquire(root)
    write(output/'data_quality.json',quality)
    print('Archive verified: six normalized datasets, 36 raw pages; building causal features',flush=True)
    packs={p:{lb:features(b,lb) for lb in (50,100)} for p,b in data.items()}
    times=sorted({b.t for bars in data.values() for b in bars})
    folds=periods(times)
    cfg=Config()
    frozen=dict(configuration=config_record,execution=asdict(cfg),folds=folds,reused_sources=existing.sources,
                source_hashes={p.name:digest(p) for p in sorted(package.glob('*.py'))},
                config_sha256=digest(package/'study_config.json'),data_quality=quality)
    write(output/'frozen_inputs.json',frozen)  # written BEFORE any strategy outcomes
    policies={'baseline':Filter(),'spread':Filter(max_spread_atr=.25),'regime_spread':Filter(True,.25)}
    results=[]; all_trades=defaultdict(list); selection_records=[]; filter_audit=[]; original=[]; original_trades=defaultdict(list)
    # Single deterministic compressed stream: every candidate acceptance/rejection and every fill.
    with (output/'records.jsonl.gz').open('wb') as binary:
        with gzip.GzipFile(filename='',mode='wb',fileobj=binary,mtime=0) as stream:
            scenario={}
            def record(kind, row):
                stream.write((json.dumps(dict(scenario=scenario,kind=kind,record=row),sort_keys=True,allow_nan=False)+'\n').encode())
            def execute(fold,phase,strategy,policy='baseline',protection=False,pair=None,weights=None,stress=False):
                nonlocal scenario
                scenario=dict(fold=fold['fold'],phase=phase,strategy=strategy,policy=policy,
                              protection=protection,pair=pair or 'PORTFOLIO',stress=stress)
                r=replay(data,packs,existing,fold[phase],strategy=strategy,policy=policies[policy],
                         protection=protection,config=replace(cfg,slippage_pips=.5) if stress else cfg,
                         instruments=[pair] if pair else None,weights=weights,record=record)
                row={**scenario,'metrics':r['metrics']}
                if phase=='test':
                    row['by_regime']=grouped(r['trades'],'regime'); row['by_session']=grouped(r['trades'],'session')
                    row['by_pair']=grouped(r['trades'],'pair')
                    key=(strategy,policy,protection,pair or 'PORTFOLIO',stress)
                    all_trades[key].extend(r['trades'])
                results.append(row)
                return r
            for fold in folds:
                print('Starting fold',fold['fold'],flush=True)
                selected={}; weights={}
                for pair in PAIRS:
                    train={}; validation={}
                    for name in STRATEGIES:
                        train[name]=execute(fold,'train',name,pair=pair)['metrics']
                        validation[name]=execute(fold,'validation',name,pair=pair)['metrics']
                    selected[pair]=selection(train,validation,config_record['selection_minimum_trades_per_partition'])
                    weights[pair]={n:max(0,train[n]['expectancy_r'] or 0) if train[n]['trades']>=20 else 0 for n in STRATEGIES}
                    selection_records.append(dict(fold=fold['fold'],pair=pair,selected=selected[pair],train=train,validation=validation,weights=weights[pair]))
                write(output/f"fold_{fold['fold']}_frozen_selection.json",selection_records[-6:])
                # Nothing below feeds back into feature thresholds or model selection.
                for pair in PAIRS:
                    for name in STRATEGIES:
                        for policy in policies:
                            for protection in (False,True):
                                r=execute(fold,'test',name,policy,protection,pair)
                                if policy=='baseline' and not protection:
                                    for policy_name in ('spread','regime_spread'):
                                        accepted=[]; rejected=[]
                                        for t in r['trades']:
                                            mismatch=('RANGE' if 'mean_reversion' in name else 'TREND')!=t['regime']
                                            drop=t['spread_reference']/t['atr']>.25 or (policy_name=='regime_spread' and mismatch)
                                            (rejected if drop else accepted).append(t)
                                        filter_audit.append(dict(fold=fold['fold'],pair=pair,strategy=name,policy=policy_name,
                                            interpretation='matched baseline executed-entry outcomes, not independent portfolios',
                                            accepted=metrics(accepted),rejected=metrics(rejected)))
                for router,w in [('hybrid_research',weights),('selected',selected)]:
                    for protection in (False,True):
                        for stress in (False,True):
                            execute(fold,'test',router,protection=protection,weights=w,stress=stress)
                for pair in PAIRS:
                    for name in STRATEGIES:
                        for protection in (False,True):
                            scenario=dict(fold=fold['fold'],phase='test',pair=pair,strategy=name,protection=protection,
                                          policy='baseline',stress=False,entry_geometry='source_default')
                            r=replay(data,packs,existing,fold['test'],strategy=name,instruments=[pair],protection=protection,
                                     config=cfg,record=record,entry_geometry='source_default')
                            original.append({**scenario,'metrics':r['metrics']})
                            original_trades[(pair,name,protection)].extend(r['trades'])
    aggregate=[]
    for key,trades in all_trades.items():
        name,policy,protection,pair,stress=key
        aggregate.append(dict(strategy=name,policy=policy,protection=protection,pair=pair,stress=stress,
                              metrics=metrics(trades,initial=cfg.initial*len(folds))))
    summary=dict(classification='TIV2_OFFLINE_RESEARCH_PARTIALLY_VERIFIED',production='NO-GO',
                 original_sl_tp_benchmark=dict(results=original,aggregate=[dict(pair=p,strategy=n,protection=b,
                    metrics=metrics(t,initial=cfg.initial*len(folds))) for (p,n,b),t in original_trades.items()],
                    qualification='source defaults with cleared environment, not current production settings; added for requested original-geometry benchmark, no tuning'),
                 results=results,aggregate=aggregate,selection=selection_records,filter_audit=filter_audit,
                 availability=existing.availability(),folds=folds,
                 ablations={name:dict(status='UNAVAILABLE_ABSTAIN',approved_trades=0,expectancy_r=None)
                            for name in ('quant_plus_ai','quant_plus_rl','quant_plus_ai_plus_rl')},
                 records_sha256=digest(output/'records.jsonl.gz'),frozen_inputs_sha256=digest(output/'frozen_inputs.json'))
    write(output/'metrics.json',summary)
    from .reporting import generate
    generate(package,summary,frozen)
    print('Study complete:',len(results)+len(original),'runs; records SHA256',summary['records_sha256'],flush=True)
