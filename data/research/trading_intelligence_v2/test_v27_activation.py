"""Actual admission/controller/worker path, grants confined to synthetic archives."""
import copy
import io
import json
from pathlib import Path
import os
import socket
import ssl
import threading
import time
import unittest
from unittest.mock import patch,MagicMock
from . import test_v26d as legacy
from . import oneshot_authorisation as authority
from . import oneshot_network as network
from . import direct_history
from .oneshot import run_once,journal,SPEC
from .oneshot_archive import Refused,Archive,APPROVED
from .oneshot_credentials import ReservedCredentialProvider
from .oneshot_bridge import SyntheticCredentialProvider
from .https_test_server import LocalHTTPS
from .oanda_history_manifest import encoded,decode,digest
from .test_v27 import TTY,SyntheticConsole

legacy.NATIVE=globals().get('NATIVE',False)


class AdmissionHTTPS(unittest.TestCase):
    setUpClass=classmethod(legacy.HTTPSLifecycle.setUpClass.__func__)
    tearDownClass=classmethod(legacy.HTTPSLifecycle.tearDownClass.__func__)
    fixture=legacy.HTTPSLifecycle.fixture

    def admitted_fixture(self):
        archive=self.fixture(authorised=False)
        cap=authority.issue_offline_fixture(archive)
        return archive,cap

    def run_session(self,archive,cap,server,**kwargs):
        verification=kwargs.pop('verification','trusted')
        return run_once(archive.root,synthetic_secret=None,_credential_provider=SyntheticCredentialProvider(self.secret),
            _live_reservation=cap,_https_fixture=server.binding(verification),pin=archive.identity,**kwargs)

    def no_repeat(self,archive,cap,server):
        before=(server.connections,len(server.requests))
        with patch.object(SyntheticCredentialProvider,'credential',side_effect=AssertionError('NO_SECOND_CREDENTIAL')):
            try:
                result=self.run_session(archive,cap,server)
                self.assertIn(result['kind'],('REFUSED','OUTCOME_UNKNOWN'))
                self.assertTrue(result['worker_exited'])
            except Refused:pass
        self.assertEqual(before,(server.connections,len(server.requests)))

    def test_source_bound_admission_to_worker_https_publication(self):
        archive,cap=self.admitted_fixture();seen=[]
        def credential(_):
            self.assertEqual(journal(archive)['state'],'REQUEST_ATTEMPTED')
            worker=decode(archive.read('worker.claimed.json'))
            self.assertEqual(worker['parent'],os.getpid());seen.append(worker['pid'])
            return self.secret
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(SyntheticCredentialProvider,'credential',credential):result=self.run_session(archive,cap,server)
            self.assertEqual(result['kind'],'DONE',result);self.assertEqual(seen,[result['worker_pid']])
            self.assertEqual(len(server.requests),1);self.assertEqual(journal(archive)['state'],'SESSION_CONSUMED')
            receipt=decode(archive.read('manifests/v26c_https.json'));self.assertIs(receipt['synthetic'],True)
            for key in ('raw','validated'):self.assertEqual(digest(archive.read(receipt[key])),receipt[key+'_sha256'])
            for path in archive.root.rglob('*'):
                if path.is_file():self.assertNotIn(self.secret.encode(),path.read_bytes())
            self.no_repeat(archive,cap,server)

    def test_actual_nine_candle_count_preserved(self):
        archive,cap=self.admitted_fixture()
        with LocalHTTPS(self.cert,self.key,scenario='nine',secret=self.secret) as server:
            result=self.run_session(archive,cap,server)
            self.assertEqual(result['kind'],'DONE',result);self.assertEqual(result['count'],9)
            self.no_repeat(archive,cap,server)

    def test_hidden_terminal_provider_uses_actual_reserved_admission(self):
        archive,cap=self.admitted_fixture();console=SyntheticConsole(self.secret+'\r');output=TTY()
        def credential(_):
            return direct_history.TerminalCredentialProvider().credential(cap,deadline=cap['started']+14)
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(direct_history,'_console',return_value=console),patch.object(os,'getenv',side_effect=AssertionError('NO_ENV')), \
                 patch.object(authority.sys,'stdin',TTY()),patch.object(authority.sys,'stdout',output), \
                 patch.object(SyntheticCredentialProvider,'credential',credential):
                result=self.run_session(archive,cap,server)
            self.assertEqual(result['kind'],'DONE',result);self.assertEqual(len(server.requests),1)
            self.assertNotIn(self.secret,output.getvalue());self.assertEqual(output.getvalue(),'API token: \n')
            self.no_repeat(archive,cap,server)

    def test_terminal_timeout_under_real_admission_fences_worker(self):
        archive,cap=self.admitted_fixture()
        def credential(_):
            return direct_history.TerminalCredentialProvider().credential(cap,deadline=time.monotonic()+.03)
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(direct_history,'_console',return_value=SyntheticConsole('')), \
                 patch.object(authority.sys,'stdin',TTY()),patch.object(authority.sys,'stdout',TTY()), \
                 patch.object(SyntheticCredentialProvider,'credential',credential):
                result=self.run_session(archive,cap,server)
            self.assertEqual(result['kind'],'TOKEN_ENTRY_TIMEOUT');self.assertTrue(result['worker_exited'])
            self.assertEqual(server.connections,0);self.no_repeat(archive,cap,server)

    def test_slow_token_entry_has_separate_fresh_acquisition_budget(self):
        archive,cap=self.admitted_fixture()
        def credential(_):
            self.assertEqual(journal(archive)['state'],'REQUEST_ATTEMPTED')
            self.assertFalse(archive.path('acquisition.json').exists())
            self.assertEqual(server.connections,0)
            time.sleep(16)
            self.assertEqual(server.connections,0)
            return self.secret
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(SyntheticCredentialProvider,'credential',credential):result=self.run_session(archive,cap,server)
            self.assertEqual(result['kind'],'DONE',result);self.assertGreater(result['total_elapsed'],16)
            self.assertLess(result['elapsed'],15);self.assertEqual(len(server.requests),1)
            phase=decode(archive.read('acquisition.json'))
            self.assertEqual(phase['deadline']-phase['started'],15)
            self.assertGreater(phase['started']-cap['started'],16)
            self.no_repeat(archive,cap,server)

    def test_token_timeout_preserves_consumed_state_and_never_starts_network_phase(self):
        from . import token_input
        archive,cap=self.admitted_fixture()
        class Clock:
            now=1000.
            def monotonic(self):return self.now
            def sleep(self,seconds):self.now+=seconds
        def credential(_):
            clock=Clock()
            with patch.object(token_input,'time',clock):
                return token_input.read_hidden_token(SyntheticConsole(''),deadline=1120.)
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(SyntheticCredentialProvider,'credential',credential),patch.object(authority.sys,'stdout',TTY()):
                result=self.run_session(archive,cap,server)
            self.assertEqual(result['kind'],'TOKEN_ENTRY_TIMEOUT',result);self.assertTrue(result['worker_exited'])
            self.assertEqual((server.connections,len(server.requests)),(0,0))
            self.assertFalse(archive.path('acquisition.json').exists())
            self.assertTrue(archive.path('grant.claimed.json').exists())
            self.assertEqual(journal(archive)['attempts'],1)
            self.no_repeat(archive,cap,server)

    def test_network_role_refuses_during_token_entry(self):
        archive,cap=self.admitted_fixture()
        def credential(_):
            worker=decode(archive.read('worker.claimed.json'))
            with patch.object(authority.os,'getpid',return_value=worker['pid']), \
                 patch.object(authority.os,'getppid',return_value=cap['parent']):
                with self.assertRaises(Refused):authority.require_role(cap,'fixture_dispatch')
            self.assertEqual(server.connections,0)
            return self.secret
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(SyntheticCredentialProvider,'credential',credential):result=self.run_session(archive,cap,server)
            self.assertEqual(result['kind'],'DONE',result);self.assertEqual(len(server.requests),1)

    def test_expired_preparation_cannot_claim_grant_or_start_worker(self):
        archive,cap=self.admitted_fixture()
        with patch.object(authority.time,'monotonic',return_value=cap['started']+16):
            with self.assertRaisesRegex(Refused,'PREPARATION_DEADLINE_EXHAUSTED'):
                authority.require_live_reservation(cap)
        self.assertTrue(archive.path('grant.json').exists())
        self.assertFalse(archive.path('grant.claimed.json').exists())
        self.assertFalse(archive.path('worker.claimed.json').exists())
        self.assertEqual(journal(archive)['attempts'],0)

    def test_worker_crash_while_waiting_for_token_cannot_replay(self):
        from . import oneshot
        archive,cap=self.admitted_fixture();processes=[];spawn=oneshot.subprocess.Popen
        def start(*args,**kwargs):
            process=spawn(*args,**kwargs);processes.append(process);return process
        def credential(_):
            self.assertEqual(journal(archive)['attempts'],1)
            processes[0].kill();processes[0].wait(timeout=1)
            return self.secret
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(oneshot.subprocess,'Popen',side_effect=start), \
                 patch.object(SyntheticCredentialProvider,'credential',credential):result=self.run_session(archive,cap,server)
            self.assertNotEqual(result['kind'],'DONE');self.assertTrue(result['worker_exited'])
            self.assertEqual((server.connections,len(server.requests)),(0,0))
            self.no_repeat(archive,cap,server)

    def test_malformed_acquisition_phase_refuses_before_any_connection(self):
        original=authority.begin_acquisition
        for change in ({'deadline':0.},{'seconds':120.},{'worker':0},{'source':'0'*64}):
            with self.subTest(change=change):
                archive,cap=self.admitted_fixture()
                def corrupt(*args):
                    phase=original(*args)
                    archive.put('acquisition.json',encoded(dict(phase,**change)),replace=True)
                    return phase
                with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
                    with patch.object(authority,'begin_acquisition',side_effect=corrupt):result=self.run_session(archive,cap,server)
                    self.assertEqual(result['kind'],'REFUSED',result);self.assertTrue(result['worker_exited'])
                    self.assertEqual((server.connections,len(server.requests)),(0,0))
                    self.no_repeat(archive,cap,server)

    def test_tls_http_redirect_refuse_without_retry(self):
        cases=[('valid','untrusted'),('valid','hostname_mismatch'),('redirect','trusted'),
               ('http_404','trusted'),('http_429','trusted'),('http_500','trusted')]
        for scenario,verification in cases:
            with self.subTest(scenario=scenario,verification=verification):
                archive,cap=self.admitted_fixture()
                with LocalHTTPS(self.cert,self.key,scenario=scenario,secret=self.secret) as server:
                    result=self.run_session(archive,cap,server,verification=verification)
                    self.assertEqual(result['kind'],'REFUSED',result);self.assertTrue(result['worker_exited'])
                    self.assertEqual(server.connections,1,result)
                    if verification!='trusted':
                        self.assertEqual(len(server.requests),0)
                        self.assertEqual(result['local_error'],'SSLCertVerificationError',result)
                    else:self.assertEqual(len(server.requests),1,result)
                    self.assertFalse(archive.path('manifests/v26c_https.json').exists())
                    self.no_repeat(archive,cap,server)

    def test_timeout_consumes_and_fences_without_second_attempt(self):
        archive,cap=self.admitted_fixture()
        with LocalHTTPS(self.cert,self.key,scenario='delayed_headers',secret=self.secret) as server:
            result=self.run_session(archive,cap,server,seconds=3)
            self.assertTrue(result['worker_exited']);self.assertLessEqual(result['elapsed'],3,result)
            self.assertIn(result['kind'],('REFUSED','OUTCOME_UNKNOWN'))
            self.assertTrue(server.phase.is_set());self.assertEqual(len(server.requests),1,result)
            self.assertEqual(journal(archive)['attempts'],1)
            self.no_repeat(archive,cap,server)

    def test_crash_and_ambiguous_publication_cannot_replay(self):
        for phase in ('before_reservation','after_reservation','before_dispatch','during_dispatch',
                      'after_response','archive_publication','final_persistence'):
            with self.subTest(phase=phase):
                archive,cap=self.admitted_fixture()
                with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
                    result=self.run_session(archive,cap,server,fault='crash_'+phase)
                    self.assertTrue(result['worker_exited']);self.assertEqual(result['kind'],'OUTCOME_UNKNOWN',result)
                    self.assertLessEqual(len(server.requests),1);self.no_repeat(archive,cap,server)

    def test_two_process_controllers_share_one_durable_claim(self):
        archive,cap=self.admitted_fixture();barrier=threading.Barrier(3);results=[]
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            def contender():
                barrier.wait()
                try:results.append(self.run_session(archive,cap,server)['kind'])
                except Refused:results.append('REFUSED')
            threads=[threading.Thread(target=contender) for _ in range(2)]
            for thread in threads:thread.start()
            barrier.wait()
            for thread in threads:thread.join(16);self.assertFalse(thread.is_alive())
            self.assertEqual(results.count('DONE'),1,results);self.assertEqual(len(server.requests),1)
            self.no_repeat(archive,cap,server)

    def test_cap_mutations_and_copy_to_foreign_root_are_refused(self):
        archive,cap=self.admitted_fixture();other=self.fixture(authorised=False)
        changes=[('root',str(other.root)),('spec','0'*64),('identity','0'*64),('source','0'*64),
                 ('session','f'*32),('mode','LIVE'),('parent',True),('version',True),('conditions','true')]
        with patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')):
            for key,value in changes:
                bad=copy.deepcopy(cap);bad[key]=value
                with self.subTest(key=key),self.assertRaises(Refused):authority.require_live_reservation(bad)
        with self.assertRaises(Refused):authority.issue_offline_fixture(archive)

    def test_no_credentials_before_reservation_and_no_environment_provider(self):
        archive,cap=self.admitted_fixture()
        with patch.object(os,'getenv',side_effect=AssertionError('NO_ENV')), \
             patch.object(direct_history,'_console',side_effect=AssertionError('NO_TOKEN')):
            with self.assertRaises(Refused):direct_history.TerminalCredentialProvider().credential(cap,deadline=time.monotonic()+1)
            with self.assertRaisesRegex(Refused,'TERMINAL_CREDENTIALS_REQUIRED'):ReservedCredentialProvider().credential(cap)
        with self.assertRaises(Refused):authority.require_role(cap,'network')

    def test_fixture_grant_never_authorises_external_network(self):
        archive,cap=self.admitted_fixture()
        with patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_EXTERNAL_DNS')), \
             patch.object(socket,'socket',side_effect=AssertionError('NO_EXTERNAL_SOCKET')):
            for action in (lambda:network.LiveSocketPolicy(cap),lambda:network._LiveConnection(cap,time.monotonic()+1),
                           lambda:network.fetch_live(reservation=cap,token=self.secret,deadline=time.monotonic()+1)):
                with self.assertRaises(Refused):action()

    def test_changed_seal_and_expiry_refuse(self):
        archive,cap=self.admitted_fixture()
        original=decode(authority.SEAL.read_bytes());changed=dict(original,baseline='0'*40)
        path=archive.root/'test_source_seal.json';path.write_bytes(encoded(changed))
        with patch.object(authority,'SEAL',path),self.assertRaisesRegex(Refused,'SOURCE_REVISION_CHANGED'):
            authority.require_live_reservation(cap)
        with patch.object(authority.time,'time',return_value=cap['expires']+1),self.assertRaises(Refused):
            authority.require_live_reservation(cap)

    def test_prepared_request_id_is_not_authorisation(self):
        archive=self.fixture(authorised=False);source=authority.source_seal()
        from .oneshot import SPEC_HASH
        proposal=dict(version=1,request_id='e'*32,source=source,spec=SPEC_HASH,authorises_execution=False)
        path=archive.root/'prepared_request.json';path.write_bytes(encoded(proposal))
        with patch.object(authority,'PREPARATION',path):
            self.assertEqual(authority.prepared_request_nonce(source),'e'*32)
            with self.assertRaises(Refused):authority.require_live_reservation(proposal)
            for change in ({'authorises_execution':True},{'source':'0'*64},{'request_id':'bad'}):
                path.write_bytes(encoded(dict(proposal,**change)))
                with self.assertRaisesRegex(Refused,'REQUEST_PREPARATION_REFUSED'):authority.prepared_request_nonce(source)
        self.assertFalse(archive.path('grant.json').exists());self.assertFalse(archive.path('journal.json').exists())

    def test_unprepared_invocations_generate_distinct_confirmation_ids(self):
        archive=self.fixture(authorised=False)
        with patch.object(authority,'PREPARATION',archive.root/'absent_preparation.json'):
            first=authority.prepared_request_nonce('a'*64);second=authority.prepared_request_nonce('a'*64)
        self.assertNotEqual(first,second);self.assertEqual(len(first),32);self.assertEqual(len(second),32)


