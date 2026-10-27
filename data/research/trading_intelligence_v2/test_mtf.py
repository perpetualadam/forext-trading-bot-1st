"""Deterministic synthetic MTF regression/adversarial tests; never profit evidence."""
from dataclasses import replace,FrozenInstanceError
import hashlib
import json
import math
import sys
import unittest

from . import test_contract as fixtures
from .core import Bar,Config,Quotes,ResearchRejected,features,timestamp,usd_direction
from .adapters import Existing
from .engine import run as replay
from .timeframes import DURATIONS,DailySession,aggregate,last_completed
from .mtf_features import Policy,Provider,agreement,prepare,trend_state
from .mtf_selector import Fitted,fit,score,select_hold,validate_fit
from .mtf_statistics import interval,holm
from .mtf_walkforward import purged

T=timestamp('2026-09-01T00:00:00Z')


def source(n,start=T):
    return [replace(fixtures.bar(i,price=1.1+i*.000001),t=start+300*i) for i in range(n)]


class AggregationTests(unittest.TestCase):
    def test_M15(self): self.assertEqual(len(aggregate(source(6),'M15')[0]),2)
    def test_H1(self): self.assertEqual(len(aggregate(source(24),'H1')[0]),2)
    def test_H4(self): self.assertEqual(len(aggregate(source(96),'H4')[0]),2)
    def test_M5_identity(self):
        b=source(12); self.assertEqual(aggregate(b,'M5')[0],b)
    def test_bid_ask_OHLC(self):
        b=source(3); out=aggregate(b,'M15')[0][0]
        for o,h,l,c in (('o','h','l','c'),('bo','bh','bl','bc'),('ao','ah','al','ac')):
            self.assertEqual(getattr(out,o),getattr(b[0],o)); self.assertEqual(getattr(out,c),getattr(b[-1],c))
            self.assertEqual(getattr(out,h),max(getattr(x,h) for x in b)); self.assertEqual(getattr(out,l),min(getattr(x,l) for x in b))
    def test_incomplete_aggregate(self):
        b,q=aggregate(source(2),'M15'); self.assertEqual(b,[]); self.assertEqual(q['unavailable'][0]['missing'],1)
    def test_missing_middle(self):
        b=source(12); del b[4]
        self.assertEqual(aggregate(b,'H1')[0],[])
    def test_duplicate(self):
        b=source(3)
        with self.assertRaises(ResearchRejected): aggregate(b+[b[-1]],'M15')
    def test_out_of_order(self):
        with self.assertRaises(ResearchRejected): aggregate(list(reversed(source(3))),'M15')
    def test_malformed(self):
        with self.assertRaises(ResearchRejected): aggregate([replace(source(1)[0],ac=math.nan)],'M15')
    def test_incomplete_source(self):
        with self.assertRaises(ResearchRejected): aggregate([replace(source(1)[0],complete=False)],'M15')
    def test_truthy_completion_is_not_complete(self):
        for flag in ('false','true',1):
            with self.subTest(flag=flag),self.assertRaises(ResearchRejected):
                aggregate([replace(b,complete=flag) for b in source(3)],'M15')
    def test_boolean_prices_are_not_market_prices(self):
        with self.assertRaises(ResearchRejected): aggregate([Bar(T,*([True]*12))],'M5')
    def test_empty(self):
        with self.assertRaises(ResearchRejected): aggregate([],'H1')
    def test_UTC_alignment(self):
        b=source(60,start=T+300)
        self.assertTrue(all(x.t%3600==0 for x in aggregate(b,'H1')[0]))
    def test_weekend_no_fabrication(self):
        friday=timestamp('2026-09-04T20:00:00Z'); sunday=timestamp('2026-09-06T21:00:00Z')
        b=source(12,friday)+source(12,sunday)
        out,q=aggregate(b,'H1')
        self.assertEqual([x.t for x in out],[friday,sunday]); self.assertGreater(len(q['unavailable']),40)
    def test_daily_no_implicit_midnight(self):
        with self.assertRaisesRegex(ResearchRejected,'calendar_required'): aggregate(source(288),'D1')
    def test_daily_explicit_17NY_fixture(self):
        start=timestamp('2026-09-01T17:00:00-04:00')
        b=source(288,start)
        out,_=aggregate(b,'D1',daily_sessions=[DailySession(start,start+86400,'SYNTHETIC_NY17','synthetic calendar fixture',True)])
        self.assertEqual(out[0].t,start); self.assertNotEqual(start%86400,0)
    def test_daily_23_hour_DST_fixture(self):
        s=DailySession(T,T+23*3600,'SYNTHETIC_DST','synthetic fixture',True)
        self.assertEqual(len(aggregate(source(276),'D1',daily_sessions=[s])[0]),1)
    def test_daily_25_hour_DST_fixture(self):
        s=DailySession(T,T+25*3600,'SYNTHETIC_DST','synthetic fixture',True)
        self.assertEqual(len(aggregate(source(300),'D1',daily_sessions=[s])[0]),1)
    def test_unreviewed_daily_refused(self):
        with self.assertRaises(ResearchRejected): aggregate(source(288),'D1',daily_sessions=[DailySession(T,T+86400,'UTC','unreviewed')])
    def test_daily_missing_bar(self):
        s=DailySession(T,T+86400,'synthetic','fixture',True)
        self.assertEqual(aggregate(source(287),'D1',daily_sessions=[s])[0],[])


