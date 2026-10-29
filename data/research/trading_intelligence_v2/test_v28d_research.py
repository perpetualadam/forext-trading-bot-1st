"""Invented byte bundles; no real authority, credentials or filesystem archive."""
import copy,unittest
from . import partial_history as p
from .core import timestamp,ResearchRejected
from .history_fixtures import payload
from .oanda_history_manifest import encoded,decode,digest,validated
from .bounded_acquisition import spec,LIMITS,CATALOGUE


def fixture():
    rights=dict(provider='OANDA',provider_identity_url='https://www.oanda.com/',terms_url='https://www.oanda.com/terms/',terms_evidence='SYNTHETIC TEST ONLY',rights_reviewed=True,scope_reviewed=True,permitted_use='offline_research_and_derived_results',permitted_scope='PRIVATE_LOCAL_106_WINDOWS',public_distribution_allowed=False,catalogue_sha256=p.CATALOGUE,source_seal=p.SOURCE,proposal_id=p.SESSION)
    rb=encoded(rights);identity={'invented':p.SESSION};request=encoded(dict(kind='BOUNDED_106',session=p.SESSION,source=p.SOURCE,catalogue=p.CATALOGUE,limits=LIMITS,identity=identity,rights=digest(rb),authorises_execution=False))
    grant=encoded(dict(version=4,mode='LIVE',synthetic_not_executable=True,session=p.SESSION,source=p.SOURCE,catalogue=p.CATALOGUE,identity=digest(encoded(identity)),rights=digest(rb),limits=LIMITS))
    windows=[];bundles=[]
    for i in range(106):
        s=spec(i);state='COMPLETED' if i<39 else 'UNKNOWN' if i==39 else 'NEVER';w=dict(index=i,spec=digest(encoded(s)),state=state,http_attempts=1 if i<40 else 0)
        if i<39:
            start=timestamp(s['params']['from']);end=timestamp(s['params']['to'])+1;raw=encoded(payload(start=start,count=1));rows,validation=validated(raw,'EUR_USD',start,end,1800000000);derivative=encoded(rows)
            manifest=encoded(dict(index=i,session=p.SESSION,source=p.SOURCE,catalogue=p.CATALOGUE,spec_sha256=w['spec'],identity=digest(encoded(identity)),request_sha256=digest(request),synthetic=False,instrument='EUR_USD',granularity='M5',start=start,end=end,retrieved=1800000000,raw='raw/v26c_year_'+str(i).zfill(3)+'.json',validated='validated/v26c_year_'+str(i).zfill(3)+'.json',raw_sha256=digest(raw),validated_sha256=digest(derivative),validation=validation,observed_complete_count=1))
            w['manifest_sha256']=digest(manifest);review=dict(rights,provenance_verified=True,previously_examined=True,manifest_sha256=digest(manifest));bundles.append(dict(manifest=manifest,raw=raw,validated=derivative,review=review))
        windows.append(w)
    journal=encoded(dict(session=p.SESSION,source=p.SOURCE,catalogue=p.CATALOGUE,state='OUTCOME_UNKNOWN',attempts=40,next=39,windows=windows))
    result=encoded(dict(session=p.SESSION,source=p.SOURCE,catalogue=p.CATALOGUE,kind='OUTCOME_UNKNOWN',attempts=40,completed=39,worker_exited=True,grant_sha256=digest(grant)))
    return [request,grant,journal,result,rb,tuple(bundles)]


