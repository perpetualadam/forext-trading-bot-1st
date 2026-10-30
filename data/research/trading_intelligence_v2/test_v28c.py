"""Bounded mode: invented credentials/candles and loopback TLS only."""
import copy
import contextlib
import sys
import os
import subprocess
import importlib.util
import threading
import time
import uuid
import unittest
from unittest.mock import patch
from pathlib import Path
if __name__=='__main__':
    _p=Path(__file__).resolve().parent
    _s=importlib.util.spec_from_file_location('tiv2',_p/'__init__.py',submodule_search_locations=[str(_p)])
    _m=importlib.util.module_from_spec(_s);sys.modules['tiv2']=_m;_s.loader.exec_module(_m);__package__='tiv2'
from . import test_v26d as legacy
from . import bounded_acquisition as b
from . import oneshot_authorisation as a
from .oneshot_archive import Archive,Refused
from .session_namespace import prepare_session,acquisition_lock
from .oneshot_bridge import SyntheticCredentialProvider
from .https_test_server import LocalHTTPS
from .oanda_history_manifest import encoded,decode,digest
from .core import timestamp,ResearchRejected
legacy.NATIVE=globals().get('NATIVE',False)


def review():
    return dict(provider='OANDA',provider_identity_url='https://www.oanda.com/',terms_url='https://www.oanda.com/terms/',
        terms_evidence='SYNTHETIC FIXTURE ONLY',rights_reviewed=True,permitted_use='offline_research_and_derived_results',
        catalogue_sha256=b.CATALOGUE_HASH,scope_reviewed=True,permitted_scope='PRIVATE_LOCAL_106_WINDOWS',public_distribution_allowed=False)


class Catalogue(unittest.TestCase):
    def test_106_exact(self):self.assertEqual(len(b.catalogue()),106)
    def test_hash(self):self.assertEqual(digest(b.CATALOGUE.read_bytes().replace(b'\r\n',b'\n')),b.CATALOGUE_HASH)
    def test_slots(self):self.assertEqual([w['maximum_candles'] for w in b.catalogue()],[1000]*105+[120])
    def test_contiguous(self):
        windows=[b.spec(i) for i in range(106)]
        self.assertEqual(timestamp(windows[0]['params']['from']),timestamp('2024-09-01T00:00:00Z'))
        self.assertEqual(timestamp(windows[-1]['params']['to'])+1,timestamp('2025-09-01T00:00:00Z'))
        self.assertTrue(all(timestamp(x['params']['to'])+1==timestamp(y['params']['from']) for x,y in zip(windows,windows[1:])))
    def test_no_extra_indices(self):
        for i in (-1,106,True,'0'):self.assertRaises(Refused,b.spec,i)
    def test_immutable_copy(self):
        s=b.spec(0);s['path']='/v3/orders';self.assertEqual(b.spec(0)['path'],'/v3/instruments/EUR_USD/candles')
    def test_exact_get_only(self):
        for i in range(106):
            s=b.spec(i);self.assertEqual((s['method'],s['host'],s['path']),('GET','api-fxtrade.oanda.com','/v3/instruments/EUR_USD/candles'))
            self.assertEqual(set(s['params']),{'from','to','price','granularity','smooth','includeFirst'})
            self.assertEqual([s['params'][k] for k in ('price','granularity','smooth','includeFirst')],['MBA','M5','false','true'])
    def test_catalogue_mismatch(self):
        with patch.object(Path,'read_bytes',return_value=b'{}'):self.assertRaises(Refused,b.catalogue)
    def test_rate_limiter(self):
        self.assertEqual(b.rate_delay(10,lambda:9),1);self.assertEqual(b.rate_delay(10,lambda:11),0)
    def test_no_operational_imports(self):
        for name in ('bounded_acquisition.py','bounded_history_entry.py'):
            text=(b.PACKAGE/name).read_text();self.assertNotIn('import forex_bot',text);self.assertNotIn('load_dotenv',text)


