"""Read-only adapter for the verified completed prefix of the consumed V2.8C run."""
from .core import ResearchRejected,timestamp,iso
from .oanda_history_manifest import decode,encoded,digest
from .oanda_research_import import import_bundle
from .pilot_history import Window,merge_imported_batches

SESSION='6fc23c0be49741a3a066ccc948d1b5fa'
SOURCE='9a8b0960f0beefe7fb7fbd116cfa320bdfe6b18a2414c936b370a8c3c58445f2'
CATALOGUE='2d5f5b38efb65a0cffd5f63ad38a7da62344d653bdba84dad9438cf1eac96bf9'


def verify_parent(request,grant,journal,result,rights):
    req,g,j,res,r=(decode(x) for x in (request,grant,journal,result,rights))
    if (req.get('session')!=SESSION or req.get('source')!=SOURCE or req.get('catalogue')!=CATALOGUE or
        req.get('kind')!='BOUNDED_106' or req.get('authorises_execution') is not False or
        req.get('rights')!=digest(rights) or g.get('mode')!='LIVE' or g.get('version')!=4 or
        g.get('session')!=SESSION or g.get('source')!=SOURCE or g.get('catalogue')!=CATALOGUE or
        g.get('identity')!=digest(encoded(req.get('identity'))) or g.get('rights')!=digest(rights) or
        j.get('session')!=SESSION or j.get('source')!=SOURCE or j.get('catalogue')!=CATALOGUE or
        j.get('state')!='OUTCOME_UNKNOWN' or j.get('attempts')!=40 or j.get('next')!=39 or
        res.get('session')!=SESSION or res.get('source')!=SOURCE or res.get('catalogue')!=CATALOGUE or
        res.get('kind')!='OUTCOME_UNKNOWN' or res.get('attempts')!=40 or res.get('completed')!=39 or
        res.get('worker_exited') is not True or res.get('grant_sha256')!=digest(grant) or
        r.get('catalogue_sha256')!=CATALOGUE or r.get('source_seal')!=SOURCE or r.get('proposal_id')!=SESSION or
        r.get('scope_reviewed') is not True or r.get('public_distribution_allowed') is not False):
        raise ResearchRejected('partial_parent_binding_refused')
    from .bounded_acquisition import spec,LIMITS
    if req.get('limits')!=LIMITS or g.get('limits')!=LIMITS or len(j.get('windows',[]))!=106:
        raise ResearchRejected('partial_parent_budget_refused')
    for i,w in enumerate(j['windows']):
        state='COMPLETED' if i<39 else 'UNKNOWN' if i==39 else 'NEVER'
        if (type(w.get('index')) is not int or w['index']!=i or w.get('spec')!=digest(encoded(spec(i))) or
            w.get('state')!=state or type(w.get('http_attempts')) is not int or w['http_attempts']!=(1 if i<40 else 0)):
            raise ResearchRejected('partial_window_accounting_refused')
    return req,j,r


