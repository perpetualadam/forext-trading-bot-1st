"""Deterministic causal/cost/portfolio controls; never profitability evidence."""
from dataclasses import replace, FrozenInstanceError
import ast
import hashlib
import json
from pathlib import Path
import unittest
from .decision_quality import Request, Pricing, Policy, evaluate
from .cost_aware_policies import POLICIES, Split, fit_selector, unique_votes
from .frequency_diagnostics import Frequency, counterfactual, opportunity_summary
from .core import Config, features, ResearchRejected
from .test_contract import bar, Forced, T
from .v25_engine import run
from .v24_engine import run as baseline
from .cost_ledger import reconcile
from .timeframes import last_completed


def request(**kwargs):
    r=Request('EUR_USD','BUY',T,T,True,T,1.1,1.1002,.001,.002,.004,3600,
              Pricing(),'USD','trend','TREND',units=10000)
    return replace(r,**kwargs)


def decision(r=None,p=None,book=None): return evaluate(r or request(),p or POLICIES[0],book or {})


def replay(gate=None,**kwargs):
    bars=[bar(i) for i in range(5)]
    pack=features([bar(i) for i in range(60)],50)
    pack={k:([v[-1]]*5 if isinstance(v,list) else 5) for k,v in pack.items()}
    return run({'EUR_USD':bars},{'EUR_USD':{50:pack,100:pack}},Forced(),
               (bars[1].t,bars[-1].t+300),decision_evaluator=gate,cost_trace=True,cost_breakdown=True,**kwargs)


