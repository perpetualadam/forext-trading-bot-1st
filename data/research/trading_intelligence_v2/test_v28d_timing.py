"""Closed deterministic fixture and unchanged fail-closed acquisition rules."""
import copy
import os
import subprocess
import sys
import time
from unittest.mock import patch
from . import test_v28c as previous
from . import bounded_acquisition as b,oneshot
from .oneshot_archive import Refused
from .oneshot_bridge import SyntheticCredentialProvider
from .oanda_history_manifest import encoded,decode
from .timing_test_fixture import FixtureClock,HeaderWaitClock,deterministic_input_clock,synchronized_header_wait,WALL_LIMIT,LIFETIME
previous.legacy.NATIVE=globals().get('NATIVE',False)


class TimingFixture(previous.Bounded):
    def test_clock_advancement_and_real_wall_watchdog(self):
        wall=[100.];clock=FixtureClock(100.,_wall=lambda:wall[0])
        clock.advance(1);self.assertEqual(clock.monotonic(),101.)
        self.assertRaises(ValueError,clock.advance,-1)
        self.assertRaises(ValueError,clock.synchronize,100.)
        wall[0]+=WALL_LIMIT
        self.assertGreater(clock.monotonic()-clock.start,LIFETIME)
    def refused_bootstrap(self,cap):
        exe=getattr(sys,'_base_executable',sys.executable)
        cmd=[exe,'-I','-S','-B',str(b.PACKAGE/'timing_test_worker.py'),'--bounded-worker']
        packet=dict(root=cap['root'],reservation=cap,fault='crash_after_response',https_fixture={})
        p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'SystemRoot':r'C:\Windows'} if os.name=='nt' else {},close_fds=True)
        out,err=p.communicate(encoded(packet),timeout=5)
        self.assertEqual(p.returncode,2);self.assertEqual(out.strip(),b'TIMING_FIXTURE_REFUSED');self.assertEqual(err,b'')
    def test_live_bootstrap_refuses_before_credential_entry(self):
        _,ar,cap=self.new(limits=dict(token=4,session=2,spacing=1));bad=copy.deepcopy(cap);bad['mode']='LIVE'
        self.refused_bootstrap(bad)
        self.assertFalse(ar.path('worker.claimed.json').exists());self.assertEqual(b.ledger(ar,cap)['attempts'],0)
    def test_non_fixture_root_refuses_before_archive_access(self):
        _,ar,cap=self.new(limits=dict(token=4,session=2,spacing=1));bad=copy.deepcopy(cap);bad['root']=str(b.PACKAGE)
        self.refused_bootstrap(bad)
        self.assertFalse(ar.path('worker.claimed.json').exists())
    def test_token_expiry_still_consumes_without_dispatch_or_retry(self):
        with deterministic_input_clock() as clock:
            _,ar,cap=self.new(limits=dict(token=4,session=2,spacing=1))
            def expired(_):clock.advance(4);return self.secret
            with self.server() as server,patch.object(SyntheticCredentialProvider,'credential',expired):
                result=self.run_bounded(ar,cap,server,fault='crash_after_response')
                self.assertEqual(result['kind'],'TOKEN_ENTRY_TIMEOUT');self.assertEqual(server.requests,[])
                self.assertRaises(Refused,self.run_bounded,ar,cap,server,fault='crash_after_response')
            self.assertFalse(ar.path('acquisition.json').exists())
            self.assertEqual(b.ledger(ar,cap)['state'],'OUTCOME_UNKNOWN')
            self.assertTrue(ar.path('grant.claimed.json').exists())
    def test_oracle_detects_budget_started_before_input_completed(self):
        with deterministic_input_clock() as clock:
            _,ar,cap=self.new(limits=dict(token=4,session=2,spacing=1));original=ar.put
            def early(name,raw,**kw):
                if name=='acquisition.json':
                    v=decode(raw);v['started']-=1;v['deadline']-=1;raw=encoded(v)
                return original(name,raw,**kw)
            def token(_):clock.advance(1);return self.secret
            with self.server() as server,patch.object(ar,'put',early),patch.object(SyntheticCredentialProvider,'credential',token):
                self.run_bounded(ar,cap,server,fault='crash_after_response');self.assertEqual(server.requests,[])
            phase=decode(ar.read('acquisition.json'));worker=decode(ar.read('worker.claimed.json'))
            self.assertLess(phase['started']-(worker['credential_deadline']-4),1)
            self.assertRaises(Refused,b.verify,cap)
    def test_fixture_scope_restores_real_clock_and_original_worker(self):
        real=time.monotonic;worker=oneshot.WORKER
        with deterministic_input_clock() as clock:
            self.assertEqual(time.monotonic(),clock.start)
            self.assertEqual(oneshot.WORKER.name,'timing_test_worker.py')
        self.assertIs(time.monotonic,real);self.assertEqual(oneshot.WORKER,worker)


