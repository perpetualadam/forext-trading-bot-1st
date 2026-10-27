"""Strict quote/precision checks, extending existing candle validation."""
from dataclasses import asdict
from .core import PAIRS,ResearchRejected,validate,pip_size,utc


def quality(pair,bars,*,holiday_windows=()):
    if pair not in PAIRS: raise ResearchRejected('unsupported_instrument')
    if any(b.complete is not True or type(b.t) is not int or
           any(type(getattr(b,k)) not in (int,float) for k in ('o','h','l','c','bo','bh','bl','bc','ao','ah','al','ac')) for b in bars):
        raise ResearchRejected('invalid_candle_types_or_completion')
    q=validate(bars)
    if q['status']=='FAIL': raise ResearchRejected('invalid_candles:'+str(q['errors'][:4]))
    decimals=3 if pair=='USD_JPY' else 5
    q['off_precision_values']=sum(abs(getattr(b,k)*10**decimals-round(getattr(b,k)*10**decimals))>1e-6
                                 for b in bars for k in ('bo','bh','bl','bc','ao','ah','al','ac'))
    q.update(pip_size=pip_size(pair),price_rounding='NONE',precision='preserved; off-grid values reported, not rounded')
    for gap in q['gaps']:
        # No inferred holiday calendar. Only explicitly supplied reviewed UTC intervals.
        from .core import timestamp
        a=timestamp(gap['before'])+300; b=timestamp(gap['after'])
        match=[x for x in holiday_windows if x.get('reviewed') is True and x.get('evidence') and x['start']<=a and x['end']>=b]
        if match: gap['kind']='DOCUMENTED_HOLIDAY_CLOSURE'; gap['calendar_evidence']=match[0]['evidence']
        elif gap['kind']=='unexpected': gap['kind']='UNEXPLAINED_OUTAGE_OR_UNVERIFIED_HOLIDAY'
    return q
