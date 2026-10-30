"""Exact remaining profile only: invented token/candles, loopback HTTPS."""
import copy
import uuid
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from . import test_v28d_diagnostics as previous
from . import bounded_acquisition as b,oneshot_authorisation as a,failure_diagnostics as d
from .oneshot_archive import Archive,Refused
from .session_namespace import prepare_session,acquisition_lock
from .oneshot_bridge import SyntheticCredentialProvider
from .https_test_server import LocalHTTPS
from .oanda_history_manifest import encoded,decode,digest
from .core import timestamp
previous.previous.legacy.NATIVE=globals().get('NATIVE',False)
H=b.REMAINING_HASH


class Catalogue66(unittest.TestCase):
    def test_exact_immutable_hash(self):self.assertEqual(b.catalogue_identity(b.REMAINING_CATALOGUE.read_bytes(),H),H)
    def test_git_and_windows_newlines_preserve_reviewed_identity(self):
        raw=b.REMAINING_CATALOGUE.read_bytes().replace(b'\r\n',b'\n')
        self.assertEqual(digest(raw),'7027daa2660507d61b47e53be4619d7254eb8991e717ffbfe277300678a26592')
        self.assertEqual(b.catalogue_identity(raw,H),H);self.assertEqual(b.catalogue_identity(raw.replace(b'\n',b'\r\n'),H),H)
        self.assertNotEqual(b.catalogue_identity(raw+b' ',H),H)
    def test_exact_original_identities(self):
        rows=b.catalogue(H)
        self.assertEqual([w['original_window'] for w in rows],list(range(41,107)))
        self.assertEqual([w['original_index'] for w in rows],list(range(40,106)))
        for i,w in enumerate(rows):
            self.assertEqual(w['specification'],b.spec(i+40))
            self.assertEqual(w['spec_sha256'],digest(encoded(b.spec(i+40))))
    def test_exact_66_and_slots(self):self.assertEqual([w['maximum_candles'] for w in b.catalogue(H)],[1000]*65+[120])
    def test_contiguous_excludes_40(self):
        rows=[b.spec(i,H) for i in range(66)]
        self.assertEqual(timestamp(rows[0]['params']['from']),timestamp('2025-01-17T21:20:00Z'))
        self.assertEqual(timestamp(rows[-1]['params']['to'])+1,timestamp('2025-09-01T00:00:00Z'))
        self.assertTrue(all(timestamp(x['params']['to'])+1==timestamp(y['params']['from']) for x,y in zip(rows,rows[1:])))
        self.assertGreater(timestamp(rows[0]['params']['from']),timestamp(b.spec(39)['params']['to']))
    def test_exact_get_only(self):
        for i in range(66):
            s=b.spec(i,H)
            self.assertEqual((s['host'],s['method'],s['path']),('api-fxtrade.oanda.com','GET','/v3/instruments/EUR_USD/candles'))
            self.assertEqual({k:v for k,v in s['params'].items() if k not in ('from','to')},dict(price='MBA',granularity='M5',smooth='false',includeFirst='true'))
    def test_no_arbitrary_profile(self):
        for h in (None,'0'*64,'../catalogue',b.CATALOGUE_HASH+'x',66,{}):self.assertRaises(Refused,b.profile,h)
    def test_index_bounds(self):
        for i in (-1,66,106,True,'40',None):
            self.assertRaises(Refused,b.spec,i,H);self.assertRaises(Refused,b.marker,i,H)
    def test_cache_is_profile_scoped_and_returns_copies(self):
        self.assertNotEqual(b.spec(0),b.spec(0,H))
        changed=b.spec(0,H);changed['params']['from']='2025-01-14T10:00:00Z'
        self.assertEqual(b.spec(0,H),b.spec(40));self.assertNotEqual(b.spec(0,H),b.spec(39))
    def test_catalogue_substitution_after_cache(self):
        b.catalogue(H)
        with patch.object(Path,'read_bytes',return_value=b'{}'):self.assertRaises(Refused,b.catalogue,H)
    def test_limits_have_only_attempt_count_difference(self):
        self.assertEqual(b.limits_for(H),dict(b.LIMITS,attempts=66))
    def test_original_profile_unchanged(self):
        self.assertEqual(len(b.catalogue()),106);self.assertEqual(b.spec(0)['params']['from'],'2024-09-01T00:00:00+00:00')
    def test_diagnostics_index_bound_is_catalogue_specific(self):
        cap=dict(session='1'*32,source='2'*64,catalogue=H)
        self.assertEqual(d.record(cap,'UNKNOWN_FAILURE','UNKNOWN',65)['window_index'],65)
        for i in (66,105,-1,True):self.assertRaises(Refused,d.record,cap,'UNKNOWN_FAILURE','UNKNOWN',i)
        cap['catalogue']=b.CATALOGUE_HASH;self.assertEqual(d.record(cap,'UNKNOWN_FAILURE','UNKNOWN',105)['window_index'],105)


