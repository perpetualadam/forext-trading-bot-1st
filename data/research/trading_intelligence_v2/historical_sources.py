"""Reviewed public-source discovery. This module never opens a network connection."""
from .core import ResearchRejected

SOURCES = {
 'FXCM':dict(identity='FXCM-owned MarketData repository',
   documentation='https://github.com/fxcm/MarketData/blob/master/CandleData/README.md',
   terms='https://www.fxcm.com/uk/forms/eula/',
   status='PERMISSION_NOT_ESTABLISHED',
   limitation='Personal-use grant is subject to EULA; applicable automated research/derived-publication rights not verified. Indicative active-trader quotes; AUDUSD omitted from candle instrument list.'),
 'HISTDATA':dict(identity='HistData.com',documentation='https://www.histdata.com/f-a-q/',
   terms='https://www.histdata.com/terms-of-use/',status='PERMISSION_AND_FORMAT_NOT_VERIFIED',
   limitation='Minute bars are bid-only; ask is in Generic ASCII tick format. Reproducible permission and timestamp convention must be reviewed; no scraping or bid-to-ask fabrication.'),
 'DUKASCOPY':dict(identity='Dukascopy Europe',
   documentation='https://www.dukascopy.com/swiss/english/about/faq/?mob=0',
   terms='https://www.dukascopy.com/europe/english/legal-pages/terms-of-use/',
   status='DATABASE_USE_PERMISSION_NOT_ESTABLISHED',
   limitation='Reviewed terms restrict constructing databases; do not assume another jurisdiction or a public URL grants this project rights. No authenticated service used.')}


def permission(record):
    """Require explicit, reviewable rights evidence; public availability is insufficient."""
    fields=('provider','provider_identity_url','terms_url','terms_evidence','permitted_use')
    if any(not isinstance(record.get(k),str) or not record[k].strip() for k in fields):
        raise ResearchRejected('missing_provenance_or_rights_evidence')
    if record.get('rights_reviewed') is not True:
        raise ResearchRejected('data_rights_not_reviewed')
    if record['permitted_use']!='offline_research_and_derived_results':
        raise ResearchRejected('research_and_derived_result_rights_required')
    for key in ('provider_identity_url','terms_url'):
        url=record[key].lower()
        if not url.startswith('https://') or '@' in url or any(x in url for x in ('api-fxtrade.oanda','api-fxpractice.oanda','access_token','api_key','password')):
            raise ResearchRejected('unsafe_or_credential_url')
    return True
