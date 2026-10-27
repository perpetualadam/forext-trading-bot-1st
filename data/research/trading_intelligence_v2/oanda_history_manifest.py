"""Strict response validation, lexeme preservation and conservative provenance."""
from decimal import Decimal
import hashlib
import json
import re
from .core import PAIRS,Bar,ResearchRejected,timestamp,iso,utc,validate
from .historical_manifest import KNOWN_EXPOSURE


def digest(raw): return hashlib.sha256(raw).hexdigest()
def encoded(value): return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def decode(raw):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d: raise ValueError()
            d[k]=v
        return d
    try:
        return json.loads(raw,object_pairs_hook=pairs,
            parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
    except (ValueError,UnicodeError,TypeError,RecursionError):
        raise ResearchRejected('MALFORMED_JSON') from None


def candle_time(text):
    if not isinstance(text,str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.0{1,9})?(?:Z|[+-]\d\d:\d\d)',text):
        raise ResearchRejected('INVALID_OR_FRACTIONAL_TIMESTAMP')
    try: t=timestamp(text)
    except (ValueError,OverflowError): raise ResearchRejected('INVALID_TIMESTAMP') from None
    if t%300: raise ResearchRejected('OFF_GRID_TIMESTAMP')
    return t


def validated(raw,pair,start,end,retrieved):
    x=decode(raw)
    if (type(x) is not dict or set(x)!={'instrument','granularity','candles'} or
        x['instrument']!=pair or pair not in PAIRS or x['granularity']!='M5' or
        type(x['candles']) is not list or len(x['candles'])>5000):
        raise ResearchRejected('UNEXPECTED_RESPONSE_STRUCTURE')
    rows=[];previous=None;incomplete=0;seen=set()
    for c in x['candles']:
        if (type(c) is not dict or set(c)!={'time','complete','volume','mid','bid','ask'} or
            type(c['complete']) is not bool or type(c['volume']) is not int or c['volume']<0):
            raise ResearchRejected('INVALID_CANDLE_STRUCTURE')
        t=candle_time(c['time'])
        if not start<=t<end or t in seen or previous is not None and t<=previous:
            raise ResearchRejected('DUPLICATE_DISORDER_OR_OUT_OF_RANGE')
        previous=t;seen.add(t);texts=[]
        for component in ('mid','bid','ask'):
            block=c[component]
            if type(block) is not dict or set(block)!=set('ohlc'):
                raise ResearchRejected('MISSING_PRICE_COMPONENT')
            prices=[]
            for key in 'ohlc':
                value=block[key]
                if not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,6}(?:\.[0-9]{1,12})?',value):
                    raise ResearchRejected('PRICE_PRECISION_OR_FORMAT')
                d=Decimal(value)
                if not d.is_finite() or d<=0: raise ResearchRejected('INVALID_PRICE')
                prices.append(d);texts.append(value)
            o,h,l,close=prices
            if not l<=min(o,close)<=max(o,close)<=h:
                raise ResearchRejected('INVALID_OHLC')
        if any(Decimal(texts[4+i])>Decimal(texts[8+i]) for i in range(4)):
            raise ResearchRejected('CROSSED_BID_ASK')
        if c['complete'] is False:
            incomplete+=1;continue
        if t+300>retrieved: raise ResearchRejected('COMPLETION_AFTER_RETRIEVAL')
        rows.append(dict(time=iso(t),instrument=pair,complete=True,prices=texts,volume=c['volume']))
    present={timestamp(r['time']) for r in rows}
    # Compact contiguous missing runs, preserving unknown market-closure status.
    gaps=[];begin=None
    for t in range(start,end,300):
        if t not in present and begin is None: begin=t
        if begin is not None and (t in present or t+300==end):
            stop=t if t in present else end
            gaps.append(dict(start=iso(begin),end=iso(stop),missing_candles=(stop-begin)//300,
                kind='WEEKEND_CONTAINING_UNVERIFIED' if any(utc(j).weekday()>=5 for j in range(begin,stop,300)) else 'UNKNOWN_CLOSURE_OR_MISSING'))
            begin=None
    report=dict(returned=len(x['candles']),candles=len(rows),incomplete=incomplete,duplicates=0,
        first=rows[0]['time'] if rows else None,last=rows[-1]['time'] if rows else None,
        missing_intervals=gaps,coverage='OBSERVED_WITH_GAPS' if gaps else 'FULL_REQUEST_GRID',
        empty_is_not_completeness=not rows,validation_failures=[],
        decimal_lexemes_sha256=digest(encoded([r['prices'] for r in rows])))
    return rows,report


def bars(rows):
    return [Bar(timestamp(r['time']),*(float(p) for p in r['prices'])) for r in rows]


def independence(start,end,*,previously_examined=False,provenance=False,rights=False,
                 history_reviewed=False,controlled_first_access=False,evidence='',intervals=KNOWN_EXPOSURE):
    if type(start) is not int or type(end) is not int or start>=end:
        raise ResearchRejected('INVALID_INDEPENDENCE_RANGE')
    if previously_examined is True: return 'PREVIOUSLY_EXAMINED'
    if any(start<b and end>a for a,b in intervals): return 'OVERLAPPING'
    if (all(x is True for x in (provenance,rights,history_reviewed,controlled_first_access)) and
        isinstance(evidence,str) and evidence.strip()): return 'INDEPENDENT_UNTOUCHED'
    return 'PROVENANCE_UNVERIFIED'
