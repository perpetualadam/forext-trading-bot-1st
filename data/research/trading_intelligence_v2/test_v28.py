"""Synthetic offline V2.8 provenance and integrity regressions."""
import unittest
from .core import ResearchRejected,iso
from .core import timestamp
T=timestamp('2024-01-01T00:00:00Z')
def payload(count):
    return dict(instrument='EUR_USD',granularity='M5',candles=[dict(time=iso(T+i*300),complete=True,volume=1,**{name:dict(o=value,h=value,l=value,c=value) for name,value in [('mid','1.10000'),('bid','1.09990'),('ask','1.10010')]}) for i in range(count)])
from .oanda_history_manifest import encoded,digest,validated
from .oanda_research_import import import_bundle,CONNECTIVITY_SESSION


def fixture():
    raw=encoded(payload(count=10));rows,report=validated(raw,'EUR_USD',T,T+3000,T+86400)
    derivative=encoded(rows)
    request=dict(session='a'*32,identity={'synthetic_fixture_identity':1},spec=dict(method='GET',host='api-fxtrade.oanda.com',path='/v3/instruments/EUR_USD/candles',params=dict(price='MBA',granularity='M5',smooth='false',includeFirst='true',**{'from':iso(T),'to':iso(T+2999)})))
    manifest=dict(identity=digest(encoded(request['identity'])),session=request['session'],instrument='EUR_USD',granularity='M5',synthetic=False,request_sha256=digest(encoded(request)),raw_sha256=digest(raw),validated_sha256=digest(derivative),start=T,end=T+3000,retrieved=T+86400,observed_complete_count=10,validation=report)
    review=dict(provider='OANDA',provider_identity_url='https://www.oanda.com/',terms_url='https://www.oanda.com/terms/',terms_evidence='SYNTHETIC TEST REVIEW ONLY',rights_reviewed=True,permitted_use='offline_research_and_derived_results',provenance_verified=True,research_history_complete=True,controlled_first_access=True,independence_evidence='SYNTHETIC ONLY')
    return request,manifest,raw,derivative,review


class ImportTests(unittest.TestCase):
    def setUp(self):self.r,self.m,self.raw,self.derivative,self.review=fixture()
    def run_import(self,independent=True):
        self.m['request_sha256']=digest(encoded(self.r))
        mb=encoded(self.m);self.review['manifest_sha256']=digest(mb)
        return import_bundle(encoded(self.r),mb,self.raw,self.derivative,review=self.review,independent_required=independent)
    def test_valid_historical_not_stale(self):
        result=self.run_import();self.assertEqual(len(result['records']),10)
        self.assertEqual(result['independence'],'INDEPENDENT_UNTOUCHED')
        self.assertFalse(result['strategy_evaluation_permitted'])
    def test_deterministic(self):self.assertEqual(self.run_import(),self.run_import())
    def test_raw_tamper(self):
        self.raw+=b' ';self.assertRaises(ResearchRejected,self.run_import)
    def test_derivative_tamper(self):
        self.derivative+=b' ';self.assertRaises(ResearchRejected,self.run_import)
    def test_rights_missing(self):
        self.review['rights_reviewed']=False;self.assertRaises(ResearchRejected,self.run_import)
    def test_synthetic_provenance(self):
        self.m['synthetic']=True;self.assertRaises(ResearchRejected,self.run_import)
    def test_foreign_endpoint(self):
        self.r['spec']['path']='/v3/accounts/x/orders';self.assertRaises(ResearchRejected,self.run_import)
    def test_wrong_host(self):
        self.r['spec']['host']='example.com';self.assertRaises(ResearchRejected,self.run_import)
    def test_count_parameter(self):
        self.r['spec']['params']['count']='10';self.assertRaises(ResearchRejected,self.run_import)
    def test_session_substitution(self):
        self.m['session']='b'*32;self.assertRaises(ResearchRejected,self.run_import)
    def test_range_substitution(self):
        self.m['start']-=300;self.assertRaises(ResearchRejected,self.run_import)
    def test_receipt_report_tamper(self):
        self.m['validation']['candles']=11;self.assertRaises(ResearchRejected,self.run_import)
    def test_connectivity_never_independent(self):
        self.r['session']=CONNECTIVITY_SESSION;self.m['session']=CONNECTIVITY_SESSION
        self.assertRaises(ResearchRejected,self.run_import)
        self.assertEqual(self.run_import(False)['independence'],'PREVIOUSLY_EXAMINED_CONNECTIVITY_ONLY')
    def test_overlap_never_holdout(self):
        self.review['previously_examined']=True;self.assertRaises(ResearchRejected,self.run_import)
    def test_incomplete_rejected_by_derivative(self):
        from .oanda_history_manifest import decode
        obj=decode(self.raw);obj['candles'][-1]['complete']=False
        self.raw=encoded(obj);self.m['raw_sha256']=digest(self.raw)
        self.assertRaises(ResearchRejected,self.run_import)
    def test_crossed_bid_ask(self):
        from .oanda_history_manifest import decode
        obj=decode(self.raw);obj['candles'][0]['bid']['o']='2.00000'
        self.raw=encoded(obj);self.m['raw_sha256']=digest(self.raw)
        self.assertRaises(ResearchRejected,self.run_import)
    def test_out_of_order(self):
        from .oanda_history_manifest import decode
        obj=decode(self.raw);obj['candles'].reverse();self.raw=encoded(obj);self.m['raw_sha256']=digest(self.raw)
        self.assertRaises(ResearchRejected,self.run_import)
    def test_review_hash_required(self):
        self.assertRaises(ResearchRejected,import_bundle,encoded(self.r),encoded(self.m),self.raw,self.derivative,review=self.review)

    def test_no_network_import(self):
        self.assertRaises(PermissionError,__import__,'socket')
    def test_no_operational_import(self):
        self.assertRaises(PermissionError,__import__,'forex_bot')
    def test_no_credential_read(self):
        self.assertRaises(PermissionError,(TEMP/'.env').read_bytes)
    def test_no_archive_write(self):
        self.assertRaises(PermissionError,(ROOT/'forbidden-v28-write.txt').write_text,'blocked')

    def test_identity_substitution(self):
        self.m['identity']='0'*64;self.assertRaises(ResearchRejected,self.run_import)
    def test_unverified_provenance(self):
        self.review['provenance_verified']=False;self.assertRaises(ResearchRejected,self.run_import)
