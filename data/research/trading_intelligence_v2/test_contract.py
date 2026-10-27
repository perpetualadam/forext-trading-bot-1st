"""Synthetic correctness tests only. No profitability evidence."""
from dataclasses import replace
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

from .core import Bar, Config, Quotes, ResearchRejected, features, periods, pip_size, timestamp, validate, usd_direction, read_csv
from .adapters import Existing
from .engine import Filter, metrics, quality_filter, run
from .study import selection

T = timestamp('2026-09-01T10:00:00Z')


def bar(i=0, price=1.1, spread=.0002, high=None, low=None):
    h = high if high is not None else price + .0001
    l = low if low is not None else price - .0001
    s = spread / 2
    return Bar(T + i * 300, price, h, l, price,
               price-s, h-s, l-s, price-s, price+s, h+s, l+s, price+s)


class Forced:
    """Toy signal source for execution tests; never used for market evaluation."""
    def __init__(self, side='BUY'):
        self.side = side

    def signal(self, strategy, i, pack):
        return self.side, 'SYNTHETIC_TEST'


def replay(bars, side='BUY', **kwargs):
    pack = features([bar(i) for i in range(60)], 50)
    pack = {k: ([v[-1]] * len(bars) if isinstance(v, list) else len(bars)) for k, v in pack.items()}
    return run({'EUR_USD': bars}, {'EUR_USD': {50: pack, 100: pack}}, Forced(side),
               (bars[1].t, bars[-1].t+300), **kwargs)


class DataTests(unittest.TestCase):
    def test_valid(self): self.assertEqual(validate([bar(), bar(1)])['status'], 'PASS')
    def test_empty(self): self.assertEqual(validate([])['status'], 'FAIL')
    def test_duplicate(self): self.assertIn((1, 'duplicate'), validate([bar(), bar()])['errors'])
    def test_order(self): self.assertIn((1, 'unordered'), validate([bar(1), bar()])['errors'])
    def test_incomplete(self): self.assertIn((0, 'incomplete'), validate([replace(bar(), complete=False)])['errors'])
    def test_grid(self): self.assertIn((0, 'off_grid'), validate([replace(bar(), t=T+1)])['errors'])
    def test_missing(self): self.assertEqual(validate([bar(), bar(2)])['gaps'][0]['missing_bars'], 1)
    def test_weekend(self):
        a=timestamp('2026-09-04T20:00:00Z'); b=timestamp('2026-09-06T22:00:00Z')
        self.assertEqual(validate([replace(bar(),t=a), replace(bar(),t=b)])['gaps'][0]['kind'], 'weekend_containing')
    def test_ohlc(self): self.assertEqual(validate([replace(bar(), h=1)])['status'], 'FAIL')
    def test_nan(self): self.assertEqual(validate([replace(bar(), c=math.nan)])['status'], 'FAIL')
    def test_cross(self): self.assertIn((0, 'crossed_quote'), validate([replace(bar(), bo=2)])['errors'])
    def test_naive(self):
        with self.assertRaises(ResearchRejected): timestamp('2026-09-01T00:00:00')
    def test_fractional_time_not_repaired(self):
        with self.assertRaises(ResearchRejected): timestamp('2026-09-01T00:00:00.5Z')
    def test_utc(self): self.assertEqual(timestamp('2026-09-01T11:00:00+01:00'),T)
    def test_jpy_pip(self): self.assertEqual(pip_size('USD_JPY'), .01)
    def test_unknown_pair(self):
        with self.assertRaises(ResearchRejected): pip_size('BAD')
    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError): read_csv(TEMP/'missing.csv')
    def test_warmup(self):
        p=features([bar(i) for i in range(51)],50)
        self.assertTrue(math.isnan(p['atr'][48])); self.assertTrue(math.isfinite(p['atr'][49]))
    def test_gap_resets(self):
        p=features([bar(i) for i in range(60)]+[bar(70)],50)
        self.assertTrue(math.isnan(p['atr'][-1]))
    def test_prefix_causality(self):
        b=[bar(i, 1.1+i*.00001) for i in range(120)]
        a,c=features(b[:100],50),features(b,50)
        for k in ('ma_fast','ma_slow','atr','atr14','boll_up','prior_hi','regime','volatility','momentum'):
            self.assertEqual(a[k][50:], c[k][50:100],k)
    def test_breakout_excludes_current(self):
        b=[bar(i) for i in range(59)]+[bar(59,high=2)]
        self.assertLess(features(b,50)['prior_hi'][-1],2)
    def test_folds(self):
        f=periods(list(range(0,300000,300)))
        for x in f:
            self.assertEqual(x['train'][1],x['validation'][0]); self.assertEqual(x['validation'][1],x['test'][0])
        self.assertEqual(f[0]['test'][1],f[1]['test'][0])
    def test_short_folds(self):
        with self.assertRaises(ResearchRejected): periods([0,300])
    def test_known_indicator_values(self):
        b=[bar(i,1+i*.001,high=1+i*.001+.002,low=1+i*.001-.002) for i in range(60)]
        p=features(b,50)
        self.assertAlmostEqual(p['ma_fast'][-1],1.057)
        self.assertAlmostEqual(p['ma_slow'][-1],1.047)
        self.assertAlmostEqual(p['atr'][-1],.004)
        self.assertAlmostEqual(p['atr14'][-1],.004)
    def test_selection_ignores_test(self):
        from .core import STRATEGIES
        train={s:dict(trades=30,expectancy_r=-1) for s in STRATEGIES}
        validation={s:dict(trades=30,expectancy_r=10) for s in STRATEGIES}
        self.assertIsNone(selection(train,validation))
        train['trend']['expectancy_r']=.1
        self.assertEqual(selection(train,validation),'trend')


