"""Explicit offline integration: engine -> causal request -> structured decision."""
from .decision_quality import Request, evaluate
from .cost_aware_policies import unique_votes
from .timeframes import last_completed, DURATIONS
from .mtf_features import trend_state


class Evaluator:
    def __init__(self,policy,pricing,frames,packs,timeframe='M5'):
        self.policy,self.pricing,self.frames,self.packs,self.timeframe=policy,pricing,frames,packs,timeframe

    def __call__(self,*,pair,when,side,signal_bar,pack,index,bar,stop_distance,
                 target_distance,units,quotes,config,candidate,baseline_reason):
        contexts=[]
        for tf in ('M15','H1','H4'):
            i=last_completed(self.frames[pair][tf],tf,when)
            state=trend_state(self.packs[pair][tf][50],i)
            completed=self.frames[pair][tf][i].t+DURATIONS[tf] if i is not None else when+1
            contexts.append((tf,state,completed,DURATIONS[tf]))
        request=Request(pair,side,when,signal_bar.t+DURATIONS[self.timeframe],signal_bar.complete,
            bar.t,bar.bo,bar.ao,pack['atr'][index],stop_distance,target_distance,
            (12*300 if self.timeframe=='M5' else 4*DURATIONS[self.timeframe]),
            self.pricing,config.account,candidate['strategy'],candidate['regime'],tuple(contexts),
            units=units,momentum=pack['momentum'][index],volatility=pack['volatility'][index])
        result=evaluate(request,self.policy,dict(quotes.book))
        if self.policy.name=='E_EXACT_VOTES':
            votes=((pair,when,side,'PINNED_STRATEGY:'+candidate['strategy']),)
            result['vote_accounting']=dict(raw=len(votes),unique=len(unique_votes(votes)),
                suppression='NO_CROSS_TIME_OR_SIMILAR_STRATEGY_SUPPRESSION')
        return result
