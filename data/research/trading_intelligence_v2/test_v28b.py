"""Invented yearly-plan records. Never LIVE authority or market evidence."""
import unittest
from .core import iso,ResearchRejected
from .year_history import plan,request_plan,merge_completed_year,independence,START,END
from .oanda_history_manifest import encoded,decode,digest,validated
from .request_profile import specification
SOURCE='a'*64

def fixture(w):
    identity={'synthetic_identity':w.session}
    req=encoded(dict(session=w.session,source=SOURCE,identity=identity,spec=w.spec))
    raw=encoded(dict(instrument='EUR_USD',granularity='M5',candles=[dict(time=iso(w.start),complete=True,volume=1,**{n:dict(o=p,h=p,l=p,c=p) for n,p in [('mid','1.10000'),('bid','1.09990'),('ask','1.10010')]})]))
    rows,report=validated(raw,'EUR_USD',w.start,w.end,END+86400);derivative=encoded(rows)
    manifest=encoded(dict(identity=digest(encoded(identity)),session=w.session,instrument='EUR_USD',granularity='M5',synthetic=False,request_sha256=digest(req),raw_sha256=digest(raw),validated_sha256=digest(derivative),start=w.start,end=w.end,retrieved=END+86400,observed_complete_count=1,validation=report))
    grant=encoded(dict(session=w.session,source=SOURCE,spec=digest(encoded(w.spec)),synthetic_not_executable=True))
    review=dict(provider='OANDA',provider_identity_url='https://www.oanda.com/',terms_url='https://www.oanda.com/terms/',terms_evidence='SYNTHETIC TEST ONLY',rights_reviewed=True,permitted_use='offline_research_and_derived_results',provenance_verified=True,manifest_sha256=digest(manifest),previously_examined=True)
    return dict(request=req,manifest=manifest,raw=raw,validated=derivative,claimed_grant=grant,review=review,journal=encoded(dict(session=w.session,state='SESSION_CONSUMED',attempts=1)),result=encoded(dict(session=w.session,source=SOURCE,kind='DONE',worker_exited=True,journal_state='SESSION_CONSUMED',attempts=1,grant_sha256=digest(grant))))

