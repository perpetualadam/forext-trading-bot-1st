"""Synthetic-only tests. Real gate stays closed; no actual credential getters."""
import ast
import copy
import os
from pathlib import Path
import socket
import ssl
import time
import unittest
from unittest.mock import Mock,MagicMock,patch
from . import test_v26e as previous
from . import oneshot_authorisation as authority
from . import oneshot_network as network
from .oneshot_credentials import ReservedCredentialProvider,acquire_history,validate_token,run_reserved_history
from .oneshot_archive import Refused,Archive
from .oneshot import SPEC,request_guard

previous.legacy.NATIVE=globals().get('NATIVE',False)


class ExistingContract(previous.ExistingClientContract):pass
class IntegratedHTTPS(previous.ExistingClientHTTPS):
    def test_reserved_provider_implementation_through_existing_bounded_ipc(self):
        from .oneshot_bridge import SyntheticCredentialProvider
        from .oneshot import journal
        from .https_test_server import LocalHTTPS
        archive=self.fixture();receipt=object();seen=[]
        def validate_synthetic_receipt(value):
            self.assertIs(value,receipt)
            self.assertEqual(journal(archive)['state'],'REQUEST_RESERVED')
            self.assertTrue(archive.path('grant.claimed.json').is_file())
            seen.append('reserved')
        def deliver(_):return ReservedCredentialProvider().credential(receipt)
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(authority,'require_live_reservation',side_effect=validate_synthetic_receipt), \
                 patch.object(os,'getenv',return_value=self.secret) as getter, \
                 patch.object(SyntheticCredentialProvider,'credential',deliver):
                result=self.run_session(archive,server)
            self.assertEqual(result['kind'],'DONE',result)
            getter.assert_called_once_with('OANDA_ACCESS_TOKEN')
            self.assertEqual(seen,['reserved']);self.assertEqual(len(server.requests),1)
            for path in archive.root.rglob('*'):
                if path.is_file():self.assertNotIn(self.secret.encode(),path.read_bytes())
            self.consumed(archive,server)


