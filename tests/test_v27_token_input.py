"""Synthetic terminal input tests; no grant, credential source or socket access."""
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PACKAGE=Path(__file__).resolve().parents[1]/'data/research/trading_intelligence_v2'
if 'tiv2' not in sys.modules:
    spec=importlib.util.spec_from_file_location('tiv2',PACKAGE/'__init__.py',submodule_search_locations=[str(PACKAGE)])
    module=importlib.util.module_from_spec(spec);sys.modules['tiv2']=module;spec.loader.exec_module(module)
from tiv2 import token_input as token
from tiv2 import direct_history as direct
from tiv2.oneshot_archive import Refused

SECRET='SYNTHETIC_MEMORY_ONLY_TOKEN_123456'


class Clock:
    def __init__(self):self.now=1000.
    def monotonic(self):return self.now
    def sleep(self,duration):self.now+=duration


class Console:
    def __init__(self,clock,delay,text):self.clock=clock;self.ready=clock.now+delay;self.text=list(text);self.reads=0
    def kbhit(self):return self.clock.now>=self.ready and bool(self.text)
    def getwch(self):self.reads+=1;return self.text.pop(0)


class TokenEntry(unittest.TestCase):
    def read(self,delay,text=SECRET+'\r'):
        clock=Clock();console=Console(clock,delay,text);out=io.StringIO()
        with patch.object(token,'time',clock),patch.object(sys,'stdout',out):
            result=token.read_hidden_token(console,deadline=clock.now+120)
        self.assertNotIn(SECRET,out.getvalue());self.assertEqual(out.getvalue(),'API token: \n')
        return result,clock

    def test_slow_input_does_not_use_network_budget(self):
        result,clock=self.read(30)
        self.assertEqual(result,SECRET);self.assertGreaterEqual(clock.now,1030)

    def test_input_near_120_seconds_is_accepted(self):self.assertEqual(self.read(119)[0],SECRET)

    def test_timeout_at_120_seconds_never_reads_or_echoes_token(self):
        clock=Clock();console=Console(clock,121,SECRET+'\r');out=io.StringIO()
        with patch.object(token,'time',clock),patch.object(sys,'stdout',out):
            with self.assertRaisesRegex(Refused,'TOKEN_ENTRY_TIMEOUT'):
                token.read_hidden_token(console,deadline=1120.)
        self.assertEqual(console.reads,0);self.assertEqual(clock.now,1120.)
        self.assertNotIn(SECRET,out.getvalue())

    def test_invalid_deadlines_refused_before_prompt(self):
        clock=Clock();console=Console(clock,0,SECRET+'\r')
        for deadline in (None,True,float('nan'),float('inf'),1121.,1000.,999.):
            out=io.StringIO()
            with patch.object(token,'time',clock),patch.object(sys,'stdout',out),self.assertRaises(Refused):
                token.read_hidden_token(console,deadline=deadline)
            self.assertEqual(console.reads,0);self.assertEqual(out.getvalue(),'')

    def test_backspace_and_hidden_valid_input(self):self.assertEqual(self.read(0,SECRET+'x\b\r')[0],SECRET)

    def test_invalid_input_and_interrupt_never_echo(self):
        for text in ('short\r','x'*129,'SYNTHETIC bad value!\r','\x00','\x03'):
            clock=Clock();out=io.StringIO()
            with patch.object(token,'time',clock),patch.object(sys,'stdout',out):
                with self.assertRaises(KeyboardInterrupt if text=='\x03' else Refused):
                    token.read_hidden_token(Console(clock,0,text),deadline=1120.)
            self.assertEqual(out.getvalue(),'API token: \n')

    def test_default_gate_precedes_input_console_and_worker(self):
        with patch.object(sys,'stdin',io.StringIO()),patch.object(sys,'stdout',io.StringIO()), \
             patch.object(direct,'_console') as console,patch.object(direct,'run_once') as controller:
            with self.assertRaises(Refused):direct.TerminalCredentialProvider().credential(None,deadline=1120.)
            self.assertEqual(direct.launch([]),2)
        console.assert_not_called();controller.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
