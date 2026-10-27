"""Independent Decimal arithmetic for the research engine's cost trace.

Costs are positive debits, all reported components are in account currency.
Waterfall differences handle sign-dependent FX without pretending conversion is
linear across zero. This module provides no broker or production authority.
"""
from decimal import Decimal, localcontext
import hashlib
import json
import math

from .core import ResearchRejected

TOLERANCE_ACCOUNT = 1e-7  # < 0.00001 of a USD/GBP penny; float replay roundoff only.


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ResearchRejected('invalid_ledger_number')
    return Decimal(str(value))


def convert(amount, source, target, when, book):
    """Independent implementation of baseline 300-second signed bid/ask graph."""
    amount = number(amount) if not isinstance(amount, Decimal) else amount
    if not amount.is_finite():
        raise ResearchRejected('invalid_ledger_number')
    if source == target:
        return amount
    edges = {}
    for pair, (t, bid, ask) in sorted(book.items()):
        bid, ask = number(bid), number(ask)
        if not 0 < bid <= ask:
            raise ResearchRejected('invalid_ledger_quote')
        if not 0 <= when-t <= 300:
            continue
        base, quote = pair.split('_')
        edges.setdefault(base, []).append((quote, bid if amount >= 0 else ask))
        edges.setdefault(quote, []).append((base, 1/(ask if amount >= 0 else bid)))
    queue = [(source, amount, {source})]
    for ccy, value, seen in queue:
        for nxt, rate in edges.get(ccy, []):
            if nxt in seen:
                continue
            if nxt == target:
                return value*rate
            queue.append((nxt, value*rate, seen | {nxt}))
    raise ResearchRejected('ledger_conversion_unavailable_or_stale')


def fee_account(units, rate_per_100k_side, fee_currency, account, when, book):
    """Explicit hypothetical fee, one side; no minimum or broker rate implied."""
    if number(units) <= 0 or number(rate_per_100k_side) < 0:
        raise ResearchRejected('invalid_fee')
    return -convert(-number(units)*number(rate_per_100k_side)/100000,
                    fee_currency, account, when, book)


def reconcile(trade, *, tolerance=TOLERANCE_ACCOUNT):
    """Recompute P/L from fills, never define residual as an untested balancing fee."""
    x = trade['cost_trace']
    with localcontext() as ctx:
        ctx.prec = 40
        sign = 1 if trade['direction'] == 'BUY' else -1
        if trade['direction'] not in ('BUY', 'SELL'):
            raise ResearchRejected('invalid_ledger_direction')
        n = number(trade['units'])
        if n <= 0:
            raise ResearchRejected('invalid_ledger_units')
        quote = trade['pair'].split('_')[1]
        book = {**x['conversion_book'], **x['conversion_override']}
        def fx(amount):
            return convert(amount, quote, x['account'], trade['exit_time'], book)
        entry_mid, exit_mid = number(x['entry_mid']), number(x['exit_mid'])
        entry_quote = number(x['entry_ask'] if sign == 1 else x['entry_bid'])
        exit_quote = number(x['exit_before_slippage'])
        entry_fill, exit_fill = number(trade['entry_price']), number(trade['exit_price'])
        slip = number(x['slippage_price'])
        if abs(entry_fill-(entry_quote+sign*slip)) > Decimal('1e-10') or abs(exit_fill-(exit_quote-sign*slip)) > Decimal('1e-10'):
            raise ResearchRejected('fill_slippage_inconsistent')
        gross_quote = sign*(exit_mid-entry_mid)*n
        bidask_quote = sign*(exit_quote-entry_quote)*n
        filled_quote = sign*(exit_fill-entry_fill)*n
        gross, bidask, filled = fx(gross_quote), fx(bidask_quote), fx(filled_quote)
        commission = number(x['entry_fee'])+number(x['exit_fee'])
        funding = number(trade['funding_assumption_account'])
        net = filled-commission-funding
        residual = number(trade['net_account'])-net
        gross_residual = number(trade['gross_account'])-gross
        if max(abs(residual), abs(gross_residual)) > number(tolerance):
            raise ResearchRejected('cost_ledger_reconciliation_failed')
        identity = [trade['pair'], trade['direction'], trade['entry_time'], trade['exit_time'], trade['units']]
        return dict(trade_id=hashlib.sha256(json.dumps(identity).encode()).hexdigest(),
            instrument=trade['pair'], direction=trade['direction'], units=trade['units'],
            entry_timestamp=trade['entry_time'], exit_timestamp=trade['exit_time'],
            entry_mid=float(entry_mid), entry_bid=x['entry_bid'], entry_ask=x['entry_ask'],
            entry_fill=float(entry_fill), exit_mid=float(exit_mid), exit_bid=x['exit_bid'],
            exit_ask=x['exit_ask'], exit_fill=float(exit_fill), exit_quote_status=x['exit_quote_status'],
            gross_quote=float(gross_quote), bidask_quote=float(bidask_quote), filled_quote=float(filled_quote),
            quote_currency=quote, gross_account=float(gross), bidask_account=float(bidask),
            execution_account=float(filled), spread_attribution_account=float(gross-bidask),
            slippage_attribution_account=float(bidask-filled), commission_account=float(commission),
            financing_account=float(funding), net_account=float(net), account_currency=x['account'],
            conversion=dict(model='SIGNED_BID_ASK_300S_NOT_OANDA_SETTLEMENT', book=book,
                            applied_override=x['conversion_override']),
            reconciliation_residual=float(residual), gross_residual=float(gross_residual),
            status='RECONCILED_RESEARCH_ASSUMPTIONS', tolerance_account=tolerance)