class RestrictedBridge(unittest.TestCase):
    def test_real_supervisor_reserves_before_any_worker_start_with_memory_stubs(self):
        from . import oneshot
        events=[];archive=MagicMock();receipt=object()
        archive.close.side_effect=lambda:events.append('closed')
        def reserved(a,**kwargs):
            self.assertIs(a,archive);self.assertIs(kwargs['_live_reservation'],receipt)
            events.append('reserved')
        def spawn(*args,**kwargs):
            self.assertEqual(events,['reserved']);events.append('startup')
            raise OSError('SYNTHETIC_NO_CHILD_CREATED')
        with patch.object(authority,'require_live_reservation',return_value=None), \
             patch.object(oneshot,'Archive',return_value=archive), \
             patch.object(oneshot,'reserve',side_effect=reserved), \
             patch.object(oneshot.subprocess,'Popen',side_effect=spawn), \
             patch.object(os,'getenv',side_effect=AssertionError('GETTER_MUST_NOT_RUN')):
            result=oneshot.run_once('SYNTHETIC_UNOPENED',synthetic_secret=None,
                _credential_provider=ReservedCredentialProvider(),_live_reservation=receipt)
        self.assertEqual(events,['reserved','startup','closed'])
        self.assertEqual(result['kind'],'OUTCOME_UNKNOWN');self.assertTrue(result['worker_exited'])
        archive.locked.assert_called_once_with()

    def test_reserved_real_worker_claim_is_single_use_in_existing_journal(self):
        from .oneshot import claim_reserved_worker,SPEC_HASH
        from .oanda_history_manifest import encoded,decode
        class MemoryArchive:
            synthetic=False;identity=['SYNTHETIC_MEMORY_ONLY']
            def __init__(self):
                self.data={'journal.json':encoded({'version':1,'state':'REQUEST_RESERVED','attempts':0,'spec':SPEC_HASH}),
                           'grant.claimed.json':encoded({'synthetic_memory_only':True})}
            def read(self,name):return self.data[name]
            def put(self,name,value,**kwargs):self.data[name]=value
        archive=MemoryArchive()
        with patch.object(authority,'require_live_reservation',return_value=None):
            claim_reserved_worker(archive,object())
            self.assertEqual(decode(archive.read('journal.json'))['state'],'REQUEST_ATTEMPTED')
            with self.assertRaisesRegex(Refused,'SESSION_NOT_UNUSED'):claim_reserved_worker(archive,object())

    def test_default_refuses_before_credential_or_network(self):
        with patch.object(os,'getenv',side_effect=AssertionError('GETTER_MUST_NOT_RUN')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_MUST_NOT_RUN')), \
             patch.object(socket,'socket',side_effect=AssertionError('SOCKET_MUST_NOT_RUN')):
            for candidate in (None,{},True,{'synthetic':True},object()):
                with self.subTest(kind=type(candidate).__name__):
                    with self.assertRaisesRegex(Refused,authority.DISABLED):ReservedCredentialProvider().credential(candidate)
                    with self.assertRaisesRegex(Refused,authority.DISABLED):
                        network.fetch_live(reservation=candidate,token='SYNTHETIC_NOT_A_REAL_TOKEN',deadline=time.monotonic()+10)
                    with self.assertRaisesRegex(Refused,authority.DISABLED):network._LiveConnection(candidate,time.monotonic()+10)
            with self.assertRaisesRegex(Refused,authority.DISABLED):acquire_history(credential_provider=object())
            with self.assertRaisesRegex(Refused,authority.DISABLED):run_reserved_history('UNOPENED',reservation={})
            from .oneshot import run_once
            with self.assertRaisesRegex(Refused,authority.DISABLED):
                run_once('UNOPENED',synthetic_secret=None,_credential_provider=ReservedCredentialProvider(),_live_reservation={})

    def test_worker_socket_policy_refuses_foreign_dns_and_repeat_dispatch(self):
        with patch.object(authority,'require_live_reservation',return_value=None):policy=network.LiveSocketPolicy(object())
        dns=(network.HOST,443,socket.AF_UNSPEC,socket.SOCK_STREAM,socket.IPPROTO_TCP)
        self.assertFalse(policy.permits('socket.getaddrinfo',dns))
        policy.resolving=True
        self.assertFalse(policy.permits('socket.getaddrinfo',('example.invalid',*dns[1:])))
        self.assertTrue(policy.permits('socket.getaddrinfo',dns))
        self.assertFalse(policy.permits('socket.getaddrinfo',dns))
        policy.address=('8.8.8.8',443);policy.family=socket.AF_INET
        self.assertFalse(policy.permits('socket.connect',(object(),('8.8.4.4',443))))
        self.assertTrue(policy.permits('socket.connect',(object(),policy.address)))
        self.assertFalse(policy.permits('socket.connect',(object(),policy.address)))

    def test_provider_implementation_reads_only_reviewed_keys_under_synthetic_stub(self):
        receipt=object();secret='SYNTHETIC_OFFLINE_PROVIDER_TEST'
        def accept(value):self.assertIs(value,receipt)
        # Test-only replacement of the permanently refusing validator, never a
        # real grant. Getter is replaced before the guarded method is invoked.
        with patch.object(authority,'require_live_reservation',side_effect=accept) as gate, \
             patch.object(os,'getenv',side_effect=[None,secret]) as getter:
            provider=ReservedCredentialProvider()
            self.assertEqual(provider.credential(receipt),secret)
            self.assertEqual([c.args for c in getter.call_args_list],[('OANDA_ACCESS_TOKEN',),('OANDA_API_KEY',)])
            gate.assert_called_once_with(receipt)
            self.assertNotIn(secret,repr(provider));self.assertFalse(hasattr(provider,'__dict__'))

    def test_invalid_credential_and_exception_redaction(self):
        for value in (None,'','x','SYNTHETIC_BAD\r\nInjected: yes',' SYNTHETIC_WHITESPACE ', 'x'*513):
            with self.subTest(kind=type(value).__name__),self.assertRaises(Refused) as caught:validate_token(value)
            self.assertEqual(str(caught.exception),'CREDENTIAL_INPUT_REFUSED')
        secret='SYNTHETIC_ERROR_NEVER_ECHO'
        with patch.object(authority,'require_live_reservation',return_value=None), \
             patch.object(os,'getenv',side_effect=RuntimeError(secret)):
            with self.assertRaises(Refused) as caught:ReservedCredentialProvider().credential(object())
            self.assertNotIn(secret,str(caught.exception));self.assertTrue(caught.exception.__suppress_context__)

    def test_approval_metadata_is_not_a_grant_even_if_copied(self):
        binding=authority.approval_requirements('a'*40,{'source.py':'b'*64})
        self.assertFalse(binding['authorises_execution']);self.assertEqual(binding['attempts'],1)
        self.assertEqual(binding['seconds'],15);self.assertEqual(binding['spec_sha256'],previous.SPEC_HASH)
        for candidate in (binding,copy.deepcopy(binding),{**binding,'authorises_execution':True}):
            with self.assertRaisesRegex(Refused,authority.DISABLED):authority.require_live_reservation(candidate)

    def test_proxy_and_foreign_request_refusal(self):
        for proxy in ('http://127.0.0.1:1','https://example.invalid','socks5://127.0.0.1:1'):
            with self.assertRaises(Refused):request_guard(**SPEC,proxy=proxy)
        for key,value in (('method','PUT'),('host','api-fxpractice.oanda.com'),('path','/v3/accounts/SYNTHETIC/orders')):
            bad=copy.deepcopy(SPEC);bad[key]=value
            with self.assertRaises(Refused):request_guard(**bad)

    def test_dns_addresses_are_public_and_exact_port(self):
        valid=(socket.AF_INET,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',('8.8.8.8',443))
        self.assertEqual(network.select_address([valid]),(socket.AF_INET,('8.8.8.8',443)))
        for address in ('127.0.0.1','10.0.0.1','169.254.169.254','0.0.0.0','224.0.0.1','192.0.2.1'):
            bad=(*valid[:4],(address,443))
            with self.subTest(address=address),self.assertRaises(Refused):network.select_address([valid,bad])
        for bad in ([],[(*valid[:4],('8.8.8.8',80))],[(*valid[:4],('localhost',443))],[valid]*65):
            with self.assertRaises(Refused):network.select_address(bad)

    def test_ipv6_dns_scope_and_family(self):
        valid=(socket.AF_INET6,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',('2606:4700:4700::1111',443,0,0))
        self.assertEqual(network.select_address([valid]),(valid[0],valid[4]))
        for address in (('::1',443,0,0),('fe80::1',443,0,1),('2606:4700:4700::1111',443,0,1)):
            with self.assertRaises(Refused):network.select_address([(*valid[:4],address)])

    def test_fixed_dns_sni_and_single_connection_with_fake_sockets(self):
        record=(socket.AF_INET,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',('8.8.8.8',443))
        context=Mock();context.verify_mode=ssl.CERT_REQUIRED;context.check_hostname=True;sock=Mock()
        with patch.object(authority,'require_live_reservation',return_value=None), \
             patch.object(socket,'getaddrinfo',return_value=[record]) as resolve, \
             patch.object(socket,'socket',return_value=sock) as create, \
             patch.object(ssl,'create_default_context',return_value=context):
            connection=network._LiveConnection(object(),time.monotonic()+10)
            connection.connect()
            resolve.assert_called_once_with(network.HOST,443,socket.AF_UNSPEC,socket.SOCK_STREAM,socket.IPPROTO_TCP)
            sock.connect.assert_called_once_with(('8.8.8.8',443))
            context.wrap_socket.assert_called_once_with(sock,server_hostname=network.HOST)
            with self.assertRaises(Refused):connection.connect()
            self.assertEqual(create.call_count,1)
            connection.close()

    def test_dns_failure_never_retries_or_connects(self):
        with patch.object(authority,'require_live_reservation',return_value=None), \
             patch.object(socket,'getaddrinfo',side_effect=OSError('SYNTHETIC_DNS_FAILURE')) as resolve, \
             patch.object(socket,'socket',side_effect=AssertionError('NO_CONNECTION')):
            connection=network._LiveConnection(object(),time.monotonic()+10)
            with self.assertRaises(OSError):connection.connect()
            with self.assertRaises(Refused):connection.connect()
            self.assertEqual(resolve.call_count,1)

    def test_real_context_keeps_certificate_and_hostname_verification(self):
        with patch.object(authority,'require_live_reservation',return_value=None):
            connection=network._LiveConnection(object(),time.monotonic()+10)
            self.assertTrue(connection._context.check_hostname)
            self.assertEqual(connection._context.verify_mode,ssl.CERT_REQUIRED)
            connection.close()

    def test_no_archive_fallback(self):
        for path in (Path.cwd(),Path(r'C:\Users\Brian\OneDrive\ResearchArchive')):
            with self.assertRaisesRegex(Refused,'APPROVED_ROOT_REQUIRED'):Archive(path)

    def test_no_ordinary_environment_or_operational_reads_in_new_imports(self):
        package=Path(__file__).resolve().parent
        for name in ('oneshot_credentials.py','oneshot_network.py','oneshot_authorisation.py'):
            tree=ast.parse((package/name).read_text(encoding='utf-8'))
            for node in tree.body:
                if isinstance(node,ast.Import):
                    self.assertTrue(all(a.name.split('.')[0] not in {'forex_bot','dotenv','requests','oandapyV20','keyring'} for a in node.names))
                self.assertFalse(isinstance(node,ast.Expr) and isinstance(node.value,ast.Call))
        self.assertIn('DISABLED',repr(ReservedCredentialProvider()))

    def test_deadline_input_refusal(self):
        for value in (True,None,float('nan'),float('inf'),time.monotonic()-1,time.monotonic()+20):
            with self.assertRaises(Refused):network.remaining(value)
