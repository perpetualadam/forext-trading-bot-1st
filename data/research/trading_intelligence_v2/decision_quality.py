"""Causal research decisions. No broker imports, learned probabilities or authority."""
from dataclasses import dataclass, asdict
import math
from .core import PAIRS, STRATEGIES, ResearchRejected, pip_size
from .cost_ledger import convert, fee_account


@dataclass(frozen=True)
class Pricing:
    name: str = 'OBSERVED_BID_ASK_ONLY'
    slippage_pips_side: float = 0
    commission_account_per_100k_side: float = 0
    applicability_verified: bool = False
    hypothetical: bool = True


@dataclass(frozen=True)
class Policy:
    name: str
    spread_atr_limit: float | None = None
    cost_target_limit: float | None = None
    require_context: bool = False
    available: bool = True

    def __post_init__(self):
        for x in (self.spread_atr_limit,self.cost_target_limit):
            if x is not None and (type(x) not in (int,float) or not math.isfinite(x) or x<=0):
                raise ResearchRejected('invalid_policy_threshold')


@dataclass(frozen=True)
class Request:
    instrument: str
    direction: str
    decision_time: int
    feature_available_at: int
    feature_complete: bool
    quote_time: int
    bid: float
    ask: float
    atr: float
    stop_distance: float
    target_distance: float
    horizon_seconds: int
    pricing: Pricing
    account: str
    strategy: str
    regime: str
    contexts: tuple = ()  # (timeframe, state, completion time, duration seconds)
    data_quality: str = 'COMPLETE_OBSERVED_BID_ASK'
    units: int = 1
    momentum: str = 'UNKNOWN'
    volatility: str = 'UNKNOWN'


