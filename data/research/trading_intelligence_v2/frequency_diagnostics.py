"""Chronological diagnostics and explicitly matched baseline counterfactuals."""
from collections import Counter
from .core import utc


class Frequency:
    def __init__(self):
        self.last_signal={}; self.last_exit={}; self.counts=Counter(); self.groups=Counter()

    def record(self,kind,row):
        if kind=='trade':
            self.last_exit[row['pair']]=(row['exit_time'],row['exit_reason'])
            return
        if kind!='candidate': return
        pair=row['pair']; when=row['signal_time']; side=row['direction']
        old=self.last_signal.get(pair)
        repeated=old is not None and old[1]==side
        adjacent=old is not None and when-old[0]==300
        exit=self.last_exit.get(pair)
        immediate=exit is not None and 0<=when-exit[0]<=300
        row['frequency']=dict(repeated_direction=repeated,adjacent_signal=adjacent,
            existing_position=row.get('reason')=='ALREADY_OPEN',immediate_reentry=immediate,
            reentry_after_stop=bool(immediate and 'STOP' in exit[1]),
            diagnostic_only_no_cooldown=True)
        for k,v in row['frequency'].items():
            if v is True and k!='diagnostic_only_no_cooldown': self.counts[k]+=1
        self.counts['candidate_signals']+=1
        self.counts['accepted_entries']+=int(row['accepted'])
        metrics=row.get('quality_decision',{}).get('metrics')
        ratio=metrics['spread_atr'] if metrics else row['spread_reference']/row['atr']
        spread_bin='HIGH_GT_025_ATR' if ratio>.25 else 'LOWER'
        self.groups[(row['pair'],row['strategy'],row.get('entry_timeframe','M5'),row['session'],
                     row['regime'],row['volatility'],utc(when).weekday(),spread_bin)]+=1
        self.last_signal[pair]=(when,side)


def counterfactual(decisions,baseline_trades,baseline_candidates=()):
    """Only actually executed baseline entries have observable baseline outcomes."""
    index={(t['pair'],t['entry_time'],t['direction']):t for t in baseline_trades}
    candidates={(t['pair'],t['signal_time'],t['direction']):t for t in baseline_candidates}
    rows=[]
    for d in decisions:
        key=(d['pair'],d['signal_time'],d['direction'])
        t=index.get(key)
        q=d.get('quality_decision',{})
        rows.append(dict(pair=key[0],decision_time=key[1],direction=key[2],
            status=q.get('status'),reason=q.get('reason'),
            policy_portfolio_accepted=d['accepted'],portfolio_reason=d['reason'],
            baseline_trade_exists=t is not None,
            baseline_action={k:candidates[key][k] for k in ('accepted','reason')} if key in candidates else None,
            baseline_net_account=t['net_account'] if t else None,
            baseline_outcome=('WIN' if t['net_account']>0 else 'LOSS' if t['net_account']<0 else 'FLAT') if t else 'UNKNOWN_UNEXECUTED_BASELINE',
            baseline_trade=t))
    return rows


def opportunity_summary(rows):
    rejected=[r for r in rows if r['status']!='ACCEPT']
    known=[r for r in rejected if r['baseline_trade_exists']]
    return dict(rejected_candidates=len(rejected),matched_baseline_rejections=len(known),
        avoided_losers=sum(r['baseline_outcome']=='LOSS' for r in known),
        rejected_winners=sum(r['baseline_outcome']=='WIN' for r in known),
        rejected_flats=sum(r['baseline_outcome']=='FLAT' for r in known),
        unknown_outcomes=len(rejected)-len(known),
        baseline_net_on_rejected=sum(r['baseline_net_account'] for r in known),
        new_available_entries=sum(r['policy_portfolio_accepted'] and not r['baseline_trade_exists'] for r in rows),
        retained_baseline_entries=sum(r['policy_portfolio_accepted'] and r['baseline_trade_exists'] for r in rows),
        cost_rejected_winners=sum(r['status']=='REJECT_COST' and r['baseline_outcome']=='WIN' for r in known),
        cost_avoided_losers=sum(r['status']=='REJECT_COST' and r['baseline_outcome']=='LOSS' for r in known),
        signal_rejected_winners=sum(r['status']=='REJECT_SIGNAL' and r['baseline_outcome']=='WIN' for r in known),
        signal_avoided_losers=sum(r['status']=='REJECT_SIGNAL' and r['baseline_outcome']=='LOSS' for r in known),
        interpretation='Matched baseline opportunities only; not causal effect or subtractive portfolio estimate')
