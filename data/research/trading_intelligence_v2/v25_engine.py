"""V2.5 decision-hook copy of V2.4 research replay. Simulated positions are never broker positions."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import statistics
from types import SimpleNamespace

from .core import Config, Quotes, ResearchRejected, pip_size, usd_direction, utc, iso


@dataclass(frozen=True)
class Filter:
    regime: bool = False
    max_spread_atr: float | None = None


def quality_filter(strategy, pack, i, bar, policy):
    atr = pack['atr'][i]
    if not math.isfinite(atr) or atr <= 0:
        return 'WARMUP'
    if policy.max_spread_atr is not None and (bar.ac - bar.bc) / atr > policy.max_spread_atr:
        return 'SPREAD_ATR'
    if policy.regime:
        regime = pack['regime'][i]
        want = 'RANGE' if 'mean_reversion' in strategy else 'TREND'
        if regime != want:
            return 'REGIME_UNCERTAIN_OR_MISMATCH'
    return None


def session(t):
    h = utc(t).hour
    return 'ASIA_UTC' if h < 7 else ('EUROPE_UTC' if h < 12 else ('OVERLAP_UTC' if h < 16 else 'US_UTC'))


def metrics(trades, marks=(), initial=10000):
    pnls = [t['net_account'] for t in trades]
    rs = [t['net_r'] for t in trades]
    wins, losses = [x for x in pnls if x > 0], [x for x in pnls if x < 0]
    result = dict(trades=len(trades), wins=len(wins), losses=len(losses),
                  win_rate=len(wins) / len(trades) if trades else None,
                  average_win=statistics.fmean(wins) if wins else None,
                  average_loss=statistics.fmean(losses) if losses else None,
                  expectancy_account=statistics.fmean(pnls) if pnls else None,
                  expectancy_r=statistics.fmean(rs) if rs else None,
                  profit_factor=sum(wins) / abs(sum(losses)) if losses else None,
                  profit_factor_status='DEFINED' if losses else 'NO_LOSSES_OR_NO_TRADES',
                  net_account=sum(pnls), gross_account=sum(t['gross_account'] for t in trades),
                  transaction_costs=sum(t['cost_account'] for t in trades),
                  net_return_fraction=sum(pnls) / initial,
                  gross_return_fraction=sum(t['gross_account'] for t in trades) / initial,
                  average_reward_risk=statistics.fmean(t['reward_risk'] for t in trades) if trades else None,
                  exposure_position_seconds=sum(t['duration_seconds'] for t in trades),
                  average_duration_seconds=statistics.fmean(t['duration_seconds'] for t in trades) if trades else None,
                  sharpe_annualized_daily=None, sortino_annualized_daily=None,
                  max_drawdown_account=None, max_drawdown_fraction=None)
    streak = worst = 0
    for x in pnls:
        streak = streak + 1 if x < 0 else 0
        worst = max(worst, streak)
    result['consecutive_losses'] = worst
    if marks:
        peak = initial
        dd_cash = dd_pct = 0
        days = {}
        for t, equity in marks:
            peak = max(peak, equity)
            dd_cash = max(dd_cash, peak - equity)
            dd_pct = max(dd_pct, (peak - equity) / peak)
            days[utc(t).date()] = equity
        result.update(max_drawdown_account=dd_cash, max_drawdown_fraction=dd_pct)
        returns, prev = [], initial
        for _, equity in sorted(days.items()):
            if prev > 0:
                returns.append(equity / prev - 1)
            prev = equity
        if len(returns) >= 20:
            sd = statistics.stdev(returns)
            downside = math.sqrt(statistics.fmean(min(x, 0) ** 2 for x in returns))
            result['sharpe_annualized_daily'] = statistics.fmean(returns) / sd * math.sqrt(252) if sd > 0 else None
            result['sortino_annualized_daily'] = statistics.fmean(returns) / downside * math.sqrt(252) if downside > 0 else None
        result['daily_return_observations'] = len(returns)
    return result


def run(data, packs, existing, window, *, strategy='trend', policy=Filter(), protection=False,
        config=Config(), instruments=None, weights=None, record=None, entry_geometry='atr_research',
        decision_provider=None, cost_breakdown=False, cost_trace=False, decision_evaluator=None):
    """Events: open quotes -> opening exits -> entries -> intrabar -> closes.

    No capacity or P/L from a later bar phase can fund an earlier entry. All
    candidate filters see the PREVIOUS completed bar, never the fill bar.
    """
    targets = tuple(sorted(instruments or data))
    if entry_geometry not in ('atr_research','source_default'):
        raise ResearchRejected('unknown_entry_geometry')
    events = {}
    for pair, bars in data.items():
        if config.account == 'USD' and pair not in targets:
            continue  # every supported pair has a USD leg; no other FX leg needed
        for i, bar in enumerate(bars):
            if window[0] <= bar.t < window[1]:
                events.setdefault(bar.t, {})[pair] = (i, bar)
    cash = config.initial
    positions, trades, marks, rejected = {}, [], [(window[0], cash)], {}
    quotes = Quotes()
    ambiguous = 0
    margin_breaches = 0
    peaks = dict(positions=0, same_usd_direction=0, planned_risk_fraction=0.0, margin_fraction=0.0)
    cfg = config
    fee_unit = cfg.commission_per_100k_side / 100000

    def count_reason(reason):
        rejected[reason] = rejected.get(reason, 0) + 1

    def override(pair, price, side, spread, when):
        return {pair: (when, price if side == 'BUY' else price - spread,
                       price + spread if side == 'BUY' else price)}

    def mark(when):
        value = cash
        for pair, p in positions.items():
            qt, bid, ask = quotes.book[pair]
            if not 0 <= when - qt <= 300:
                raise ResearchRejected('unpriceable_simulated_exposure')
            close = bid if p.direction == 'BUY' else ask
            pnl = p.sign * (close - p.entry_price) * p.units
            value += quotes.convert(pnl, pair.split('_')[1], cfg.account, when) - fee_unit * p.units
        return value

    def close(pair, bar, price, when, reason):
        nonlocal cash
        p = positions.pop(pair)
        # Opening/intrabar events cannot know the later closing spread.
        spread = bar.ac - bar.bc if reason == 'TIME_OR_SESSION_EXIT' else bar.ao - bar.bo
        slip = pip_size(pair) * cfg.slippage_pips
        executed = price - p.sign * slip
        if executed <= 0:
            raise ResearchRejected('nonpositive_simulated_fill')
        fx = override(pair, executed, p.direction, spread, when)
        quote = pair.split('_')[1]
        pnl = quotes.convert(p.sign * (executed - p.entry_price) * p.units, quote, cfg.account, when, override=fx)
        mid_exit = price + p.sign * spread / 2
        gross = quotes.convert(p.sign * (mid_exit - p.entry_mid) * p.units, quote, cfg.account, when, override=fx)
        fees = fee_unit * p.units
        funding = p.notional * .0001 * max(0, (utc(when).date() - utc(p.open_time).date()).days)
        cash += pnl - fees - funding
        net = pnl - p.entry_fee - fees - funding
        trade = {**p.candidate, 'entry_time': p.open_time, 'exit_time': when,
                 'entry_price': p.entry_price, 'exit_price': executed, 'units': p.units,
                 'initial_stop': p.stop_loss, 'initial_target': p.take_profit,
                 'net_account': net, 'gross_account': gross, 'cost_account': gross - net,
                 'net_r': net / p.initial_risk, 'initial_risk_account': p.initial_risk,
                 'reward_risk': cfg.reward_risk, 'duration_seconds': when - p.open_time,
                 'exit_reason': reason, 'protection': protection,
                 'protected_exit_pips': getattr(p, 'profit_protection_exit_pips', None),
                 'funding_assumption_account': funding}
        if decision_provider is not None or cost_breakdown:
            spread_cost=-quotes.convert(-(p.entry_spread+spread)*p.units/2,quote,cfg.account,when,override=fx)
            slippage_cost=-quotes.convert(-2*slip*p.units,quote,cfg.account,when,override=fx)
            trade.update(spread_cost_account=spread_cost,slippage_cost_account=slippage_cost,
                         commission_account=p.entry_fee+fees,
                         conversion_cost_residual=trade['cost_account']-spread_cost-slippage_cost-p.entry_fee-fees-funding)
        if cost_trace:
            # Observation only: no cash, sizing, trigger or execution changes.
            trade['cost_trace'] = dict(entry_mid=p.entry_mid, entry_bid=p.entry_bid,
                entry_ask=p.entry_ask, exit_mid=mid_exit,
                exit_bid=price if p.sign == 1 else price-spread,
                exit_ask=price+spread if p.sign == 1 else price,
                exit_before_slippage=price, spread_used=spread,
                exit_quote_status=('OBSERVED_CLOSE' if reason == 'TIME_OR_SESSION_EXIT' else
                    'OBSERVED_OPEN' if reason in ('STOP_GAP','SOFTWARE_PROTECTION_NEXT_OPEN','MARGIN_NEXT_OPEN') else
                    'INFERRED_FROM_TRIGGER_AND_OPEN_SPREAD_NOT_CONTEMPORANEOUS_QUOTE'),
                conversion_book=dict(quotes.book), conversion_override=fx,
                entry_fee=p.entry_fee, exit_fee=fees, account=cfg.account,
                notional_account=p.notional, margin_account=p.margin,
                slippage_price=slip)
        trades.append(trade)
        if record:
            record('trade', trade)

    def opening_exit(pair, i, b):
        p = positions[pair]
        price = b.bo if p.direction == 'BUY' else b.ao
        if b.t - p.last_bar != 300:
            close(pair, b, min(price, p.stop_loss) if p.sign == 1 else max(price, p.stop_loss),
                  b.t, 'DATA_GAP_CONSERVATIVE_STOP')
        elif p.sign * (price - p.stop_loss) <= 0:
            close(pair, b, price, b.t, 'STOP_GAP')
        elif p.sign * (price - p.take_profit) >= 0:
            close(pair, b, p.take_profit, b.t, 'TARGET_GAP_NO_IMPROVEMENT')
        elif p.pending:
            close(pair, b, price, b.t, p.pending)

    for t in sorted(events):
        group = events[t]
        for pair, (_, b) in group.items():
            quotes.put(pair, t, b.bo, b.ao)
        for pair in sorted(set(positions) & group.keys()):
            i, b = group[pair]
            opening_exit(pair, i, b)
        # Only opening quotes, prior completed features and prior equity here.
        for pair in targets:
            if pair not in group:
                continue
            i, b = group[pair]
            if i == 0 or data[pair][i - 1].t + 300 != t:
                count_reason('NO_CONTIGUOUS_COMPLETED_SIGNAL'); continue
            j = i - 1
            selected = strategy
            supplied = decision_provider(pair, t) if decision_provider is not None else None
            if decision_provider is not None and supplied is None:
                count_reason('MTF_WAIT_OR_ABSTAIN'); continue
            if supplied is not None:
                selected = supplied['strategy']
            elif strategy == 'hybrid_research':
                base = packs[pair][50]
                family = existing.hybrid_family(base['atr'][j], base['atr_median'][j])
                names = ('scalp', 'trend', 'mean_reversion') if family == 'scalp' else ('swing_trend', 'swing_mean_reversion', 'swing_breakout')
                selected = existing.select_argmax({n: (weights or {}).get(pair, {}).get(n, 1) for n in names})
            elif strategy == 'selected':
                selected = (weights or {}).get(pair)
            if selected is None:
                count_reason('TRAIN_VALIDATION_ABSTAIN'); continue
            lb = 100 if selected.startswith('swing_') else 50
            pack = supplied['pack'] if supplied is not None else packs[pair][lb]
            if supplied is not None:
                j = supplied['index']
            signal_bar = supplied['bar'] if supplied is not None else data[pair][j]
            if supplied is not None and (supplied['metadata']['signal_available_at']!=t
                    or signal_bar.t>=t or signal_bar.complete is not True
                    or type(supplied['hold_bars']) is not int or supplied['hold_bars']<1):
                raise ResearchRejected('invalid_or_future_MTF_decision')
            side, detail = existing.signal(selected, j, pack)
            if side is None:
                count_reason(str(detail)); continue
            atr = pack['atr'][j]
            stop_distance = max(cfg.stop_atr * atr, cfg.min_stop_pips * pip_size(pair))
            target_distance=stop_distance*cfg.reward_risk
            if entry_geometry=='source_default':
                stop_distance,target_distance=existing.entry_distances(pair,atr)
            candidate = {'pair': pair, 'signal_time': t, 'bar_start': signal_bar.t,
                         'strategy': selected, 'direction': side, 'signal_detail': str(detail),
                         'regime': pack['regime'][j], 'volatility': pack['volatility'][j],
                         'momentum': pack['momentum'][j], 'confidence': None,
                         'entry_reference': (signal_bar.bc + signal_bar.ac) / 2,
                         'stop_distance': stop_distance, 'target_distance': target_distance,
                         'entry_geometry':entry_geometry,
                         'spread_reference': signal_bar.ac - signal_bar.bc,
                         'slippage_pips_side': cfg.slippage_pips, 'expected_reward_risk': cfg.reward_risk,
                         'atr': atr, 'data_quality': 'COMPLETE_OBSERVED_BID_ASK', 'session': session(t)}
            if supplied is not None:
                candidate.update(supplied['metadata'])
            reason = quality_filter(selected, pack, j, signal_bar, policy)
            clock = utc(t)
            cutoff = cfg.flatten_hour_utc * 60 + cfg.flatten_minute
            if clock.weekday() >= 5 or clock.hour * 60 + clock.minute >= cutoff:
                reason = reason or 'SESSION_FLAT_WINDOW'
            if pair in positions:
                reason = reason or 'ALREADY_OPEN'
            equity = mark(t)
            if len(positions) >= cfg.max_positions:
                reason = reason or 'MAX_POSITIONS'
            direction = usd_direction(pair, side)
            if sum(usd_direction(k, p.direction) == direction for k, p in positions.items()) >= cfg.usd_slots:
                reason = reason or 'USD_DIRECTION_CAP'
            slip = cfg.slippage_pips * pip_size(pair)
            sign = 1 if side == 'BUY' else -1
            entry = (b.ao if sign == 1 else b.bo) + sign * slip
            stop, target = entry - sign * stop_distance, entry + sign * target_distance
            units, risk_unit, notional_unit = 0, None, None
            try:
                if stop <= 0 or target <= 0 or equity <= 0:
                    raise ResearchRejected('invalid_entry_geometry_or_equity')
                risk_unit = -quotes.convert(-stop_distance - slip, pair.split('_')[1], cfg.account, t,
                                           override=override(pair, stop - sign * slip, side, b.ao - b.bo, t)) + 2 * fee_unit
                notional_unit = -quotes.convert(-1, pair.split('_')[0], cfg.account, t)
                remaining_risk = cfg.portfolio_risk * equity - sum(p.initial_risk for p in positions.values())
                remaining_margin = cfg.margin_fraction * equity - sum(p.margin for p in positions.values())
                units = math.floor(max(0, min(cfg.risk_fraction * equity / risk_unit,
                                  remaining_risk / risk_unit, remaining_margin * cfg.leverage / notional_unit)))
                if units <= 0:
                    reason = reason or 'RISK_OR_MARGIN_SIZE_ZERO'
            except ResearchRejected as exc:
                reason = reason or str(exc)
            if decision_evaluator is not None:
                decision = decision_evaluator(pair=pair, when=t, side=side,
                    signal_bar=signal_bar, pack=pack, index=j, bar=b,
                    stop_distance=stop_distance, target_distance=target_distance,
                    units=units, quotes=quotes, config=cfg, candidate=candidate,
                    baseline_reason=reason)
                candidate['quality_decision'] = decision
                if reason is None and decision['status'] != 'ACCEPT':
                    reason = 'QUALITY_' + decision['status'] + ':' + decision['reason']
            if reason:
                count_reason(reason)
                if record:
                    record('candidate', {**candidate, 'accepted': False, 'reason': reason})
                continue
            candidate.update(accepted=True, reason='ACCEPTED')
            if record:
                record('candidate', candidate)
            p = SimpleNamespace(symbol=pair, direction=side, sign=sign, units=units,
                                entry_price=entry, entry_mid=(b.bo + b.ao) / 2,
                                stop_loss=stop, take_profit=target, open_time=t, last_bar=t - 300,
                                entry_fee=fee_unit * units, initial_risk=risk_unit * units,
                                notional=notional_unit * units, margin=notional_unit * units / cfg.leverage,
                                max_profit_pips=0.0, pending=None, candidate=candidate)
            p.hold_bars = supplied['hold_bars'] if supplied is not None else cfg.max_hold_bars
            p.entry_spread=b.ao-b.bo
            if cost_trace:
                p.entry_bid, p.entry_ask = b.bo, b.ao
            cash -= p.entry_fee
            positions[pair] = p
            peaks['positions'] = max(peaks['positions'], len(positions))
            peaks['same_usd_direction'] = max(peaks['same_usd_direction'], max(
                sum(usd_direction(k, v.direction) == side for k, v in positions.items()) for side in ('LONG', 'SHORT')))
            peaks['planned_risk_fraction'] = max(peaks['planned_risk_fraction'], sum(v.initial_risk for v in positions.values()) / equity)
            peaks['margin_fraction'] = max(peaks['margin_fraction'], sum(v.margin for v in positions.values()) / equity)
        # Intrabar events cannot release capital for the entries just processed.
        for pair in sorted(set(positions) & group.keys()):
            i, b = group[pair]
            p = positions[pair]
            stop_hit = b.bl <= p.stop_loss if p.sign == 1 else b.ah >= p.stop_loss
            target_hit = b.bh >= p.take_profit if p.sign == 1 else b.al <= p.take_profit
            if stop_hit:
                ambiguous += int(target_hit)
                close(pair, b, p.stop_loss, t + 300, 'STOP_FIRST_AMBIGUOUS' if target_hit else 'STOP')
            elif target_hit:
                close(pair, b, p.take_profit, t + 300, 'TARGET')
        for pair, (_, b) in group.items():
            quotes.put(pair, t + 300, b.bc, b.ac)
        for pair in sorted(set(positions) & group.keys()):
            i, b = group[pair]
            p = positions[pair]
            clock = utc(t + 300)
            if (clock.hour * 60 + clock.minute >= cfg.flatten_hour_utc * 60 + cfg.flatten_minute
                    or t + 300 - p.open_time >= p.hold_bars * 300 or t + 300 >= window[1]):
                close(pair, b, b.bc if p.sign == 1 else b.ac, t + 300, 'TIME_OR_SESSION_EXIT')
                continue
            if protection:
                extreme = b.bh if p.sign == 1 else b.al
                p.max_profit_pips = max(p.max_profit_pips, p.sign * (extreme - p.entry_price) / pip_size(pair))
                pack = packs[pair][100 if p.candidate['strategy'].startswith('swing_') else 50]
                atr14 = pack['atr14'][i]
                decision = existing.protection(p, b.bc if p.sign == 1 else b.ac,
                                               atr_price=atr14 if math.isfinite(atr14) else None)
                if decision.should_close:
                    p.pending = 'SOFTWARE_PROTECTION_NEXT_OPEN'
            p.last_bar = t
        equity = mark(t + 300)
        if sum(p.margin for p in positions.values()) > equity:
            margin_breaches += 1
            for p in positions.values():
                p.pending = 'MARGIN_NEXT_OPEN'
        marks.append((t + 300, equity))
    if positions:
        # Missing end quotes must not erase exposure or manufacture a final fill.
        raise ResearchRejected('unliquidated_end_exposure')
    if not math.isclose(cash - cfg.initial, sum(t['net_account'] for t in trades), abs_tol=1e-6):
        raise ResearchRejected('cash_ledger_mismatch')
    result = metrics(trades, marks, cfg.initial)
    result.update(ambiguous_stop_first=ambiguous, margin_breach_events=margin_breaches,
                  peak_entry_allocation=peaks,
                  rejections=rejected, account_currency=cfg.account, status='SIMULATED_NOT_BROKER')
    return {'metrics': result, 'trades': trades, 'equity': marks}
