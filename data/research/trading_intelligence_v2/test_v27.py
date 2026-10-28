"""Focused terminal/read-only integration. Synthetic credentials and loopback only."""
import ast
import io
import json
import os
from pathlib import Path
import socket
import sys
import time
import unittest
from unittest.mock import patch
from . import direct_history as direct
from . import oneshot_authorisation as authority
from . import test_v26e as previous
from .core import timestamp,ResearchRejected
from .oneshot import SPEC,journal
from .oneshot_archive import APPROVED,Refused
from .oneshot_bridge import SyntheticCredentialProvider,run_https_fixture
from .https_test_server import LocalHTTPS

previous.legacy.NATIVE=globals().get('NATIVE',False)
PACKAGE=Path(__file__).resolve().parent
R56=PACKAGE.parent/'adaptive_ensemble/r56/phase6_connection_enablement'


class TTY(io.StringIO):
    def isatty(self):return True


class SyntheticConsole:
    def __init__(self,text):self.characters=list(text);self.reads=0
    def kbhit(self):return bool(self.characters)
    def getwch(self):self.reads+=1;return self.characters.pop(0)


class ExistingContract(previous.ExistingClientContract):pass


class TerminalContract(unittest.TestCase):
    def source(self,name):return (R56/name).read_text(encoding='utf-8')

    def test_r56_prompt_contract_is_gated_and_getpass_hidden(self):
        tree=ast.parse(self.source('credential_ipc.py'))
        functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        token=functions['prompt_hidden_token'];account=functions['prompt_account_id']
        calls=[n.func.attr for n in ast.walk(token) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertIn('assert_real_session',calls);self.assertIn('assert_runtime_authorisation',calls);self.assertIn('getpass',calls)
        self.assertIn('API token: ',[n.value for n in ast.walk(token) if isinstance(n,ast.Constant)])
        self.assertIn('Account ID: ',[n.value for n in ast.walk(account) if isinstance(n,ast.Constant)])
        self.assertTrue({16,128}.issubset({n.value for n in ast.walk(token) if isinstance(n,ast.Constant) and type(n.value) is int}))

    def test_r56_gate_and_two_get_plan_are_not_reused(self):
        tree=ast.parse(self.source('live_session_gate.py'))
        constants={n.targets[0].id:n.value.value for n in tree.body if isinstance(n,ast.Assign)
                   and isinstance(n.targets[0],ast.Name) and isinstance(n.value,ast.Constant)}
        self.assertIs(constants['REAL_SESSION_SOURCE_ENABLEMENT'],False)
        self.assertNotEqual(direct.CONFIRMATION,constants['ONE_SESSION_PHRASE'])
        source=self.source('diagnostic_supervisor.py')
        self.assertIn('activation.consume()',source);self.assertIn('ipc.prompt_hidden_token(',source)
        transport=self.source('restricted_live_transport.py')
        self.assertIn('http.client.HTTPSConnection',transport)
        self.assertIn('timeout=5',transport)
        self.assertIn('/v3/accounts/{accountID}/summary',self.source('live_session_gate.py'))
        self.assertIn('/v3/accounts/{accountID}/pricing',self.source('live_session_gate.py'))
        self.assertFalse(any(k.startswith('r56p') for k in sys.modules))

    def test_r56_permit_and_marker_reads_and_mutation_are_sealed(self):
        for name in ('one_session.permit','one_session.consumed'):
            path=R56/'real_activation'/name
            with self.assertRaises(PermissionError):path.read_bytes()
            with self.assertRaises(PermissionError):path.unlink()

    def test_default_entry_refuses_before_confirmation_console_or_environment(self):
        output=io.StringIO()
        with patch.object(sys,'stdout',output),patch('builtins.input',side_effect=AssertionError('NO_INPUT')), \
             patch.object(direct,'_console',side_effect=AssertionError('NO_CONSOLE')), \
             patch.object(os,'getenv',side_effect=AssertionError('NO_ENV')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')), \
             patch.object(direct,'run_once',side_effect=AssertionError('NO_WORKER')):
            self.assertEqual(direct.launch([]),2)
            with self.assertRaisesRegex(Refused,authority.DISABLED):direct.TerminalCredentialProvider().credential(None,deadline=time.monotonic()+1)
        self.assertIn(authority.DISABLED,output.getvalue());self.assertNotIn('Account ID:',output.getvalue())

    def test_no_cli_bypass_or_secret_arguments(self):
        for args in (['--live'],['--force'],['SYNTHETIC_ARGUMENT_NOT_USED']):
            with patch.object(sys,'stdout',io.StringIO()),patch.object(direct,'run_approved_session',side_effect=AssertionError('NO_SESSION')):
                self.assertEqual(direct.launch(args),2)

    def test_r56_confirmation_cannot_authorise_history(self):
        with patch.object(authority,'require_live_reservation',return_value=None), \
             patch('builtins.input',return_value='CONFIRM ONE DIAGNOSTIC SESSION'), \
             patch.object(sys,'stdout',io.StringIO()),patch.object(direct,'run_once',side_effect=AssertionError('NO_WORKER')):
            with self.assertRaisesRegex(Refused,'HISTORICAL_CONFIRMATION_REFUSED'):direct.run_approved_session(object())

    def test_hidden_console_has_no_echo_and_supports_backspace(self):
        secret='SYNTHETIC_TERMINAL_INPUT_123456';output=TTY();console=SyntheticConsole(secret+'x\b\r')
        with patch.object(authority,'require_live_reservation',return_value=None), \
             patch.object(direct,'_console',return_value=console),patch.object(sys,'stdin',TTY()),patch.object(sys,'stdout',output):
            value=direct.TerminalCredentialProvider().credential(object(),deadline=time.monotonic()+1)
        self.assertEqual(value,secret);self.assertNotIn(secret,output.getvalue())
        self.assertEqual(output.getvalue(),'API token: \n');self.assertIn('REDACTED',repr(direct.TerminalCredentialProvider()))

    def test_console_deadline_and_noninteractive_refusal(self):
        console=SyntheticConsole('');output=TTY()
        with patch.object(authority,'require_live_reservation',return_value=None), \
             patch.object(direct,'_console',return_value=console),patch.object(sys,'stdout',output):
            with patch.object(sys,'stdin',io.StringIO()),self.assertRaisesRegex(Refused,'INTERACTIVE_TERMINAL_REQUIRED'):
                direct.TerminalCredentialProvider().credential(object(),deadline=time.monotonic()+1)
            started=time.monotonic()
            with patch.object(sys,'stdin',TTY()),self.assertRaises(Refused):
                direct.TerminalCredentialProvider().credential(object(),deadline=started+.03)
            self.assertLess(time.monotonic()-started,.3);self.assertEqual(console.reads,0)

    def test_invalid_hidden_input_and_interrupt_do_not_echo(self):
        for text in ('short\r','SYNTHETIC_bad token!\r','x'*129,'\x00','\x03'):
            output=TTY();console=SyntheticConsole(text)
            with patch.object(authority,'require_live_reservation',return_value=None), \
                 patch.object(direct,'_console',return_value=console),patch.object(sys,'stdin',TTY()),patch.object(sys,'stdout',output):
                with self.assertRaises(KeyboardInterrupt if text=='\x03' else Refused):
                    direct.TerminalCredentialProvider().credential(object(),deadline=time.monotonic()+1)
            self.assertEqual(output.getvalue(),'API token: \n')

    def test_licensed_importer_still_refuses_broker_api_url(self):
        from .historical_import import import_dataset
        # Synthetic in-memory negative case, not an assertion of real rights.
        manifest=dict(provider='SYNTHETIC_NEGATIVE_FIXTURE',provider_identity_url='https://example.invalid',
            terms_url='https://example.invalid/terms',terms_evidence='SYNTHETIC_NOT_REAL_RIGHTS',
            permitted_use='offline_research_and_derived_results',rights_reviewed=True,
            schema='OBSERVED_M5_BID_ASK_MID_V1',timestamp_convention='UTC_START_AWARE',
            completion_evidence='explicit_source_complete_flag',files=[dict(instrument='EUR_USD',
                source_url='https://api-fxtrade.oanda.com/v3/instruments/EUR_USD/candles')])
        with self.assertRaisesRegex(ResearchRejected,'public_source_url_required_no_credentials_or_broker_api'):
            import_dataset(manifest,PACKAGE)


class TerminalHTTPS(previous.ExistingClientHTTPS):
    def test_terminal_workflow_uses_existing_reserved_ipc_tls_and_archive(self):
        archive=self.fixture();receipt=object();console=SyntheticConsole(self.secret+'\r');output=TTY();events=[]
        def admit(value):self.assertIs(value,receipt)
        def controller(root,**kwargs):
            self.assertEqual(root,APPROVED);self.assertEqual(kwargs['seconds'],15)
            self.assertIs(kwargs['_live_reservation'],receipt)
            self.assertIs(type(kwargs['_credential_provider']),direct.TerminalCredentialProvider)
            def deliver(_):
                self.assertEqual(journal(archive)['state'],'REQUEST_RESERVED')
                self.assertTrue(archive.path('grant.claimed.json').exists());events.append('reserved')
                return kwargs['_credential_provider'].credential(receipt,deadline=time.monotonic()+10)
            with patch.object(SyntheticCredentialProvider,'credential',deliver):
                return run_https_fixture(archive.root,provider=SyntheticCredentialProvider(self.secret),
                    binding=server.binding(),pin=archive.identity)
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(authority,'require_live_reservation',side_effect=admit), \
                 patch.object(direct,'run_once',side_effect=controller),patch.object(direct,'_console',return_value=console), \
                 patch.object(sys,'stdin',TTY()),patch.object(sys,'stdout',output), \
                 patch('builtins.input',return_value=direct.CONFIRMATION) as confirmation:
                result=direct.run_approved_session(receipt)
            confirmation.assert_called_once_with('Confirmation: ')
            self.assertEqual(result['kind'],'DONE',result);self.assertEqual(events,['reserved'])
            self.assertEqual(len(server.requests),1);self.assertNotIn(self.secret,output.getvalue())
            for path in archive.root.rglob('*'):
                if path.is_file():self.assertNotIn(self.secret.encode(),path.read_bytes())
            self.consumed(archive,server)

    def test_terminal_timeout_fences_existing_worker_without_dispatch(self):
        archive=self.fixture();console=SyntheticConsole('')
        def deliver(_):
            self.assertEqual(journal(archive)['state'],'REQUEST_RESERVED')
            return direct.TerminalCredentialProvider().credential(object(),deadline=time.monotonic()+.03)
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(authority,'require_live_reservation',return_value=None), \
                 patch.object(direct,'_console',return_value=console),patch.object(sys,'stdin',TTY()), \
                 patch.object(sys,'stdout',TTY()),patch.object(SyntheticCredentialProvider,'credential',deliver):
                result=self.run_session(archive,server)
            self.assertEqual(result['kind'],'OUTCOME_UNKNOWN');self.assertTrue(result['worker_exited'])
            self.assertEqual(server.connections,0);self.consumed(archive,server)

    def test_nine_candle_archive_has_existing_import_schema_and_bars(self):
        from .historical_import import SCHEMA
        archive=self.fixture()
        with LocalHTTPS(self.cert,self.key,scenario='nine',secret=self.secret) as server:
            result=self.run_session(archive,server);self.assertEqual(result['kind'],'DONE',result)
        receipt=json.loads(archive.read('manifests/v26c_https.json'));raw=archive.read(receipt['raw'])
        preview=direct.import_preview(raw,retrieved=timestamp('2026-10-28T00:00:00Z'))
        self.assertEqual(len(preview['rows']),9);self.assertEqual(len(preview['bars']),9)
        self.assertEqual(tuple(preview['rows'][0]),SCHEMA)
        source=json.loads(raw)['candles'][0]
        self.assertEqual(preview['rows'][0]['bid_o'],source['bid']['o'])
        self.assertEqual(preview['rows'][0]['ask_c'],source['ask']['c'])
        self.assertFalse(preview['strategy_evaluation_permitted'])
        self.assertEqual(preview['independence'],'PREVIOUSLY_EXAMINED_CONNECTIVITY_ONLY')
