"""Small fixed hypothesis set and an abstaining research-only selector."""
from dataclasses import dataclass
import math
import statistics
from .decision_quality import Policy
from .core import ResearchRejected

POLICIES=(Policy('A_BASELINE'),Policy('B_SPREAD_ATR',spread_atr_limit=.25),
          Policy('C_COST_TARGET',cost_target_limit=.25),Policy('D_HTF',require_context=True),
          Policy('E_EXACT_VOTES'),Policy('F_COMBINED',.25,.25,True,False))


def unique_votes(votes):
    """Only identical predicate fingerprints at the same timestamp are duplicates.

    Similar directions or scalp/trend agreement are NOT equivalence proofs.
    Input tuples: (instrument,time,direction,predicate_hash). No cross-time cooldown.
    """
    if any(type(v) is not tuple or len(v)!=4 or not isinstance(v[3],str) or not v[3] for v in votes):
        raise ResearchRejected('predicate_identity_required')
    return tuple(dict.fromkeys(votes))


@dataclass(frozen=True)
class Split:
    train: tuple
    validation: tuple
    test: tuple
    embargo: int = 57600  # longest candidate holding horizon: 4 H4 candles

    def __post_init__(self):
        if (any(type(x) is not tuple or len(x)!=2 or any(type(t) is not int for t in x) or x[0]>=x[1]
                for x in (self.train,self.validation,self.test)) or
            type(self.embargo) is not int or self.embargo<57600 or
            self.train[1]+self.embargo>self.validation[0] or
            self.validation[1]+self.embargo>self.test[0]):
            raise ResearchRejected('unpurged_or_invalid_split')


@dataclass(frozen=True)
class FrozenSelector:
    split: Split
    rules: tuple
    audit: tuple

    def choose(self,context,when):
        if not self.split.test[0]<=when<self.split.test[1]:
            raise ResearchRejected('selector_outside_frozen_test')
        return dict(self.rules).get(context)  # None is an explicit abstention.


def fit_selector(rows,split,*,independent=False,evidence=''):
    """Synthetic-testable lifecycle; attestations are not independent-data proof."""
    if independent is not True or not isinstance(evidence,str) or not evidence.strip():
        return FrozenSelector(split,(),(('ALL','ABSTAIN_NO_INDEPENDENT_VALIDATION'),))
    groups={}; audit=[]; seen=set()
    for r in rows:
        if r['phase'] not in ('train','validation'):
            raise ResearchRejected('test_outcomes_forbidden')
        identity=(r['context'],r['policy'],r['entry_time'])
        if identity in seen: raise ResearchRejected('duplicate_selection_outcome')
        seen.add(identity)
        start,end=getattr(split,r['phase'])
        if (not start<=r['entry_time']<r['outcome_end']<=end or
            not r['outcome_end']<=r['available_at']<=end or
            r['policy'] not in {p.name for p in POLICIES[:5]} or
            type(r['net_r']) not in (int,float) or not math.isfinite(r['net_r'])):
            raise ResearchRejected('unavailable_or_invalid_selection_outcome')
        groups.setdefault((r['context'],r['policy'],r['phase']),[]).append(r['net_r'])
    def eligible(values):
        return len(values)>=30 and statistics.fmean(values)-2*statistics.stdev(values)/math.sqrt(len(values))>0
    selected=[]
    for context in sorted({k[0] for k in groups}):
        candidates=[]
        for policy in POLICIES[:5]:
            train=groups.get((context,policy.name,'train'),[])
            validation=groups.get((context,policy.name,'validation'),[])
            ok=eligible(train) and eligible(validation)
            audit.append((context,policy.name,'ELIGIBLE' if ok else 'REJECT_SAMPLE_OR_NET_SCORE'))
            if ok: candidates.append((statistics.fmean(validation),policy.name))
        if candidates: selected.append((context,sorted(candidates,key=lambda x:(-x[0],x[1]))[0][1]))
        else: audit.append((context,'NONE','ABSTAIN'))
    return FrozenSelector(split,tuple(selected),tuple(audit))