class DecisionTests(unittest.TestCase):
    def test_spread_atr(self): self.assertAlmostEqual(decision()['metrics']['spread_atr'],.2)
    def test_cost_target(self): self.assertAlmostEqual(decision()['metrics']['cost_target'],.05)
    def test_cost_r(self): self.assertAlmostEqual(decision()['metrics']['cost_r'],.1)
    def test_break_even(self): self.assertAlmostEqual(decision()['metrics']['break_even_win_rate'],22/60)
    def test_buy_sell(self): self.assertEqual(decision()['metrics'],decision(request(direction='SELL'))['metrics'])
    def test_jpy(self):
        x=decision(request(instrument='USD_JPY',bid=150,ask=150.02,atr=.1,stop_distance=.2,target_distance=.4))
        self.assertAlmostEqual(x['metrics']['spread_pips'],2)
    def test_gbp_conversion(self):
        x=decision(request(account='GBP'),book={'GBP_USD':(T,1.25,1.2502)})
        self.assertAlmostEqual(x['metrics']['estimated_round_trip_account'],1.6)
    def test_missing_conversion(self): self.assertEqual(decision(request(account='GBP'))['status'],'REJECT_DATA')
    def test_stale_conversion(self):
        self.assertEqual(decision(request(account='GBP'),book={'GBP_USD':(T-301,1.25,1.2502)})['status'],'REJECT_DATA')
    def test_future_conversion(self):
        self.assertEqual(decision(request(account='GBP'),book={'GBP_USD':(T+1,1.25,1.2502)})['status'],'REJECT_DATA')
    def test_pricing_unverified(self):
        self.assertEqual(decision(request(pricing=Pricing('DOCUMENTED_COMMISSION_PLAN')))['status'],'ABSTAIN_UNCERTAIN')
    def test_spread_plan_unverified(self):
        self.assertEqual(decision(request(pricing=Pricing('DOCUMENTED_SPREAD_ONLY')))['status'],'ABSTAIN_UNCERTAIN')
    def test_unknown_plan(self): self.assertEqual(decision(request(pricing=Pricing('UNKNOWN')))['status'],'ABSTAIN_UNCERTAIN')
    def test_mislabelled_plan(self): self.assertEqual(decision(request(pricing=Pricing(slippage_pips_side=.2)))['status'],'REJECT_DATA')
    def test_cost_stress(self):
        x=decision(request(pricing=Pricing('HYPOTHETICAL_STRESS',.2,3)))
        self.assertAlmostEqual(x['metrics']['estimated_round_trip_account'],3)
    def test_no_double_spread(self): self.assertAlmostEqual(decision()['metrics']['estimated_round_trip_account'],2)
    def test_incorrect_cost_negative_control(self):
        with self.assertRaises(AssertionError): self.assertAlmostEqual(decision()['metrics']['estimated_round_trip_account'],4)
    def test_no_forecast(self): self.assertIsNone(decision()['metrics']['expected_gross_movement'])
    def test_cost_reject(self): self.assertEqual(decision(p=Policy('test',cost_target_limit=.01))['status'],'REJECT_COST')
    def test_spread_reject(self): self.assertEqual(decision(p=Policy('test',spread_atr_limit=.1))['reason'],'SPREAD_ATR_LIMIT')
    def test_combined_abstains(self): self.assertEqual(decision(p=POLICIES[-1])['status'],'ABSTAIN_UNCERTAIN')
    def test_frozen_threshold(self):
        with self.assertRaises(FrozenInstanceError): POLICIES[1].spread_atr_limit=.5
    def test_unknown_future_field(self):
        with self.assertRaises(TypeError): request(future_mfe=20)
    def test_invalid_result_is_json_safe(self):
        json.dumps(decision(request(atr=float('nan'))),allow_nan=False)
    def test_nested_malformed_context(self):
        self.assertEqual(decision(request(contexts=(([], 'BUY',T,900),('H1','BUY',T,3600),('H4','BUY',T,14400))),POLICIES[3])['status'],'ABSTAIN_UNCERTAIN')
    def test_derived_overflow_rejects(self): self.assertEqual(decision(request(target_distance=1e-320))['status'],'REJECT_DATA')
    def test_risk_rejection(self): self.assertEqual(decision(request(stop_distance=0))['status'],'REJECT_RISK')
    def test_bad_context_shape(self): self.assertEqual(decision(request(contexts=None),POLICIES[3])['status'],'ABSTAIN_UNCERTAIN')
    def test_wrong_context_duration(self):
        contexts=(('M15','BUY',T,999999),('H1','BUY',T,3600),('H4','BUY',T,14400))
        self.assertEqual(decision(request(contexts=contexts),POLICIES[3])['status'],'ABSTAIN_UNCERTAIN')
    def test_unknown_signal(self): self.assertEqual(decision(request(strategy='UNKNOWN'))['status'],'REJECT_SIGNAL')
    def test_negative_cost(self): self.assertEqual(decision(request(pricing=Pricing('HYPOTHETICAL_STRESS',-.2,0)))['status'],'REJECT_DATA')
    def test_financing_unknown(self): self.assertEqual(decision(request(horizon_seconds=86400))['status'],'ABSTAIN_UNCERTAIN')
    def test_unattainable_payoff(self):
        x=decision(request(target_distance=.00001))
        self.assertGreater(x['metrics']['break_even_win_rate'],1)
    def test_missing_context(self): self.assertEqual(decision(p=POLICIES[3])['reason'],'MISSING_CONTEXT')
    def test_context_conflict(self):
        contexts=tuple((tf,'SELL',T,d) for tf,d in [('M15',900),('H1',3600),('H4',14400)])
        self.assertEqual(decision(request(contexts=contexts),POLICIES[3])['status'],'REJECT_SIGNAL')
    def test_context_accept(self):
        contexts=tuple((tf,'BUY',T,d) for tf,d in [('M15',900),('H1',3600),('H4',14400)])
        self.assertEqual(decision(request(contexts=contexts),POLICIES[3])['status'],'ACCEPT')
    def test_future_context_negative_control(self):
        contexts=tuple((tf,'BUY',T+1,d) for tf,d in [('M15',900),('H1',3600),('H4',14400)])
        self.assertEqual(decision(request(contexts=contexts),POLICIES[3])['status'],'ABSTAIN_UNCERTAIN')
    def test_completed_candles(self):
        self.assertIsNone(last_completed([bar()], 'M5',T+299))
        self.assertEqual(last_completed([bar()],'M5',T+300),0)
    def test_adapter_does_not_read_future_features(self):
        from types import SimpleNamespace
        from .v25_adapter import Evaluator
        class Guard(list):
            def __getitem__(self,index):
                if index>0: raise AssertionError('FUTURE_FEATURE_READ')
                return super().__getitem__(index)
        frames={'EUR_USD':{tf:[SimpleNamespace(t=T-d),SimpleNamespace(t=T)] for tf,d in [('M15',900),('H1',3600),('H4',14400)]}}
        context_pack={k:Guard([v,999999]) for k,v in [('ma_fast',1.101),('ma_slow',1.1),('atr',.001)]}
        packs={'EUR_USD':{tf:{50:context_pack} for tf in frames['EUR_USD']}}
        evaluator=Evaluator(POLICIES[3],Pricing(),frames,packs)
        candidate=dict(strategy='trend',regime='TREND')
        result=evaluator(pair='EUR_USD',when=T,side='BUY',signal_bar=bar(-1),
            pack={'atr':Guard([.001]),'momentum':Guard(['STRONG']),'volatility':Guard(['NORMAL'])},
            index=0,bar=bar(),stop_distance=.002,target_distance=.004,units=10000,
            quotes=SimpleNamespace(book={}),config=Config(),candidate=candidate,baseline_reason=None)
        self.assertEqual(result['status'],'ACCEPT')
    def test_result_hash(self):
        digest=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
        self.assertEqual(digest(decision()),digest(decision()))
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
    def test_older_reports_blocked(self):
        with self.assertRaises(PermissionError): (Path(__file__).parent/'reports/v24/never.txt').write_text('never')


