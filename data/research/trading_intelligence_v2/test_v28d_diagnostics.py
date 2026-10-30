"""Synthetic native/loopback failures only; no credential loader or LIVE issuer."""
import json,os,sys,time,ssl,socket,copy,subprocess,importlib.util
from pathlib import Path
from unittest.mock import patch
if __name__=='__main__':
    _p=Path(__file__).resolve().parent
    _s=importlib.util.spec_from_file_location('tiv2',_p/'__init__.py',submodule_search_locations=[str(_p)])
    _m=importlib.util.module_from_spec(_s);sys.modules['tiv2']=_m;_s.loader.exec_module(_m);__package__='tiv2'
from . import test_v28c as previous
from . import failure_diagnostics as d,oneshot_network as network
from . import bounded_acquisition as b
from .oneshot_archive import Refused,Archive
from .oneshot_bridge import SyntheticCredentialProvider
from .oanda_history_manifest import encoded,decode,digest
previous.legacy.NATIVE=globals().get('NATIVE',False)

class Diagnostics(previous.Bounded):
    def checked(self,ar,cap,reason=None,stage=None):
        value=d.read_verified(ar)
        if reason:self.assertEqual(value['reason'],reason,value)
        if stage:self.assertEqual(value['stage'],stage,value)
        self.assertFalse(value['retry_allowed']);self.assertEqual(value['outcome'],'UNKNOWN_NO_RETRY')
        result=decode(ar.read('result.json'));self.assertEqual(result['diagnostic_sha256'],digest(ar.read('diagnostic.json')))
        with Archive(ar.root,synthetic=True) as reopened:self.assertEqual(d.read_verified(reopened),value)
        for name in ('diagnostic.json','result.json'):
            body=ar.read(name);self.assertNotIn(self.secret.encode(),body);self.assertLess(len(body),2048)
        return value
    def test_diag_independent_process_restart(self):
        _,ar,cap,_=self.failure(scenario='invalid_schema',expected_requests=1);value=self.checked(ar,cap)
        exe=getattr(sys,'_base_executable',sys.executable);command=[exe,'-I','-S','-B',str(Path(__file__).resolve()),'--fixture-diagnostic-probe']
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'SystemRoot':r'C:\Windows'} if os.name=='nt' else {},close_fds=True)
        out,err=process.communicate(encoded(dict(root=str(ar.root))),timeout=10);self.assertEqual(process.returncode,0,err.decode())
        self.assertEqual(decode(out),dict(reason=value['reason'],stage=value['stage'],sha256=digest(ar.read('diagnostic.json'))))
    def test_diag_parent_exception_secret_not_persisted(self):
        _,ar,cap=self.new()
        with self.server() as server,patch.object(SyntheticCredentialProvider,'credential',side_effect=RuntimeError(self.secret+' Authorization: SECRET')):
            result=self.run_bounded(ar,cap,server);self.assertNotEqual(result['kind'],'DONE');self.assertEqual(server.requests,[])
        self.checked(ar,cap,'UNKNOWN_FAILURE','TOKEN')
        for path in ar.root.rglob('*'):
            if path.is_file():self.assertNotIn(self.secret.encode(),path.read_bytes())
    def test_diag_interrupted_publication_stays_spent(self):
        _,ar,cap=self.new()
        def interrupted(name):
            if name=='diagnostic.json':raise OSError('SYNTHETIC_INTERRUPTED_PUBLICATION')
        ar.after_pending=interrupted
        with self.server('invalid_schema') as server:
            result=self.run_bounded(ar,cap,server);self.assertNotEqual(result['kind'],'DONE');self.assertEqual(len(server.requests),1)
            self.assertRaises(Refused,self.run_bounded,ar,cap,server)
        self.assertTrue(ar.path('diagnostic.json.pending').exists());self.assertFalse(ar.path('diagnostic.json').exists());self.assertTrue(ar.path('grant.claimed.json').exists())
        self.assertRaises((Refused,FileNotFoundError),d.read_verified,ar)
    def test_diag_global_lock_loss(self):
        from .session_namespace import acquisition_lock
        _,ar,cap=self.new()
        @previous.contextlib.contextmanager
        def lost(archive):
            with acquisition_lock(archive) as lease:
                class Proxy:
                    @property
                    def closed(self):return archive.path('worker.claimed.json').exists()
                    def fileno(self):return lease.fileno()
                yield Proxy()
        with self.server() as server,patch('tiv2.session_namespace.acquisition_lock',lost):
            result=self.run_bounded(ar,cap,server);self.assertNotEqual(result['kind'],'DONE');self.assertEqual(server.requests,[])
        self.checked(ar,cap,'GLOBAL_LOCK_LOST')
    def test_diag_atomic_derivative_manifest_interruption(self):
        ar=self.fixture(authorised=False);ar.path('research_outputs').mkdir();ar.path('research_outputs/partial').mkdir()
        ar.put('research_outputs/partial/candles.json.gz',b'SYNTHETIC_DATASET')
        def interrupted(name):
            if name.endswith('manifest.json'):raise OSError('SYNTHETIC_POWER_LOSS')
        ar.after_pending=interrupted
        self.assertRaises(OSError,ar.put,'research_outputs/partial/manifest.json',encoded(dict(synthetic=True)))
        self.assertFalse(ar.path('research_outputs/partial/manifest.json').exists());self.assertTrue(ar.path('research_outputs/partial/manifest.json.pending').exists())
        self.assertRaises(Refused,ar.put,'research_outputs/partial/candles.json.gz',b'OVERWRITE_FORBIDDEN')
    def test_diag_connect_refused(self):_,ar,cap,_=self.failure(scenario='connection_refused',expected_requests=0);self.checked(ar,cap,'CONNECT_REFUSED','CONNECT')
    def test_diag_connect_timeout(self):_,ar,cap,_=self.failure(fault='connect_timeout',expected_requests=0);self.checked(ar,cap,'CONNECT_TIMEOUT','CONNECT')
    def test_diag_http_rejected(self):_,ar,cap,_=self.failure(scenario='http_403',expected_requests=1);self.checked(ar,cap,'HTTP_STATUS_REJECTED','HTTP')
    def test_diag_delayed_headers(self):
        from .timing_test_fixture import synchronized_header_wait
        with synchronized_header_wait() as phase:
            _,ar,cap,_=self.failure(scenario='delayed_headers',limits=dict(request=3,session=900,spacing=.001),expected_requests=1,phase_fixture=phase)
            self.assertTrue(phase.entered)
            self.assertIn(self.checked(ar,cap)['reason'],('RESPONSE_HEADERS_TIMEOUT','WORKER_DEADLINE_EXCEEDED'));self.assertEqual(d.read_verified(ar)['stage'],'HEADERS')
    def test_diag_slow_body(self):
        _,ar,cap,_=self.failure(scenario='slow_body',limits=dict(request=3,session=900,spacing=.001),expected_requests=1)
        self.assertIn(self.checked(ar,cap)['reason'],('RESPONSE_BODY_TIMEOUT','WORKER_DEADLINE_EXCEEDED'));self.assertEqual(d.read_verified(ar)['stage'],'BODY')
    def test_diag_truncated(self):_,ar,cap,_=self.failure(scenario='incomplete_body',expected_requests=1);self.checked(ar,cap,'RESPONSE_TRUNCATED','BODY')
    def test_diag_schema(self):_,ar,cap,_=self.failure(scenario='invalid_schema',expected_requests=1);self.checked(ar,cap,'RESPONSE_SCHEMA_INVALID','VALIDATION')
    def test_diag_archive_failure(self):_,ar,cap,_=self.failure(fault='archive_write_failure',expected_requests=1);self.checked(ar,cap,'ARCHIVE_PUBLICATION_FAILED','ARCHIVE')
    def test_diag_worker_crash(self):_,ar,cap,_=self.failure(fault='crash_after_response',expected_requests=1);self.checked(ar,cap,'WORKER_CRASHED')
    def test_diag_worker_deadline(self):_,ar,cap,_=self.failure(fault='stall_after_response',limits=dict(request=3,session=900,spacing=.001),expected_requests=1);self.checked(ar,cap,'WORKER_DEADLINE_EXCEEDED','BODY')
    def test_diag_tls_failure(self):
        _,ar,cap=self.new()
        with self.server() as server:
            result=b.run(ar,cap,SyntheticCredentialProvider(self.secret),https_fixture=server.binding('untrusted'))
            self.assertNotEqual(result['kind'],'DONE');self.assertTrue(result['worker_exited']);self.assertEqual(server.requests,[])
        self.checked(ar,cap,'TLS_FAILURE','TLS')
    def test_diag_parent_session_deadline(self):
        _,ar,cap=self.new(limits=dict(session=2,spacing=1))
        with self.server() as server:result=self.run_bounded(ar,cap,server)
        self.assertNotEqual(result['kind'],'DONE');self.assertTrue(result['worker_exited']);self.checked(ar,cap,'SESSION_DEADLINE_EXCEEDED')
    def test_diag_termination_during_transmission(self):
        _,ar,cap,_=self.failure(fault='crash_during_transmission');self.checked(ar,cap,'WORKER_CRASHED')
    def test_diag_hash_tamper_rejected(self):
        _,ar,cap,_=self.failure(scenario='invalid_schema',expected_requests=1);value=self.checked(ar,cap);value['reason']='UNKNOWN_FAILURE';ar.put('diagnostic.json',encoded(value),replace=True);self.assertRaises(Refused,d.read_verified,ar)
    def test_diag_unknown_exception_redacted(self):
        f=d.classify(RuntimeError(self.secret+' Authorization account identifier'), 'BODY');self.assertEqual((f.reason,f.stage),('UNKNOWN_FAILURE','BODY'));self.assertNotIn(self.secret,str(f));self.assertRaises(Refused,d.record,{'session':'0'*32,'source':'a'*64,'catalogue':'b'*64},self.secret,'BODY',0)
    def test_diag_dns_refusal_without_socket(self):
        context=d.Context()
        with patch.object(network.authority,'require_role',return_value=None),patch.object(network.socket,'getaddrinfo',side_effect=socket.gaierror('SYNTHETIC_DNS_SECRET')):
            conn=network._LiveConnection(object(),time.monotonic()+10,diagnostic=context)
            with self.assertRaises(d.Failure) as caught:conn.connect()
            self.assertEqual((caught.exception.reason,caught.exception.stage),('DNS_FAILURE','DNS'))
    def test_diag_mapping_source_and_accounting(self):
        self.assertEqual(d.classify(Refused('APPROVED_SOURCE_SEAL_REQUIRED'),'RESERVATION').reason,'SOURCE_BINDING_INVALID')
        self.assertEqual(d.classify(Refused('REQUEST_BUDGET_INCONSISTENT'),'ACCOUNTING').reason,'ACCOUNTING_INCONSISTENT')
        self.assertEqual(d.classify(Refused('GLOBAL_LOCK_LOST'),'SUPERVISION').reason,'GLOBAL_LOCK_LOST')
    def test_diag_failed_accounting_still_has_durable_diagnostic(self):
        _,ar,cap=self.new();original=b.claim_window
        def corrupt(*args):
            result=original(*args);state=decode(ar.read('journal.json'));state['attempts']=999;ar.put('journal.json',encoded(state),replace=True);raise Refused('REQUEST_BUDGET_INCONSISTENT')
        with self.server() as server,patch.object(b,'claim_window',corrupt):
            result=self.run_bounded(ar,cap,server);self.assertNotEqual(result['kind'],'DONE');self.assertTrue(result['worker_exited']);self.assertEqual(server.requests,[])
        self.checked(ar,cap,'ACCOUNTING_INCONSISTENT','ACCOUNTING');self.assertTrue(ar.path('grant.claimed.json').exists());self.assertRaises(Refused,b.verify,cap)
    def test_diag_no_live_authority_expansion(self):
        _,ar,cap=self.new();cap['mode']='LIVE';self.assertRaises(Refused,b.verify,cap);self.assertEqual(b.LIMITS,dict(startup=15,token=120,request=15,session=1800,spacing=1,bytes=268435456,attempts=106));self.assertEqual(b.spec(0)['path'],'/v3/instruments/EUR_USD/candles')
    def test_diag_secret_response_no_persistence(self):
        _,ar,cap,_=self.failure(scenario='credential_echo',expected_requests=1);self.checked(ar,cap)
        for path in ar.root.rglob('*'):
            if path.is_file():self.assertNotIn(self.secret.encode(),path.read_bytes())

for _name in dir(previous.Bounded):
    if _name.startswith('test_'):setattr(Diagnostics,_name,None)

if __name__=='__main__':
    from .oneshot_archive import FIXTURES,NATIVE_FIXTURES
    if sys.argv[1:]!=['--fixture-diagnostic-probe']:raise SystemExit('FIXTURE_PROBE_ONLY')
    value=decode(sys.stdin.buffer.readline(4097));root=Path(value['root']).absolute()
    if set(value)!={'root'} or not any(root.is_relative_to(p) for p in (FIXTURES,NATIVE_FIXTURES)):raise SystemExit('FIXTURE_ROOT_REQUIRED')
    with Archive(root,synthetic=True) as ar:
        diagnostic=d.read_verified(ar)
        print(json.dumps(dict(reason=diagnostic['reason'],stage=diagnostic['stage'],sha256=digest(ar.read('diagnostic.json')))))
