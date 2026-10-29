"""Actual selected-profile controller/worker/loopback path; no LIVE grants."""
import unittest
from unittest.mock import patch
from . import test_v27_rollover as reusable
from . import oneshot_authorisation as authority
from .request_profile import SELECTED,PILOT_IDS,specification,_selection
from .pilot_history import plan
from .oneshot import SPEC,SPEC_HASH,request_guard,journal
from .oneshot_archive import Refused
from .oanda_history_manifest import encoded,digest,decode
from .https_test_server import LocalHTTPS
from .test_v27 import TTY
from .oneshot_bridge import SyntheticCredentialProvider

reusable.previous.legacy.NATIVE=globals().get('NATIVE',False)
# Reuse actual fixtures and controller helpers, not copies of security logic.
class PilotNative(unittest.TestCase):
    setUpClass=classmethod(reusable.NamespacedHTTPS.setUpClass.__func__)
    tearDownClass=classmethod(reusable.NamespacedHTTPS.tearDownClass.__func__)
    fixture=reusable.NamespacedHTTPS.fixture
    prepared=reusable.NamespacedHTTPS.prepared
    admitted_fixture=reusable.NamespacedHTTPS.admitted_fixture
    run_session=reusable.NamespacedHTTPS.run_session
    no_repeat=reusable.NamespacedHTTPS.no_repeat
    def test_selected_exact_plan(self):
        self.assertIn(SELECTED,(0,1,2));self.assertEqual(SPEC,plan(authority.source_seal())[SELECTED].spec)
    def test_other_windows_and_write_endpoints_refused(self):
        for i in (None,0,1,2):
            if i!=SELECTED:
                with self.assertRaises(Refused):request_guard(**specification(i))
        bad=specification(SELECTED);bad['method']='POST'
        with self.assertRaises(Refused):request_guard(**bad)
    def test_actual_profile_child_https_and_no_repeat(self):
        archive,cap=self.admitted_fixture()
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            result=self.run_session(archive,cap,server)
            self.assertEqual(result['kind'],'DONE',result)
            self.assertEqual(len(server.requests),1);self.assertTrue(server.requests[0]['scope_valid'])
            self.assertEqual(journal(archive)['state'],'SESSION_CONSUMED')
            self.assertEqual(decode(archive.read('request.json'))['spec'],SPEC)
            self.assertNotIn(self.secret.encode(),archive.read('manifests/v26c_https.json'))
            self.no_repeat(archive,cap,server)
    def test_sibling_profile_cap_refused_before_credentials(self):
        archive,cap=self.admitted_fixture();cap=dict(cap,spec=digest(encoded(specification((SELECTED+1)%3))))
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            with patch.object(SyntheticCredentialProvider,'credential',side_effect=AssertionError('NO_CREDENTIAL')):
                with self.assertRaises(Refused):self.run_session(archive,cap,server)
            self.assertEqual(len(server.requests),0)
    def test_selector_is_fixed_and_unambiguous(self):
        for argv in (['--pilot-window=4'],['--pilot-window=1','--pilot-window=2'],['--pilot-window=01']):
            with self.assertRaises(ValueError):_selection(argv)
    def test_pilot_metadata_required_not_generated(self):
        class Missing:
            def exists(self):return False
        with patch.object(authority,'PREPARATION',Missing()):
            with self.assertRaisesRegex(Refused,'PILOT_PREPARATION_REQUIRED'):authority.prepared_request_nonce(authority.source_seal())
    def test_no_automatic_grant_from_fixture_success(self):
        archive,cap=self.admitted_fixture()
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            result=self.run_session(archive,cap,server);self.assertEqual(result['kind'],'DONE',result)
        self.assertFalse(authority._CONFIRMATIONS)
        with self.assertRaisesRegex(Refused,'TERMINAL_CONFIRMATION_REQUIRED'):
            authority._issue(archive,'LIVE',confirmation='0'*32)
    def test_prior_unknown_stops_before_terminal_confirmation(self):
        with patch.object(authority,'require_pilot_predecessors',side_effect=Refused('PILOT_PREDECESSOR_NOT_SUCCESSFUL')),patch.object(authority.sys,'stdin',TTY()),patch.object(authority.sys,'stdout',TTY()),patch('builtins.input',side_effect=AssertionError('NO_CONFIRMATION')):
            with self.assertRaisesRegex(Refused,'PILOT_PREDECESSOR_NOT_SUCCESSFUL'):authority.issue_live_interactively()
    def test_predecessors_require_durable_success(self):
        archive=self.fixture(authorised=False)
        def fixture_archive(path):return archive
        if SELECTED==0:
            with patch.object(authority,'Archive',side_effect=AssertionError('NO_SIBLING_READ')):authority.require_pilot_predecessors()
            return
        # Actual disposable fixture files read by the parent admission helper.
        previous=PILOT_IDS[0];spec=digest(encoded(specification(0)))
        grant=encoded(dict(fixture_only=True));archive.put('grant.claimed.json',grant)
        archive.put('journal.json',encoded(dict(session=previous,state='SESSION_CONSUMED',spec=spec,attempts=1)))
        archive.put('result.json',encoded(dict(session=previous,source=authority.source_seal(),spec=spec,kind='OUTCOME_UNKNOWN',attempts=1,worker_exited=True,journal_state='SESSION_CONSUMED',grant_sha256=digest(grant))))
        with patch.object(authority,'Archive',fixture_archive):
            with self.assertRaisesRegex(Refused,'PILOT_PREDECESSOR_NOT_SUCCESSFUL'):authority.require_pilot_predecessors()

    def successful_predecessor_fixtures(self):
        fixtures={}
        for index in range(SELECTED):
            archive=self.fixture(authorised=False);previous=PILOT_IDS[index]
            source=authority.source_seal();spec=digest(encoded(specification(index)));identity=digest(encoded(archive.identity))
            req=encoded(dict(session=previous,source=source,spec=specification(index),identity=archive.identity))
            grant=encoded(dict(session=previous,source=source,spec=spec,mode='LIVE',root=str(archive.root),identity=identity,fixture_not_executable=True))
            raw=b'fixture candle body';rows=b'fixture derivative'
            values={'request.json':req,'grant.claimed.json':grant,'journal.json':encoded(dict(session=previous,state='SESSION_CONSUMED',attempts=1,spec=spec,identity=identity)),
                    'result.json':encoded(dict(session=previous,source=source,spec=spec,kind='DONE',attempts=1,worker_exited=True,journal_state='SESSION_CONSUMED',grant_sha256=digest(grant))),
                    'raw/v26c_https.json':raw,'validated/v26c_https.json':rows,'manifests/v26c_https.json':encoded(dict(synthetic=False,session=previous,request_sha256=digest(req),raw_sha256=digest(raw),validated_sha256=digest(rows)))}
            for n,v in values.items():archive.put(n,v)
            fixtures[previous]=archive
        return fixtures
    def test_verified_predecessors_still_create_no_authority(self):
        fixtures=self.successful_predecessor_fixtures()
        with patch.object(authority,'Archive',lambda path:fixtures[path.name]):authority.require_pilot_predecessors()
        self.assertFalse(authority._CONFIRMATIONS)
    def test_corrupt_predecessor_archive_stops(self):
        if SELECTED==0:return
        fixtures=self.successful_predecessor_fixtures();archive=fixtures[PILOT_IDS[0]]
        archive.put('raw/v26c_https.json',b'corrupt',replace=True)
        with patch.object(authority,'Archive',lambda path:fixtures[path.name]):
            with self.assertRaisesRegex(Refused,'PILOT_PREDECESSOR_ARCHIVE_REFUSED'):authority.require_pilot_predecessors()
    def test_predecessor_pending_record_stops(self):
        if SELECTED==0:return
        fixtures=self.successful_predecessor_fixtures();fixtures[PILOT_IDS[0]].put('journal.json.pending',b'ambiguous')
        with patch.object(authority,'Archive',lambda path:fixtures[path.name]):
            with self.assertRaisesRegex(Refused,'PILOT_PREDECESSOR_AMBIGUOUS'):authority.require_pilot_predecessors()
