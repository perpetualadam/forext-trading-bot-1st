"""Offline-only transport, storage, validation and integration safety oracles."""
from dataclasses import replace
import ast
import base64
import json
from pathlib import Path
import tempfile
import threading
import unittest
from .core import PAIRS,ResearchRejected,timestamp
from .history_fixtures import T,payload,Virtual
from .oanda_history_transport import CandleTransport,Response,Approval,HOSTS,approved_request,MAX_BODY
from .oanda_history_manifest import validated,encoded,decode,digest,independence,candle_time
from .oanda_history_resume import Store,BASE
from .oanda_history import Plan,acquire
from .oanda_history_integration import load_dataset,verify_policy_seal,evaluate_independent
from .mtf_features import prepare


def params(): return {'from':'2024-01-01T00:00:00+00:00','to':'2024-01-01T00:14:59+00:00',
    'price':'MBA','granularity':'M5','smooth':'false','includeFirst':'true'}


class TransportTests(unittest.TestCase):
    def test_approved_get(self):
        v=Virtual(); self.assertTrue(v.transport().candles('EUR_USD',T,T+900)); self.assertEqual(len(v.calls),1)
    def test_no_default_authentication(self):
        with self.assertRaisesRegex(ResearchRejected,'NOT_AUTHORISED'): CandleTransport()
    def test_no_credentials_in_fixture(self):
        with self.assertRaises(ResearchRejected): CandleTransport(sender=lambda *a:None,token='SYNTHETIC_SECRET')
    def test_host_environment_mismatch(self):
        v=Virtual()
        with self.assertRaises(ResearchRejected): v.transport().request('GET',HOSTS['live'],'/v3/instruments/EUR_USD/candles',params())
        self.assertEqual(v.calls,[])
    def test_no_request_count_parameter(self):
        p=params();p['count']=5000
        with self.assertRaises(ResearchRejected): approved_request('GET',HOSTS['practice'],'/v3/instruments/EUR_USD/candles',p)
    def test_redirect(self):
        v=Virtual([Response(302,b'SYNTHETIC_SECRET')])
        with self.assertRaisesRegex(ResearchRejected,'REDIRECT'): v.transport().candles('EUR_USD',T,T+900)
        self.assertEqual(len(v.calls),1)
    def test_429(self):
        v=Virtual([Response(429,b'',retry_after='7')]);v.transport().candles('EUR_USD',T,T+900)
        self.assertIn(7,v.waits);self.assertEqual(len(v.calls),2)
    def test_retry_after_date(self):
        from email.utils import formatdate
        v=Virtual([Response(429,b'',retry_after=formatdate(T+86400+5,usegmt=True))])
        v.transport().candles('EUR_USD',T,T+900);self.assertIn(5,v.waits)
    def test_long_retry_after_stops(self):
        v=Virtual([Response(429,b'',retry_after='3600')])
        with self.assertRaisesRegex(ResearchRejected,'BUDGET'): v.transport().candles('EUR_USD',T,T+900)
        self.assertEqual(len(v.calls),1)
    def test_malformed_retry_after(self):
        v=Virtual([Response(429,b'',retry_after='not-a-date')])
        with self.assertRaisesRegex(ResearchRejected,'INVALID_RETRY'): v.transport().candles('EUR_USD',T,T+900)
    def test_timeout_bounded_and_redacted(self):
        v=Virtual([TimeoutError('SYNTHETIC_SECRET')]*3)
        with self.assertRaises(ResearchRejected) as e: v.transport().candles('EUR_USD',T,T+900)
        self.assertNotIn('SYNTHETIC_SECRET',str(e.exception));self.assertEqual(len(v.calls),3)
    def test_429_exhausted(self):
        v=Virtual([Response(429,b'')]*3)
        with self.assertRaisesRegex(ResearchRejected,'EXHAUSTED'): v.transport().candles('EUR_USD',T,T+900)
        self.assertEqual(len(v.calls),3)
    def test_401_no_retry_or_body(self):
        v=Virtual([Response(401,b'SYNTHETIC_SECRET')])
        with self.assertRaises(ResearchRejected) as e: v.transport().candles('EUR_USD',T,T+900)
        self.assertNotIn('SYNTHETIC_SECRET',str(e.exception));self.assertEqual(len(v.calls),1)
    def test_body_cap(self):
        v=Virtual([Response(200,b'x'*(MAX_BODY+1))])
        with self.assertRaises(ResearchRejected): v.transport().candles('EUR_USD',T,T+900)
    def test_html_refused(self):
        v=Virtual([Response(200,b'<html>',content_type='text/html')])
        with self.assertRaises(ResearchRejected): v.transport().candles('EUR_USD',T,T+900)
    def test_pacing(self):
        v=Virtual();t=v.transport();t.candles('EUR_USD',T,T+900);t.candles('EUR_USD',T+900,T+1800)
        self.assertGreaterEqual(v.now,1)
    def test_cancel_before_request(self):
        v=Virtual();stop=threading.Event();stop.set()
        with self.assertRaisesRegex(ResearchRejected,'CANCELLED'): v.transport(cancel=stop).candles('EUR_USD',T,T+900)
        self.assertFalse(v.calls)
    def test_repr_redacted(self): self.assertIn('REDACTED',repr(Virtual().transport()))
    def test_approval_requires_scope(self):
        a=Approval('practice',True,True,True,True)
        with self.assertRaisesRegex(ResearchRejected,'SCOPE'): CandleTransport(token='SYNTHETIC_SECRET',approval=a)
    def test_scope_blocks_before_sender(self):
        a=Approval('practice',True,True,True,True,T,T+900,('EUR_USD',))
        t=CandleTransport(token='SYNTHETIC_SECRET',approval=a,wall=lambda:T+86400)
        calls=[];t.sender=lambda *a:calls.append(a)
        with self.assertRaisesRegex(ResearchRejected,'SCOPE'): t.candles('GBP_USD',T,T+900)
        self.assertFalse(calls)
    def test_tls_backend_with_fake_http_only(self):
        import sys,types
        saved={k:sys.modules.get(k) for k in ('http','http.client','ssl')}
        calls=[]
        class Reply:
            status=200
            def getheader(self,name,default=None): return 'application/json' if name=='Content-Type' else default
            def read1(self,size):
                if getattr(self,'done',False): return b''
                self.done=True;return encoded(payload())
        class Connection:
            sock=None
            def __init__(self,host,**kwargs): calls.append(('host',host,kwargs))
            def request(self,method,path,headers): calls.append(('request',method,path,dict(headers)))
            def getresponse(self): return Reply()
            def close(self): calls.append(('closed',))
        http=types.ModuleType('http');client=types.ModuleType('http.client');client.HTTPSConnection=Connection
        http.client=client;http.__path__=[]
        ssl=types.ModuleType('ssl');ssl.create_default_context=lambda:'SYNTHETIC_TLS_CONTEXT'
        try:
            sys.modules.update({'http':http,'http.client':client,'ssl':ssl})
            a=Approval('practice',True,True,True,True,T,T+900,('EUR_USD',))
            v=Virtual();t=CandleTransport(token='SYNTHETIC_SECRET',approval=a,clock=v.clock,wait=v.wait,wall=lambda:T+86400)
            self.assertTrue(t.candles('EUR_USD',T,T+900))
            self.assertEqual(calls[0][1],HOSTS['practice']);self.assertEqual(calls[1][1],'GET')
            self.assertNotIn('SYNTHETIC_SECRET',calls[1][2]);self.assertIn('Authorization',calls[1][3])
            self.assertEqual(calls[-1],('closed',))
        finally:
            for key,value in saved.items():
                if value is None: sys.modules.pop(key,None)
                else: sys.modules[key]=value
    def test_no_broker_write_imports(self):
        p=Path(__file__).parent
        for name in ('oanda_history.py','oanda_history_transport.py','oanda_history_resume.py','oanda_history_manifest.py'):
            tree=ast.parse((p/name).read_text())
            names=[a.name for node in ast.walk(tree) if isinstance(node,ast.Import) for a in node.names]
            names += [node.module or '' for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
            self.assertFalse(any('oandapy' in n or n.startswith('forex_bot') for n in names))


def forbidden_case(method='GET',host=HOSTS['practice'],path='/v3/instruments/EUR_USD/candles'):
    def test(self):
        v=Virtual()
        with self.assertRaises(ResearchRejected): v.transport().request(method,host,path,params())
        self.assertEqual(v.calls,[])
    return test
for method in ('POST','PUT','PATCH','DELETE','get','HEAD'):
    setattr(TransportTests,'test_method_'+method,forbidden_case(method=method))
for i,host in enumerate(('https://api-fxpractice.oanda.com','evil.example','api-fxpractice.oanda.com.evil','api-fxpractice.oanda.com:443','127.0.0.1')):
    setattr(TransportTests,'test_host_'+str(i),forbidden_case(host=host))
for i,path in enumerate(('/v3/accounts/123/orders','/v3/accounts/123/positions/EUR_USD/close','/v3/accounts/123/trades/1/close',
    '/v3/accounts/123/instruments/EUR_USD/candles','/v3/instruments/EUR_USD/candles?token=secret',
    '/v3/instruments/../candles','/v3/instruments/EUR%5FUSD/candles')):
    setattr(TransportTests,'test_endpoint_'+str(i),forbidden_case(path=path))


class ValidationTests(unittest.TestCase):
    def check(self,p): return validated(encoded(p),'EUR_USD',T,T+900,T+86400)
    def test_valid(self): self.assertEqual(self.check(payload())[1]['candles'],3)
    def test_incomplete_excluded(self):
        p=payload();p['candles'][1]['complete']=False
        r,q=self.check(p);self.assertEqual((len(r),q['incomplete']),(2,1));self.assertTrue(q['missing_intervals'])
    def test_empty_not_complete(self):
        _,q=self.check(payload(empty=True));self.assertTrue(q['empty_is_not_completeness']);self.assertEqual(q['missing_intervals'][0]['missing_candles'],3)
    def test_missing_range(self):
        p=payload();p['candles'].pop(1);_,q=self.check(p)
        self.assertEqual(q['missing_intervals'][0]['missing_candles'],1)
    def test_weekend_unknown(self):
        start=timestamp('2024-01-06T00:00:00Z')
        _,q=validated(encoded(payload(start=start,empty=True)),'EUR_USD',start,start+900,start+86400)
        self.assertEqual(q['missing_intervals'][0]['kind'],'WEEKEND_CONTAINING_UNVERIFIED')
    def test_no_nan_json(self):
        with self.assertRaises(ResearchRejected): decode(b'{"a":NaN}')
    def test_duplicate_json_key(self):
        with self.assertRaises(ResearchRejected): decode(b'{"a":1,"a":2}')
    def test_preserve_lexemes(self):
        p=payload();p['candles'][0]['mid']['o']='1.100000000000'
        r,_=self.check(p);self.assertEqual(r[0]['prices'][0],'1.100000000000')
    def test_utc_normalization(self): self.assertEqual(candle_time('2024-01-01T01:00:00+01:00'),T)
    def test_nanos_no_truncation(self):
        with self.assertRaises(ResearchRejected): candle_time('2024-01-01T00:00:00.000000001Z')


def bad_payload(kind):
    def test(self):
        p=payload();c=p['candles'][0]
        if kind=='duplicate': p['candles'].insert(1,c)
        elif kind=='disorder': p['candles'].reverse()
        elif kind=='crossed': c['bid']['o']='2.0';c['bid']['h']='2.0'
        elif kind=='ohlc': c['ask']['h']='1.0'
        elif kind=='missing_ask': c.pop('ask')
        elif kind=='incomplete_flag': c['complete']='true'
        elif kind=='nonfinite': c['bid']['o']='NaN'
        elif kind=='precision': c['bid']['o']='1.1234567890123'
        elif kind=='wrong_instrument': p['instrument']='GBP_USD'
        elif kind=='wrong_granularity': p['granularity']='H1'
        elif kind=='out_of_range': c['time']='2023-12-31T23:55:00Z'
        elif kind=='unexpected_field': p['token']='SYNTHETIC_SECRET'
        elif kind=='future_complete': c['time']='2024-01-01T00:00:00Z';return self.assertRaises(ResearchRejected,validated,encoded(p),'EUR_USD',T,T+900,T)
        with self.assertRaises(ResearchRejected): self.check(p)
    return test
for kind in ('duplicate','disorder','crossed','ohlc','missing_ask','incomplete_flag','nonfinite','precision',
             'wrong_instrument','wrong_granularity','out_of_range','unexpected_field','future_complete'):
    setattr(ValidationTests,'test_'+kind,bad_payload(kind))


class StorageTests(unittest.TestCase):
    def setUp(self):
        BASE.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=BASE,prefix='synthetic-')
        self.root=Path(self.temp.name);self.v=Virtual();self.plan=Plan(T,T+1800,('EUR_USD',),batch_candles=3)
    def tearDown(self): self.temp.cleanup()
    def get(self,**kwargs): return acquire(self.plan,self.v.transport(),self.root,retrieved=lambda:T+86400,**kwargs)
    def test_batches_terminate(self):
        m=self.get();self.assertEqual(len(self.v.calls),2);self.assertEqual(m['candle_count'],6)
    def test_resume_no_network(self):
        self.get();self.v.calls.clear();self.get();self.assertFalse(self.v.calls)
    def test_resume_after_interruption(self):
        def stop(row): raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.get(progress=stop)
        self.assertEqual(len(self.v.calls),1);self.get();self.assertEqual(len(self.v.calls),2)
    def test_orphan_raw_resume_retains_retrieval_time(self):
        store=Store(self.root);raw=encoded(payload())
        envelope=dict(request=dict(instrument='EUR_USD',start=T,end=T+900),retrieved_epoch=T+3600,
                      body_base64=base64.b64encode(raw).decode())
        store.publish('raw/000000.json',encoded(envelope))
        self.get()
        commit=decode(store.read('commits/000000.json'))
        self.assertEqual(commit['retrieved_epoch'],T+3600);self.assertEqual(len(self.v.calls),1)
    def test_unfinished_raw_stops_without_http(self):
        store=Store(self.root);store.publish('raw/000000.json.pending',b'partial')
        with self.assertRaisesRegex(ResearchRejected,'AMBIGUOUS'): self.get()
        self.assertFalse(self.v.calls)
    def test_hash_mismatch(self):
        self.get();p=self.root/'validated/000000.json';p.write_bytes(b'[]')
        with self.assertRaisesRegex(ResearchRejected,'HASH'): self.get()
    def test_atomic_no_partial_complete(self):
        store=Store(self.root);store.path('item.pending').write_bytes(b'partial')
        with self.assertRaisesRegex(ResearchRejected,'AMBIGUOUS'): store.publish('item',b'complete')
        self.assertFalse(store.path('item').exists())
    def test_verified_pending_adopted(self):
        store=Store(self.root);store.path('item.pending').write_bytes(b'complete')
        store.publish('item',b'complete');self.assertEqual(store.read('item'),b'complete')
    def test_cannot_replace_immutable_batch(self):
        with self.assertRaisesRegex(ResearchRejected,'REPLACEMENT'): Store(self.root).publish('raw/a.json',b'no',replace_index=True)
    def test_manifest_count_tamper(self):
        self.get();p=self.root/'manifest.json';m=decode(p.read_bytes());m['candle_count']+=1;p.write_bytes(encoded(m))
        with self.assertRaisesRegex(ResearchRejected,'TOTAL'): load_dataset(self.root)
    def test_synthetic_not_independent(self):
        self.get()
        with self.assertRaisesRegex(ResearchRejected,'SYNTHETIC'):
            evaluate_independent(self.root,{},coverage_reviewed=True,calendar_evidence='SYNTHETIC')
    def test_immutable_conflict(self):
        store=Store(self.root);store.publish('item',b'first')
        with self.assertRaisesRegex(ResearchRejected,'CONFLICT'): store.publish('item',b'second')
    def test_disk_budget(self):
        with self.assertRaisesRegex(ResearchRejected,'BUDGET'): self.get(max_bytes=10)
    def test_preserve_on_failed_request(self):
        self.v.responses=[Response(200,encoded(payload())),Response(401,b'')]
        with self.assertRaises(ResearchRejected): self.get()
        self.assertTrue((self.root/'commits/000000.json').exists());self.assertFalse((self.root/'commits/000001.json').exists())
    def test_root_escape(self):
        with self.assertRaises(ResearchRejected): Store(ROOT/'production')
    def test_path_escape(self):
        with self.assertRaises(ResearchRejected): Store(self.root).publish('../../../../outside',b'no')
    def test_single_writer(self):
        store=Store(self.root)
        with store.locked():
            with self.assertRaisesRegex(ResearchRejected,'BUSY'):
                with Store(self.root).locked(): self.fail('second writer accepted')
    def test_reproducible(self):
        a=self.get();b=self.get();self.assertEqual(encoded(a),encoded(b))
    def test_all_six_aggregation(self):
        plan=Plan(T,T+60*300,PAIRS,batch_candles=50)
        acquire(plan,self.v.transport(),self.root,retrieved=lambda:T+86400)
        data,provenance=load_dataset(self.root);frames,_,_=prepare(data)
        self.assertEqual(set(data),set(PAIRS));self.assertEqual(len(frames['EUR_USD']['H4']),1)
    def test_independent_eval_closed_by_default(self):
        with self.assertRaisesRegex(ResearchRejected,'COVERAGE'): evaluate_independent(self.root,{})