class AvailabilityTests(unittest.TestCase):
    def test_1035_cannot_see_unfinished_H1(self):
        b,_=aggregate(source(24,start=T+9*3600),'H1')
        i=last_completed(b,'H1',T+10*3600+35*60)
        self.assertEqual(i,0); self.assertEqual(b[i].t,T+9*3600)
    def test_exact_H1_boundary(self):
        b=aggregate(source(12),'H1')[0]
        self.assertIsNone(last_completed(b,'H1',T+3599)); self.assertEqual(last_completed(b,'H1',T+3600),0)
    def test_exact_H4_boundary(self):
        b=aggregate(source(48),'H4')[0]
        self.assertIsNone(last_completed(b,'H4',T+14399)); self.assertEqual(last_completed(b,'H4',T+14400),0)
    def test_stale_context(self):
        b=aggregate(source(12),'H1')[0]
        self.assertIsNone(last_completed(b,'H1',T+7200))
    def test_higher_features_warmup(self):
        b=aggregate(source(600),'H1')[0]; p=features(b,50,step_seconds=3600)
        self.assertTrue(math.isnan(p['atr'][48])); self.assertTrue(math.isfinite(p['atr'][49]))
    def test_future_tail_does_not_change_completed_bar(self):
        a=source(24); b=list(a); b[-1]=replace(b[-1],h=9,bh=8.9,ah=9.1)
        self.assertEqual(aggregate(a,'H1')[0][0],aggregate(b,'H1')[0][0])
    def test_future_tail_does_not_change_features(self):
        b=source(1000); a=features(aggregate(b[:600],'H1')[0],50,step_seconds=3600)
        c=features(aggregate(b,'H1')[0],50,step_seconds=3600)
        self.assertEqual(a['ma_fast'][49:],c['ma_fast'][49:50])
    def test_expected_weekend_retains_history_only_if_enabled(self):
        b=aggregate(source(600,start=timestamp('2026-08-31T18:00:00Z')),'H1')[0]
        # Forty-nine hourly bars followed by a declared weekend-containing gap.
        b=[replace(x,t=timestamp('2026-09-02T20:00:00Z')+i*3600) for i,x in enumerate(b[:49])]
        b.append(replace(b[-1],t=timestamp('2026-09-06T21:00:00Z')))
        self.assertTrue(math.isnan(features(b,50,step_seconds=3600)['atr'][-1]))
        self.assertTrue(math.isfinite(features(b,50,step_seconds=3600,weekend_continuity=True)['atr'][-1]))


class DecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.existing=Existing(ROOT); cls.data={'EUR_USD':source(6000)}
        cls.frames,cls.packs,cls.quality=prepare(cls.data)
    def test_M15_only_signals(self): self.check_entry('M15')
    def test_H1_only_signals(self): self.check_entry('H1')
    def test_H4_only_signals(self): self.check_entry('H4')
    def check_entry(self,tf):
        b=self.frames['EUR_USD'][tf][50]; t=b.t+DURATIONS[tf]
        p=Provider(self.frames,self.packs,self.existing,Policy(tf,'trend',4))
        self.assertIsNotNone(p('EUR_USD',t)); self.assertIsNone(p('EUR_USD',t+300))
    def test_M5_native_equivalence(self):
        pol=Policy('M5','trend',12); p=Provider(self.frames,self.packs,self.existing,pol)
        window=(T+60*300,T+90*300)
        kw=dict(data=self.data,packs={'EUR_USD':self.packs['EUR_USD']['M5']},existing=self.existing,window=window)
        a=replay(**kw); b=replay(**kw,decision_provider=p,cost_breakdown=True)
        self.assertEqual(a['metrics'],b['metrics'])
        for x,y in zip(a['trades'],b['trades']):
            for k,v in x.items(): self.assertEqual(v,y[k],k)
    def test_higher_timeframe_execution_after_completion(self):
        for tf in ('M15','H1','H4'):
            when=self.frames['EUR_USD'][tf][50].t+DURATIONS[tf]
            p=Provider(self.frames,self.packs,self.existing,Policy(tf,'trend',4))
            r=replay(self.data,{'EUR_USD':self.packs['EUR_USD']['M5']},self.existing,(when,when+300),decision_provider=p)
            self.assertEqual(len(r['trades']),1,tf)
            self.assertEqual(r['trades'][0]['entry_time'],when)
            self.assertLessEqual(r['trades'][0]['initial_risk_account'],25)
    def test_partition_boundaries_start_flat(self):
        p=Provider(self.frames,self.packs,self.existing,Policy('H1','trend',12))
        when=self.frames['EUR_USD']['H1'][50].t+3600
        for start in (when,when+3600):
            r=replay(self.data,{'EUR_USD':self.packs['EUR_USD']['M5']},self.existing,(start,start+3600),decision_provider=p)
            self.assertEqual(r['equity'][0],(start,10000))
            self.assertTrue(all(t['entry_time']>=start and t['exit_time']<=start+3600 for t in r['trades']))
    def test_missing_confirmation_abstains(self):
        records=[]; p=Provider(self.frames,self.packs,self.existing,Policy('M5','trend',12,('H1',)),lambda *r:records.append(r))
        self.assertIsNone(p('EUR_USD',T+60*300)); self.assertEqual(records[-1][1]['reason'],'INSUFFICIENT_DATA')
    def test_BUY_SELL_symmetry(self):
        p={'ma_fast':[2,0],'ma_slow':[1,1],'atr':[1,1]}
        self.assertEqual(trend_state(p,0),'BUY'); self.assertEqual(trend_state(p,1),'SELL')
    def test_conflict(self): self.assertEqual(agreement(['BUY','SELL','WAIT'],2),'CONFLICT')
    def test_opposing_entry_and_single_context_labelled_conflict(self):
        when=self.frames['EUR_USD']['H1'][50].t+3600
        old=self.packs['EUR_USD']['H1'][50]
        changed={**old,'ma_fast':list(old['ma_fast'])}
        changed['ma_fast'][50]=old['ma_slow'][50]-2*old['atr'][50]
        packs={**self.packs,'EUR_USD':{**self.packs['EUR_USD'],'H1':{**self.packs['EUR_USD']['H1'],50:changed}}}
        records=[]
        p=Provider(self.frames,packs,self.existing,Policy('M5','trend',12,('H1',)),lambda *row:records.append(row))
        self.assertIsNone(p('EUR_USD',when))
        self.assertEqual(records[-1][1]['reason'],'CONFLICT')
    def test_missing_not_agreement(self): self.assertEqual(agreement(['BUY','BUY','INSUFFICIENT_DATA'],2),'INSUFFICIENT_DATA')
    def test_quorum_not_universal(self): self.assertEqual(agreement(['BUY','BUY','WAIT'],2),'BUY')
    def test_WAIT(self): self.assertEqual(agreement(['BUY','WAIT','WAIT'],2),'WAIT')
    def test_policy_invalid(self):
        for args in [('M1','trend',4),('M5','invented',4),('H1','trend',True),('H1','trend',4,('M5',))]:
            with self.assertRaises(ResearchRejected): Policy(*args)
    def test_original_PP_unchanged(self):
        from types import SimpleNamespace
        p=SimpleNamespace(symbol='EUR_USD',direction='BUY',entry_price=1.1,take_profit=1.102,max_profit_pips=15)
        self.existing.protection(p,1.1014,atr_price=None)
        self.assertAlmostEqual(p.profit_protection_exit_pips,11)
    def test_cost_components_reconcile(self):
        r=replay(self.data,{'EUR_USD':self.packs['EUR_USD']['M5']},self.existing,(T+60*300,T+90*300),cost_breakdown=True)
        for t in r['trades']:
            self.assertGreater(t['spread_cost_account'],0); self.assertGreater(t['slippage_cost_account'],0)
            self.assertAlmostEqual(t['cost_account'],sum(t[k] for k in ('spread_cost_account','slippage_cost_account','commission_account','funding_assumption_account','conversion_cost_residual')))
    def test_AI_RL_abstention(self):
        a=self.existing.availability(); self.assertEqual(a['rl'],'UNAVAILABLE'); self.assertEqual(a['ai']['status'],'unavailable')
    def test_future_provider_refused(self):
        window=(T+60*300,T+65*300); p=Provider(self.frames,self.packs,self.existing,Policy('M5','trend',12))
        def future(pair,t):
            s=p(pair,t); s['metadata']['signal_available_at']=t+300; return s
        with self.assertRaisesRegex(ResearchRejected,'future_MTF'):
            replay(self.data,{'EUR_USD':self.packs['EUR_USD']['M5']},self.existing,window,decision_provider=future)


