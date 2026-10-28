"""Non-activating UI tests; runnable with stdlib unittest or normal CI pytest."""
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
from tiv2.confirmation_input import read_confirmation
from tiv2.oneshot_archive import Refused
from tiv2 import direct_history as direct

PHRASE='CONFIRM ONE HISTORICAL EUR_USD REQUEST '+('a'*12)+' '+('b'*32)


class ConfirmationInput(unittest.TestCase):
    def assert_rejected(self,value=None,*,eof=False):
        output=io.StringIO()
        with patch('builtins.input',side_effect=EOFError() if eof else None,return_value=value) as reader, \
             patch.object(sys,'stdout',output):
            with self.assertRaisesRegex(Refused,'HISTORICAL_CONFIRMATION_REFUSED'):read_confirmation(PHRASE)
        reader.assert_called_once_with('Confirmation: ')
        text=output.getvalue()
        self.assertIn(PHRASE,text);self.assertIn('CONFIRMATION_MISMATCH',text)
        self.assertNotIn('Confirmation accepted.',text)
        self.assertNotIn('No authenticated request',text) # UI alone cannot establish durable outcome.
        return text

    def test_exact_line_accepted_once(self):
        output=io.StringIO()
        with patch('builtins.input',return_value=PHRASE) as reader,patch.object(sys,'stdout',output):
            self.assertIsNone(read_confirmation(PHRASE))
        reader.assert_called_once_with('Confirmation: ')
        self.assertEqual(output.getvalue().count('Confirmation accepted.'),1)

    def test_concatenated_duplicate_rejected(self):self.assert_rejected(PHRASE*2)
    def test_separated_duplicate_not_repaired(self):self.assert_rejected(PHRASE+' '+PHRASE)
    def test_embedded_newline_not_split(self):self.assert_rejected(PHRASE+'\n'+PHRASE)
    def test_empty_line_rejected(self):self.assert_rejected('')
    def test_missing_line_rejected(self):self.assert_rejected(eof=True)
    def test_wrong_request_id_rejected(self):self.assert_rejected(PHRASE[:-1]+'c')
    def test_wrong_source_seal_rejected(self):self.assert_rejected(PHRASE.replace('a'*12,'c'*12))

    def test_whitespace_is_not_trimmed(self):
        for value in (' '+PHRASE,PHRASE+' ',PHRASE+'\t','\t'+PHRASE):
            with self.subTest(value_length=len(value)):self.assert_rejected(value)

    def test_rejected_response_never_echoed_or_logged(self):
        sensitive='SYNTHETIC_SENSITIVE_INPUT_MUST_NOT_ECHO'
        self.assertNotIn(sensitive,self.assert_rejected(sensitive))

    def test_rejection_never_enters_controller_or_token_provider(self):
        with patch.object(direct.authority,'require_live_reservation',return_value=None), \
             patch('builtins.input',return_value=direct.CONFIRMATION*2) as reader, \
             patch.object(sys,'stdout',io.StringIO()),patch.object(direct,'run_once') as controller, \
             patch.object(direct.TerminalCredentialProvider,'credential') as credential:
            with self.assertRaisesRegex(Refused,'HISTORICAL_CONFIRMATION_REFUSED'):direct.run_approved_session(object())
        reader.assert_called_once();controller.assert_not_called();credential.assert_not_called()

    def test_acceptance_notice_precedes_controller(self):
        output=io.StringIO()
        def controller(*args,**kwargs):
            self.assertIn('Confirmation accepted.',output.getvalue())
            return {'kind':'SYNTHETIC_TEST_ONLY'}
        with patch.object(direct.authority,'require_live_reservation',return_value=None), \
             patch('builtins.input',return_value=direct.CONFIRMATION),patch.object(sys,'stdout',output), \
             patch.object(direct,'run_once',side_effect=controller) as run:
            direct.run_approved_session(object())
        run.assert_called_once()

    def test_default_admission_still_refuses_without_input(self):
        with patch.object(sys,'stdin',io.StringIO()),patch.object(sys,'stdout',io.StringIO()), \
             patch('builtins.input') as reader,patch.object(direct,'run_once') as run:
            self.assertEqual(direct.launch([]),2)
        reader.assert_not_called();run.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
