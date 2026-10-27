"""Synthetic executable specifications. Test grant seeding is fixture-only."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from .oneshot_archive import Archive,Refused,FIXTURES,safe_parts
from .oneshot import SPEC,SPEC_HASH,PHASES,initialise,journal,reserve,run_once,request_guard
from .oanda_history_manifest import encoded,digest

SECRET='SYNTHETIC_NOT_A_REAL_CREDENTIAL_123456'


class Safety(unittest.TestCase):
    def fixture(self,authorised=True):
        root=Path(tempfile.mkdtemp(prefix='case_',dir=FIXTURES))
        archive=Archive(root,synthetic=True)
        if authorised:
            archive.put('journal.json',encoded({'version':1,'state':'AUTHORISED_NOT_CONSUMED','spec':SPEC_HASH,'attempts':0}))
            archive.put('grant.json',encoded({'synthetic':True,'spec':SPEC_HASH,'identity':archive.identity}))
        return archive

    def run_fixture(self,archive,**kw):
        return run_once(archive.root,synthetic_secret=SECRET,pin=archive.identity,**kw)

    def assert_consumed(self,archive):
        self.assertTrue(archive.path('grant.claimed.json').exists())
        before={p.name:p.read_bytes() for p in archive.root.iterdir() if p.is_file()}
        result=self.run_fixture(archive)
        self.assertEqual(result['kind'],'REFUSED',result)
        self.assertEqual(before,{p.name:p.read_bytes() for p in archive.root.iterdir() if p.is_file()})

    def test_initialise_never_authorises(self):
        a=self.fixture(False);initialise(a)
        self.assertEqual(journal(a)['state'],'NOT_AUTHORISED');self.assertFalse(a.path('grant.json').exists())
        self.assertEqual(self.run_fixture(a)['kind'],'REFUSED')

    def test_transition_cannot_authorise_or_reset(self):
        from .oneshot import transition
        a=self.fixture(False);initialise(a)
        for state in ('AUTHORISED_NOT_CONSUMED','REQUEST_RESERVED','SESSION_CONSUMED'):
            with self.subTest(state=state),self.assertRaises(Refused):transition(a,state,0)
        self.assertEqual(journal(a)['state'],'NOT_AUTHORISED')

    def test_guard_cannot_follow_mutated_spec(self):
        old=SPEC['host']
        try:
            SPEC['host']='example.invalid'
            with self.assertRaises(Refused):request_guard(**SPEC)
        finally:SPEC['host']=old

    def test_missing_journal(self):
        a=self.fixture(False);self.assertEqual(self.run_fixture(a)['kind'],'REFUSED')
        self.assertFalse(a.path('synthetic_dispatch.json').exists())

    def test_corrupt_journal(self):
        a=self.fixture();a.put('journal.json',b'{bad',replace=True)
        self.assertEqual(self.run_fixture(a)['kind'],'REFUSED')

    def test_malformed_journal_types(self):
        for field,value in [('version',True),('state',[]),('attempts',False),('attempts','0')]:
            with self.subTest(field=field):
                a=self.fixture();obj=json.loads(a.read('journal.json'));obj[field]=value
                a.put('journal.json',encoded(obj),replace=True)
                self.assertEqual(self.run_fixture(a)['kind'],'REFUSED')
                self.assertFalse(a.path('grant.claimed.json').exists())

    def test_numeric_synthetic_flag_refused(self):
        a=self.fixture();obj=json.loads(a.read('grant.json'));obj['synthetic']=1
        a.put('grant.json',encoded(obj),replace=True)
        self.assertEqual(self.run_fixture(a)['kind'],'REFUSED')

    def test_missing_grant(self):
        a=self.fixture();a.path('grant.json').unlink();self.assertEqual(self.run_fixture(a)['kind'],'REFUSED')

    def test_mismatched_grant(self):
        a=self.fixture();a.put('grant.json',encoded({'synthetic':True,'spec':'wrong'}),replace=True)
        self.assertEqual(self.run_fixture(a)['kind'],'REFUSED')

    def test_durable_reservation(self):
        a=self.fixture()
        with a.locked():reserve(a)
        self.assertEqual(journal(a)['state'],'REQUEST_RESERVED');self.assert_consumed(a)

    def test_duplicate_reservation(self):
        a=self.fixture()
        with a.locked():
            reserve(a)
            with self.assertRaises(Refused):reserve(a)

    def test_valid_response(self):
        a=self.fixture();r=self.run_fixture(a)
        self.assertEqual((r['kind'],r.get('count')),('DONE',10),r)
        self.assertEqual(journal(a)['state'],'SESSION_CONSUMED');self.assert_consumed(a)
        receipt=json.loads(a.read('receipt.json'))
        self.assertEqual(receipt['raw_sha256'],digest(a.read('raw.json')))
        self.assertEqual(receipt['validated_sha256'],digest(a.read('validated.json')))

    def test_two_process_race(self):
        a=self.fixture();barrier=threading.Barrier(3,timeout=4);results=[];errors=[]
        def contender():
            try:barrier.wait();results.append(self.run_fixture(a,seconds=4))
            except BaseException as e:errors.append(type(e).__name__)
        workers=[threading.Thread(target=contender) for _ in range(2)]
        for t in workers:t.start()
        barrier.wait()
        for t in workers:t.join(5);self.assertFalse(t.is_alive())
        self.assertEqual(errors,[]);self.assertEqual(sorted(r['kind'] for r in results),['DONE','REFUSED'],results)
        self.assertEqual(json.loads(a.read('synthetic_dispatch.json'))['attempts'],1)
        self.assert_consumed(a)

    def test_total_deadline_preparation(self):self.check_stall('preparation',consumed=False)
    def test_total_deadline_connection(self):self.check_stall('connection')
    def test_total_deadline_headers(self):self.check_stall('headers')
    def test_total_deadline_body(self):self.check_stall('body')
    def test_total_deadline_validation(self):self.check_stall('validation')

    def check_stall(self,phase,consumed=True):
        a=self.fixture();r=self.run_fixture(a,seconds=1.5,fault='stall_'+phase)
        self.assertEqual(r['kind'],'OUTCOME_UNKNOWN',r);self.assertTrue(r['worker_exited'],r)
        self.assertLessEqual(r['elapsed'],1.5,r)
        if consumed:self.assert_consumed(a)
        else:self.assertFalse(a.path('synthetic_dispatch.json').exists())

    def test_secret_not_persisted(self):
        a=self.fixture();r=self.run_fixture(a)
        self.assertNotIn(SECRET,repr(r))
        for path in a.root.iterdir():
            if path.is_file():self.assertNotIn(SECRET.encode(),path.read_bytes())

    def test_secret_error_redaction(self):
        a=self.fixture();r=self.run_fixture(a,fault='malformed')
        self.assertEqual(r['kind'],'REFUSED');self.assertNotIn(SECRET,repr(r));self.assert_consumed(a)

    def test_non_synthetic_secret_refused(self):
        a=self.fixture()
        with self.assertRaises(Refused):run_once(a.root,synthetic_secret='NOT_A_TOKEN')
        self.assertFalse(a.path('grant.claimed.json').exists())

    def test_invalid_deadline(self):
        a=self.fixture()
        for value in (0,True,float('nan'),float('inf'),16,'15'):
            with self.subTest(value=value),self.assertRaises(Refused):self.run_fixture(a,seconds=value)

    def test_exact_request(self):self.assertTrue(request_guard(**SPEC))
    def test_existing_transport_never_retries(self):
        from .oneshot_transport import fetch_fixture_once
        from .oanda_history_transport import Response
        from .core import ResearchRejected
        for failure in (Response(503,b''),Response(429,b''),Response(302,b''),OSError('SYNTHETIC')):
            calls=[]
            def sender(method,host,path,params):
                calls.append((method,host,path,params))
                if isinstance(failure,Exception):raise failure
                return failure
            with self.subTest(failure=type(failure).__name__),self.assertRaises(ResearchRejected):fetch_fixture_once(sender)
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0],(SPEC['method'],SPEC['host'],SPEC['path'],SPEC['params']))
    def test_get_only(self):
        for method in ('POST','PUT','PATCH','DELETE','get'):
            with self.subTest(method=method),self.assertRaises(Refused):request_guard(**{**SPEC,'method':method})
    def test_host_only(self):
        for host in ('api-fxpractice.oanda.com','api-fxtrade.oanda.com.evil','https://api-fxtrade.oanda.com'):
            with self.subTest(host=host),self.assertRaises(Refused):request_guard(**{**SPEC,'host':host})
    def test_path_only(self):
        for path in ('/v3/accounts','/v3/accounts/1/orders','/v3/instruments/GBP_USD/candles'):
            with self.subTest(path=path),self.assertRaises(Refused):request_guard(**{**SPEC,'path':path})
    def test_params_exact(self):
        for params in ({**SPEC['params'],'count':10},{**SPEC['params'],'price':'M'},{}):
            with self.subTest(params=params),self.assertRaises(Refused):request_guard(**{**SPEC,'params':params})
    def test_proxy_refused(self):
        with self.assertRaises(Refused):request_guard(**SPEC,proxy='http://localhost')
    def test_headers_refused(self):
        with self.assertRaises(Refused):request_guard(**SPEC,headers={'Authorization':SECRET})

    def test_traversal_refused(self):
        for value in ('../raw','/raw','raw/../x','raw\\x','x:stream','x//y','x.'):
            with self.subTest(value=value),self.assertRaises(Refused):safe_parts(value)
    def test_repository_root_refused(self):
        with self.assertRaises(Refused):Archive(Path(__file__).parent,synthetic=True)
    def test_onedrive_root_refused(self):
        with self.assertRaises(Refused):Archive(r'C:\Users\Example\OneDrive\OANDA')
    def test_missing_archive(self):
        with self.assertRaises(Refused):Archive(FIXTURES/'missing',synthetic=True)
    def test_identity_mismatch(self):
        a=self.fixture()
        with self.assertRaises(Refused):Archive(a.root,synthetic=True,pin=[0,0])
    def test_atomic_immutable_publication(self):
        a=self.fixture();self.assertEqual(a.put('atomic.json',b'123'),digest(b'123'))
        self.assertFalse(a.path('atomic.json.pending').exists())
        with self.assertRaises(Refused):a.put('atomic.json',b'456')
        self.assertEqual(a.read('atomic.json'),b'123')

    def test_atomic_no_overwrite_race(self):
        a=self.fixture();a.put('a.json',b'A');a.put('b.json',b'B')
        barrier=threading.Barrier(3,timeout=3);accepted=[];rejected=[]
        def contender(name):
            barrier.wait()
            try:a.rename(name+'.json','winner.json');accepted.append(name)
            except Exception:rejected.append(name)
        threads=[threading.Thread(target=contender,args=(n,)) for n in ('a','b')]
        for t in threads:t.start()
        barrier.wait()
        for t in threads:t.join(3);self.assertFalse(t.is_alive())
        self.assertEqual(len(accepted),1);self.assertEqual(len(rejected),1)
        self.assertEqual(a.read('winner.json'),accepted[0].upper().encode())

    def test_fence_unavailable_never_releases_secret(self):
        from unittest.mock import patch
        a=self.fixture()
        target='tiv2.oneshot_windows.Job' if os.name=='nt' else 'tiv2.oneshot.subprocess.Popen'
        with patch(target,side_effect=RuntimeError('SYNTHETIC_FENCING_FAILURE')):
            result=self.run_fixture(a)
        self.assertEqual(result['kind'],'OUTCOME_UNKNOWN');self.assertTrue(result['worker_exited'])
        self.assertFalse(a.path('grant.claimed.json').exists())
        self.assertFalse(a.path('synthetic_dispatch.json').exists())
    def test_pending_ambiguous_refused(self):
        a=self.fixture();a.path('journal.json.pending').write_bytes(b'torn')
        self.assertEqual(self.run_fixture(a)['kind'],'REFUSED');self.assert_consumed(a)
    def test_hash_mismatch(self):
        a=self.fixture();original=a.read
        a.read=lambda name:b'tampered' if name=='x.json' else original(name)
        with self.assertRaises(Refused):a.put('x.json',b'expected')
    def test_hardlink_refused(self):
        a=self.fixture();a.put('original.json',b'x');os.link(a.path('original.json'),a.root/'link.json')
        with self.assertRaises(Refused):a.read('link.json')
    def test_symlink_or_junction_refused(self):
        a=self.fixture();link=a.root/'link'
        if os.name=='nt':
            # Unprivileged Windows symlink creation is not assumed. Directly
            # emulate only the reparse predicate; native junction tested separately.
            from unittest.mock import patch
            with patch.object(Path,'is_junction',return_value=True):
                with self.assertRaises(Refused):a.path('link/x')
        else:
            os.symlink(a.root,link,target_is_directory=True)
            with self.assertRaises(Refused):a.path('link/x')
    def test_no_operational_imports(self):
        import sys
        self.assertFalse(any(n=='forex_bot' or n.startswith('forex_bot.') for n in sys.modules))
    def test_no_production_state_access(self):
        with self.assertRaises(PermissionError):Path('fake_production.db').read_bytes()
    def test_no_network(self):
        import socket
        with self.assertRaises(PermissionError):socket.socket()

    def test_existing_validator_archive_binding(self):
        from .oneshot_response import publish_candles
        from .history_fixtures import payload
        from .core import timestamp
        a=self.fixture()
        for name in ('raw','validated','manifests'):a.path(name).mkdir()
        start=timestamp(SPEC['params']['from'])
        receipt=publish_candles(a,encoded(payload(start=start,count=9)),name='v26c_fixture',
            start=start,end=start+3000,retrieved=start+86400,synthetic=True)
        self.assertEqual(receipt['observed_complete_count'],9)
        self.assertEqual(receipt['raw_sha256'],digest(a.read(receipt['raw'])))
        self.assertTrue(a.path('manifests/v26c_fixture.json').exists())

    def test_archive_rejects_secret_bearing_response(self):
        from .oneshot_response import publish_candles
        from .history_fixtures import payload
        from .core import timestamp,ResearchRejected
        a=self.fixture();start=timestamp(SPEC['params']['from'])
        obj=payload(start=start,count=1);obj['token']=SECRET
        with self.assertRaises(ResearchRejected):
            publish_candles(a,encoded(obj),name='v26c_fixture',start=start,end=start+3000,
                retrieved=start+86400,synthetic=True)
        self.assertFalse(a.path('raw/v26c_fixture.json').exists())

    def test_fixture_cannot_assert_authenticated_provenance(self):
        from .oneshot_response import publish_candles
        a=self.fixture()
        with self.assertRaises(Refused):
            publish_candles(a,b'{}',name='v26c_fixture',start=0,end=300,retrieved=600,synthetic=False)

    def test_raw_pending_retained_after_crash(self):
        a=self.fixture();self.run_fixture(a,fault='crash_archive_publication')
        self.assertTrue(a.path('raw.json.pending').exists());self.assertFalse(a.path('receipt.json').exists())
        self.assert_consumed(a)

    def test_final_pending_retained_after_crash(self):
        a=self.fixture();self.run_fixture(a,fault='crash_final_persistence')
        self.assertTrue(a.path('journal.json.pending').exists())
        self.assertEqual(journal(a)['state'],'RESPONSE_RECEIVED');self.assert_consumed(a)


def crash_test(phase):
    def test(self):
        a=self.fixture();r=self.run_fixture(a,fault='crash_'+phase)
        self.assertEqual(r['kind'],'OUTCOME_UNKNOWN',r);self.assertTrue(r['worker_exited'])
        self.assert_consumed(a)
    return test


def stall_test(phase):
    def test(self):self.check_stall(phase)
    return test


for phase in PHASES:
    setattr(Safety,'test_crash_'+phase,crash_test(phase))
    setattr(Safety,'test_stall_'+phase,stall_test(phase))


def response_test(fault,count):
    def test(self):
        a=self.fixture();r=self.run_fixture(a,fault=fault)
        self.assertEqual(r['kind'],'DONE' if count is not None else 'REFUSED',r)
        if count is not None:self.assertEqual(r['count'],count)
        self.assert_consumed(a)
    return test


for fault,count in [('malformed',None),('http_error',None),('redirect',None),('empty',0),
                    ('nine',9),('incomplete',9),('out_of_range',None)]:
    setattr(Safety,'test_response_'+fault,response_test(fault,count))
