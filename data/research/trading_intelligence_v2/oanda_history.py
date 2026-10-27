"""Standalone research acquisition with explicit approval required for any network."""
from dataclasses import dataclass,asdict
import time
import base64
from .core import PAIRS,ResearchRejected,iso
from .oanda_history_manifest import validated,digest,encoded,decode
from .oanda_history_resume import Store
from .oanda_history_transport import HOSTS


@dataclass(frozen=True)
class Plan:
    start: int
    end: int
    instruments: tuple=PAIRS
    environment: str='practice'
    batch_candles: int=1000

    def __post_init__(self):
        if (type(self.start) is not int or type(self.end) is not int or self.start%300 or self.end%300 or
            not 0<self.end-self.start<=3*366*86400 or self.environment not in HOSTS or
            type(self.instruments) is not tuple or not self.instruments or
            len(set(self.instruments))!=len(self.instruments) or any(p not in PAIRS for p in self.instruments) or
            type(self.batch_candles) is not int or not 1<=self.batch_candles<=5000):
            raise ResearchRejected('INVALID_ACQUISITION_PLAN')
        if len(self.instruments)*((self.end-self.start+self.batch_candles*300-1)//(self.batch_candles*300))>20000:
            raise ResearchRejected('REQUEST_BUDGET_EXCEEDED')

    def batches(self):
        return tuple((p,start,min(self.end,start+self.batch_candles*300)) for p in self.instruments
            for start in range(self.start,self.end,self.batch_candles*300))


def acquire(plan,transport,root,*,retrieved=time.time,progress=lambda _:None,max_bytes=2*1024**3):
    if transport.host!=HOSTS[plan.environment]: raise ResearchRejected('TRANSPORT_PLAN_ENVIRONMENT_MISMATCH')
    store=Store(root,max_bytes);plan_record=dict(version=1,provider='OANDA',transport_mode=transport.mode,plan=asdict(plan),
        granularity='M5',price='MBA',smooth=False,endpoint='/v3/instruments/{instrument}/candles')
    batches=plan.batches()
    with store.locked():
        store.publish('plan.json',encoded(plan_record))
        completed=[];all_times={p:set() for p in plan.instruments}
        for i,(pair,start,end) in enumerate(batches):
            if transport.cancel.is_set(): raise ResearchRejected('CANCELLED')
            name=f'{i:06d}';raw_name='raw/'+name+'.json';valid_name='validated/'+name+'.json';commit_name='commits/'+name+'.json'
            request=dict(instrument=pair,start=start,end=end)
            if store.path(commit_name).exists():
                commit=decode(store.read(commit_name))
                if commit['request']!=request: raise ResearchRejected('COMMITTED_RANGE_MISMATCH')
                archive=store.verify(raw_name,commit['archive_sha256'])
                envelope=decode(archive)
                raw=base64.b64decode(envelope['body_base64'],validate=True)
                if digest(raw)!=commit['raw_sha256'] or envelope['request']!=request or envelope['retrieved_epoch']!=commit['retrieved_epoch']:
                    raise ResearchRejected('RAW_ENVELOPE_MISMATCH')
                canonical=store.verify(valid_name,commit['validated_sha256'])
                rows,report=validated(raw,pair,start,end,commit['retrieved_epoch'])
                if canonical!=encoded(rows) or report!=commit['validation']:
                    raise ResearchRejected('COMMITTED_VALIDATION_MISMATCH')
            else:
                # A verified durable raw response can finish publication without re-fetching.
                if store.path(raw_name).exists():
                    archive=store.read(raw_name)
                    envelope=decode(archive)
                    if set(envelope)!={'request','retrieved_epoch','body_base64'} or envelope['request']!=request:
                        raise ResearchRejected('RAW_ENVELOPE_MISMATCH')
                    raw=base64.b64decode(envelope['body_base64'],validate=True)
                    now=envelope['retrieved_epoch']
                elif store.path(raw_name+'.pending').exists():
                    raise ResearchRejected('AMBIGUOUS_LOCAL_PUBLICATION_REQUIRES_REVIEW')
                else:
                    raw=transport.candles(pair,start,end);now=int(retrieved())
                    archive=encoded(dict(request=request,retrieved_epoch=now,body_base64=base64.b64encode(raw).decode('ascii')))
                rows,report=validated(raw,pair,start,end,now)
                store.publish(raw_name,archive)
                store.publish(valid_name,encoded(rows))
                commit=dict(request=request,archive_sha256=digest(archive),raw_sha256=digest(raw),validated_sha256=digest(encoded(rows)),
                    retrieved_epoch=now,retrieved_utc=iso(now),validation=report,
                    status='BATCH_RESPONSE_VALIDATED_NOT_COVERAGE_GUARANTEED')
                store.publish(commit_name,encoded(commit))
            times={r['time'] for r in rows}
            if all_times[pair]&times: raise ResearchRejected('CROSS_BATCH_DUPLICATE')
            all_times[pair].update(times);completed.append(commit)
            index=dict(plan_sha256=digest(encoded(plan_record)),completed_batches=len(completed),
                expected_batches=len(batches),commits_sha256=[digest(encoded(c)) for c in completed],
                status='RANGES_PROCESSED_WITH_EXPLICIT_COVERAGE_LIMITATIONS')
            store.publish('progress.json',encoded(index),replace_index=True)
            progress(dict(completed=len(completed),total=len(batches),instrument=pair,candles=len(rows)))
        manifest=dict(provider='OANDA',transport_mode=transport.mode,environment=plan.environment,endpoint=plan_record['endpoint'],
            granularity='M5',price_components='MBA',requested_range=[iso(plan.start),iso(plan.end)],
            batch_count=len(completed),batches=[dict(request=c['request'],commit_path=f'commits/{i:06d}.json',
                commit_sha256=digest(encoded(c)),candles=c['validation']['candles'],
                missing_candles=sum(g['missing_candles'] for g in c['validation']['missing_intervals']),
                incomplete=c['validation']['incomplete'],first=c['validation']['first'],last=c['validation']['last'],
                retrieved_utc=c['retrieved_utc']) for i,c in enumerate(completed)],candle_count=sum(len(x) for x in all_times.values()),
            status='VALIDATED_RESPONSES_COVERAGE_REVIEW_REQUIRED',
            usage_rights='MUST_BE_REVIEWED_BEFORE_AUTHENTICATED_RETRIEVAL_OR_REDISTRIBUTION',
            limitations=['No historical completeness guarantee','Unverified closure calendar',
                'Not filled prices, commissions, slippage, funding or settlement FX',
                'Independence requires full research-history and first-access evidence'])
        store.publish('manifest.json',encoded(manifest),replace_index=True)
        return manifest


if __name__=='__main__':
    raise SystemExit('Use v26_run.py --offline-check or --tests. No authenticated-download CLI is enabled.')