def evaluate(request,policy,book):
    """No outcome argument exists. Outputs include every cost input for audit."""
    r=request
    def safe(value):
        if type(value) is float and not math.isfinite(value): return None
        if isinstance(value,dict): return {k:safe(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)): return [safe(v) for v in value]
        if value is None or type(value) in (str,int,float,bool): return value
        return {'invalid_type':type(value).__name__}
    result=dict(status='REJECT_DATA',reason='INVALID_INPUT',policy=policy.name,
                inputs=safe(asdict(r)),metrics=None)
    def reject(status,reason):
        return dict(result,status=status,reason=reason)
    numbers=(r.bid,r.ask,r.atr,r.stop_distance,r.target_distance,
             r.pricing.slippage_pips_side,r.pricing.commission_account_per_100k_side)
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in numbers):
        return reject('REJECT_DATA','MISSING_OR_NONFINITE')
    if (r.instrument not in PAIRS or r.direction not in ('BUY','SELL') or
        any(type(x) is not int for x in (r.decision_time,r.feature_available_at,r.quote_time,r.horizon_seconds)) or
        r.data_quality!='COMPLETE_OBSERVED_BID_ASK' or r.feature_complete is not True or
        r.atr<=0 or not 0<r.bid<=r.ask or
        not 0<=r.decision_time-r.quote_time<=300 or
        not 0<=r.decision_time-r.feature_available_at<300):
        return reject('REJECT_DATA','INVALID_OR_STALE_CAUSAL_INPUT')
    if r.strategy not in STRATEGIES:
        return reject('REJECT_SIGNAL','UNKNOWN_STRATEGY')
    if r.stop_distance<=0 or r.target_distance<=0 or type(r.units) is not int or r.units<=0:
        return reject('REJECT_RISK','INVALID_GEOMETRY_OR_CAPACITY')
    if r.pricing.slippage_pips_side<0 or r.pricing.commission_account_per_100k_side<0:
        return reject('REJECT_DATA','NEGATIVE_COST')
    if r.horizon_seconds<=0 or r.horizon_seconds>=86400:
        return reject('ABSTAIN_UNCERTAIN','HOLDING_FINANCING_NOT_SUPPORTED')
    if r.pricing.name not in ('OBSERVED_BID_ASK_ONLY','DOCUMENTED_SPREAD_ONLY',
                               'DOCUMENTED_COMMISSION_PLAN','HYPOTHETICAL_BASELINE','HYPOTHETICAL_STRESS'):
        return reject('ABSTAIN_UNCERTAIN','UNKNOWN_PRICING')
    if r.pricing.name.startswith('DOCUMENTED_') and r.pricing.applicability_verified is not True:
        return reject('ABSTAIN_UNCERTAIN','PRICING_APPLICABILITY_UNVERIFIED')
    if r.pricing.name=='OBSERVED_BID_ASK_ONLY' and (r.pricing.slippage_pips_side or r.pricing.commission_account_per_100k_side):
        return reject('REJECT_DATA','MISLABELLED_OBSERVED_ONLY')
    try:
        spread=r.ask-r.bid; slip=pip_size(r.instrument)*r.pricing.slippage_pips_side
        quote=r.instrument.split('_')[1]
        # Only the request's causal quote can value its own instrument.
        causal_book=dict(book); causal_book[r.instrument]=(r.quote_time,r.bid,r.ask)
        def liability(x): return float(-convert(-x,quote,r.account,r.decision_time,causal_book))
        spread_account=liability(spread*r.units)
        slip_account=liability(2*slip*r.units)
        commission=float(2*fee_account(r.units,r.pricing.commission_account_per_100k_side,
                                       r.account,r.account,r.decision_time,causal_book))
        cost=spread_account+slip_account+commission
        stop=liability(r.stop_distance*r.units); target=liability(r.target_distance*r.units)
        result['metrics']=dict(spread_pips=spread/pip_size(r.instrument),spread_atr=spread/r.atr,
            spread_stop=spread/r.stop_distance,spread_target=spread/r.target_distance,
            spread_account=spread_account,slippage_account=slip_account,commission_account=commission,
            estimated_round_trip_account=cost,cost_r=cost/stop,cost_target=cost/target,
            break_even_win_rate=(stop+cost)/(stop+target),account=r.account,
            expected_gross_movement=None,financing='NOT_ESTIMATED_INTRADAY_FLATTEN_ASSUMED',
            model='CURRENT_SPREAD_AND_SPOT_LIABILITY_CONVERSION_PROXY',
            payoff_assumption='Mid-reference binary +target/-stop with fixed round-trip debit; not fill-anchored engine payoff',
            forecast_status='TARGET_IS_NOT_A_FORECAST')
        if any(type(v) is float and not math.isfinite(v) for v in result['metrics'].values()):
            result['metrics']=None
            return reject('REJECT_DATA','NONFINITE_COST_ARITHMETIC')
    except (ResearchRejected,ValueError,TypeError,OverflowError,ZeroDivisionError):
        return reject('REJECT_DATA','CONVERSION_OR_ARITHMETIC_UNAVAILABLE')
    if not policy.available:
        return reject('ABSTAIN_UNCERTAIN','FRESH_VALIDATION_REQUIRED')
    if policy.require_context:
        if (type(r.contexts) is not tuple or any(type(x) is not tuple or len(x)!=4 for x in r.contexts)
            or any(type(x[0]) is not str for x in r.contexts) or len(r.contexts)!=3 or {x[0] for x in r.contexts}!={'M15','H1','H4'}):
            return reject('ABSTAIN_UNCERTAIN','MISSING_CONTEXT')
        for tf,state,completed,duration in r.contexts:
            if (type(completed) is not int or type(duration) is not int or duration!={'M15':900,'H1':3600,'H4':14400}[tf] or
                not 0<=r.decision_time-completed<duration or state=='INSUFFICIENT_DATA'):
                return reject('ABSTAIN_UNCERTAIN','INCOMPLETE_OR_STALE_CONTEXT')
            if state!=r.direction:
                return reject('REJECT_SIGNAL','HIGHER_TIMEFRAME_NOT_CONFIRMED')
    if policy.spread_atr_limit is not None and spread/r.atr>policy.spread_atr_limit:
        return reject('REJECT_COST','SPREAD_ATR_LIMIT')
    if policy.cost_target_limit is not None and cost/target>policy.cost_target_limit:
        return reject('REJECT_COST','COST_TARGET_LIMIT')
    return reject('ACCEPT','HEURISTIC_PASSED_NOT_PREDICTED_EDGE')
