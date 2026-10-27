"""Passive trade evidence. Outcome tags are hypotheses, never proven causes."""
from bisect import bisect_left
import math
import statistics
from .core import pip_size,utc
from .timeframes import DURATIONS,last_completed
from .mtf_features import trend_state

INTRABAR={'STOP','STOP_FIRST_AMBIGUOUS','TARGET'}


class ProtectionObserver:
    """Delegate unchanged original source; observe only disposable simulation objects."""
    def __init__(self,existing): self.existing=existing; self.events={}
    def __getattr__(self,name): return getattr(self.existing,name)
    def protection(self,p,price,*,atr_price=None):
        result=self.existing.protection(p,price,atr_price=atr_price)
        key=(p.symbol,p.open_time,p.candidate['strategy'])
        self.events.setdefault(key,[]).append(dict(available_at=p.last_bar+600,
            active=getattr(p,'profit_protection_active',False),
            observed_MFE_pips=p.max_profit_pips,protected_exit_pips=getattr(p,'profit_protection_exit_pips',None),
            should_close=result.should_close))
        return result


def excursions(trade,bars,times=None):
    sign=1 if trade['direction']=='BUY' else -1; pip=pip_size(trade['pair']); entry=trade['entry_price']
    times=times if times is not None else [b.t for b in bars]; a=bisect_left(times,trade['entry_time'])
    end=trade['exit_time']; partial=trade['exit_reason'] in INTRABAR
    stop=bisect_left(times,end)
    held=bars[a:stop]
    closing_at_end=trade['exit_reason']=='TIME_OR_SESSION_EXIT'
    complete=held[:-1] if partial else held
    fav=max([0.0,sign*(trade['exit_price']-entry)/pip]+[
        sign*((b.bh if sign==1 else b.al)-entry)/pip for b in complete])
    adverse=max([0.0,-sign*(trade['exit_price']-entry)/pip]+[
        -sign*((b.bl if sign==1 else b.ah)-entry)/pip for b in complete])
    upper_f=max([fav]+[sign*((b.bh if sign==1 else b.al)-entry)/pip for b in held])
    upper_a=max([adverse]+[-sign*((b.bl if sign==1 else b.ah)-entry)/pip for b in held])
    gap=any(y.t-x.t!=300 for x,y in zip(held,held[1:])) or 'GAP' in trade['exit_reason']
    status='UNKNOWN_BETWEEN_OBSERVATIONS' if gap else ('OHLC_BOUNDS_EXIT_ORDER_UNKNOWN' if partial else 'COMPLETE_BAR_EXTREMA_UNDER_REPLAY_CLOCK')
    return dict(MFE_lower_pips=fav,MFE_upper_pips=None if gap else upper_f,
                MAE_lower_pips=adverse,MAE_upper_pips=None if gap else upper_a,excursion_status=status,
                exit_bar_order='UNKNOWN' if partial else 'OPEN_OR_CLOSE_BY_REPLAY_RULE')


