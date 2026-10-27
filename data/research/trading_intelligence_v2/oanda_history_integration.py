"""Verified archives -> existing MTF/replay components. Never a new trading engine."""
import base64
import hashlib
from pathlib import Path
from .core import PAIRS,ResearchRejected,Config,periods
from .oanda_history import Plan
from .oanda_history_resume import Store
from .oanda_history_manifest import decode,encoded,digest,validated,bars,independence
from .mtf_features import prepare,Provider,Policy as EntryPolicy
from .cost_aware_policies import POLICIES
from .decision_quality import Pricing
from .v25_adapter import Evaluator
from .v25_engine import run as replay
from .historical_quality import quality

PACKAGE=Path(__file__).resolve().parent


def verify_policy_seal():
    spec=decode((PACKAGE/'v26_frozen_policy.json').read_bytes())
    for name,h in spec['sha256_lf'].items():
        if digest((PACKAGE/name).read_bytes().replace(b'\r\n',b'\n'))!=h:
            raise ResearchRejected('FROZEN_V25_POLICY_SOURCE_CHANGED')
    if digest((PACKAGE.parents[2]/'forex_bot/profit_protection.py').read_bytes())!=spec['protection_raw_sha256']:
        raise ResearchRejected('FROZEN_PROFIT_PROTECTION_SOURCE_CHANGED')
    return digest(encoded(spec))


def load_dataset(root):
    store=Store(root)
    with store.locked():
        manifest=decode(store.read('manifest.json')); plan_record=decode(store.read('plan.json'));plan_dict=plan_record['plan']
        plan=Plan(**dict(plan_dict,instruments=tuple(plan_dict['instruments'])))
        if (manifest['environment']!=plan.environment or manifest.get('transport_mode')!=plan_record['transport_mode'] or
            manifest['granularity']!='M5' or manifest['price_components']!='MBA'):
            raise ResearchRejected('MANIFEST_METADATA_MISMATCH')
        if manifest['batch_count']!=len(plan.batches()) or len(manifest['batches'])!=len(plan.batches()):
            raise ResearchRejected('DATASET_BATCHES_INCOMPLETE')
        data={p:[] for p in plan.instruments}
        for i,((pair,start,end),ref) in enumerate(zip(plan.batches(),manifest['batches'])):
            if ref['commit_path']!=f'commits/{i:06d}.json': raise ResearchRejected('COMMIT_PATH_MISMATCH')
            commit=decode(store.verify(ref['commit_path'],ref['commit_sha256']))
            if commit['request']!=dict(instrument=pair,start=start,end=end): raise ResearchRejected('COMMIT_RANGE_MISMATCH')
            envelope=decode(store.verify(f'raw/{i:06d}.json',commit['archive_sha256']))
            raw=base64.b64decode(envelope['body_base64'],validate=True)
            if digest(raw)!=commit['raw_sha256'] or envelope['request']!=commit['request'] or envelope['retrieved_epoch']!=commit['retrieved_epoch']:
                raise ResearchRejected('RAW_ENVELOPE_MISMATCH')
            rows,report=validated(raw,pair,start,end,commit['retrieved_epoch'])
            normalized=store.verify(f'validated/{i:06d}.json',commit['validated_sha256'])
            if normalized!=encoded(rows) or report!=commit['validation']: raise ResearchRejected('VALIDATED_ARCHIVE_MISMATCH')
            if ref['request']!=commit['request'] or ref['candles']!=len(rows) or ref['first']!=report['first'] or ref['last']!=report['last']:
                raise ResearchRejected('MANIFEST_BATCH_SUMMARY_MISMATCH')
            data[pair].extend(bars(rows))
        if manifest['candle_count']!=sum(len(b) for b in data.values()):
            raise ResearchRejected('MANIFEST_TOTAL_MISMATCH')
        reports={p:quality(p,b) if b else dict(status='EMPTY_NO_COVERAGE') for p,b in data.items()}
        return data,dict(manifest=manifest,quality=reports,plan=plan_dict)


def evaluate_independent(root,evidence,*,minimum_days=365,coverage_reviewed=False,calendar_evidence=''):
    """Guarded future entry point; not invoked without acquired independent data."""
    if type(minimum_days) is not int or not 365<=minimum_days<=3*366:
        raise ResearchRejected('INDEPENDENT_COVERAGE_MINIMUM_NOT_MET')
    if coverage_reviewed is not True or not isinstance(calendar_evidence,str) or not calendar_evidence.strip():
        raise ResearchRejected('COVERAGE_AND_MARKET_CLOSURE_REVIEW_REQUIRED')
    seal=verify_policy_seal();data,provenance=load_dataset(root)
    if provenance['manifest'].get('transport_mode')!='AUTHENTICATED_HTTPS':
        raise ResearchRejected('SYNTHETIC_INPUT_IS_NOT_INDEPENDENT_MARKET_DATA')
    if set(data)!=set(PAIRS) or any(not b for b in data.values()): raise ResearchRejected('SIX_PAIR_DATA_REQUIRED')
    if minimum_days<365: raise ResearchRejected('INDEPENDENT_COVERAGE_MINIMUM_NOT_MET')
    for p,b in data.items():
        if b[-1].t+300-b[0].t<minimum_days*86400: raise ResearchRejected('INDEPENDENT_COVERAGE_MINIMUM_NOT_MET')
        if independence(b[0].t,b[-1].t+300,**evidence)!='INDEPENDENT_UNTOUCHED':
            raise ResearchRejected('UNTOUCHED_INDEPENDENCE_NOT_ESTABLISHED')
    store=Store(root)
    with store.locked():
        if store.path('evaluation_started.json').exists(): raise ResearchRejected('DATA_ALREADY_INSPECTED_FOR_PERFORMANCE')
        store.publish('evaluation_started.json',encoded(dict(policy_seal=seal,dataset_manifest_sha256=digest(encoded(provenance['manifest'])),
            status='FIRST_PERFORMANCE_INSPECTION_STARTED')))
    # No adaptive fitting unless independently supported. Fixed policy comparison only.
    from .adapters import Existing
    existing=Existing(PACKAGE.parents[2]);frames,packs,_=prepare(data)
    rawpacks={p:packs[p]['M5'] for p in PAIRS}
    folds=periods(sorted({b.t for series in data.values() for b in series}))
    rows=[]
    for f in folds:
        for tf,hold in [('M5',12),('M15',4),('H1',4),('H4',4)]:
            for price in (Pricing(),Pricing('HYPOTHETICAL_STRESS',.5,3),Pricing('HYPOTHETICAL_BASELINE',.2,3)):
                cfg=Config(slippage_pips=price.slippage_pips_side,commission_per_100k_side=price.commission_account_per_100k_side)
                for policy in (POLICIES[:1] if price.name=='HYPOTHETICAL_BASELINE' else POLICIES[:5]):
                    entry=EntryPolicy(tf,'trend',hold)
                    r=replay(data,rawpacks,existing,f['test'],config=cfg,
                        decision_provider=None if tf=='M5' else Provider(frames,packs,existing,entry),
                        decision_evaluator=Evaluator(policy,price,frames,packs,tf),cost_breakdown=True,cost_trace=True)
                    rows.append(dict(fold=f['fold'],timeframe=tf,pricing=price.name,policy=policy.name,metrics=r['metrics']))
    store.publish('evaluation_results.json',encoded(dict(status='FIXED_POLICY_SAMPLE_NOT_PRODUCTION_AUTHORITY',
        policy_seal=seal,results=rows,adaptive='ABSTAIN_NO_VALIDATION',D1='DISABLED')))
    return rows
