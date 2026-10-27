"""Causal higher-timeframe snapshots and an entry provider for the TIV2 replay."""
from dataclasses import dataclass
import math
from .core import features,STRATEGIES,ResearchRejected
from .engine import session
from .timeframes import DURATIONS, aggregate, last_completed


@dataclass(frozen=True,order=True)
class Policy:
    entry: str
    strategy: str
    hold: int  # number of entry-timeframe candles
    contexts: tuple=()
    quorum: int=1

    def __post_init__(self):
        if (self.entry not in DURATIONS or self.strategy not in STRATEGIES
                or type(self.hold) is not int or self.hold<1
                or type(self.contexts) is not tuple or len(set(self.contexts))!=len(self.contexts)
                or any(tf not in DURATIONS or DURATIONS[tf]<=DURATIONS[self.entry] for tf in self.contexts)
                or type(self.quorum) is not int or not 1<=self.quorum<=max(1,len(self.contexts))):
            raise ResearchRejected('invalid_MTF_policy')

    @property
    def key(self): return f'{self.entry}:{self.strategy}:{self.hold}:'+('+'.join(self.contexts) or 'NONE')+f':q{self.quorum}'


def prepare(data):
    frames={}; packs={}; quality={}
    for pair,source in data.items():
        frames[pair]={}; packs[pair]={}; quality[pair]={}
        for tf,step in DURATIONS.items():
            b,q=aggregate(source,tf)
            frames[pair][tf]=b; quality[pair][tf]=q
            packs[pair][tf]={lb:features(b,lb,step_seconds=step,weekend_continuity=tf!='M5') for lb in (50,100)}
            q['warmed_50']=sum(math.isfinite(x) for x in packs[pair][tf][50]['atr'])
            q['warmed_100']=sum(math.isfinite(x) for x in packs[pair][tf][100]['atr'])
        quality[pair]['D1']=dict(status='INSUFFICIENT_DATA',reason='No independently validated session calendar; only 29 days < 50/100 candle warm-up')
    return frames,packs,quality


def trend_state(pack,i):
    if i is None or not all(math.isfinite(pack[k][i]) for k in ('ma_fast','ma_slow','atr')) or pack['atr'][i]<=0:
        return 'INSUFFICIENT_DATA'
    strength=(pack['ma_fast'][i]-pack['ma_slow'][i])/pack['atr'][i]
    return 'BUY' if strength>=.5 else ('SELL' if strength<=-.5 else 'WAIT')


def agreement(states,quorum=1):
    sides={s for s in states if s in ('BUY','SELL')}
    if len(sides)>1: return 'CONFLICT'
    if 'INSUFFICIENT_DATA' in states: return 'INSUFFICIENT_DATA'
    if sides:
        side=next(iter(sides))
        if states.count(side)>=quorum: return side
    return 'WAIT'


class Provider:
    def __init__(self,frames,packs,existing,policy,record=None):
        self.frames,self.packs,self.existing,self.policy,self.record=frames,packs,existing,policy,record

    def context_key(self,pair,when):
        i=last_completed(self.frames[pair]['M5'],'M5',when)
        if i is None: return 'INSUFFICIENT_DATA'
        p=self.packs[pair]['M5'][50]
        return p['regime'][i]+'|'+p['volatility'][i]

    def __call__(self,pair,when):
        context_key=self.context_key(pair,when)
        policy=self.policy(pair,context_key) if callable(self.policy) else self.policy
        if policy is None:
            return None
        bars=self.frames[pair][policy.entry]
        i=last_completed(bars,policy.entry,when)
        if i is None or bars[i].t+DURATIONS[policy.entry]!=when: return None
        lb=100 if policy.strategy.startswith('swing_') else 50
        pack=self.packs[pair][policy.entry][lb]
        side,detail=self.existing.signal(policy.strategy,i,pack)
        if side is None: return None
        states=[]
        for tf in policy.contexts:
            j=last_completed(self.frames[pair][tf],tf,when)
            states.append(trend_state(self.packs[pair][tf][50],j))
        combined=agreement(states,policy.quorum) if states else side
        if combined in ('BUY','SELL') and combined!=side:
            combined='CONFLICT'
        reason='CONTEXT_CONFIRMED' if combined==side else combined
        meta=dict(entry_timeframe=policy.entry,context_timeframes=list(policy.contexts),timeframe_states=states,
                  confirmation_state=combined,selected_policy=policy.key,context_key=context_key,
                  signal_available_at=bars[i].t+DURATIONS[policy.entry],why_timeframe='FROZEN_POLICY_OR_TRAIN_VALIDATION_CONTEXT_MAP')
        if self.record:
            self.record('mtf_signal',dict(pair=pair,time=when,strategy=policy.strategy,direction=side,
                                         spread_reference=bars[i].ac-bars[i].bc,atr=pack['atr'][i],
                                         allowed=combined==side,reason=reason,**meta))
        if combined!=side: return None
        return dict(strategy=policy.strategy,pack=pack,index=i,bar=bars[i],
                    hold_bars=policy.hold*DURATIONS[policy.entry]//300,metadata=meta)