class Remaining(previous.Diagnostics):
    # All 25 existing diagnostic fault scenarios also execute under the 66 profile.
    def prepared(self,base=None,review_change=None):
        base=base or self.fixture(authorised=False)
        if not base.path('temporary_batches').exists():base.path('temporary_batches').mkdir()
        session=uuid.uuid4().hex
        review=previous.previous.review()
        review.update(catalogue_sha256=H,permitted_scope='PRIVATE_LOCAL_66_WINDOWS',source_seal=a.source_seal(),proposal_id=session)
        if review_change:review.update(review_change)
        root=prepare_session(base.root,session,a.source_seal(),synthetic=True,_bounded_rights=review,_bounded_catalogue=H)
        ar=Archive(root,synthetic=True);self.addCleanup(ar.close)
        return base,ar
    def new(self,base=None,limits=None):
        base,ar=self.prepared(base)
        cap=b.issue(ar,_fixture=True,fixture_limits=limits or dict(session=900,spacing=.001))
        return base,ar,cap
    def server(self,scenario='valid'):
        return LocalHTTPS(self.cert,self.key,scenario=scenario,secret=self.secret,catalogue=tuple(b.spec(i,H) for i in range(66)))
    def test_remaining_full_66_one_token_one_attempt(self):
        base,ar,cap=self.new();calls=[];original=SyntheticCredentialProvider.credential
        def credential(provider):calls.append(1);return original(provider)
        with self.server() as server,patch.object(SyntheticCredentialProvider,'credential',credential):
            result=self.run_bounded(ar,cap,server)
            self.assertEqual(result['kind'],'DONE',result);self.assertTrue(result['worker_exited'])
            self.assertEqual(len(server.requests),66);self.assertTrue(all(r['scope_valid'] and r['auth_matches'] for r in server.requests))
            self.assertEqual(calls,[1]);self.assertRaises(Refused,self.run_bounded,ar,cap,server)
            self.assertEqual(len(server.requests),66)
        state=b.ledger(ar,cap);self.assertEqual((state['state'],state['attempts'],state['next']),('SESSION_CONSUMED',66,66))
        self.assertEqual(cap['limits']['attempts'],66)
        for i in range(66):
            receipt=b.verify_completed(ar,cap,i)
            self.assertEqual((receipt['original_index'],receipt['original_window'],receipt['parent_catalogue']),(i+40,i+41,b.CATALOGUE_HASH))
            self.assertEqual(state['windows'][i]['http_attempts'],1)
            self.assertTrue(base.path(b.marker(i,H)).exists())
        self.assertFalse(ar.path('raw/v26c_year_039.json').exists())
        self.assertFalse(ar.path('raw/v26c_year_000.json').exists())
        self.assertFalse(ar.path('diagnostic.json').exists())
        self.assertRaises(Refused,b.claim_window,ar,cap,66,123)
        self.assertRaises(Refused,b.preflight,ar)
    def test_remaining_exact_confirmation_and_selector(self):
        _,ar=self.prepared();phrase=b.confirmation(ar)
        self.assertEqual(phrase,'CONFIRM 66 HISTORICAL EUR_USD GETS '+ar.session_id+' '+H+' '+a.source_seal())
        proposal=dict(version=1,session=ar.session_id,source=a.source_seal(),catalogue=H,authorises_execution=False)
        self.assertEqual(b.validate_selector(proposal),proposal)
        for key,value in (('source','0'*64),('catalogue','0'*64),('authorises_execution',True),('session','../old')):
            bad=dict(proposal);bad[key]=value;self.assertRaises(Refused,b.validate_selector,bad)
        self.assertFalse(ar.path('grant.json').exists());self.assertFalse(ar.path('journal.json').exists())
    def test_remaining_original_rights_not_reused(self):
        for change in (dict(catalogue_sha256=b.CATALOGUE_HASH),dict(permitted_scope='PRIVATE_LOCAL_106_WINDOWS'),dict(source_seal='0'*64),dict(proposal_id='0'*32),dict(scope_reviewed=False)):
            _,ar=self.prepared(review_change=change);self.assertRaises(Refused,b.issue,ar,_fixture=True)
            self.assertFalse(ar.path('grant.json').exists())
    def test_remaining_old_authority_substitution(self):
        base,ar,cap=self.new()
        for change in (dict(catalogue=b.CATALOGUE_HASH),dict(source='0'*64),dict(session='0'*32),dict(limits=dict(cap['limits'],attempts=106))):
            bad=copy.deepcopy(cap);bad.update(change);self.assertRaises(Refused,b.verify,bad)
        self.assertFalse(ar.path('worker.claimed.json').exists())
    def test_remaining_consumed_106_grant_cannot_switch_catalogues(self):
        base,unused=self.prepared()
        old=prepare_session(base.root,uuid.uuid4().hex,a.source_seal(),synthetic=True,_bounded_rights=previous.previous.review())
        with Archive(old,synthetic=True) as ar:
            cap=b.issue(ar,_fixture=True,fixture_limits=dict(session=900,spacing=.001))
            with LocalHTTPS(self.cert,self.key,secret=self.secret,catalogue=tuple(b.spec(i) for i in range(106))) as server:
                result=self.run_bounded(ar,cap,server,fault='crash_before_dispatch')
                self.assertNotEqual(result['kind'],'DONE');self.assertEqual(server.requests,[])
            self.assertEqual(b.ledger(ar,cap)['state'],'OUTCOME_UNKNOWN');self.assertRaises(Refused,b.verify,cap)
            bad=copy.deepcopy(cap);bad.update(catalogue=H,limits=dict(cap['limits'],attempts=66))
            self.assertRaisesRegex(Refused,'BOUNDED_CATALOGUE_SUBSTITUTED',b.verify,bad)
        self.assertFalse(unused.path('grant.json').exists());self.assertFalse(unused.path('journal.json').exists())
    def test_remaining_grant_catalogue_must_equal_prepared_request(self):
        _,ar,cap=self.new();bad=copy.deepcopy(cap)
        bad.update(catalogue=b.CATALOGUE_HASH,limits=dict(cap['limits'],attempts=106))
        self.assertRaisesRegex(Refused,'BOUNDED_CATALOGUE_SUBSTITUTED',b.verify,bad)
    def test_remaining_cross_namespace_copy_refused(self):
        base,ar,cap=self.new();_,sibling=self.prepared(base)
        sibling.put('grant.json',ar.read('grant.json'));sibling.put('journal.json',ar.read('journal.json'))
        bad=copy.deepcopy(cap);bad['root']=str(sibling.root);self.assertRaises(Refused,b.verify,bad)
    def test_remaining_106_journal_substitution(self):
        _,ar,cap=self.new();state=decode(ar.read('journal.json'))
        state['windows']+=copy.deepcopy(state['windows'][:40]);ar.put('journal.json',encoded(state),replace=True)
        self.assertRaises(Refused,b.ledger,ar,cap);self.assertRaises(Refused,b.verify,cap)
    def test_remaining_prior_40_markers_preserved(self):
        base,ar=self.prepared();saved={}
        for i in range(40):saved[b.marker(i)]=base.put(b.marker(i),encoded(dict(state='UNKNOWN' if i==39 else 'COMPLETED',original_index=i)))
        self.assertTrue(b.preflight(ar))
        for name,sha in saved.items():self.assertEqual(digest(base.read(name)),sha)
        self.assertFalse(ar.path('grant.json').exists())
    def test_remaining_original_spent_window_blocks(self):
        base,ar=self.prepared();base.put(b.marker(40),b'SYNTHETIC_SPENT')
        self.assertRaises(Refused,b.issue,ar,_fixture=True);self.assertFalse(ar.path('grant.json').exists())
    def test_remaining_original_pending_window_blocks(self):
        base,ar=self.prepared();base.put(b.marker(40)+'.pending',b'SYNTHETIC_PENDING')
        self.assertRaises(Refused,b.issue,ar,_fixture=True)
    def test_remaining_crash_blocks_new_namespace_same_catalogue(self):
        base,ar,cap,_=self.failure(fault='crash_before_dispatch',expected_requests=0)
        _,fresh=self.prepared(base);self.assertRaises(Refused,b.issue,fresh,_fixture=True)
        self.assertFalse(fresh.path('grant.json').exists());self.assertEqual(b.ledger(ar,cap)['state'],'OUTCOME_UNKNOWN')
    def test_remaining_pacing_enforced(self):
        _,ar,cap=self.new(limits=dict(session=900,spacing=1))
        original=b.claim_window
        def stop(ar,cap,index,pid):
            if index==2:raise Refused('SYNTHETIC_STOP')
            return original(ar,cap,index,pid)
        with self.server() as server,patch.object(b,'claim_window',stop):
            result=self.run_bounded(ar,cap,server);self.assertNotEqual(result['kind'],'DONE');self.assertEqual(len(server.requests),2)
            self.assertGreaterEqual(server.request_times[1]-server.request_times[0],1)
        self.assertRaises(Refused,b.verify,cap)
    def test_remaining_manifest_cannot_relabel_window_40(self):
        _,ar,cap=self.new();original=b.claim_window
        def stop(ar,cap,index,pid):
            if index==1:raise Refused('SYNTHETIC_STOP')
            return original(ar,cap,index,pid)
        with self.server() as server,patch.object(b,'claim_window',stop):
            self.run_bounded(ar,cap,server);self.assertEqual(len(server.requests),1)
        receipt=b.verify_completed(ar,cap,0);receipt['original_window']=40
        name='manifests/'+b.batch_name(0,H)+'.json';body=encoded(receipt)
        ar.put(name,body,replace=True);state=decode(ar.read('journal.json'))
        state['windows'][0]['manifest_sha256']=digest(body);ar.put('journal.json',encoded(state),replace=True)
        self.assertRaisesRegex(Refused,'COMPLETED_PROVENANCE_CORRUPTED',b.verify_completed,ar,cap,0)
        self.assertRaises(Refused,b.verify,cap)
    def test_remaining_token_timeout_no_request(self):
        _,ar,cap=self.new(limits=dict(token=1,session=900,spacing=.001))
        original=SyntheticCredentialProvider.credential
        def slow(provider):time.sleep(1.1);return original(provider)
        with self.server() as server,patch.object(SyntheticCredentialProvider,'credential',slow):
            result=self.run_bounded(ar,cap,server);self.assertEqual(result['kind'],'TOKEN_ENTRY_TIMEOUT');self.assertEqual(server.requests,[])
        self.assertFalse(ar.path('acquisition.json').exists());self.checked(ar,cap,'TOKEN_ENTRY_TIMEOUT','TOKEN')
    def test_remaining_slow_entry_new_acquisition_clock(self):
        _,ar,cap=self.new(limits=dict(token=3,session=900,spacing=.001))
        original=SyntheticCredentialProvider.credential;entered=[]
        def slow(provider):time.sleep(.35);entered.append(time.monotonic());return original(provider)
        with self.server('invalid_schema') as server,patch.object(SyntheticCredentialProvider,'credential',slow):
            self.run_bounded(ar,cap,server);self.assertEqual(len(server.requests),1)
        phase=decode(ar.read('acquisition.json'));self.assertGreaterEqual(phase['started'],entered[0]);self.assertEqual(phase['deadline']-phase['started'],900)
    def test_remaining_global_lock_shared_with_106(self):
        base,ar,cap=self.new();old=prepare_session(base.root,uuid.uuid4().hex,a.source_seal(),synthetic=True,_bounded_rights=previous.previous.review())
        with Archive(old,synthetic=True) as legacy,acquisition_lock(ar):
            self.assertRaises(Refused,b.issue,legacy,_fixture=True)
        self.assertEqual(b.ledger(ar,cap)['attempts'],0)