class MoneyTests(unittest.TestCase):
    def setUp(self):
        self.q=Quotes(); self.q.put('USD_JPY',T,150,150.02); self.q.put('GBP_USD',T,1.25,1.251)
    def test_jpy_gain(self): self.assertAlmostEqual(self.q.convert(150.02,'JPY','USD',T),1)
    def test_jpy_loss(self): self.assertAlmostEqual(self.q.convert(-150,'JPY','USD',T),-1)
    def test_cross_gain(self): self.assertAlmostEqual(self.q.convert(150.02,'JPY','GBP',T),1/1.251)
    def test_cross_loss(self): self.assertAlmostEqual(self.q.convert(-150,'JPY','GBP',T),-1/1.25)
    def test_stale(self):
        with self.assertRaises(ResearchRejected): self.q.convert(1,'JPY','USD',T+301)
    def test_future_quote(self):
        with self.assertRaises(ResearchRejected): self.q.convert(1,'JPY','USD',T-1)
    def test_missing(self):
        with self.assertRaises(ResearchRejected): self.q.convert(1,'CAD','GBP',T)
    def test_cross_quote(self):
        with self.assertRaises(ResearchRejected): self.q.put('EUR_USD',T,2,1)
    def test_usd_sides(self):
        self.assertEqual(usd_direction('EUR_USD','BUY'),usd_direction('USD_JPY','SELL'))
        self.assertNotEqual(usd_direction('EUR_USD','BUY'),usd_direction('GBP_USD','SELL'))
    def test_config(self):
        for kwargs in ({'risk_fraction':math.nan},{'usd_slots':True},{'initial':0},{'flatten_hour_utc':24},{'leverage':0}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ResearchRejected): Config(**kwargs)


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.existing=Existing(ROOT)
    def test_model_abstention(self):
        a=self.existing.availability()
        self.assertEqual(a['ai']['status'],'unavailable'); self.assertEqual(a['rl'],'UNAVAILABLE'); self.assertEqual(a['quant_stub']['status'],'unavailable')
    def test_original_entry_geometry(self):
        for pair,pip in [('EUR_USD',.0001),('USD_JPY',.01)]:
            self.assertEqual(self.existing.entry_distances(pair,.1),(20*pip,40*pip))
    def test_real_shadow_rule(self):
        p=features([bar(i,1.1+i*.00001) for i in range(120)],50)
        self.assertEqual(self.existing.signal('trend',119,p)[0],'BUY')
    def test_signal_symmetry(self):
        p=features([bar(i,1.2-i*.00001) for i in range(120)],50)
        self.assertEqual(self.existing.signal('trend',119,p)[0],'SELL')
    def test_rule_nonfinite(self):
        p=features([bar(i) for i in range(60)],50); p['close'][-1]=math.inf
        self.assertIsNone(self.existing.signal('trend',59,p)[0])
    def test_router_tie(self): self.assertEqual(self.existing.select_argmax({'trend':1,'scalp':1}),'scalp')
    def test_pp_benchmark(self):
        for side,sign in [('BUY',1),('SELL',-1)]:
            p=SimpleNamespace(symbol='EUR_USD',direction=side,entry_price=1.1,take_profit=1.1+sign*.002,
                              max_profit_pips=13.3)
            self.existing.protection(p,1.1+sign*.001,atr_price=.001)
            self.assertFalse(getattr(p,'profit_protection_active',False))
            p.max_profit_pips=14
            d=self.existing.protection(p,1.1+sign*.001,atr_price=.001)
            self.assertTrue(getattr(p,'profit_protection_active',False))
            self.assertFalse(d.should_close)
    def test_pp_fallback_ratchet(self):
        p=SimpleNamespace(symbol='EUR_USD',direction='BUY',entry_price=1.1,take_profit=1.102,max_profit_pips=15)
        self.existing.protection(p,1.1014,atr_price=None)
        first=p.profit_protection_exit_pips
        self.assertAlmostEqual(first,11)
        self.existing.protection(p,1.1014,atr_price=.004)
        self.assertGreaterEqual(p.profit_protection_exit_pips,first)
    def test_pp_jpy(self):
        p=SimpleNamespace(symbol='USD_JPY',direction='SELL',entry_price=150,take_profit=149.8,max_profit_pips=15)
        self.existing.protection(p,149.86,atr_price=.1)
        self.assertAlmostEqual(p.profit_protection_exit_pips,10)
    def test_pp_close_after_giveback(self):
        p=SimpleNamespace(symbol='EUR_USD',direction='BUY',entry_price=1.1,take_profit=1.102,max_profit_pips=15)
        self.assertTrue(self.existing.protection(p,1.1008,atr_price=.001).should_close)