class Bounded(legacy.HTTPSLifecycle):
    # Only the finite-mode tests below. Inherited legacy tests run separately.
    def new(self,base=None,limits=None):
        base=base or self.fixture(authorised=False)
        if not base.path('temporary_batches').exists():base.path('temporary_batches').mkdir()
        root=prepare_session(base.root,uuid.uuid4().hex,a.source_seal(),synthetic=True,_bounded_rights=review())
        ar=Archive(root,synthetic=True);self.addCleanup(ar.close)
        cap=b.issue(ar,_fixture=True,fixture_limits=limits or dict(session=900,spacing=.001))
        return base,ar,cap
    def run_bounded(self,ar,cap,server,**kw):
        return b.run(ar,cap,SyntheticCredentialProvider(self.secret),https_fixture=server.binding(),**kw)
    def server(self,scenario='valid'):
        return LocalHTTPS(self.cert,self.key,scenario=scenario,secret=self.secret,catalogue=tuple(b.spec(i) for i in range(106)))
    def failure(self,*,fault='',scenario='valid',limits=None,expected_requests=None,phase_fixture=None):
        base,ar,cap=self.new(limits=limits)
        server=self.server(scenario)
        if phase_fixture is not None:phase_fixture.bind(ar,server)
        with server:
            result=self.run_bounded(ar,cap,server,fault=fault)
            self.assertNotEqual(result['kind'],'DONE',result);self.assertTrue(result['worker_exited'],result)
            self.assertLessEqual(len(server.requests),1)
            if expected_requests is not None:self.assertEqual(len(server.requests),expected_requests,result)
            state=b.ledger(ar,cap);self.assertEqual(state['state'],'OUTCOME_UNKNOWN');self.assertLessEqual(state['attempts'],1)
            before=len(server.requests);self.assertRaises(Refused,self.run_bounded,ar,cap,server)
            self.assertEqual(before,len(server.requests));self.assertRaises(Refused,b.preflight,ar)
            self.assertTrue(ar.path('grant.claimed.json').exists())
        return base,ar,cap,result
    def test_bounded_all_106_one_token_and_import_rejection(self):
        base,ar,cap=self.new()
        calls=[];original=SyntheticCredentialProvider.credential
        def credential(provider):calls.append(1);return original(provider)
        with self.server() as server,patch.object(SyntheticCredentialProvider,'credential',credential):
            result=self.run_bounded(ar,cap,server)
            self.assertEqual(result['kind'],'DONE',result);self.assertEqual(calls,[1]);self.assertTrue(result['worker_exited'])
            self.assertEqual(len(server.requests),106);self.assertTrue(all(r['scope_valid'] and r['auth_matches'] for r in server.requests))
        state=b.ledger(ar,cap);self.assertEqual((state['attempts'],state['next'],state['state']),(106,106,'SESSION_CONSUMED'))
        for i in range(106):
            r=b.verify_completed(ar,cap,i);self.assertEqual(r['observed_complete_count'],1)
            self.assertEqual(state['windows'][i]['http_attempts'],1);self.assertTrue(base.path(b.marker(i)).exists())
        for p in ar.root.rglob('*'):
            if p.is_file():self.assertNotIn(self.secret.encode(),p.read_bytes())
        self.assertRaises(Refused,b.verify,cap)
        # A new identity cannot reuse any spent catalogue entry.
        root=prepare_session(base.root,uuid.uuid4().hex,a.source_seal(),synthetic=True,_bounded_rights=review())
        with Archive(root,synthetic=True) as other:self.assertRaises(Refused,b.issue,other,_fixture=True)
        from .oanda_research_import import import_bundle
        r=b.verify_completed(ar,cap,0);rb=ar.read('manifests/v26c_year_000.json');rev=review();rev.update(provenance_verified=True,manifest_sha256=digest(rb))
        self.assertRaises(ResearchRejected,import_bundle,ar.read('request.json'),rb,ar.read(r['raw']),ar.read(r['validated']),review=rev,independent_required=False)
    def test_bounded_slow_token_entry_receives_fresh_acquisition_clock(self):
        from .timing_test_fixture import deterministic_input_clock
        with deterministic_input_clock() as clock:
            _,ar,cap=self.new(limits=dict(token=4,session=2,spacing=1))
            def token(_):clock.advance(1);return self.secret
            with self.server() as server,patch.object(SyntheticCredentialProvider,'credential',token):
                result=self.run_bounded(ar,cap,server,fault='crash_after_response')
                self.assertTrue(result['worker_exited']);self.assertEqual(len(server.requests),1)
            phase=decode(ar.read('acquisition.json'));worker=decode(ar.read('worker.claimed.json'))
            self.assertGreaterEqual(phase['started']-(worker['credential_deadline']-4),1)
            self.assertEqual(phase['deadline']-phase['started'],2)
    def test_bounded_parent_hash_verification_stops_progression(self):
        _,ar,cap=self.new()
        with self.server() as server,patch.object(b,'verify_completed',side_effect=Refused('SYNTHETIC_CORRUPTED_RECEIPT')):
            result=self.run_bounded(ar,cap,server)
            self.assertNotEqual(result['kind'],'DONE');self.assertTrue(result['worker_exited']);self.assertEqual(len(server.requests),1)
        self.assertEqual(b.ledger(ar,cap)['attempts'],1);self.assertRaises(Refused,b.verify,cap)
    def test_bounded_actual_one_second_pacing(self):
        _,ar,cap=self.new(limits=dict(session=900,spacing=1))
        original=b.verify_completed
        with self.server() as server:
            def verified(*args):
                result=original(*args);server.scenario='http_500';return result
            with patch.object(b,'verify_completed',verified):result=self.run_bounded(ar,cap,server)
            self.assertNotEqual(result['kind'],'DONE');self.assertTrue(result['worker_exited'])
            self.assertEqual(len(server.requests),2);self.assertGreaterEqual(server.request_times[1]-server.request_times[0],1)
        self.assertEqual(b.ledger(ar,cap)['attempts'],2)
    def test_bounded_lost_global_lease_fences_before_token(self):
        _,ar,cap=self.new();original=acquisition_lock
        @contextlib.contextmanager
        def lost(archive):
            with original(archive) as lease:
                class Proxy:
                    @property
                    def closed(self):return archive.path('worker.claimed.json').exists()
                    def fileno(self):return lease.fileno()
                yield Proxy()
        with self.server() as server,patch('tiv2.session_namespace.acquisition_lock',lost),patch.object(SyntheticCredentialProvider,'credential',side_effect=AssertionError('NO_TOKEN_AFTER_LOCK_LOSS')):
            result=self.run_bounded(ar,cap,server)
            self.assertNotEqual(result['kind'],'DONE');self.assertTrue(result['worker_exited']);self.assertEqual(server.requests,[])
        self.assertEqual(b.ledger(ar,cap)['state'],'OUTCOME_UNKNOWN');self.assertRaises(Refused,b.verify,cap)
    def test_bounded_two_process_global_lock(self):
        _,ar,_=self.new();exe=getattr(sys,'_base_executable',sys.executable)
        command=[exe,'-I','-S','-B',str(Path(__file__).resolve()),'--fixture-lock-probe']
        def probe():
            p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'SystemRoot':r'C:\Windows'},close_fds=True)
            out,err=p.communicate(encoded({'root':str(ar.root)}),timeout=10)
            self.assertEqual(p.returncode,0,err.decode());return out.strip()
        with acquisition_lock(ar):self.assertEqual(probe(),b'BUSY')
        self.assertEqual(probe(),b'ACQUIRED')
    def test_bounded_competing_session_preserves_unused_authority(self):
        base,first,c1=self.new();_,second,c2=self.new(base)
        entered=threading.Event();release=threading.Event();results=[]
        def token(_):entered.set();release.wait(10);return self.secret
        with self.server() as server,patch.object(SyntheticCredentialProvider,'credential',token):
            thread=threading.Thread(target=lambda:results.append(self.run_bounded(first,c1,server,fault='crash_before_dispatch')));thread.start()
            try:
                self.assertTrue(entered.wait(10));self.assertRaisesRegex(Refused,'GLOBAL_ACQUISITION_BUSY',self.run_bounded,second,c2,server)
                self.assertTrue(second.path('grant.json').exists());self.assertEqual(b.ledger(second,c2)['attempts'],0)
            finally:release.set();thread.join(20)
            self.assertFalse(thread.is_alive());self.assertEqual(server.requests,[]);self.assertTrue(results[0]['worker_exited'])
    def test_bounded_import_adapter_with_independently_reviewed_fixture(self):
        # Invented byte bundle, never a protected execution record or real data.
        from .test_v28b import fixture,SOURCE
        from .year_history import plan
        from .oanda_research_import import import_bundle
        x=fixture(plan(SOURCE)[0]);request=decode(x['request']);request.pop('spec');request.update(kind='BOUNDED_106',catalogue=b.CATALOGUE_HASH,limits=b.LIMITS,authorises_execution=False)
        req=encoded(request);manifest=decode(x['manifest']);manifest.update(index=0,catalogue=b.CATALOGUE_HASH,source=SOURCE,spec_sha256=digest(encoded(b.spec(0))),request_sha256=digest(req))
        mb=encoded(manifest);rev=x['review'];rev['manifest_sha256']=digest(mb)
        imported=import_bundle(req,mb,x['raw'],x['validated'],review=rev,independent_required=False)
        self.assertEqual(len(imported['records']),1);self.assertFalse(imported['strategy_evaluation_permitted'])
        rev['manifest_sha256']='0'*64;self.assertRaises(ResearchRejected,import_bundle,req,mb,x['raw'],x['validated'],review=rev,independent_required=False)
    def test_bounded_crash_before_dispatch(self):self.failure(fault='crash_before_dispatch',expected_requests=0)
    def test_bounded_crash_during_dispatch(self):self.failure(fault='crash_during_dispatch',expected_requests=0)
    def test_bounded_crash_after_response(self):self.failure(fault='crash_after_response',expected_requests=1)
    def test_bounded_http_timeout(self):self.failure(scenario='delayed_headers',limits=dict(request=3,session=900,spacing=.001),expected_requests=1)
    def test_bounded_deadline_cleanup(self):self.failure(fault='stall_after_response',limits=dict(request=3,session=900,spacing=.001),expected_requests=1)
    def test_bounded_invalid_schema(self):self.failure(scenario='invalid_schema',expected_requests=1)
    def test_bounded_incomplete_refuses(self):self.failure(scenario='incomplete_candles',expected_requests=1)
    def test_bounded_redirect_no_follow(self):self.failure(scenario='redirect',expected_requests=1)
    def test_bounded_http_failure_no_retry(self):self.failure(scenario='http_429',expected_requests=1)
    def test_bounded_secret_echo_refused(self):
        _,ar,_,_=self.failure(scenario='credential_echo',expected_requests=1)
        for p in ar.root.rglob('*'):
            if p.is_file():self.assertNotIn(self.secret.encode(),p.read_bytes())
    def test_bounded_token_timeout_no_dispatch(self):
        _,ar,cap=self.new(limits=dict(token=1,session=900,spacing=.001))
        with self.server() as server,patch.object(SyntheticCredentialProvider,'credential',side_effect=lambda:(time.sleep(1.1) or self.secret)):
            r=self.run_bounded(ar,cap,server);self.assertEqual(r['kind'],'TOKEN_ENTRY_TIMEOUT',r);self.assertEqual(server.requests,[])
        self.assertEqual(b.ledger(ar,cap)['attempts'],0);self.assertRaises(Refused,b.verify,cap)
    def test_bounded_session_deadline(self):
        _,ar,cap=self.new(limits=dict(session=2,spacing=1))
        with self.server() as server:
            started=time.monotonic();r=self.run_bounded(ar,cap,server);self.assertNotEqual(r['kind'],'DONE');self.assertTrue(r['worker_exited']);self.assertLess(time.monotonic()-started,17);self.assertLessEqual(len(server.requests),1)
    def test_bounded_source_mismatch(self):
        _,_,cap=self.new();cap['source']='0'*64;self.assertRaises(Refused,b.verify,cap)
    def test_bounded_cap_catalogue_mismatch(self):
        _,_,cap=self.new();cap['catalogue']='0'*64;self.assertRaises(Refused,b.verify,cap)
    def test_bounded_invalid_budget(self):
        _,_,cap=self.new();cap['limits']['attempts']=107;self.assertRaises(Refused,b.verify,cap)
    def test_bounded_identity_mismatch(self):
        _,_,cap=self.new();cap['identity']='0'*64;self.assertRaises(Refused,b.verify,cap)
    def test_bounded_no_noninteractive_live_issuer(self):
        _,ar,_=self.new();self.assertRaises(Refused,b.issue,ar)
    def test_bounded_scope_rights_required(self):
        _,ar,_=self.new();r=review();r['scope_reviewed']=False;ar.put('rights_scope.json',encoded(r),replace=True);self.assertRaises(Refused,b.rights,ar)
    def test_bounded_disk_space(self):
        _,ar,_=self.new()
        with patch.object(b.shutil,'disk_usage',return_value=type('Usage',(),{'free':0})()):self.assertRaises(Refused,b.budget_guard,ar,1)
    def test_bounded_256mib_peak_quota(self):
        _,ar,_=self.new();p=ar.path('raw/synthetic_quota.bin')
        with p.open('wb') as f:f.truncate(b.LIMITS['bytes'])
        self.assertRaises(Refused,b.budget_guard,ar,1)
    def test_bounded_reserved_marker_blocks_new_identity(self):
        base,ar,_=self.new();base.put(b.marker(0),encoded({'synthetic':'spent'}));self.assertRaises(Refused,b.preflight,ar)
    def test_bounded_pending_marker_blocks(self):
        base,ar,_=self.new();base.put(b.marker(0)+'.pending',b'{}');self.assertRaises(Refused,b.preflight,ar)
    def test_bounded_journal_budget_inconsistency(self):
        _,ar,cap=self.new();s=b.ledger(ar,cap);s['attempts']=1;ar.put('journal.json',encoded(s),replace=True);self.assertRaises(Refused,b.ledger,ar,cap)
    def test_bounded_journal_out_of_order(self):
        _,ar,cap=self.new();s=b.ledger(ar,cap);s['windows'][1]['state']='RESERVED';s['attempts']=1;ar.put('journal.json',encoded(s),replace=True);self.assertRaises(Refused,b.ledger,ar,cap)
    def test_bounded_namespace_grant_substitution(self):
        base,_,cap=self.new();_,other,c2=self.new(base);other.put('grant.json',encoded(cap),replace=True);self.assertRaises(Refused,b.verify,c2)
    def test_bounded_exact_confirmation(self):
        _,ar,cap=self.new();phrase=b.confirmation(ar)
        self.assertEqual(phrase,'CONFIRM 106 HISTORICAL EUR_USD GETS '+cap['session']+' '+b.CATALOGUE_HASH+' '+cap['source'])
    def test_bounded_only_protected_or_fixture_roots(self):
        self.assertRaises(Refused,Archive,b.PACKAGE,synthetic=False)
    def test_bounded_phase_cannot_start_before_reservation(self):
        _,ar,cap=self.new();self.assertRaises((Refused,FileNotFoundError),b.role,cap,'network')
    def test_bounded_duplicate_window_refused(self):
        _,ar,cap=self.new();self.assertRaises((Refused,FileNotFoundError),b.claim_window,ar,cap,0,123)
    def test_bounded_budget_reserves_accounting_room(self):
        _,ar,_=self.new();p=ar.path('raw/synthetic_quota.bin')
        with p.open('wb') as f:f.truncate(b.LIMITS['bytes']-900000)
        self.assertRaises(Refused,b.budget_guard,ar,1)
        self.assertGreater(b.budget_guard(ar,1024,accounting=True),0)

# The inherited suites are executed under their own selectors, avoiding duplicate runs.
for _name in list(vars(legacy.HTTPSLifecycle)):
    if _name.startswith('test_') and not _name.startswith('test_bounded_'):setattr(Bounded,_name,None)

if __name__=='__main__':
    from .oneshot_archive import FIXTURES,NATIVE_FIXTURES
    if sys.argv[1:]!=['--fixture-lock-probe']:raise SystemExit('SYNTHETIC_PROBE_ONLY')
    value=decode(sys.stdin.buffer.readline(4097));root=Path(value['root']).absolute()
    if set(value)!={'root'} or not any(root.is_relative_to(p) for p in (FIXTURES,NATIVE_FIXTURES)):raise SystemExit('SYNTHETIC_ROOT_REQUIRED')
    with Archive(root,synthetic=True) as ar:
        try:
            with acquisition_lock(ar):print('ACQUIRED')
        except Refused as error:
            if str(error)!='GLOBAL_ACQUISITION_BUSY':raise
            print('BUSY')