def invalid_case(field,value):
    def test(self): self.assertEqual(decision(request(**{field:value}))['status'],'REJECT_DATA')
    return test
for field,value,name in [('bid',None,'missing_quote'),('bid',float('nan'),'nan_quote'),
    ('ask',float('inf'),'infinite'),('atr',None,'missing_atr'),('atr',0,'zero_atr'),
    ('atr',True,'bool_atr'),('quote_time',T-301,'stale'),('quote_time',T+1,'future_quote'),
    ('feature_available_at',T+1,'future_feature'),('feature_complete',False,'incomplete'),
    ('feature_available_at',T-300,'stale_feature'),('data_quality','UNKNOWN','data_quality')]:
    setattr(DecisionTests,'test_'+name,invalid_case(field,value))


class FrequencyTests(unittest.TestCase):
    def row(self,t=T,**kwargs):
        return dict(pair='EUR_USD',signal_time=t,direction='BUY',reason='ACCEPTED',accepted=True,
                    strategy='trend',session='EUROPE_UTC',regime='TREND',volatility='NORMAL',
                    spread_reference=.0002,atr=.001,**kwargs)
    def test_repeated(self):
        f=Frequency(); f.record('candidate',self.row()); r=self.row(T+300); f.record('candidate',r)
        self.assertTrue(r['frequency']['repeated_direction']); self.assertTrue(r['frequency']['adjacent_signal'])
    def test_reentry_after_stop(self):
        f=Frequency(); f.record('trade',dict(pair='EUR_USD',exit_time=T,exit_reason='STOP'))
        r=self.row(); f.record('candidate',r); self.assertTrue(r['frequency']['reentry_after_stop'])
    def test_duplicate_votes(self):
        v=('EUR_USD',T,'BUY','exact_predicate')
        self.assertEqual(len(unique_votes([v,v])),1)
    def test_similar_not_duplicate(self):
        self.assertEqual(len(unique_votes([('EUR_USD',T,'BUY','scalp'),('EUR_USD',T,'BUY','trend')])),2)
    def test_different_bar_not_duplicate(self):
        self.assertEqual(len(unique_votes([('EUR_USD',T,'BUY','p'),('EUR_USD',T+300,'BUY','p')])),2)
    def test_missing_identity(self):
        with self.assertRaises(ResearchRejected): unique_votes([('EUR_USD',T,'BUY','')])
    def test_counterfactual_both_sides(self):
        ds=[dict(self.row(T+i*300),quality_decision=dict(status='REJECT_COST',reason='test')) for i in range(3)]
        ts=[dict(pair='EUR_USD',entry_time=T,direction='BUY',net_account=5),
            dict(pair='EUR_USD',entry_time=T+300,direction='BUY',net_account=-7)]
        rows=counterfactual(ds,ts); s=opportunity_summary(rows)
        self.assertEqual((s['rejected_winners'],s['avoided_losers'],s['unknown_outcomes']),(1,1,1))
        self.assertEqual(s['baseline_net_on_rejected'],-2)


