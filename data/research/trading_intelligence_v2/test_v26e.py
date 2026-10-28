"""Existing schema + V2.6D lifecycle. Synthetic credentials and loopback TLS only."""
import ast
import copy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from . import test_v26d as legacy
from .oneshot import SPEC,SPEC_HASH,journal
from .oneshot_archive import Refused
from .oneshot_bridge import SyntheticCredentialProvider
from .oanda_existing_readonly import (
    ExistingOandaCredentialProvider,acquire_history,candle_request,run_synthetic_session,
)
from .https_test_server import LocalHTTPS

legacy.NATIVE=globals().get('NATIVE',False)
PACKAGE=Path(__file__).resolve().parent
ROOT=PACKAGE.parents[2]


class ExistingClientContract(unittest.TestCase):
    def test_existing_client_uses_non_account_instruments_candles(self):
        source=ast.parse((ROOT/'forex_bot/oanda_client.py').read_text(encoding='utf-8'))
        functions={n.name:n for n in source.body if isinstance(n,ast.FunctionDef)}
        for name in ('fetch_ohlcv','fetch_ohlcv_range'):
            calls=[n for n in ast.walk(functions[name]) if isinstance(n,ast.Call)
                   and isinstance(n.func,ast.Attribute) and n.func.attr=='InstrumentsCandles']
            self.assertEqual(len(calls),1)
            self.assertEqual({kw.arg for kw in calls[0].keywords},{'instrument','params'})
        latest=functions['fetch_ohlcv']
        self.assertIn('M5',[n.value for n in ast.walk(latest.args) if isinstance(n,ast.Constant)])
        dictionaries=[n for n in ast.walk(latest) if isinstance(n,ast.Dict)]
        self.assertTrue(any(any(isinstance(k,ast.Constant) and k.value=='price' and
            isinstance(v,ast.Constant) and v.value=='MBA' for k,v in zip(d.keys,d.values)) for d in dictionaries))
        self.assertFalse(any(isinstance(n,ast.Attribute) and n.attr=='AccountInstrumentsCandles' for n in ast.walk(source)))

    def test_importing_operational_config_would_read_dotenv(self):
        source=ast.parse((ROOT/'forex_bot/config.py').read_text(encoding='utf-8'))
        self.assertTrue(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                            and n.func.id=='load_dotenv' for n in ast.walk(source)))
        self.assertFalse(any(n=='forex_bot' or n.startswith('forex_bot.') for n in sys.modules))

    def test_existing_research_helper_reaches_operational_client(self):
        source=ast.parse((ROOT/'forex_bot/oanda_candles_read.py').read_text(encoding='utf-8'))
        self.assertTrue(any(isinstance(n,ast.ImportFrom) and n.module=='forex_bot.oanda_client'
                            for n in ast.walk(source)))

    def test_exact_first_request_and_count_omitted(self):
        self.assertEqual(candle_request(),SPEC)
        self.assertEqual(candle_request()['host'],'api-fxtrade.oanda.com')
        self.assertEqual(candle_request()['path'],'/v3/instruments/EUR_USD/candles')
        self.assertEqual(candle_request()['params'],{
            'from':'2026-09-02T10:00:00Z','to':'2026-09-02T10:49:59Z',
            'granularity':'M5','price':'MBA','smooth':'false','includeFirst':'true'})
        self.assertNotIn('count',candle_request()['params'])

    def test_returned_request_cannot_mutate_shared_authority(self):
        first=candle_request();first['params']['price']='M'
        self.assertEqual(candle_request(),SPEC)

    def test_foreign_routes_hosts_methods_and_parameters_are_refused(self):
        changes=[('method','POST'),('host','api-fxpractice.oanda.com'),('host','example.invalid'),
                 ('path','/v3/accounts/SYNTHETIC_ACCOUNT/instruments/EUR_USD/candles'),
                 ('path','/v3/accounts/SYNTHETIC_ACCOUNT/orders'),
                 ('path','/v3/accounts/SYNTHETIC_ACCOUNT/trades'),
                 ('path','/v3/accounts/SYNTHETIC_ACCOUNT/positions/EUR_USD/close'),
                 ('path','/v3/instruments/GBP_USD/candles')]
        for key,value in changes:
            bad=copy.deepcopy(SPEC);bad[key]=value
            with self.subTest(field=key),self.assertRaisesRegex(Refused,'EXACT_READ_ONLY_REQUEST_REQUIRED'):
                candle_request(bad)
        for key,value in (('granularity','M1'),('price','M'),('smooth','true'),('includeFirst','false'),
                          ('from','2026-09-02T10:05:00Z'),('to','2026-09-02T10:54:59Z'),('count',10)):
            bad=copy.deepcopy(SPEC);bad['params'][key]=value
            with self.subTest(parameter=key),self.assertRaises(Refused):candle_request(bad)

    def test_sensitive_headers_proxy_and_account_metadata_are_not_accepted(self):
        for field in ('headers','proxy','accountID','token'):
            bad=copy.deepcopy(SPEC);bad[field]='SYNTHETIC_DO_NOT_ECHO_123456'
            with self.subTest(field=field),self.assertRaises(Refused) as caught:candle_request(bad)
            self.assertTrue(bad[field] not in str(caught.exception),'SENSITIVE_INPUT_LEAK')

    def test_real_provider_is_inactive_and_does_not_read_configuration(self):
        provider=ExistingOandaCredentialProvider()
        with patch.object(os,'getenv',side_effect=AssertionError('ENVIRONMENT_MUST_NOT_BE_READ')):
            with self.assertRaisesRegex(Refused,'AUTHENTICATED_EXECUTION_DISABLED'):provider.credential()
            with patch.object(ExistingOandaCredentialProvider,'credential',side_effect=AssertionError('PROVIDER_MUST_NOT_RUN')):
                with self.assertRaisesRegex(Refused,'AUTHENTICATED_EXECUTION_DISABLED'):
                    acquire_history(credential_provider=provider)
        self.assertIn('DISABLED',repr(provider))

    def test_real_provider_cannot_enter_the_synthetic_controller(self):
        with patch.object(ExistingOandaCredentialProvider,'credential',side_effect=AssertionError('PROVIDER_MUST_NOT_RUN')):
            with self.assertRaisesRegex(Refused,'SYNTHETIC_PROVIDER_REQUIRED'):
                run_synthetic_session('UNOPENED_ROOT',provider=ExistingOandaCredentialProvider(),binding={})

    def test_no_environment_loader_or_operational_import_in_adapter(self):
        source=(PACKAGE/'oanda_existing_readonly.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        forbidden={'forex_bot','dotenv','win32cred','keyring','ctypes','requests','oandapyV20'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):self.assertTrue(all(a.name.split('.')[0] not in forbidden for a in node.names))
            if isinstance(node,ast.ImportFrom):self.assertNotIn((node.module or '').split('.')[0],forbidden)
            if isinstance(node,ast.Attribute):self.assertNotIn(node.attr,('getenv','environ','load_dotenv','CredRead'))
        with self.assertRaises(PermissionError):Path('.env').read_bytes()


class ExistingClientHTTPS(legacy.HTTPSLifecycle):
    """All original HTTPS/crash/deadline assertions run through the new adapter."""
    def run_session(self,a,server,**kwargs):
        return run_synthetic_session(a.root,provider=SyntheticCredentialProvider(self.secret),
            binding=server.binding(kwargs.pop('verification','trusted')),pin=a.identity,**kwargs)

    def test_adapter_exact_get_reaches_existing_worker_and_publication(self):
        archive=self.fixture()
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            result=self.run_session(archive,server)
            self.assertEqual(result['kind'],'DONE',result)
            self.assertEqual(server.requests,[{'method':'GET','path':SPEC['path'],'scope_valid':True,'auth_matches':True}])
            self.assertTrue(result['worker_exited'])
            self.assertEqual(journal(archive)['state'],'SESSION_CONSUMED')
            self.assertEqual(journal(archive)['attempts'],1)
            self.assertEqual(journal(archive)['spec'],SPEC_HASH)
            self.consumed(archive,server)

    def test_secret_is_not_in_worker_argv_or_environment(self):
        from . import oneshot
        archive=self.fixture();real=oneshot.subprocess.Popen;seen=[]
        def launch(*args,**kwargs):
            self.assertTrue(self.secret not in repr((args,kwargs)),'CREDENTIAL_IN_PROCESS_ARGUMENTS')
            seen.append(True)
            return real(*args,**kwargs)
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(oneshot.subprocess,'Popen',side_effect=launch):
                result=self.run_session(archive,server)
            self.assertEqual(result['kind'],'DONE',result)
            self.assertEqual(seen,[True])
            for path in archive.root.rglob('*'):
                if path.is_file():self.assertTrue(self.secret.encode() not in path.read_bytes(),'PERSISTED_CREDENTIAL')
