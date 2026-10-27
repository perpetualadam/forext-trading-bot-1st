"""Synthetic cost oracles exercised through the isolated research runner."""
from dataclasses import replace
from decimal import Decimal
import json
import math
import unittest

from .cost_ledger import reconcile, convert, fee_account, TOLERANCE_ACCOUNT
from .core import PAIRS, Config, Quotes, ResearchRejected, features, pip_size
from .v24_engine import run
from .test_contract import bar, Forced, T

def replay(bars, side='BUY', **kwargs):
    pack=features([bar(i) for i in range(60)],50)
    pack={k:([v[-1]]*len(bars) if isinstance(v,list) else len(bars)) for k,v in pack.items()}
    return run({'EUR_USD':bars},{'EUR_USD':{50:pack,100:pack}},Forced(side),
               (bars[1].t,bars[-1].t+300),**kwargs)


def one(side='BUY', spread=.0002, end=None, **cfg):
    bars = [bar(0, spread=spread), bar(1, spread=spread)]
    if end is not None:
        bars.append(end)
    return replay(bars, side, config=replace(Config(), **cfg), cost_trace=True, cost_breakdown=True)['trades'][0]


class LedgerTests(unittest.TestCase):
    def test_flat_buy(self):
        t=one(slippage_pips=0, commission_per_100k_side=0)
        self.assertAlmostEqual(t['net_account'], -.0002*t['units'])
        self.assertAlmostEqual(reconcile(t)['spread_attribution_account'], .0002*t['units'])

    def test_flat_sell(self):
        t=one('SELL', slippage_pips=0, commission_per_100k_side=0)
        self.assertAlmostEqual(t['net_account'], -.0002*t['units'])
        reconcile(t)

    def test_zero_cost(self):
        t=one(spread=0, slippage_pips=0, commission_per_100k_side=0)
        self.assertEqual(t['net_account'], 0)
        self.assertEqual(reconcile(t)['net_account'], 0)

    def test_commission_per_side(self):
        t=one(spread=0, slippage_pips=0, commission_per_100k_side=7)
        self.assertAlmostEqual(-t['net_account'], t['units']*14/100000)
        self.assertAlmostEqual(reconcile(t)['commission_account'], t['units']*14/100000)

    def test_double_spread_negative_control(self):
        t=one(); t['net_account']-=.0002*t['units']
        with self.assertRaisesRegex(ResearchRejected, 'reconciliation'): reconcile(t)

    def test_double_commission_negative_control(self):
        t=one(); t['net_account']-=t['commission_account']
        with self.assertRaisesRegex(ResearchRejected, 'reconciliation'): reconcile(t)

    def test_wrong_gross(self):
        t=one(); t['gross_account']+=1
        with self.assertRaisesRegex(ResearchRejected, 'reconciliation'): reconcile(t)

    def test_unknown_not_zero(self):
        t=one(); t['cost_trace']['entry_fee']=None
        with self.assertRaises(ResearchRejected): reconcile(t)

    def test_tolerance(self):
        t=one(); t['net_account']+=TOLERANCE_ACCOUNT/2; reconcile(t)
        t['net_account']+=TOLERANCE_ACCOUNT*2
        with self.assertRaises(ResearchRejected): reconcile(t)

    def test_reproducible(self): self.assertEqual(reconcile(one()), reconcile(one()))

    def test_trace_observation_only(self):
        bars=[bar(i) for i in range(5)]
        a=replay(bars, cost_breakdown=True); b=replay(bars, cost_trace=True, cost_breakdown=True)
        self.assertEqual(a['metrics'], b['metrics']); self.assertEqual(a['equity'], b['equity'])
        for t in b['trades']: t.pop('cost_trace')
        self.assertEqual(a['trades'], b['trades'])

    def test_foreign_fee(self):
        book={'GBP_USD':(T,1.25,1.26)}
        self.assertEqual(fee_account(100000, 3, 'USD','GBP',T,book),Decimal(3)/Decimal('1.25'))

    def test_missing_fee_conversion(self):
        with self.assertRaises(ResearchRejected): fee_account(100000,3,'USD','GBP',T,{})

    def test_missing_conversion(self):
        with self.assertRaises(ResearchRejected): convert(1,'JPY','GBP',T,{})

    def test_stale_conversion(self):
        with self.assertRaises(ResearchRejected): convert(1,'USD','GBP',T+301,{'GBP_USD':(T,1.2,1.3)})

    def test_future_conversion(self):
        with self.assertRaises(ResearchRejected): convert(1,'USD','GBP',T-1,{'GBP_USD':(T,1.2,1.3)})

    def test_boundary_conversion(self):
        self.assertEqual(convert(13,'USD','GBP',T+300,{'GBP_USD':(T,1.2,1.3)}),10)

    def test_invalid_fill(self):
        t=one(); t['entry_price']+=.001
        with self.assertRaisesRegex(ResearchRejected,'slippage'): reconcile(t)

    def test_intrabar_unknown(self):
        t=one(end=bar(2,high=1.11,low=1.09))
        self.assertEqual(t['exit_reason'],'STOP_FIRST_AMBIGUOUS')
        self.assertIn('NOT_CONTEMPORANEOUS',reconcile(t)['exit_quote_status'])

    def test_weekend_gap(self):
        t=one(end=replace(bar(2,price=1.09),t=T+172800))
        self.assertEqual(t['exit_reason'],'DATA_GAP_CONSERVATIVE_STOP'); reconcile(t)

    def test_hold_exit(self):
        t=one(max_hold_bars=1)
        self.assertEqual(t['exit_reason'],'TIME_OR_SESSION_EXIT'); reconcile(t)

    def test_financing_labelled(self):
        t=one(end=replace(bar(2,price=1.09),t=T+172800))
        self.assertGreater(reconcile(t)['financing_account'],0)

    def test_no_network(self):
        import sys
        with self.assertRaises(PermissionError): sys.audit('socket.connect',None,None)

    def test_no_journal(self):
        with self.assertRaises(PermissionError): (ROOT/'production.sqlite3').read_bytes()

    def test_no_credentials(self):
        with self.assertRaises(PermissionError): (ROOT/'.env').read_bytes()

    def test_no_enablement(self):
        from . import PRODUCTION_AUTHORISED
        self.assertFalse(PRODUCTION_AUTHORISED)
        with self.assertRaises(PermissionError): (ROOT/'live.permit').write_text('never')

    def test_v24_write_scope(self):
        with self.assertRaises(PermissionError): (ROOT/'data/research/trading_intelligence_v2/reports/v23/never.txt').write_text('never')


