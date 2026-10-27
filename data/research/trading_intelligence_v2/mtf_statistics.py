"""Exploratory paired daily moving-block intervals and multiplicity accounting."""
import itertools
import math
import random
import statistics
from .core import utc


def daily_pnl(marks,initial=10000):
    days={}
    for t,equity in marks:
        days[utc(t).date().isoformat()]=equity
    previous=initial; result={}
    for day,equity in sorted(days.items()):
        result[day]=(equity-previous)/initial
        previous=equity
    return result


def interval(fold_differences,*,seed=22,repeats=2000):
    """Keep fold boundaries; resample adjacent 2-trading-day blocks within folds.

    Short nonstationary samples cannot validate the block/symmetry assumptions.
    Values are illustrative, never a confirmatory significance claim.
    """
    samples=[list(x) for x in fold_differences if x]
    n=sum(map(len,samples))
    base=dict(days=n,block_days=2,confidence='illustrative dependent-block 95%',
              interval=None,raw_block_sign_p=None,status='INSUFFICIENT_DATA')
    if n<8 or any(len(x)<2 for x in samples): return base
    rng=random.Random(seed); values=[]
    for _ in range(repeats):
        picked=[]
        for data in samples:
            out=[]
            while len(out)<len(data):
                start=rng.randrange(len(data)-1)
                out.extend(data[start:start+2])
            picked.extend(out[:len(data)])
        values.append(statistics.fmean(picked))
    values.sort()
    blocks=[sum(data[i:i+2]) for data in samples for i in range(0,len(data),2)]
    observed=abs(sum(blocks))
    if len(blocks)<=16:
        outcomes=[abs(sum(s*x for s,x in zip(signs,blocks))) for signs in itertools.product((-1,1),repeat=len(blocks))]
        p=sum(x>=observed-1e-12 for x in outcomes)/len(outcomes)
    else: p=None
    base.update(interval=[values[int(repeats*.025)],values[int(repeats*.975)]],
                mean_daily_difference=statistics.fmean(x for data in samples for x in data),
                raw_block_sign_p=p,status='EXPLORATORY_UNVALIDATED_BLOCK_ASSUMPTIONS')
    return base


def holm(rows):
    indexed=sorted(((r['statistics']['raw_block_sign_p'],i) for i,r in enumerate(rows)
                    if r['statistics']['raw_block_sign_p'] is not None))
    # Count unavailable comparisons too; do not shrink the preregistered family.
    m=len(rows); running=0
    for rank,(p,i) in enumerate(indexed):
        running=max(running,min(1,p*(m-rank)))
        rows[i]['statistics']['holm_adjusted_p']=running
    for r in rows:
        r['statistics'].setdefault('holm_adjusted_p',None)
        r['statistics']['comparison_family']=m
        r['statistics']['reliable_advantage_established']=False
    return rows