class YearTests(unittest.TestCase):
    def setUp(self):self.windows=plan(SOURCE)
    def bundles(self):return tuple(fixture(w) for w in self.windows)
    def mutate(self,name,key,value):
        b=list(self.bundles());x=decode(b[0][name]);x[key]=value;b[0][name]=encoded(x);return tuple(b)
    def test_exact_count(self):self.assertEqual(len(self.windows),106)
    def test_exact_calendar_slots(self):self.assertEqual(sum(w.maximum_candles for w in self.windows),105120)
    def test_first_boundary(self):self.assertEqual(self.windows[0].spec['params']['to'],'2024-09-04T11:19:59+00:00')
    def test_last_boundary(self):
        self.assertEqual(self.windows[-1].spec['params']['from'],'2025-08-31T14:00:00+00:00')
        self.assertEqual(self.windows[-1].spec['params']['to'],'2025-08-31T23:59:59+00:00')
    def test_maximum_slots(self):self.assertEqual([w.maximum_candles for w in self.windows],[1000]*105+[120])
    def test_no_calendar_gaps_overlaps(self):
        self.assertEqual(self.windows[0].start,START);self.assertEqual(self.windows[-1].end,END)
        self.assertTrue(all(a.end==b.start for a,b in zip(self.windows,self.windows[1:])))
    def test_unique_deterministic_ids(self):self.assertEqual(plan(SOURCE),self.windows);self.assertEqual(len(set(w.session for w in self.windows)),106)
    def test_different_seal_different_proposals(self):self.assertNotEqual(plan('b'*64)[0].session,self.windows[0].session)
    def test_bad_seal(self):self.assertRaises(ResearchRejected,plan,'bad')
    def test_plan_non_authorising(self):
        p=request_plan(SOURCE);self.assertFalse(p['authorises_execution']);self.assertFalse(p['live_scope_supported']);self.assertEqual(p['currently_authorised_attempts'],0)
        self.assertEqual(p['maximum_future_attempts_after_separate_approval'],106)
    def test_predecessor_chain(self):
        p=request_plan(SOURCE)['windows'];self.assertIsNone(p[0]['predecessor'])
        self.assertTrue(all(b['predecessor']==a['request_id'] for a,b in zip(p,p[1:])))
    def test_no_live_scope_catalogue_entry(self):self.assertTrue(all(self.windows[0].spec!=specification(i) for i in (None,0,1,2)))
    def test_unknown_history_not_holdout(self):self.assertEqual(independence({}),'PROVENANCE_UNVERIFIED')
    def test_prior_examined_stays_examined(self):self.assertEqual(independence(dict(previously_examined=True)),'PREVIOUSLY_EXAMINED')
    def test_rights_alone_not_independent(self):self.assertEqual(independence(dict(rights_reviewed=True)),'PROVENANCE_UNVERIFIED')
    def test_all_complete_synthetic_merges_without_evaluation(self):
        r=merge_completed_year(SOURCE,self.bundles());self.assertEqual(r['count'],106);self.assertEqual(r['expected_calendar_slots'],105120)
        self.assertFalse(r['strategy_evaluation_permitted']);self.assertFalse(r['authorises_execution']);self.assertTrue(r['missing_intervals'])
    def test_no_partial_or_auto_progression(self):self.assertRaises(ResearchRejected,merge_completed_year,SOURCE,self.bundles()[:1])
    def test_unknown_outcome_stops(self):self.assertRaises(ResearchRejected,merge_completed_year,SOURCE,self.mutate('result','kind','OUTCOME_UNKNOWN'))
    def test_crash_stops(self):self.assertRaises(ResearchRejected,merge_completed_year,SOURCE,self.mutate('result','worker_exited',False))
    def test_second_attempt_stops(self):self.assertRaises(ResearchRejected,merge_completed_year,SOURCE,self.mutate('journal','attempts',2))
    def test_corrupt_hash_stops(self):
        b=list(self.bundles());b[0]['raw']+=b' ';self.assertRaises(ResearchRejected,merge_completed_year,SOURCE,tuple(b))
    def test_pilot_review_not_valid_for_year_manifest(self):
        b=list(self.bundles());b[0]['review']['manifest_sha256']='28c94fed27e0a4c9c9a6770e5aaea1aec2edef6dd3a8d2ae808219a2401a0244'
        self.assertRaises(ResearchRejected,merge_completed_year,SOURCE,tuple(b))
    def test_rights_gate_unchanged(self):
        b=list(self.bundles());b[0]['review']['rights_reviewed']=False;self.assertRaises(ResearchRejected,merge_completed_year,SOURCE,tuple(b))
    def test_duplicate_session_and_out_of_order_refused(self):
        b=self.bundles();self.assertRaises(ResearchRejected,merge_completed_year,SOURCE,(b[0],b[0],*b[2:]));self.assertRaises(ResearchRejected,merge_completed_year,SOURCE,tuple(reversed(b)))
    def test_deterministic_merge(self):
        b=self.bundles();self.assertEqual(merge_completed_year(SOURCE,b),merge_completed_year(SOURCE,b))
    def test_write_endpoint_refused(self):
        b=list(self.bundles());r=decode(b[0]['request']);r['spec']['path']='/v3/accounts/x/orders';b[0]['request']=encoded(r)
        self.assertRaises(ResearchRejected,merge_completed_year,SOURCE,tuple(b))
    def test_no_network(self):
        with self.assertRaises(PermissionError):
            import socket
            socket.socket()
    def test_no_operational_import(self):self.assertRaises(PermissionError,__import__,'forex_bot')
    def test_no_credential_read(self):self.assertRaises(PermissionError,(TEMP/'.env').read_bytes)
    def test_no_operational_write(self):self.assertRaises(PermissionError,(ROOT/'forbidden-v28b-write.txt').write_text,'blocked')