def trades(n=20,value=1,entry=10,exit=20):
    return [dict(net_r=value,context_key='TREND|NORMAL',entry_time=entry,exit_time=exit) for _ in range(n)]


class SelectionTests(unittest.TestCase):
    def test_train_only_fit(self):
        pol=Policy('H1','trend',4); f=fit([('EUR_USD',pol,trades())],20)
        self.assertEqual(f.policy('EUR_USD','TREND|NORMAL'),pol)
    def test_future_train_label(self):
        with self.assertRaises(ResearchRejected): fit([('EUR_USD',Policy('H1','trend',4),trades(exit=21))],20)
    def test_validation_future_label(self):
        with self.assertRaises(ResearchRejected): validate_fit(Fitted((),10),{'EUR_USD':trades(entry=20,exit=41)},20,40)
    def test_validation_veto(self):
        f=fit([('EUR_USD',Policy('H1','trend',4),trades())],20)
        self.assertEqual(validate_fit(f,{'EUR_USD':trades(value=-1,entry=30,exit=40)},30,40).rules,())
    def test_validation_success(self):
        f=fit([('EUR_USD',Policy('H1','trend',4),trades())],20)
        self.assertEqual(validate_fit(f,{'EUR_USD':trades(entry=30,exit=40)},30,40).rules,f.rules)
    def test_small_sample_abstention(self): self.assertIsNone(score(trades(3)))
    def test_no_reward_for_trade_count(self):
        a=Policy('H1','trend',4); b=Policy('M15','trend',4)
        self.assertEqual(fit([('EUR_USD',a,trades(value=1)),('EUR_USD',b,trades(100,value=-1))],20).policy('EUR_USD','TREND|NORMAL'),a)
    def test_selection_reproducibility(self):
        rows=[('EUR_USD',Policy('H1','trend',4),trades())]
        self.assertEqual(fit(rows,20),fit(list(reversed(rows)),20))
    def test_frozen_during_test(self):
        f=Fitted((),20)
        with self.assertRaises(FrozenInstanceError): f.train_end=30
    def test_hold_selected_using_validation(self):
        self.assertEqual(select_hold([(4,trades(),trades()),(12,trades(),trades(value=-1))],12)[0],4)
    def test_holding_fallback_explicit(self):
        self.assertEqual(select_hold([(4,trades(1),trades(1))],4)[1],'PREDECLARED_FALLBACK_NOT_VALIDATED')
    def test_purge_and_embargo(self):
        f=dict(train=(0,100),validation=(100,200),test=(200,300)); g=purged(f,20)
        self.assertEqual(g['train'],(0,80)); self.assertEqual(g['validation'],(100,180)); self.assertEqual(f['train'],(0,100))
    def test_purge_invalid(self):
        with self.assertRaises(ResearchRejected): purged(dict(train=(0,10),validation=(10,20)),20)