for _name in dir(previous.Bounded):
    if _name.startswith('test_'):setattr(TimingFixture,_name,None)


class HeaderFixture(TimingFixture):
    def test_setup_clock_does_not_spend_header_wait_budget(self):
        wall=[100.];clock=HeaderWaitClock(_wall=lambda:wall[0])
        wall[0]+=10;self.assertEqual(clock.monotonic(),0)
        clock.origin=wall[0];wall[0]+=1
        self.assertEqual(clock.monotonic(),1)
        wall[0]+=WALL_LIMIT
        self.assertGreater(clock.monotonic(),1035)
    def test_header_context_restores_clock_and_worker_after_failure(self):
        real=time.monotonic;worker=oneshot.WORKER
        with self.assertRaisesRegex(ValueError,'SYNTHETIC'):
            with synchronized_header_wait():raise ValueError('SYNTHETIC')
        self.assertIs(time.monotonic,real);self.assertEqual(oneshot.WORKER,worker)
    def test_header_binding_rejects_other_scenarios_and_real_archives(self):
        _,ar,_=self.new()
        clock=HeaderWaitClock()
        with self.server() as server:self.assertRaises(Refused,clock.bind,ar,server)
        class RealArchive:
            synthetic=False
        with self.server(scenario='delayed_headers') as server:self.assertRaises(Refused,clock.bind,RealArchive(),server)
    def test_header_bootstrap_refuses_live_and_nonfixture_roots(self):
        _,ar,cap=self.new(limits=dict(request=3,session=900,spacing=.001))
        exe=getattr(sys,'_base_executable',sys.executable)
        for field,value in [('mode','LIVE'),('root',str(b.PACKAGE))]:
            bad=copy.deepcopy(cap);bad[field]=value
            packet=dict(root=bad['root'],reservation=bad,fault='',https_fixture={})
            p=subprocess.Popen([exe,'-I','-S','-B',str(b.PACKAGE/'timing_test_worker.py'),'--bounded-worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'SystemRoot':r'C:\Windows'} if os.name=='nt' else {},close_fds=True)
            out,err=p.communicate(encoded(packet),timeout=5)
            self.assertEqual((p.returncode,out.strip(),err),(2,b'TIMING_FIXTURE_REFUSED',b''))
        self.assertFalse(ar.path('worker.claimed.json').exists());self.assertEqual(b.ledger(ar,cap)['attempts'],0)
    def test_corrupt_header_marker_expires_instead_of_restarting_clock(self):
        _,ar,_=self.new();clock=HeaderWaitClock()
        clock.marker=ar.path('header_phase.json');clock.session=ar.session_id;clock.source='synthetic'
        ar.put('header_phase.json',encoded(dict(version=1,session='other',source='synthetic',origin=0,state='ATTEMPTED',http_attempts=1)))
        self.assertGreater(clock.monotonic(),1035);self.assertIsNone(clock.origin)
    def test_actual_headers_require_reservation_and_timeout_without_retry(self):
        with synchronized_header_wait() as phase:
            _,ar,cap,result=self.failure(scenario='delayed_headers',limits=dict(request=3,session=900,spacing=.001),expected_requests=1,phase_fixture=phase)
            self.assertTrue(phase.entered)
            marker=decode(ar.read('header_phase.json'));ledger=b.ledger(ar,cap)
            self.assertEqual((marker['session'],marker['source'],marker['state'],marker['http_attempts']),(cap['session'],cap['source'],'ATTEMPTED',1))
            self.assertEqual(ledger['attempts'],1)
            self.assertEqual(result['kind'],'OUTCOME_UNKNOWN')
            self.assertTrue(result['worker_exited'])


for _name in dir(TimingFixture):
    if _name.startswith('test_'):setattr(HeaderFixture,_name,None)
