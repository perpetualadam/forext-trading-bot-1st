"""Pairwise common-ready signal comparisons; abstention is never active agreement."""
from itertools import combinations
import math
import statistics
from .core import STRATEGIES,utc
from .timeframes import DURATIONS


def counts(a,b):
    if len(a)!=len(b): raise ValueError('unaligned signal timestamps')
    n=len(a); buy=sum(x==y=='BUY' for x,y in zip(a,b)); sell=sum(x==y=='SELL' for x,y in zip(a,b))
    conflict=sum(x is not None and y is not None and x!=y for x,y in zip(a,b))
    neither=sum(x is None and y is None for x,y in zip(a,b))
    only_a=sum(x is not None and y is None for x,y in zip(a,b)); only_b=sum(x is None and y is not None for x,y in zip(a,b))
    union=n-neither; both=buy+sell+conflict
    return dict(eligible=n,buy_agreement=buy,sell_agreement=sell,opposite_direction=conflict,
                joint_abstention=neither,only_a=only_a,only_b=only_b,signal_union=union,
                active_overlap_jaccard=both/union if union else None,
                conditional_direction_agreement=(buy+sell)/union if union else None,
                joint_abstention_fraction=neither/n if n else None)


def matrix(frames,packs,existing,windows):
    result=[]
    for pair,by_tf in frames.items():
        for tf,bars in by_tf.items():
            states={name:{} for name in STRATEGIES}; ready={name:set() for name in STRATEGIES}
            opens={b.t for b in by_tf['M5']}; total_eligible=0
            for i,b in enumerate(bars):
                when=b.t+DURATIONS[tf]
                if not any(a<=when<z for a,z in windows): continue
                clock=utc(when)
                if when not in opens or when-300 not in opens or clock.weekday()>=5 or clock.hour*60+clock.minute>=20*60+55: continue
                total_eligible+=1
                for name in STRATEGIES:
                    p=packs[pair][tf][100 if name.startswith('swing_') else 50]
                    if not all(math.isfinite(p[k][i]) for k in ('close','ma_fast','ma_slow','atr','boll_up','boll_down')) or p['atr'][i]<=0: continue
                    ready[name].add(when); states[name][when]=existing.signal(name,i,p)[0]
            for a,b in combinations(STRATEGIES,2):
                times=sorted(ready[a]&ready[b]); va=[states[a][t] for t in times]; vb=[states[b][t] for t in times]
                # Causal previous-signal timing comparison, within one native interval.
                previous={}; lags=[]
                for t,x,y in zip(times,va,vb):
                    if y is not None: previous[y]=t
                    if x is not None and x in previous and t-previous[x]<=DURATIONS[tf]: lags.append(t-previous[x])
                result.append(dict(pair=pair,timeframe=tf,strategy_a=a,strategy_b=b,
                    eligible_before_warmup=total_eligible,excluded_not_common_ready=total_eligible-len(times),
                    **counts(va,vb),previous_matching_b_signal_lag_mean_seconds=statistics.fmean(lags) if lags else None,
                    timing_matches=len(lags),signal_entry_reference_difference=0.0 if any(x==y and x is not None for x,y in zip(va,vb)) else None,
                    reference_note='Same completed candle close by construction; actual fills compared separately'))
    return result


def trade_key(t): return (t['pair'],t['entry_time'],t['direction'])


def unique_trades(trades):
    out={}
    for t in trades:
        k=trade_key(t)
        if k in out: raise ValueError('duplicate_closed_trade_identity')
        out[k]=t
    return out


def paired(a,b):
    x,y=unique_trades(a),unique_trades(b); keys=sorted(x.keys()&y.keys())
    ra=[x[k]['net_r'] for k in keys]; rb=[y[k]['net_r'] for k in keys]
    corr=None
    if len(keys)>=3 and statistics.pstdev(ra)>0 and statistics.pstdev(rb)>0:
        corr=statistics.correlation(ra,rb)
    return dict(matched=len(keys),only_a=len(x.keys()-y.keys()),only_b=len(y.keys()-x.keys()),
                outcome_R_correlation=corr,
                mean_absolute_entry_price_difference=statistics.fmean(abs(x[k]['entry_price']-y[k]['entry_price']) for k in keys) if keys else None,
                equal_net_R=sum(math.isclose(x[k]['net_r'],y[k]['net_r'],abs_tol=1e-12) for k in keys),
                paired_net_R_differences=[y[k]['net_r']-x[k]['net_r'] for k in keys])