def diagnose(trade,tf,bars,frames,packs,events=(),times=None,holding_limit_seconds=None,fold_end=None):
    t=dict(trade); sign=1 if t['direction']=='BUY' else -1
    context={}
    exit_context={}
    for h in ('H1','H4'):
        i=last_completed(frames[h],h,t['entry_time'])
        context[h]=trend_state(packs[h][50],i)
        reference=t['exit_time']-300 if t['exit_reason'] in INTRABAR else t['exit_time']
        j=last_completed(frames[h],h,reference)
        exit_context[h]=trend_state(packs[h][50],j)
    tags=[]
    if t['gross_account']<0: tags.append('NEGATIVE_GROSS_OUTCOME_DIRECTION_OR_EXIT')
    if t['gross_account']>0 and t['net_account']<0: tags.append('COSTS_OVERWHELM_POSITIVE_GROSS')
    if t['spread_reference']/t['atr']>.25: tags.append('SPREAD_EXCEEDS_QUARTER_ENTRY_ATR')
    if t['stop_distance']<t['atr']: tags.append('STOP_INSIDE_ONE_ENTRY_ATR')
    if t['target_distance']>=4*t['atr']-1e-12: tags.append('TARGET_AT_LEAST_FOUR_ENTRY_ATR')
    if t['exit_reason'].startswith('STOP') and t['duration_seconds']<=DURATIONS[tf]: tags.append('STOP_WITHIN_ONE_ENTRY_BAR')
    if any(v in ('BUY','SELL') and v!=t['direction'] for v in context.values()): tags.append('ENTRY_AGAINST_KNOWN_HIGHER_TREND')
    if any(context[h]==t['direction'] and exit_context[h] in ('BUY','SELL') and exit_context[h]!=t['direction'] for h in context):
        tags.append('OBSERVED_HIGHER_CONTEXT_REVERSAL_BEFORE_EXIT')
    if t['volatility']=='HIGH': tags.append('ENTRY_VOLATILITY_EXPANSION_TAG')
    if t['volatility']=='LOW' and abs(t['gross_account']/t['initial_risk_account'])<.25: tags.append('LOW_VOLATILITY_SMALL_GROSS_OUTCOME')
    if 'GAP' in t['exit_reason']: tags.append('DATA_OR_OPENING_GAP_MODEL')
    if 'breakout' in t['strategy'] and t['exit_reason'].startswith('STOP'): tags.append('BREAKOUT_RULE_STOP_OUT')
    exit_kind=t['exit_reason']
    exit_triggers=[]
    if exit_kind=='TIME_OR_SESSION_EXIT':
        clock=utc(t['exit_time'])
        if (clock.hour,clock.minute)==(20,55):
            exit_triggers.append('FRIDAY_FLATTEN' if clock.weekday()==4 else 'DAILY_SESSION_FLATTEN')
        if holding_limit_seconds is not None and t['duration_seconds']>=holding_limit_seconds: exit_triggers.append('HOLDING_TIMEOUT')
        if fold_end is not None and t['exit_time']>=fold_end: exit_triggers.append('FOLD_BOUNDARY_FLATTEN')
        exit_kind='|'.join(exit_triggers) if exit_triggers else 'HOLD_LIMIT_OR_FOLD_BOUNDARY'
        tags.extend(exit_triggers or [exit_kind])
    if t['exit_reason']=='SOFTWARE_PROTECTION_NEXT_OPEN': tags.append('LOCAL_PROTECTION_GIVEBACK_EXIT')
    if not tags or t['net_account']<0: tags.append('UNDETERMINED_CAUSAL_CONTRIBUTION')
    movement=sign*(t['exit_price']-t['entry_price'])/pip_size(t['pair'])
    t.update(excursions(t,bars,times),timeframe=tf,higher_context_at_entry=context,higher_context_before_exit=exit_context,diagnostic_tags=tags,
             exit_diagnostic=exit_kind,gross_R=t['gross_account']/t['initial_risk_account'],
             exit_rule_triggers=exit_triggers,
             protection_activation_observed=any(e['active'] for e in events) if t['protection'] else None,
             protection_management_observations=list(events),captured_price_move_pips=movement,
             turnover_account_usd=(2*t['units'] if t['pair'].startswith('USD_') else t['units']*(t['entry_price']+t['exit_price'])),
             diagnostic_use='POST_TRADE_ONLY_NOT_SELECTION_FEATURES')
    t['giveback_lower_pips']=max(0,t['MFE_lower_pips']-movement)
    t['giveback_upper_pips']=max(0,t['MFE_upper_pips']-movement) if t['MFE_upper_pips'] is not None else None
    return t


def cost_summary(trades):
    if not trades:
        return dict(trades=0,gross_expectancy_R=None,net_expectancy_R=None,cost_class='INSUFFICIENT_EVIDENCE')
    gross=statistics.fmean(t['gross_R'] for t in trades); net=statistics.fmean(t['net_r'] for t in trades)
    classification=('NEGATIVE_GROSS_AND_COST_DRAG' if gross<0 else
                    ('FLAT_GROSS_WITH_COST_DRAG' if gross==0 and net<0 else
                     ('FLAT_SAMPLE_NO_EDGE' if gross==0 else
                      ('POSITIVE_GROSS_OVERWHELMED_BY_COSTS' if net<0 else
                       ('POSITIVE_GROSS_NET_BREAK_EVEN' if net==0 else 'POSITIVE_SAMPLE_NET_NOT_PROOF')))))
    return dict(trades=len(trades),gross_expectancy_R=gross,net_expectancy_R=net,
        gross_expectancy_account=statistics.fmean(t['gross_account'] for t in trades),
        net_expectancy_account=statistics.fmean(t['net_account'] for t in trades),
        gross_net_difference_account=statistics.fmean(t['cost_account'] for t in trades),
        spread_account=sum(t['spread_cost_account'] for t in trades),slippage_account=sum(t['slippage_cost_account'] for t in trades),
        commission_account=sum(t['commission_account'] for t in trades),funding_account=sum(t['funding_assumption_account'] for t in trades),
        conversion_residual=sum(t['conversion_cost_residual'] for t in trades),
        average_holding_seconds=statistics.fmean(t['duration_seconds'] for t in trades),
        turnover_account_usd=sum(t['turnover_account_usd'] for t in trades),
        realised_gross_positive_fraction=sum(t['gross_account']>0 for t in trades)/len(trades),
        cost_class=classification)