class AdmissionGuards(unittest.TestCase):
    def test_live_writer_cannot_mint_without_interactive_one_time_proof(self):
        with self.assertRaisesRegex(Refused,'TERMINAL_CONFIRMATION_REQUIRED'):authority._issue(object(),'LIVE')
        with self.assertRaisesRegex(Refused,'TERMINAL_CONFIRMATION_REQUIRED'):
            authority._issue(object(),'LIVE',confirmation='0'*32)
        self.assertEqual(authority._CONFIRMATIONS,{})

    def test_terminal_attestations_and_exact_source_confirmation_precede_issuance(self):
        if os.name!='nt':return # Real admission is Windows-only; no socket/grant on this platform.
        archive=MagicMock();archive.__enter__.return_value=archive
        archive.identity=['SYNTHETIC_MEMORY_ONLY'];archive.path.return_value.exists.return_value=False
        source=authority.source_seal();request_id='f'*32;expected=authority.confirmation_phrase(source,request_id)
        cases=[(['wrong'],'DATA_USE_CONDITIONS_NOT_CONFIRMED'),
               ([authority.RIGHTS_PHRASE,'wrong'],'ENDPOINT_CONDITIONS_NOT_CONFIRMED'),
               ([authority.RIGHTS_PHRASE,authority.ENDPOINT_PHRASE,'wrong'],'HISTORICAL_CONFIRMATION_REFUSED'),
               ([authority.RIGHTS_PHRASE,authority.ENDPOINT_PHRASE,expected*2],'HISTORICAL_CONFIRMATION_REFUSED')]
        for answers,error in cases:
            output=TTY()
            with patch.object(authority,'Archive',return_value=archive),patch.object(authority,'_issue',side_effect=AssertionError('NO_GRANT')), \
                 patch('tiv2.session_namespace.require_prepared',return_value=None), \
                 patch.object(authority,'prepared_request_nonce',return_value=request_id), \
                 patch.object(authority.sys,'stdin',TTY()),patch.object(authority.sys,'stdout',output), \
                 patch('builtins.input',side_effect=answers):
                with self.assertRaisesRegex(Refused,error):authority.issue_live_interactively()
            for phrase in (authority.RIGHTS_PHRASE,authority.ENDPOINT_PHRASE,expected):self.assertIn(phrase,output.getvalue())
            self.assertEqual(authority._CONFIRMATIONS,{})
        # Positive UI test returns a memory sentinel; no real grant is written.
        sentinel=object()
        def issue_memory(*args,**kwargs):
            self.assertEqual(authority._CONFIRMATIONS[kwargs['confirmation']][-1],request_id)
            return sentinel
        with patch.object(authority,'Archive',return_value=archive),patch.object(authority,'_issue',side_effect=issue_memory) as issue, \
             patch('tiv2.session_namespace.require_prepared',return_value=None), \
             patch.object(authority,'prepared_request_nonce',return_value=request_id), \
             patch.object(authority.sys,'stdin',TTY()),patch.object(authority.sys,'stdout',TTY()), \
             patch('builtins.input',side_effect=[authority.RIGHTS_PHRASE,authority.ENDPOINT_PHRASE,expected]):
            self.assertIs(authority.issue_live_interactively(),sentinel)
            self.assertEqual(issue.call_args.args,(archive,'LIVE'))
            self.assertLessEqual(issue.call_args.kwargs['started'],time.monotonic())
        used_confirmation=issue.call_args.kwargs['confirmation']
        self.assertNotIn(used_confirmation,authority._CONFIRMATIONS)
        with self.assertRaisesRegex(Refused,'TERMINAL_CONFIRMATION_REQUIRED'):
            authority._issue(object(),'LIVE',confirmation=used_confirmation)

    def test_no_noninteractive_issuer_or_normal_credential_access(self):
        with patch.object(authority.sys,'stdin',io.StringIO()),patch('builtins.input',side_effect=AssertionError('NO_INPUT')), \
             patch.object(os,'getenv',side_effect=AssertionError('NO_ENV')):
            with self.assertRaisesRegex(Refused,authority.DISABLED):authority.issue_live_interactively()
            with self.assertRaises(Refused):direct_history.TerminalCredentialProvider().credential(None,deadline=time.monotonic()+1)

    def test_real_request_object_refuses_write_routes_headers_and_second_request(self):
        from urllib.parse import urlencode
        secret='SYNTHETIC_HTTP_SHAPE_ONLY_123456'
        headers={'Authorization':'Bearer '+secret,'Accept-Datetime-Format':'RFC3339',
                 'Accept':'application/json','Accept-Encoding':'identity'}
        with patch.object(authority,'require_role',return_value=None), \
             patch.object(network.http.client.HTTPSConnection,'request') as send:
            connection=network._LiveConnection(object(),time.monotonic()+10)
            for method,path in (('POST',SPEC['path']),('GET','/v3/accounts/SYNTHETIC/orders'),
                                ('PUT','/v3/accounts/SYNTHETIC/positions/EUR_USD/close'),('GET','https://example.invalid')):
                with self.assertRaises(Refused):connection.request(method,path,headers=headers)
            target=SPEC['path']+'?'+urlencode(SPEC['params'])
            with self.assertRaises(Refused):connection.request('GET',target,headers={**headers,'Host':'example.invalid'})
            with self.assertRaises(Refused):connection.request('GET',target,headers={**headers,'Authorization':None})
            connection.request('GET',target,headers=headers)
            with self.assertRaises(Refused):connection.request('GET',target,headers=headers)
            send.assert_called_once();connection.close()