class ExecutionTests(unittest.TestCase):
    def test_next_bar_only(self):
        r=replay([bar(i) for i in range(3)])
        self.assertEqual(r['trades'][0]['entry_time'],T+300)
    def test_spread_slip_cost(self):
        r=replay([bar(i) for i in range(3)])['trades'][0]
        self.assertLess(r['net_account'],0); self.assertGreater(r['cost_account'],0)
        self.assertAlmostEqual(r['entry_price'],1.10012)
    def test_stop_first(self):
        b=[bar(),bar(1,high=1.11,low=1.09)]
        r=replay(b)
        self.assertEqual(r['metrics']['ambiguous_stop_first'],1)
        self.assertEqual(r['trades'][0]['exit_reason'],'STOP_FIRST_AMBIGUOUS')
        self.assertLess(r['trades'][0]['net_account'],0)
    def test_symmetry(self):
        b=[bar(i) for i in range(3)]
        self.assertAlmostEqual(replay(b)['trades'][0]['net_account'],replay(b,'SELL')['trades'][0]['net_account'])
    def test_sizing(self):
        t=replay([bar(i) for i in range(3)])['trades'][0]
        self.assertLessEqual(t['initial_risk_account'],25)
    def test_target_gap_conservative(self):
        b=[bar(),bar(1),bar(2,price=1.11)]
        t=replay(b)['trades'][0]
        self.assertEqual(t['exit_reason'],'TARGET_GAP_NO_IMPROVEMENT')
        self.assertLess(t['exit_price'],1.11)
    def test_stop_gap_adverse(self):
        b=[bar(),bar(1),bar(2,price=1.09)]
        t=replay(b)['trades'][0]
        self.assertEqual(t['exit_reason'],'STOP_GAP'); self.assertLess(t['net_r'],-1)
    def test_data_gap_never_optimistic(self):
        b=[bar(),bar(1),bar(4,price=1.11)]
        t=replay(b)['trades'][0]
        self.assertEqual(t['exit_reason'],'DATA_GAP_CONSERVATIVE_STOP'); self.assertLess(t['net_account'],0)
    def test_reproducible(self):
        b=[bar(i) for i in range(3)]
        self.assertEqual(replay(b),replay(b))
    def test_prior_filter_only(self):
        b=[bar(i) for i in range(3)]
        before=replay(b,policy=Filter(max_spread_atr=2))['trades'][0]
        b[1]=replace(b[1],ac=1.2,ah=1.2)
        after=replay(b,policy=Filter(max_spread_atr=2))['trades'][0]
        self.assertEqual(before['entry_time'],after['entry_time'])
    def test_undefined_metrics(self):
        m=metrics([])
        for k in ('expectancy_r','win_rate','profit_factor','sharpe_annualized_daily'): self.assertIsNone(m[k])
    def test_regime_abstain(self):
        p=features([bar(i) for i in range(60)],50)
        self.assertEqual(quality_filter('trend',p,59,bar(),Filter(regime=True)),'REGIME_UNCERTAIN_OR_MISMATCH')
    def portfolio(self, config=Config(), spike=False):
        from .core import PAIRS
        # Three USD-quote instruments with same BUY USD direction.
        pairs=('AUD_USD','EUR_USD','GBP_USD')
        data={p:[bar(i,high=1.11 if spike and i==1 else None,low=1.09 if spike and i==1 else None) for i in range(3)] for p in pairs}
        p=features([bar(i) for i in range(60)],50)
        p={k:([v[-1]]*3 if isinstance(v,list) else 3) for k,v in p.items()}
        return run(data,{k:{50:p,100:p} for k in pairs},Forced(),(T+300,T+900),config=config)
    def test_usd_cap(self):
        r=self.portfolio()
        self.assertEqual(r['metrics']['peak_entry_allocation']['same_usd_direction'],2)
        self.assertIn('USD_DIRECTION_CAP',r['metrics']['rejections'])
    def test_max_positions(self):
        r=self.portfolio(Config(max_positions=1))
        self.assertEqual(r['metrics']['peak_entry_allocation']['positions'],1)
    def test_portfolio_risk(self):
        r=self.portfolio(Config(portfolio_risk=.0025,usd_slots=3))
        self.assertLessEqual(r['metrics']['peak_entry_allocation']['planned_risk_fraction'],.0025+1e-12)
    def test_margin(self):
        r=self.portfolio(Config(leverage=1,margin_fraction=.1,usd_slots=3))
        self.assertLessEqual(r['metrics']['peak_entry_allocation']['margin_fraction'],.1+1e-12)
    def test_intrabar_does_not_release_earlier_capacity(self):
        r=self.portfolio(spike=True)
        first=[t for t in r['trades'] if t['entry_time']==T+300]
        self.assertEqual(len(first),2)
    def test_cost_stress_is_worse(self):
        b=[bar(i) for i in range(3)]
        self.assertLess(replay(b,config=Config(slippage_pips=.5))['metrics']['net_account'],replay(b)['metrics']['net_account'])
    def test_pp_executes_next_open(self):
        b=[bar(),bar(1,high=1.1007),bar(2,price=1.1001)]
        class ToyPP(Forced):
            @staticmethod
            def protection(p,price,atr_price=None): return SimpleNamespace(should_close=True)
        pack=features([bar(i) for i in range(60)],50)
        pack={k:([v[-1]]*3 if isinstance(v,list) else 3) for k,v in pack.items()}
        r=run({'EUR_USD':b},{'EUR_USD':{50:pack,100:pack}},ToyPP(),(T+300,T+900),protection=True)
        self.assertEqual(r['trades'][0]['exit_time'],T+600)
        self.assertEqual(r['trades'][0]['exit_reason'],'SOFTWARE_PROTECTION_NEXT_OPEN')
    def test_end_exposure_refused(self):
        b=[bar(i) for i in range(3)]
        pack=features([bar(i) for i in range(60)],50)
        pack={k:([v[-1]]*3 if isinstance(v,list) else 3) for k,v in pack.items()}
        with self.assertRaisesRegex(ResearchRejected,'unliquidated_end_exposure'):
            run({'EUR_USD':b},{'EUR_USD':{50:pack,100:pack}},Forced(),(T+300,T+1200))


class IsolationTests(unittest.TestCase):
    def test_broker_network(self):
        import sys
        with self.assertRaises(PermissionError): sys.audit('socket.connect',None,('example.com',443))
    def test_live_import(self):
        with self.assertRaises(PermissionError): __import__('forex_bot.bot_loop')
    def test_env_read(self):
        with self.assertRaises(PermissionError): (ROOT/'.env').read_text()
    def test_journal_read(self):
        with self.assertRaises(PermissionError): (ROOT/'journal.sqlite').read_bytes()
    def test_scheduler_read(self):
        with self.assertRaises(PermissionError): (ROOT/'data/research/macro/consensus_pit/prospective/scheduler/state.json').read_bytes()
    def test_operational_write(self):
        with self.assertRaises(PermissionError): (ROOT/'forex_bot/bot_loop.py').open('w')
    def test_environment_empty(self):
        import os
        self.assertEqual(dict(os.environ),{})
