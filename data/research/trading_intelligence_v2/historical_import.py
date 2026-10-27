"""Multi-file licensed M5 importer. No sorting, repairs, inferred asks or downloads."""
import csv
from decimal import Decimal,InvalidOperation
import hashlib
from pathlib import Path
from .core import Bar,PAIRS,ResearchRejected,timestamp
from .historical_sources import permission
from .historical_quality import quality
from .historical_manifest import classify,canonical_digest,KNOWN_EXPOSURE

SCHEMA=('time','instrument','complete','mid_o','mid_h','mid_l','mid_c','bid_o','bid_h','bid_l','bid_c','ask_o','ask_h','ask_l','ask_c')


def import_dataset(manifest,root,*,independent_required=True,prior_intervals=KNOWN_EXPOSURE):
    permission(manifest)
    if manifest.get('schema')!='OBSERVED_M5_BID_ASK_MID_V1' or manifest.get('timestamp_convention')!='UTC_START_AWARE':
        raise ResearchRejected('unsupported_or_ambiguous_source_convention')
    if manifest.get('completion_evidence')!='explicit_source_complete_flag':
        raise ResearchRejected('completion_evidence_required')
    grouped={}; reports={}; file_evidence=[]
    for item in manifest.get('files',[]):
        pair=item['instrument']
        if pair not in PAIRS: raise ResearchRejected('unsupported_instrument')
        url=item.get('source_url','')
        if not isinstance(url,str) or not url.startswith('https://') or '@' in url or any(x in url.lower() for x in ('oanda.com','access_token','api_key','password')):
            raise ResearchRejected('public_source_url_required_no_credentials_or_broker_api')
        try: retrieved=timestamp(item['retrieved_utc'])
        except (KeyError,ValueError,TypeError) as exc: raise ResearchRejected('aware_retrieval_time_required') from exc
        path=(root/item['path']).resolve()
        if not path.is_relative_to(root.resolve()) or path.suffix.lower()!='.csv':
            raise ResearchRejected('unapproved_source_path')
        raw=path.read_bytes(); actual=hashlib.sha256(raw).hexdigest()
        if actual!=item['sha256']: raise ResearchRejected('source_hash_mismatch')
        rows=[]; original_prices=[]
        with path.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if tuple(reader.fieldnames or ())!=SCHEMA: raise ResearchRejected('source_schema_mismatch')
            for index,row in enumerate(reader):
                if None in row or any(row[k] is None for k in SCHEMA):
                    raise ResearchRejected('invalid_row_field_count:'+str(index))
                if row['instrument']!=pair: raise ResearchRejected('instrument_identity_mismatch')
                if row['complete']!='true': raise ResearchRejected('incomplete_or_ambiguous_source_row')
                try:
                    texts=[row[k] for k in SCHEMA[3:]]
                    values=[Decimal(x) for x in texts]
                    if not all(x.is_finite() and x>0 for x in values): raise ValueError('invalid price')
                    rows.append(Bar(timestamp(row['time']),*(float(x) for x in values)))
                    original_prices.append(texts)
                except (InvalidOperation,ValueError,OverflowError,TypeError) as exc:
                    raise ResearchRejected('invalid_source_row:'+str(index)) from exc
        q=quality(pair,rows,holiday_windows=manifest.get('holiday_windows',()))
        if rows[-1].t+300>retrieved: raise ResearchRejected('completion_after_claimed_retrieval')
        existing=grouped.setdefault(pair,[])
        if existing and rows[0].t<=existing[-1].t: raise ResearchRejected('cross_file_duplicate_or_disordered_input')
        existing.extend(rows)
        file_evidence.append(dict(instrument=pair,path=item['path'],sha256=actual,rows=len(rows),
                                 source_url=url,retrieved_utc=item['retrieved_utc'],
                                 decimal_lexemes_sha256=canonical_digest(original_prices)))
    if set(grouped)!=set(PAIRS): raise ResearchRejected('all_six_instruments_required')
    labels={}
    for pair,bars in grouped.items():
        reports[pair]=quality(pair,bars,holiday_windows=manifest.get('holiday_windows',()))
        labels[pair]=classify(bars[0].t,bars[-1].t+300,manifest,prior_intervals)
    if independent_required and set(labels.values())!={'INDEPENDENT_UNTOUCHED'}:
        raise ResearchRejected('independent_untouched_data_not_established:'+str(labels))
    return grouped,dict(files=file_evidence,quality=reports,independence=labels,manifest_sha256=canonical_digest(manifest),
                       transformations='No sort/dedup/interpolation/decimal rounding; original lexemes retained and hashed; replay uses existing IEEE-754 float Bar adapter')