def case(side, spread, endspread, move, slip):
    def test(self):
        end=bar(2,price=1.1+move,spread=endspread)
        t=one(side,spread,end,slippage_pips=slip,commission_per_100k_side=0,min_stop_pips=20)
        ledger=reconcile(t); s=1 if side=='BUY' else -1
        self.assertAlmostEqual(t['entry_price'],1.1+s*(spread/2+slip*.0001))
        self.assertAlmostEqual(t['exit_price'],1.1+move-s*(endspread/2+slip*.0001))
        self.assertAlmostEqual(t['net_account'],(s*move-(spread+endspread)/2-2*slip*.0001)*t['units'])
        self.assertLessEqual(abs(ledger['reconciliation_residual']),TOLERANCE_ACCOUNT)
    return test

for side in ('BUY','SELL'):
    for name,sp,ep,move,slip in (
        ('fixed',.0002,.0002,0,0),('variable',.0002,.0001,0,0),
        ('widen',.0002,.0006,0,0),('positive',.0002,.0002,.0001,0),
        ('negative',.0002,.0002,-.0001,0),('slip',.0002,.0002,0,.2),
        ('stress',.0002,.0002,0,1)):
        setattr(LedgerTests,'test_'+side+'_'+name,case(side,sp,ep,move,slip))


def pair_case(pair,side,account):
    def test(self):
        price={'EUR_USD':1.1,'GBP_USD':1.25,'AUD_USD':.65,'USD_JPY':150,'USD_CAD':1.35,'USD_CHF':.9}[pair]
        pip=pip_size(pair); s=1 if side=='BUY' else -1
        def b(i,p):
            return bar(i,price=p,spread=2*pip,high=p+pip,low=p-pip)
        bars=[b(0,price),b(1,price),b(2,price+s*pip)]
        data={pair:bars}
        if account=='GBP' and pair!='GBP_USD': data['GBP_USD']=[bar(i,price=1.25) for i in range(3)]
        pack=features([bar(i,high=1.102,low=1.098) for i in range(60)],50)
        pack={k:([v[-1]]*3 if isinstance(v,list) else 3) for k,v in pack.items()}
        packs={p:{50:pack,100:pack} for p in data}
        cfg=replace(Config(),account=account,slippage_pips=.2)
        r=run(data,packs,Forced(side),(bars[1].t,bars[-1].t+300),config=cfg,
              instruments=[pair],cost_trace=True,cost_breakdown=True)
        self.assertEqual(len(r['trades']),1)
        t=r['trades'][0]; l=reconcile(t)
        self.assertEqual(pip,.01 if pair=='USD_JPY' else .0001)
        expected_quote=s*(t['exit_price']-t['entry_price'])*t['units']
        self.assertAlmostEqual(l['filled_quote'],expected_quote)
        self.assertLessEqual(t['initial_risk_account'],cfg.initial*cfg.risk_fraction+1e-8)
        self.assertLessEqual(t['cost_trace']['margin_account'],cfg.initial*cfg.margin_fraction)
        book=t['cost_trace']['conversion_book']|t['cost_trace']['conversion_override']
        # Pip value is quote units per pip, then signed executable conversion.
        pipvalue=-convert(-Decimal(str(pip))*t['units'],pair.split('_')[1],account,t['exit_time'],book)
        self.assertGreater(pipvalue,0)
    return test

for pair in PAIRS:
    for side in ('BUY','SELL'):
        for account in ('USD','GBP'):
            setattr(LedgerTests,'test_'+pair+'_'+side+'_'+account,pair_case(pair,side,account))

from .test_v24_execution import EndpointTests