class ReplayTests(unittest.TestCase):
    def test_baseline_accept_equivalence(self):
        a=replay(); b=replay(lambda **kw:dict(status='ACCEPT',reason='test'))
        self.assertEqual(a['metrics'],b['metrics']); self.assertEqual(a['equity'],b['equity'])
        for t in b['trades']: t.pop('quality_decision')
        self.assertEqual(a['trades'],b['trades'])
    def test_full_path_changes_availability(self):
        a=replay(); b=replay(lambda **kw:dict(status='REJECT_COST' if kw['when']==T+300 else 'ACCEPT',reason='test'))
        self.assertEqual(a['trades'][0]['entry_time'],T+300)
        self.assertEqual(b['trades'][0]['entry_time'],T+600)
        for t in b['trades']: reconcile(t)
    def test_reject_all_accounting(self):
        r=replay(lambda **kw:dict(status='REJECT_COST',reason='test'))
        self.assertEqual(r['metrics']['trades'],0); self.assertEqual(r['metrics']['net_account'],0)
    def test_hook_boundary(self):
        p=Path(__file__).parent
        s=(p/'v25_engine.py').read_text().replace('V2.5 decision-hook copy of V2.4 research replay.',
            'V2.4 observed copy of frozen chronological bid/ask replay.')
        s=s.replace('cost_trace=False, decision_evaluator=None):','cost_trace=False):')
        start=s.index('            if decision_evaluator is not None:\n')
        end=s.index('            if reason:\n',start)
        s=s[:start]+s[end:]
        self.assertEqual(ast.dump(ast.parse(s)),ast.dump(ast.parse((p/'v24_engine.py').read_text())))


class SelectionTests(unittest.TestCase):
    def split(self): return Split((0,100000),(157600,257600),(315200,415200))
    def rows(self):
        return [dict(context='TREND',policy='B_SPREAD_ATR',phase=phase,entry_time=start+i,
            outcome_end=start+500+i,available_at=start+1000+i,net_r=.2)
            for phase,start in [('train',0),('validation',157600)] for i in range(30)]
    def test_no_independent_data_abstains(self):
        self.assertIsNone(fit_selector(self.rows(),self.split()).choose('TREND',315200))
    def test_synthetic_validation(self):
        self.assertEqual(fit_selector(self.rows(),self.split(),independent=True,evidence='SYNTHETIC').choose('TREND',315200),'B_SPREAD_ATR')
    def test_negative_abstains(self):
        rows=[dict(r,net_r=-.1) for r in self.rows()]
        self.assertIsNone(fit_selector(rows,self.split(),independent=True,evidence='SYNTHETIC').choose('TREND',315200))
    def test_no_forced_unknown_context(self):
        self.assertIsNone(fit_selector([],self.split()).choose('UNKNOWN',315200))
    def test_test_leak_rejected(self):
        rows=self.rows(); rows[0]['phase']='test'
        with self.assertRaises(ResearchRejected): fit_selector(rows,self.split(),independent=True,evidence='SYNTHETIC')
    def test_future_outcome_rejected(self):
        rows=self.rows(); rows[0]['available_at']=315200
        with self.assertRaises(ResearchRejected): fit_selector(rows,self.split(),independent=True,evidence='SYNTHETIC')
    def test_purge_required(self):
        with self.assertRaises(ResearchRejected): Split((0,100000),(100001,200000),(200001,300000))
    def test_duplicate_training_outcome(self):
        rows=self.rows(); rows.append(rows[0])
        with self.assertRaises(ResearchRejected): fit_selector(rows,self.split(),independent=True,evidence='SYNTHETIC')
    def test_insufficient_validation_abstains(self):
        rows=self.rows()[:-1]
        self.assertIsNone(fit_selector(rows,self.split(),independent=True,evidence='SYNTHETIC').choose('TREND',315200))
    def test_frozen_test_window(self):
        with self.assertRaises(ResearchRejected): fit_selector([],self.split()).choose('TREND',0)
