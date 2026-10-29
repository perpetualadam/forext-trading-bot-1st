"""Invented pilot candles and durable records; never market or LIVE authority."""
import unittest
from dataclasses import FrozenInstanceError
from .core import ResearchRejected,iso
from .oanda_history_manifest import encoded,digest,validated,decode
from .pilot_history import plan,merge_completed,START,END,IDS
SOURCE='a'*64

def bundle(window,missing=()):
    identity={'fixture_identity':window.session}
    request=dict(session=window.session,source=SOURCE,identity=identity,spec=window.spec)
    candles=[dict(time=iso(t),complete=True,volume=1,**{n:dict(o=p,h=p,l=p,c=p) for n,p in [('mid','1.10000'),('bid','1.09990'),('ask','1.10010')]}) for t in range(window.start,window.end,300) if t not in missing]
    raw=encoded(dict(instrument='EUR_USD',granularity='M5',candles=candles))
    rows,report=validated(raw,'EUR_USD',window.start,window.end,END+86400)
    derivative=encoded(rows)
    manifest=encoded(dict(identity=digest(encoded(identity)),session=window.session,instrument='EUR_USD',granularity='M5',synthetic=False,request_sha256=digest(encoded(request)),raw_sha256=digest(raw),validated_sha256=digest(derivative),start=window.start,end=window.end,retrieved=END+86400,observed_complete_count=len(rows),validation=report))
    grant=encoded(dict(session=window.session,source=SOURCE,spec=digest(encoded(window.spec))))
    review=dict(provider='OANDA',provider_identity_url='https://www.oanda.com/',terms_url='https://www.oanda.com/terms/',terms_evidence='SYNTHETIC FIXTURE ONLY',rights_reviewed=True,permitted_use='offline_research_and_derived_results',provenance_verified=True,manifest_sha256=digest(manifest))
    return dict(request=encoded(request),manifest=manifest,raw=raw,validated=derivative,claimed_grant=grant,journal=encoded(dict(session=window.session,state='SESSION_CONSUMED',attempts=1)),result=encoded(dict(session=window.session,source=SOURCE,kind='DONE',worker_exited=True,journal_state='SESSION_CONSUMED',attempts=1,grant_sha256=digest(grant))),review=review)

class PilotTests(unittest.TestCase):
    def setUp(self):self.windows=plan(SOURCE)
    def batches(self):return tuple(bundle(w) for w in self.windows)
    def mutate(self,field,key,value):
        b=list(self.batches());record=decode(b[0][field]);record[key]=value;b[0][field]=encoded(record);return tuple(b)
    def test_exact_calendar_slots(self):self.assertEqual([w.maximum_candles for w in self.windows],[1000,1000,16])
    def test_half_open_boundaries(self):
        self.assertEqual(self.windows[0].start,START);self.assertEqual(self.windows[-1].end,END)
        for a,b in zip(self.windows,self.windows[1:]):self.assertEqual(a.end,b.start)
    def test_exact_first_request(self):
        self.assertEqual(self.windows[0].spec['params']['to'],'2024-08-08T11:19:59+00:00')
    def test_frozen_window(self):self.assertRaises(FrozenInstanceError,setattr,self.windows[0],'end',END)
    def test_spec_copy_not_shared(self):
        s=self.windows[0].spec;s['params']['price']='M';self.assertEqual(self.windows[0].spec['params']['price'],'MBA')
    def test_unique_sessions(self):self.assertEqual(len(set(w.session for w in self.windows)),3)
    def test_duplicate_identity_refused(self):self.assertRaises(ResearchRejected,plan,SOURCE,(IDS[0],)*3)
    def test_bad_source_refused(self):self.assertRaises(ResearchRejected,plan,'bad')
    def test_all_three_required(self):self.assertRaises(ResearchRejected,merge_completed,SOURCE,self.batches()[:1])
    def test_merge_full_synthetic_grid(self):
        r=merge_completed(SOURCE,self.batches());self.assertEqual(r['count'],2016);self.assertEqual(r['missing_intervals'],[])
        self.assertFalse(r['strategy_evaluation_permitted']);self.assertFalse(r['authorises_execution'])
    def test_unknown_outcome_stops(self):self.assertRaises(ResearchRejected,merge_completed,SOURCE,self.mutate('result','kind','OUTCOME_UNKNOWN'))
    def test_timeout_stops(self):self.assertRaises(ResearchRejected,merge_completed,SOURCE,self.mutate('result','kind','TOKEN_ENTRY_TIMEOUT'))
    def test_crash_not_completed(self):self.assertRaises(ResearchRejected,merge_completed,SOURCE,self.mutate('result','worker_exited',False))
    def test_unconsumed_refused(self):self.assertRaises(ResearchRejected,merge_completed,SOURCE,self.mutate('journal','state','REQUEST_ATTEMPTED'))
    def test_second_attempt_refused(self):self.assertRaises(ResearchRejected,merge_completed,SOURCE,self.mutate('journal','attempts',2))
    def test_shared_claimed_grant_refused(self):
        b=list(self.batches());b[1]['claimed_grant']=b[0]['claimed_grant'];self.assertRaises(ResearchRejected,merge_completed,SOURCE,tuple(b))
    def test_session_substitution(self):self.assertRaises(ResearchRejected,merge_completed,SOURCE,self.mutate('request','session',IDS[1]))
    def test_broker_write_refused(self):
        b=list(self.batches());r=decode(b[0]['request']);r['spec']['method']='POST';b[0]['request']=encoded(r)
        self.assertRaises(ResearchRejected,merge_completed,SOURCE,tuple(b))
    def test_duplicate_batch_refused(self):
        b=self.batches();self.assertRaises(ResearchRejected,merge_completed,SOURCE,(b[0],b[0],b[2]))
    def test_reordered_batches_refused(self):self.assertRaises(ResearchRejected,merge_completed,SOURCE,tuple(reversed(self.batches())))
    def test_cross_boundary_gap_preserved(self):
        a,b,c=self.windows;missing=(a.end-300,b.start)
        r=merge_completed(SOURCE,tuple(bundle(w,missing) for w in self.windows))
        self.assertEqual(r['count'],2014);self.assertEqual(r['missing_intervals'][0]['missing_candles'],2)
    def test_edge_gap_preserved(self):
        r=merge_completed(SOURCE,tuple(bundle(w,(START,END-300)) for w in self.windows))
        self.assertEqual(sum(g['missing_candles'] for g in r['missing_intervals']),2)
    def test_tampered_raw_refused(self):
        b=list(self.batches());b[0]['raw']+=b' ';self.assertRaises(ResearchRejected,merge_completed,SOURCE,tuple(b))
    def test_deterministic_no_progression(self):
        b=self.batches();before=repr(b);self.assertEqual(merge_completed(SOURCE,b),merge_completed(SOURCE,b));self.assertEqual(repr(b),before)
