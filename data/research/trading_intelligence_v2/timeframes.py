"""Complete observed-price aggregation; no interpolation or inferred daily calendar."""
from dataclasses import dataclass
from .core import Bar, ResearchRejected, iso, validate

DURATIONS = {'M5':300, 'M15':900, 'H1':3600, 'H4':14400}


@dataclass(frozen=True)
class DailySession:
    start: int
    end: int
    convention: str
    evidence: str
    reviewed: bool=False


def combine(rows, start):
    values=[]
    for names in (('o','h','l','c'),('bo','bh','bl','bc'),('ao','ah','al','ac')):
        o,h,l,c=names
        values.extend((getattr(rows[0],o),max(getattr(b,h) for b in rows),
                       min(getattr(b,l) for b in rows),getattr(rows[-1],c)))
    return Bar(start,*values)


def aggregate(source, timeframe, *, daily_sessions=None):
    for b in source:
        if not isinstance(b,Bar) or type(b.t) is not int or b.complete is not True:
            raise ResearchRejected('invalid_M5_aggregation_source_types')
        if any(type(getattr(b,k)) not in (int,float)
               for k in ('o','h','l','c','bo','bh','bl','bc','ao','ah','al','ac')):
            raise ResearchRejected('invalid_M5_price_type')
    q=validate(source)
    if q['status']=='FAIL': raise ResearchRejected('invalid_M5_aggregation_source')
    if timeframe=='D1':
        if not daily_sessions: raise ResearchRejected('D1_verified_session_calendar_required')
        windows=[]; previous=None
        for s in daily_sessions:
            if (not isinstance(s,DailySession) or type(s.start) is not int or type(s.end) is not int
                    or s.start%300 or s.end%300 or not 23*3600<=s.end-s.start<=25*3600
                    or s.reviewed is not True or not s.convention.strip() or not s.evidence.strip()
                    or (previous is not None and s.start<previous)):
                raise ResearchRejected('invalid_explicit_daily_session')
            windows.append((s.start,s.end)); previous=s.end
    elif timeframe in DURATIONS:
        step=DURATIONS[timeframe]
        windows=[(t,t+step) for t in range(source[0].t//step*step, source[-1].t//step*step+step,step)]
    else: raise ResearchRejected('unsupported_timeframe')
    indexed={b.t:b for b in source}; bars=[]; unavailable=[]
    for start,end in windows:
        times=range(start,end,300)
        rows=[indexed[t] for t in times if t in indexed]
        if len(rows)!=(end-start)//300:
            unavailable.append(dict(start=start,available_at=end,missing=(end-start)//300-len(rows),
                                    reason='INCOMPLETE_SOURCE_COVERAGE'))
        else: bars.append(combine(rows,start))
    return bars,dict(timeframe=timeframe,complete_bars=len(bars),unavailable=unavailable,
                     source_rows=len(source),alignment='explicit verified sessions supplied by caller' if timeframe=='D1' else 'UTC epoch multiples',
                     D1_market_calendar_verified=False if timeframe=='D1' else None)


def last_completed(bars, timeframe, when):
    """Binary search completion, not opening; stale or future context is unavailable."""
    step=DURATIONS[timeframe]
    lo,hi=0,len(bars)
    while lo<hi:
        mid=(lo+hi)//2
        if bars[mid].t+step<=when: lo=mid+1
        else: hi=mid
    i=lo-1
    return i if i>=0 and 0<=when-(bars[i].t+step)<step else None