class EvidenceTests(unittest.TestCase):
    def test_block_interval_reproducibility(self): self.assertEqual(interval([[.01,-.02]*3]*2),interval([[.01,-.02]*3]*2))
    def test_insufficient_uncertainty(self): self.assertIsNone(interval([[.1,.2]])['interval'])
    def test_multiplicity_not_hidden(self):
        r=holm([dict(statistics=dict(raw_block_sign_p=.01)),dict(statistics=dict(raw_block_sign_p=.04))])
        self.assertEqual(r[0]['statistics']['holm_adjusted_p'],.02); self.assertFalse(r[0]['statistics']['reliable_advantage_established'])
    def test_record_hash(self):
        b=source(10)
        def hashed(bars): return hashlib.sha256(json.dumps(fixtures.replay(bars),sort_keys=True).encode()).hexdigest()
        self.assertEqual(hashed(b),hashed(b))
        self.assertNotEqual(hashed(b),hashed(b[:-1]+[replace(fixtures.bar(9,price=1.09),t=b[-1].t)]))
    def test_weekend_flattening(self):
        friday=timestamp('2026-09-04T20:45:00Z')
        r=fixtures.replay(source(3,friday))
        self.assertEqual(len(r['trades']),1)
        self.assertEqual(r['trades'][0]['exit_time'],timestamp('2026-09-04T20:55:00Z'))
        self.assertEqual(r['trades'][0]['exit_reason'],'TIME_OR_SESSION_EXIT')
    def test_JPY_conversion(self):
        q=Quotes(); q.put('USD_JPY',T,150,150.02)
        self.assertAlmostEqual(q.convert(150.02,'JPY','USD',T),1)
    def test_USD_directions(self): self.assertEqual(usd_direction('EUR_USD','BUY'),usd_direction('USD_JPY','SELL'))
    def test_baseline_reports_write_barred(self):
        with self.assertRaises(PermissionError): (ROOT/'data/research/trading_intelligence_v2/reports/TIV2_FINAL_DECISION.md').open('w')
    def test_original_outputs_write_barred(self):
        with self.assertRaises(PermissionError): (ROOT/'data/research/trading_intelligence_v2/outputs/metrics.json').open('w')
    def test_network_barred(self):
        with self.assertRaises(PermissionError): sys.audit('socket.connect',None,('example.com',443))
    def test_journal_barred(self):
        with self.assertRaises(PermissionError): (TEMP/'synthetic.sqlite').open('rb')
    def test_execution_barred(self):
        with self.assertRaises(PermissionError): __import__('forex_bot.bot_loop')