def merge_partial(request,grant,journal,result,rights,bundles):
    """No invented DONE/grants, no changed rights gate, no incomplete window import."""
    req,j,r=verify_parent(request,grant,journal,result,rights)
    if type(bundles) is not tuple or len(bundles)!=39:raise ResearchRejected('exact_completed_prefix_required')
    from .bounded_acquisition import spec
    windows=[];imports=[];identities=[]
    for i,bundle in enumerate(bundles):
        if set(bundle)!={'manifest','raw','validated','review'}:raise ResearchRejected('partial_bundle_shape_refused')
        manifest=decode(bundle['manifest']);w=j['windows'][i];s=spec(i)
        if (manifest.get('index')!=i or manifest.get('source')!=SOURCE or manifest.get('catalogue')!=CATALOGUE or
            digest(bundle['manifest'])!=w.get('manifest_sha256') or
            manifest.get('raw')!='raw/v26c_year_'+str(i).zfill(3)+'.json' or
            manifest.get('validated')!='validated/v26c_year_'+str(i).zfill(3)+'.json'):
            raise ResearchRejected('partial_completed_manifest_binding_refused')
        review=bundle['review']
        if any(review.get(k)!=r.get(k) for k in r) or review.get('previously_examined') is not True:
            raise ResearchRejected('partial_original_rights_required')
        imported=import_bundle(request,bundle['manifest'],bundle['raw'],bundle['validated'],review=review,independent_required=False)
        if imported['validation']['incomplete'] or imported['validation']['validation_failures']:
            raise ResearchRejected('partial_incomplete_batch_refused')
        windows.append(Window(SESSION,timestamp(s['params']['from']),timestamp(s['params']['to'])+1,SOURCE));imports.append(imported)
        identities.append(dict(session=SESSION,index=i,window_number=i+1,specification=s,spec_sha256=w['spec'],manifest_sha256=digest(bundle['manifest']),raw_sha256=manifest['raw_sha256'],validated_sha256=manifest['validated_sha256'],candles=len(imported['records'])))
    merged=merge_imported_batches(tuple(windows),tuple(imports),start=windows[0].start,end=windows[-1].end,classification='PREVIOUSLY_EXAMINED_INDEPENDENCE_UNVERIFIED')
    merged.update(source_acquisition_status='PARTIAL_OUTCOME_UNKNOWN',source_session=SESSION,source_seal=SOURCE,catalogue_sha256=CATALOGUE,source_batches=identities,source_evidence_sha256={k:digest(v) for k,v in dict(request=request,claimed_grant=grant,journal=journal,result=result,rights=rights).items()},scope_start=iso(windows[0].start),scope_end_exclusive=iso(windows[-1].end),missing_window_40=dict(start=spec(39)['params']['from'],end_exclusive=iso(timestamp(spec(39)['params']['to'])+1),state='OUTCOME_UNKNOWN',dispatch='UNKNOWN',retry_allowed=False),unattempted_remainder=dict(first_window=41,last_window=106,start=spec(40)['params']['from'],end_exclusive='2025-09-01T00:00:00+00:00'),rights_evidence=r,verified_market_closures=[],gap_classification='UNVERIFIED_MARKET_CLOSURE_OR_MISSING; NO HOLIDAY/WEEKEND REPAIR')
    return merged


def remaining_catalogue(original_bytes,journal_bytes):
    if digest(original_bytes.replace(b'\r\n',b'\n'))!=CATALOGUE:raise ResearchRejected('original_catalogue_changed')
    parent=decode(original_bytes);j=decode(journal_bytes)
    if j.get('session')!=SESSION or j.get('catalogue')!=CATALOGUE or j.get('state')!='OUTCOME_UNKNOWN' or j.get('attempts')!=40 or j.get('next')!=39:
        raise ResearchRejected('remaining_parent_state_refused')
    windows=parent['windows'];records=[]
    for i in range(106):
        w=j['windows'][i];expected='COMPLETED' if i<39 else 'UNKNOWN' if i==39 else 'NEVER'
        if w.get('index')!=i or w.get('state')!=expected or w.get('spec')!=digest(encoded(windows[i]['specification'])) or w.get('http_attempts')!=(1 if i<40 else 0):
            raise ResearchRejected('remaining_attempt_state_refused')
        if i>=40:records.append(dict(original_window=i+1,original_index=i,specification=windows[i]['specification'],spec_sha256=w['spec'],maximum_candles=windows[i]['maximum_candles']))
    if len(records)!=66 or sum(x['maximum_candles'] for x in records)!=65120:raise ResearchRejected('remaining_scope_refused')
    return dict(version='V28D_REMAINING_OFFLINE_CATALOGUE_1',parent_session=SESSION,parent_catalogue_sha256=CATALOGUE,parent_source_seal=SOURCE,parent_journal_sha256=digest(journal_bytes),parent_status='PARTIAL_OUTCOME_UNKNOWN',start='2025-01-17T21:20:00Z',end_exclusive='2025-09-01T00:00:00Z',request_count=66,maximum_future_attempts_after_separate_approval=66,currently_authorised_attempts=0,authorises_execution=False,activation_supported=False,requires_new_source_bound_approval=True,archive_destination_policy='NEW_SEPARATELY_APPROVED_PROTECTED_NAMESPACE_ONLY',archive_root=r'C:\TradingResearchData\OANDA',limits=dict(startup=15,token=120,request=15,session=1800,spacing=1,bytes=268435456,attempts=66),retries=0,redirects=False,proxies=False,pagination=False,fallback=False,stop_on_failure=True,automatic_resume=False,overwriting_existing_artifacts=False,window_40=dict(state='OUTCOME_UNKNOWN',start=windows[39]['specification']['params']['from'],end_inclusive=windows[39]['specification']['params']['to'],retry_allowed=False),windows=records,windows_sha256=digest(encoded(records)))
