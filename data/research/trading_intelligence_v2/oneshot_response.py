"""The existing candle validator bound to explicit external archive publication."""
import re
from .oneshot_archive import Refused
from .oanda_history_manifest import encoded,validated


def publish_candles(archive,raw,*,name,start,end,retrieved,synthetic,_bounded=None):
    """No HTTP, credential access, missing-candle repair or retry.

    Commit manifest is published last. A partial set is not a complete dataset.
    Native writes use only the pinned protected archive; fixture writes cannot
    assert authenticated provenance.
    """
    if not re.fullmatch(r'v26c_[a-z0-9_]{1,48}',name):raise Refused('INVALID_BATCH_NAME')
    if type(synthetic) is not bool or archive.synthetic and not synthetic:raise Refused('FIXTURE_PROVENANCE_REQUIRED')
    rows,report=validated(raw,'EUR_USD',start,end,retrieved)
    if len(raw)>8*1024*1024:raise Refused('BODY_TOO_LARGE')
    # No caller-supplied metadata or headers are persisted. The strict validator
    # has rejected extra response keys before any raw bytes reach the archive.
    raw_path='raw/'+name+'.json';rows_path='validated/'+name+'.json'
    raw_hash=archive.put(raw_path,raw);rows_hash=archive.put(rows_path,encoded(rows))
    receipt={'synthetic':synthetic,'instrument':'EUR_USD','granularity':'M5',
             'raw':raw_path,'raw_sha256':raw_hash,'validated':rows_path,
             'validated_sha256':rows_hash,'observed_complete_count':len(rows),
             'validation':report,'start':start,'end':end,'retrieved':retrieved}
    if archive.session_id is not None:
        from .oanda_history_manifest import digest
        receipt.update(session=archive.session_id,identity=digest(encoded(archive.identity)),
                       request_sha256=digest(archive.read('request.json')))
    if _bounded is not None:
        cap,index=_bounded
        from .bounded_acquisition import guard,spec,CATALOGUE_HASH
        guard(cap,spec(index))
        from .oanda_history_manifest import digest
        receipt.update(catalogue=CATALOGUE_HASH,index=index,spec_sha256=digest(encoded(spec(index))),source=cap['source'])
    archive.put('manifests/'+name+'.json',encoded(receipt))
    return receipt
