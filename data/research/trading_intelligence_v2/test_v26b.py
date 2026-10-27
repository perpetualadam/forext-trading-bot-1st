"""Additional LIVE-host preparation tests. All HTTP/credentials are synthetic."""
from pathlib import Path,PureWindowsPath
import ast
import json
import tempfile
import unittest
from .core import timestamp,iso,ResearchRejected
from .history_fixtures import Virtual,payload
from .oanda_history_transport import CandleTransport,Response,HOSTS,approved_request
from .oanda_history_manifest import encoded,validated,digest
from .oanda_history_resume import Store,BASE
from .oanda_history import Plan,acquire

START=timestamp('2026-09-02T10:00:00Z')
END=START+10*300
PATH='/v3/instruments/EUR_USD/candles'


def parameters():
    return dict(granularity='M5',price='MBA',smooth='false',includeFirst='true',
                **{'from':iso(START),'to':iso(END-1)})


class LivePreparationTests(unittest.TestCase):
    def test_live_host_is_explicit(self):
        v=Virtual();t=v.transport(environment='live',attempts=1)
        t.candles('EUR_USD',START,END)
        self.assertEqual(v.calls[0],('GET',HOSTS['live'],PATH,parameters()))
        self.assertEqual(t.mode,'INJECTED_FIXTURE')
    def test_live_not_authorised_by_environment_alone(self):
        with self.assertRaisesRegex(ResearchRejected,'NOT_AUTHORISED'): CandleTransport('live')
    def test_no_token_in_fixture_mode(self):
        with self.assertRaisesRegex(ResearchRejected,'NO_CREDENTIALS'): CandleTransport('live',sender=lambda *a:None,token='SYNTHETIC_SECRET')
    def test_repr_and_response_body_redacted(self):
        self.assertNotIn('SYNTHETIC_SECRET',repr(Response(401,b'SYNTHETIC_SECRET')))
        self.assertIn('REDACTED',repr(Virtual().transport(environment='live')))
    def test_timeout_single_attempt_and_redacted(self):
        v=Virtual([TimeoutError('SYNTHETIC_SECRET')])
        with self.assertRaises(ResearchRejected) as e: v.transport(environment='live',attempts=1).candles('EUR_USD',START,END)
        self.assertEqual(len(v.calls),1);self.assertNotIn('SYNTHETIC_SECRET',str(e.exception))
    def test_429_no_retry_for_probe(self):
        v=Virtual([Response(429,b'',retry_after='5')])
        with self.assertRaises(ResearchRejected): v.transport(environment='live',attempts=1).candles('EUR_USD',START,END)
        self.assertEqual(len(v.calls),1);self.assertFalse(any(w>0 for w in v.waits))
    def test_503_no_retry_for_probe(self):
        v=Virtual([Response(503,b'')])
        with self.assertRaises(ResearchRejected): v.transport(environment='live',attempts=1).candles('EUR_USD',START,END)
        self.assertEqual(len(v.calls),1)
    def test_redirect_no_fallback(self):
        v=Virtual([Response(302,b'')])
        with self.assertRaisesRegex(ResearchRejected,'REDIRECT'): v.transport(environment='live',attempts=1).candles('EUR_USD',START,END)
        self.assertEqual(len(v.calls),1)
    def test_probe_no_count_with_two_bounds(self):
        self.assertNotIn('count',parameters())
        self.assertTrue(approved_request('GET',HOSTS['live'],PATH,parameters()))
    def test_pacing_for_separate_synthetic_calls(self):
        v=Virtual();t=v.transport(environment='live',attempts=1)
        t.candles('EUR_USD',START,END);t.candles('EUR_USD',END,END+3000)
        self.assertGreaterEqual(v.now,1)
    def test_no_operational_or_credential_loader_imports(self):
        source=(Path(__file__).parent/'oanda_history_transport.py').read_text()
        tree=ast.parse(source)
        modules=[a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
        modules += [n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        self.assertFalse(any(n.startswith(('forex_bot','oandapy','subprocess','dotenv','keyring')) for n in modules))
        self.assertNotIn('getenv(',source);self.assertNotIn('load_dotenv',source)
    def test_no_network(self):
        import sys
        with self.assertRaises(PermissionError): sys.audit('socket.connect',None,None)
    def test_no_journal(self):
        with self.assertRaises(PermissionError): (ROOT/'production.sqlite3').read_bytes()
    def test_no_live_permit(self):
        with self.assertRaises(PermissionError): (ROOT/'live.permit').write_text('never')
    def test_no_env_read(self):
        with self.assertRaises(PermissionError): (ROOT/'.env').read_bytes()


def refused(method='GET',host=HOSTS['live'],path=PATH):
    def test(self):
        v=Virtual()
        with self.assertRaises(ResearchRejected): v.transport(environment='live',attempts=1).request(method,host,path,parameters())
        self.assertFalse(v.calls)
    return test
for method in ('POST','PUT','PATCH','DELETE'):
    setattr(LivePreparationTests,'test_method_'+method,refused(method=method))
for name,path in [('account','/v3/accounts/fixture'),('order_create','/v3/accounts/fixture/orders'),
    ('order_modify','/v3/accounts/fixture/orders/fixture'),('account_modify','/v3/accounts/fixture/configuration'),
    ('position_close','/v3/accounts/fixture/positions/EUR_USD/close'),('trade_close','/v3/accounts/fixture/trades/fixture/close'),
    ('account_candles','/v3/accounts/fixture/instruments/EUR_USD/candles')]:
    setattr(LivePreparationTests,'test_refuse_'+name,refused(path=path))
for i,host in enumerate(('evil.example','api-fxtrade.oanda.com.evil','api-fxpractice.oanda.com','api-fxtrade.oanda.com:443')):
    setattr(LivePreparationTests,'test_refuse_host_'+str(i),refused(host=host))


class BoundaryTests(unittest.TestCase):
    def test_ten_completed_mba_candles(self):
        rows,q=validated(encoded(payload(start=START,count=10)),'EUR_USD',START,END,END+86400)
        self.assertEqual(len(rows),10);self.assertEqual(len(rows[0]['prices']),12);self.assertFalse(q['missing_intervals'])
    def test_right_boundary_refused(self):
        with self.assertRaisesRegex(ResearchRejected,'OUT_OF_RANGE'):
            validated(encoded(payload(start=START,count=11)),'EUR_USD',START,END,END+86400)
    def test_duplicate_refused(self):
        p=payload(start=START,count=10);p['candles'].append(p['candles'][-1])
        with self.assertRaisesRegex(ResearchRejected,'DUPLICATE'): validated(encoded(p),'EUR_USD',START,END,END+86400)
    def test_incomplete_not_counted(self):
        p=payload(start=START,count=10);p['candles'][-1]['complete']=False
        rows,q=validated(encoded(p),'EUR_USD',START,END,END+86400)
        self.assertEqual((len(rows),q['incomplete']),(9,1))
    def test_nonzero_nanoseconds_refused(self):
        p=payload(start=START,count=10);p['candles'][0]['time']='2026-09-02T10:00:00.000000001Z'
        with self.assertRaises(ResearchRejected): validated(encoded(p),'EUR_USD',START,END,END+86400)
    def test_misaligned_from_refused(self):
        p=parameters();p['from']=iso(START+1)
        with self.assertRaises(ResearchRejected): approved_request('GET',HOSTS['live'],PATH,p)
    def test_completion_filtered_end_is_a_counterexample_not_a_verified_contract(self):
        # The docs do not resolve whether to filters candle starts or completion.
        source=payload(start=START,count=10)['candles']
        selected=[c for c in source if timestamp(c['time'])+300<=END-1]
        rows,q=validated(encoded(dict(instrument='EUR_USD',granularity='M5',candles=selected)),
                         'EUR_USD',START,END,END+86400)
        self.assertEqual(len(rows),9)
        self.assertEqual(q['missing_intervals'][0]['missing_candles'],1)
        self.assertEqual(q['missing_intervals'][0]['start'],iso(END-300))
    def test_inclusive_and_exclusive_end_models_do_not_skip_or_duplicate(self):
        source=payload(start=START,count=20)['candles']
        for inclusive in (True,False):
            calls=[]
            def sender(method,host,path,p):
                a,b=timestamp(p['from']),timestamp(p['to']);calls.append(p)
                selected=[c for c in source if timestamp(c['time'])>=a and
                          (timestamp(c['time'])<=b if inclusive else timestamp(c['time'])<b)]
                return Response(200,encoded(dict(instrument='EUR_USD',granularity='M5',candles=selected)))
            v=Virtual();t=CandleTransport('live',sender=sender,clock=v.clock,wait=v.wait,attempts=1)
            times=[]
            for a,b in ((START,END),(END,END+3000)):
                rows,_=validated(t.candles('EUR_USD',a,b),'EUR_USD',a,b,END+86400)
                times.extend(timestamp(r['time']) for r in rows)
            self.assertEqual(times,list(range(START,END+3000,300)))
            self.assertEqual(len(times),len(set(times)));self.assertEqual(len(calls),2)


class StoragePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=BASE/'v26b_synthetic_tests',prefix='case-')
        self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_approved_generic_windows_path(self):
        p=PureWindowsPath('C:/TradingResearchData/OANDA')
        self.assertEqual(p.drive,'C:');self.assertNotIn('onedrive',[x.lower() for x in p.parts])
    def test_external_archive_remains_gated_in_v26_store(self):
        with self.assertRaisesRegex(ResearchRejected,'ROOT'): Store(Path('C:/TradingResearchData/OANDA'))
    def test_traversal_refused(self):
        with self.assertRaises(ResearchRejected): Store(self.root).publish('../escape',b'no')
    def test_symlink_detection_refuses_before_write(self):
        original=Path.is_symlink
        try:
            Path.is_symlink=lambda p: p==self.root or original(p)
            with self.assertRaisesRegex(ResearchRejected,'LINK'): Store(self.root)
        finally: Path.is_symlink=original
    def test_junction_detection_refuses_before_write(self):
        original=getattr(Path,'is_junction',None)
        try:
            Path.is_junction=lambda p: p==self.root
            with self.assertRaisesRegex(ResearchRejected,'JUNCTION'): Store(self.root)
        finally:
            if original is None: delattr(Path,'is_junction')
            else: Path.is_junction=original
    def test_atomic_synthetic_publication(self):
        s=Store(self.root);raw=encoded(dict(synthetic=True,credentials=False,market_data=False))
        s.publish('synthetic.json',raw);self.assertEqual(s.verify('synthetic.json',digest(raw)),raw)
        self.assertFalse(s.path('synthetic.json.pending').exists())
    def test_hash_tampering_refused(self):
        s=Store(self.root);raw=b'synthetic';s.publish('synthetic',raw);s.path('synthetic').write_bytes(b'changed')
        with self.assertRaisesRegex(ResearchRejected,'HASH'): s.verify('synthetic',digest(raw))
    def test_error_token_not_persisted(self):
        p=payload(start=START,count=10);p['token']='SYNTHETIC_SECRET'
        v=Virtual([Response(200,encoded(p))]);plan=Plan(START,END,('EUR_USD',),environment='live',batch_candles=10)
        with self.assertRaisesRegex(ResearchRejected,'STRUCTURE'):
            acquire(plan,v.transport(environment='live',attempts=1),self.root,retrieved=lambda:END+86400)
        self.assertFalse((self.root/'raw').exists())
        for f in self.root.rglob('*'):
            if f.is_file(): self.assertNotIn(b'SYNTHETIC_SECRET',f.read_bytes())
