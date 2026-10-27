"""Real loopback TLS + synthetic grants/tokens. No real credential/API access."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid
from .https_test_server import LocalHTTPS,certificate
from .oneshot import SPEC,SPEC_HASH,PHASES,journal
from .oneshot_archive import Archive,FIXTURES,NATIVE_FIXTURES,Refused
from .oneshot_bridge import SyntheticCredentialProvider,acquire_history,run_https_fixture
from .oanda_history_manifest import encoded,digest

NATIVE=globals().get('NATIVE',False)


class HTTPSLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cert_dir=FIXTURES/('v26d_tls_'+uuid.uuid4().hex)
        cls.cert,cls.key=certificate(cls.cert_dir)
        cls.secret='SYNTHETIC_'+uuid.uuid4().hex
        if NATIVE:NATIVE_FIXTURES.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        for name in ('cert.pem','key.pem','openssl.cnf'):(cls.cert_dir/name).unlink()
        cls.cert_dir.rmdir()

    def fixture(self,authorised=True):
        base=NATIVE_FIXTURES if NATIVE else FIXTURES
        if NATIVE:
            # Python 3.13 mkdtemp applies a special 0700 DACL on Windows.
            # Inherit the protected owner+SYSTEM ACL instead; never relax it.
            root=base/('v26d_case_'+uuid.uuid4().hex);root.mkdir()
        else:root=Path(tempfile.mkdtemp(prefix='v26d_case_',dir=base))
        archive=Archive(root,synthetic=True)
        self.addCleanup(archive.close)
        for name in ('raw','validated','manifests'):archive.path(name).mkdir()
        if authorised:
            archive.put('journal.json',encoded({'version':1,'state':'AUTHORISED_NOT_CONSUMED','spec':SPEC_HASH,'attempts':0}))
            archive.put('grant.json',encoded({'synthetic':True,'spec':SPEC_HASH,'identity':archive.identity}))
        return archive

    def run_session(self,a,server,**kw):
        return run_https_fixture(a.root,provider=SyntheticCredentialProvider(self.secret),
                                 binding=server.binding(kw.pop('verification','trusted')),pin=a.identity,**kw)

    def consumed(self,a,server):
        before=len(server.requests);connections=server.connections
        files={p.relative_to(a.root).as_posix():p.read_bytes() for p in a.root.rglob('*') if p.is_file()}
        with patch.object(SyntheticCredentialProvider,'credential',side_effect=AssertionError('PROVIDER_MUST_NOT_RUN')):
            result=self.run_session(a,server)
        self.assertEqual(result['kind'],'REFUSED',result)
        self.assertTrue(result['worker_exited']);self.assertEqual(len(server.requests),before)
        self.assertEqual(server.connections,connections)
        self.assertEqual(files,{p.relative_to(a.root).as_posix():p.read_bytes() for p in a.root.rglob('*') if p.is_file()})
        self.assertTrue(a.path('grant.claimed.json').exists())

    def scenario(self,name,*,count=None,verification='trusted',timeout=False):
        a=self.fixture()
        with LocalHTTPS(self.cert,self.key,scenario=name,secret=self.secret) as server:
            result=self.run_session(a,server,verification=verification,seconds=3 if timeout else 15)
            self.assertTrue(result['worker_exited'],result)
            if timeout:
                self.assertIn(result['kind'],('OUTCOME_UNKNOWN','REFUSED'),result)
                self.assertLessEqual(result['elapsed'],3,result);self.assertTrue(server.phase.is_set())
            else:self.assertEqual(result['kind'],'DONE' if count is not None else 'REFUSED',result)
            self.assertLessEqual(server.connections,1)
            self.assertLessEqual(len(server.requests),1)
            if verification!='trusted':
                self.assertEqual(server.connections,1);self.assertEqual(server.requests,[])
                self.assertEqual(result['local_error'],'SSLCertVerificationError',result)
            if name=='connection_refused':
                self.assertEqual(server.connections,0);self.assertEqual(result['local_error'],'ConnectionRefusedError',result)
            if name=='delayed_tls':self.assertEqual(server.connections,1);self.assertEqual(server.requests,[])
            if name in ('oversized','oversized_stream'):
                self.assertEqual(result.get('reason'),'BODY_SIZE_REFUSED',result)
            if name=='incomplete_body':self.assertEqual(result.get('reason'),'INCOMPLETE_HTTP_BODY',result)
            if count is not None:
                self.assertEqual(result['count'],count)
                self.assertEqual(journal(a)['state'],'SESSION_CONSUMED')
                receipt=json.loads(a.read('manifests/v26c_https.json'))
                for key in ('raw','validated'):
                    self.assertEqual(receipt[key+'_sha256'],digest(a.read(receipt[key])))
                self.assertEqual(receipt['observed_complete_count'],count)
                self.assertTrue(receipt['synthetic'])
            else:self.assertFalse(a.path('manifests/v26c_https.json').exists())
            if name not in ('connection_refused','delayed_tls') and verification=='trusted':
                self.assertEqual(len(server.requests),1)
                self.assertEqual(server.requests[0],{'method':'GET','path':SPEC['path'],'scope_valid':True,'auth_matches':True})
            self.consumed(a,server)
            self.assertTrue(self.secret not in repr(result),'CREDENTIAL_LEAK')
            self.assertTrue(self.secret not in repr(server.requests),'CREDENTIAL_LEAK')
            for p in a.root.rglob('*'):
                if p.is_file():self.assertTrue(self.secret.encode() not in p.read_bytes(),'CREDENTIAL_PERSISTED')
        self.assertTrue(server.thread is None or not server.thread.is_alive())

    def test_valid_completed_mba(self):self.scenario('valid',count=10)
    def test_nine_does_not_require_ten(self):self.scenario('nine',count=9)
    def test_incomplete_candles(self):self.scenario('incomplete_candles',count=9)
    def test_untrusted_certificate(self):self.scenario('valid',verification='untrusted')
    def test_hostname_mismatch(self):self.scenario('valid',verification='hostname_mismatch')
    def test_connection_refusal(self):self.scenario('connection_refused')
    def test_delayed_tls(self):self.scenario('delayed_tls',timeout=True)
    def test_delayed_headers(self):self.scenario('delayed_headers',timeout=True)
    def test_slow_body(self):self.scenario('slow_body',timeout=True)
    def test_timeout_during_dispatch(self):
        a=self.fixture()
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            result=self.run_session(a,server,seconds=3,fault='stall_during_dispatch')
            self.assertEqual(result['kind'],'OUTCOME_UNKNOWN',result)
            self.assertTrue(result['worker_exited']);self.assertLessEqual(result['elapsed'],3)
            self.assertTrue(server.phase.wait(1));self.assertEqual(len(server.requests),1)
            self.consumed(a,server)
    def test_incomplete_body(self):self.scenario('incomplete_body')
    def test_oversized_response(self):self.scenario('oversized')
    def test_oversized_actual_stream(self):self.scenario('oversized_stream')
    def test_redirect(self):self.scenario('redirect')
    def test_malformed_json(self):self.scenario('malformed')
    def test_invalid_schema(self):self.scenario('invalid_schema')
    def test_credential_echo(self):self.scenario('credential_echo')

    def test_default_refuses_before_provider(self):
        provider=SyntheticCredentialProvider(self.secret)
        with patch.object(SyntheticCredentialProvider,'credential',side_effect=AssertionError('MUST_NOT_RUN')):
            with self.assertRaisesRegex(Refused,'AUTHENTICATED_EXECUTION_DISABLED'):
                acquire_history(credential_provider=provider)

    def test_missing_grant_never_reads_provider(self):
        a=self.fixture(False)
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(SyntheticCredentialProvider,'credential',side_effect=AssertionError('MUST_NOT_RUN')):
                self.assertEqual(self.run_session(a,server)['kind'],'REFUSED')
            self.assertEqual(server.connections,0)

    def test_provider_called_after_durable_reservation(self):
        a=self.fixture();original=SyntheticCredentialProvider.credential;seen=[]
        def provide(provider):
            seen.append(journal(a)['state'])
            self.assertTrue(a.path('grant.claimed.json').exists())
            return original(provider)
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(SyntheticCredentialProvider,'credential',provide):
                self.assertEqual(self.run_session(a,server)['kind'],'DONE')
        self.assertEqual(seen,['REQUEST_RESERVED'])

    def test_provider_redaction(self):
        provider=SyntheticCredentialProvider(self.secret)
        self.assertTrue(self.secret not in repr(provider),'CREDENTIAL_LEAK')
        self.assertTrue(provider.credential()==self.secret,'CREDENTIAL_DELIVERY_MISMATCH')
        with self.assertRaises(Refused):SyntheticCredentialProvider('not_synthetic')

    def test_provider_error_redaction(self):
        a=self.fixture()
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(SyntheticCredentialProvider,'credential',side_effect=RuntimeError(self.secret)):
                result=self.run_session(a,server)
            self.assertEqual(result['kind'],'OUTCOME_UNKNOWN')
            self.assertTrue(self.secret not in repr(result),'CREDENTIAL_LEAK')
            self.assertEqual(server.connections,0);self.consumed(a,server)

    def test_two_process_https_race(self):
        a=self.fixture();barrier=threading.Barrier(3,timeout=5);results=[];errors=[]
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            def contender():
                try:barrier.wait();results.append(self.run_session(a,server))
                except BaseException as e:errors.append(type(e).__name__)
            threads=[threading.Thread(target=contender) for _ in range(2)]
            for thread in threads:thread.start()
            barrier.wait()
            for thread in threads:thread.join(16);self.assertFalse(thread.is_alive())
            self.assertEqual(errors,[]);self.assertEqual(sorted(r['kind'] for r in results),['DONE','REFUSED'],results)
            self.assertEqual(server.connections,1);self.assertEqual(len(server.requests),1)
            self.consumed(a,server)

    def test_no_non_loopback_sockets(self):
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
            with self.assertRaises(PermissionError):sock.connect(('192.0.2.1',443))
        with self.assertRaises(PermissionError):socket.getaddrinfo('api-fxtrade.oanda.com',443)

    def test_no_broker_or_production_state(self):
        self.assertFalse(any(n=='forex_bot' or n.startswith('forex_bot.') for n in sys.modules))
        with self.assertRaises(PermissionError):Path('synthetic_production.db').read_bytes()

    def test_no_host_override_in_binding(self):
        from .oneshot_https_fixture import validate_binding
        good={'port':443,'certificate':self.cert.read_text(),'verification':'trusted'}
        for bad in ({**good,'host':'api-fxtrade.oanda.com'},{**good,'port':True},{**good,'verification':'insecure'}):
            with self.subTest(keys=list(bad)),self.assertRaises(Refused):validate_binding(bad)


def status_test(status):
    def test(self):self.scenario('http_'+str(status))
    return test

for status in (401,403,404,429,500):setattr(HTTPSLifecycle,'test_http_'+str(status),status_test(status))


def crash_test(phase):
    def test(self):
        a=self.fixture()
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            result=self.run_session(a,server,fault='crash_'+phase)
            self.assertEqual(result['kind'],'OUTCOME_UNKNOWN',result);self.assertTrue(result['worker_exited'])
            if phase in ('after_response','archive_publication','final_persistence'):
                self.assertEqual(len(server.requests),1)
            elif phase=='during_dispatch':
                self.assertEqual(server.connections,1)
                self.assertLessEqual(len(server.requests),1)
            else:self.assertEqual(len(server.requests),0)
            self.consumed(a,server)
    return test

for phase in PHASES:setattr(HTTPSLifecycle,'test_https_crash_'+phase,crash_test(phase))
