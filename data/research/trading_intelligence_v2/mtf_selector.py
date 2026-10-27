"""Train-only context routing and validation veto; immutable rules during test."""
from dataclasses import dataclass
import math
import statistics
from .core import ResearchRejected


def score(trades,minimum=10):
    if len(trades)<minimum: return None
    r=[t['net_r'] for t in trades]
    return statistics.fmean(r)-1.96*statistics.stdev(r)/math.sqrt(len(r))


@dataclass(frozen=True)
class Fitted:
    rules: tuple
    train_end: int
    validation_end: int | None=None

    def policy(self,pair,context):
        return next((p for a,b,p in self.rules if a==pair and b==context),None)


def fit(training,train_end):
    """training = (pair, Policy, closed training trades); no future labels allowed."""
    buckets={}
    for pair,policy,trades in training:
        for t in trades:
            if t['exit_time']>train_end: raise ResearchRejected('future_training_label')
        for key in sorted({t['context_key'] for t in trades}):
            cell=[t for t in trades if t['context_key']==key]
            value=score(cell)
            if value is not None and value>0:
                buckets.setdefault((pair,key),[]).append((value,policy))
    rules=[]
    for (pair,key),items in sorted(buckets.items()):
        best=sorted(items,key=lambda x:(-x[0],x[1].key))[0][1]
        rules.append((pair,key,best))
    return Fitted(tuple(rules),train_end)


def validate_fit(fitted,closed_validation,validation_start,validation_end):
    if not fitted.train_end<=validation_start<validation_end:
        raise ResearchRejected('invalid_validation_partition')
    approved=set()
    for pair,trades in closed_validation.items():
        if any(t['entry_time']<validation_start or t['exit_time']>validation_end for t in trades):
            raise ResearchRejected('validation_label_outside_partition')
        value=score(trades,20)
        if value is not None and value>0: approved.add(pair)
    return Fitted(tuple(r for r in fitted.rules if r[0] in approved),fitted.train_end,validation_end)


def select_hold(candidates,default):
    """(hold, train trades, validation trades); no test results accepted."""
    valid=[]
    for hold,training,validation in candidates:
        a,b=score(training),score(validation)
        if a is not None and b is not None and a>0 and b>0: valid.append((b,hold))
    return (sorted(valid,key=lambda x:(-x[0],x[1]))[0][1],'TRAIN_VALIDATION_APPROVED') if valid else (default,'PREDECLARED_FALLBACK_NOT_VALIDATED')