class ProtocolTests(unittest.TestCase):
    def test_walkforward_purge(self):
        from .cost_aware_policies import Split
        with self.assertRaises(ResearchRejected): Split((0,1000),(1001,2000),(2001,3000))
    def test_final_outcome_tuning_refused(self):
        from .cost_aware_policies import Split,fit_selector
        split=Split((0,100000),(157600,257600),(315200,415200))
        with self.assertRaisesRegex(ResearchRejected,'test_outcomes'):
            fit_selector([dict(phase='test')],split,independent=True,evidence='SYNTHETIC')
    def test_nonfinite_minimum_cannot_bypass_coverage(self):
        with self.assertRaisesRegex(ResearchRejected,'MINIMUM'):
            evaluate_independent(BASE/'not-created',{},minimum_days=float('nan'),coverage_reviewed=True,calendar_evidence='SYNTHETIC')
    def test_request_max(self): self.assertEqual(len(Plan(T,T+5001*300,('EUR_USD',),batch_candles=5000).batches()),2)
    def test_request_above_max(self):
        with self.assertRaises(ResearchRejected): Plan(T,T+900,batch_candles=5001)
    def test_total_request_budget(self):
        with self.assertRaisesRegex(ResearchRejected,'BUDGET'): Plan(T,T+365*86400,batch_candles=1)
    def test_frozen_policies(self): self.assertEqual(len(verify_policy_seal()),64)
    def test_overlap_not_new(self): self.assertEqual(independence(timestamp('2026-09-01T00:00:00Z'),timestamp('2026-10-01T00:00:00Z')),'OVERLAPPING')
    def test_unknown_not_independent(self): self.assertEqual(independence(T,T+86400),'PROVENANCE_UNVERIFIED')
    def test_prior_explicit(self): self.assertEqual(independence(T,T+86400,previously_examined=True),'PREVIOUSLY_EXAMINED')
    def test_attested_synthetic_independence(self):
        self.assertEqual(independence(T,T+86400,provenance=True,rights=True,history_reviewed=True,controlled_first_access=True,evidence='SYNTHETIC'),'INDEPENDENT_UNTOUCHED')
    def test_no_network(self):
        import sys
        with self.assertRaises(PermissionError): sys.audit('socket.connect',None,None)
    def test_no_journal(self):
        with self.assertRaises(PermissionError): (ROOT/'production.sqlite3').read_bytes()
    def test_no_trading_permit(self):
        with self.assertRaises(PermissionError): (ROOT/'live.permit').write_text('never')
    def test_no_credentials(self):
        with self.assertRaises(PermissionError): (ROOT/'.env').read_bytes()
    def test_older_reports_preserved(self):
        with self.assertRaises(PermissionError): (Path(__file__).parent/'reports/v25/never.txt').write_text('never')
