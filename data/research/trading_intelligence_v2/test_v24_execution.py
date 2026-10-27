"""Additional explicit execution endpoint and sizing oracles."""
from decimal import Decimal
from types import SimpleNamespace
import unittest
from .test_v24 import one
from .test_contract import bar, Forced, T
from .core import features, pip_size
from .v24_engine import run
from .cost_ledger import reconcile, convert


class EndpointTests(unittest.TestCase):
    def test_exact_stop_risk_budget(self):
        t=one(end=bar(2,low=1.09))
        self.assertEqual(t['exit_reason'],'STOP')
        self.assertAlmostEqual(-t['net_account'],t['initial_risk_account'])
        self.assertLessEqual(t['initial_risk_account'],25)
        self.assertGreater(t['initial_risk_account']+t['initial_risk_account']/t['units'],25)
        reconcile(t)

    def test_target_fill(self):
        t=one(end=bar(2,high=1.11))
        self.assertEqual(t['exit_reason'],'TARGET')
        self.assertAlmostEqual(t['exit_price'],t['initial_target']-.00002)
        reconcile(t)

    def test_sell_target_fill(self):
        t=one('SELL',end=bar(2,low=1.09))
        self.assertEqual(t['exit_reason'],'TARGET')
        self.assertAlmostEqual(t['exit_price'],t['initial_target']+.00002)
        reconcile(t)

    def test_gap_exceeds_planned_risk(self):
        t=one(end=bar(2,price=1.09))
        self.assertEqual(t['exit_reason'],'STOP_GAP')
        self.assertGreater(-t['net_account'],t['initial_risk_account']); reconcile(t)

    def test_margin_binds(self):
        t=one(leverage=1,margin_fraction=.01)
        self.assertLessEqual(t['cost_trace']['margin_account'],100)
        self.assertLess(t['initial_risk_account'],25)

    def test_hand_pip_values(self):
        book={'USD_JPY':(T,150,150.02),'USD_CAD':(T,1.35,1.3502),
              'USD_CHF':(T,.9,.9002),'GBP_USD':(T,1.25,1.2502)}
        for pair,rate in [('USD_JPY',150),('USD_CAD',1.35),('USD_CHF',.9)]:
            amount=Decimal(str(pip_size(pair)))*10000
            expected=amount/Decimal(str(rate))
            self.assertAlmostEqual(float(-convert(-amount,pair[4:],'USD',T,book)),float(expected))
            self.assertAlmostEqual(float(-convert(-amount,pair[4:],'GBP',T,book)),float(expected/Decimal('1.25')))

    def test_protection_next_open(self):
        class Toy(Forced):
            def protection(self,p,price,atr_price=None):
                return SimpleNamespace(should_close=True)
        bars=[bar(i) for i in range(4)]
        pack=features([bar(i) for i in range(60)],50)
        pack={k:([v[-1]]*4 if isinstance(v,list) else 4) for k,v in pack.items()}
        r=run({'EUR_USD':bars},{'EUR_USD':{50:pack,100:pack}},Toy(),
            (bars[1].t,bars[-1].t+300),protection=True,cost_trace=True,cost_breakdown=True)
        self.assertEqual(r['trades'][0]['exit_reason'],'SOFTWARE_PROTECTION_NEXT_OPEN')
        reconcile(r['trades'][0])


    def test_frozen_engine_boundary(self):
        from pathlib import Path
        import ast
        package=Path(__file__).resolve().parent
        frozen=(package/'engine.py').read_text()
        observed=(package/'v24_engine.py').read_text()
        observed=observed.replace('V2.4 observed copy of frozen chronological bid/ask replay.','Chronological bid/ask replay.')
        observed=observed.replace('decision_provider=None, cost_breakdown=False, cost_trace=False):','decision_provider=None, cost_breakdown=False):')
        start=observed.index('        if cost_trace:\n')
        end=observed.index('        trades.append(trade)',start)
        observed=observed[:start]+observed[end:]
        observed=observed.replace('            if cost_trace:\n                p.entry_bid, p.entry_ask = b.bo, b.ao\n','')
        self.assertEqual(ast.dump(ast.parse(observed)),ast.dump(ast.parse(frozen)))