class PartialTests(unittest.TestCase):
    def setUp(self):self.args=fixture()
    def merge(self):return p.merge_partial(*self.args)
    def test_all_39_identities_and_count(self):
        r=self.merge();self.assertEqual(r['count'],39);self.assertEqual([x['index'] for x in r['source_batches']],list(range(39)));self.assertEqual(r['source_acquisition_status'],'PARTIAL_OUTCOME_UNKNOWN')
    def test_gap_and_ambiguous_window_preserved(self):
        r=self.merge();self.assertTrue(r['missing_intervals']);self.assertEqual(r['missing_window_40']['state'],'OUTCOME_UNKNOWN');self.assertFalse(r['missing_window_40']['retry_allowed'])
    def test_independence_not_claimed(self):
        r=self.merge();self.assertFalse(r['strategy_evaluation_permitted']);self.assertFalse(r['authorises_execution']);self.assertIn('UNVERIFIED',r['independence'])
    def test_exact_prefix_required(self):self.args[-1]=self.args[-1][:-1];self.assertRaises(ResearchRejected,self.merge)
    def test_wrong_session(self):v=decode(self.args[0]);v['session']='0'*32;self.args[0]=encoded(v);self.assertRaises(ResearchRejected,self.merge)
    def test_wrong_source(self):v=decode(self.args[0]);v['source']='0'*64;self.args[0]=encoded(v);self.assertRaises(ResearchRejected,self.merge)
    def test_consumed_not_reclassified_done(self):v=decode(self.args[2]);v['state']='SESSION_CONSUMED';self.args[2]=encoded(v);self.assertRaises(ResearchRejected,self.merge)
    def test_ambiguous_not_reclassified_failed(self):v=decode(self.args[2]);v['windows'][39]['state']='FAILED';self.args[2]=encoded(v);self.assertRaises(ResearchRejected,self.merge)
    def test_no_second_attempt(self):v=decode(self.args[2]);v['windows'][3]['http_attempts']=2;self.args[2]=encoded(v);self.assertRaises(ResearchRejected,self.merge)
    def test_foreign_manifest(self):b=list(self.args[-1]);b[0]=b[1];self.args[-1]=tuple(b);self.assertRaises(ResearchRejected,self.merge)
    def test_raw_corruption(self):b=list(self.args[-1]);b[0]=dict(b[0],raw=b'{}');self.args[-1]=tuple(b);self.assertRaises(ResearchRejected,self.merge)
    def test_derivative_corruption(self):b=list(self.args[-1]);b[0]=dict(b[0],validated=b'[]');self.args[-1]=tuple(b);self.assertRaises(ResearchRejected,self.merge)
    def test_rights_cannot_be_removed(self):b=list(self.args[-1]);b[0]=dict(b[0],review=dict(b[0]['review'],rights_reviewed=False));self.args[-1]=tuple(b);self.assertRaises(ResearchRejected,self.merge)
    def test_rights_manifest_binding(self):b=list(self.args[-1]);b[0]=dict(b[0],review=dict(b[0]['review'],manifest_sha256='0'*64));self.args[-1]=tuple(b);self.assertRaises(ResearchRejected,self.merge)
    def test_worker_exit_required(self):v=decode(self.args[3]);v['worker_exited']=False;self.args[3]=encoded(v);self.assertRaises(ResearchRejected,self.merge)
    def test_remaining_exact_66(self):
        r=p.remaining_catalogue(CATALOGUE.read_bytes(),self.args[2]);self.assertEqual([w['original_window'] for w in r['windows']],list(range(41,107)));self.assertEqual(r['request_count'],66);self.assertFalse(r['authorises_execution']);self.assertFalse(r['activation_supported']);self.assertTrue(r['stop_on_failure']);self.assertFalse(r['automatic_resume']);self.assertFalse(r['overwriting_existing_artifacts'])
    def test_remaining_specs_exact(self):
        r=p.remaining_catalogue(CATALOGUE.read_bytes(),self.args[2]);self.assertTrue(all(encoded(w['specification'])==encoded(spec(w['original_index'])) for w in r['windows']))
    def test_remaining_no_attempted_overlap(self):
        r=p.remaining_catalogue(CATALOGUE.read_bytes(),self.args[2]);self.assertEqual(r['start'],'2025-01-17T21:20:00Z');self.assertEqual(r['window_40']['state'],'OUTCOME_UNKNOWN');self.assertFalse(r['window_40']['retry_allowed'])
    def test_remaining_tamper_refused(self):self.assertRaises(ResearchRejected,p.remaining_catalogue,b'{}',self.args[2])
    def test_remaining_attempted_entry_refused(self):v=decode(self.args[2]);v['windows'][40]['state']='RESERVED';self.assertRaises(ResearchRejected,p.remaining_catalogue,CATALOGUE.read_bytes(),encoded(v))
    def test_deterministic(self):self.assertEqual(encoded(self.merge()),encoded(self.merge()))
