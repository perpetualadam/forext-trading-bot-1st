# Network host policy

`authorize_url` and `authorize_redirect_chain` are called by `prepare_acquisition` and again by `commit_acquisition`. Proposed hosts are `pypi.org` for the index and `files.pythonhosted.org` for artifacts. They are not approved for use. This stage does not contact them.

The policy rejects HTTP, FTP, file URLs, other schemes, userinfo, unexpected ports, localhost, loopback, private and link-local addresses, other IP destinations, unapproved hosts, cross-host redirects, HTTPS-to-HTTP downgrades, and chains longer than two redirects. An index host may transition only to the proposed artifact host. Pip is not invoked. Pip's redirect behavior is not treated as this policy.

`OfflineAcquisitionTransport.commit` re-checks every authorized URL and then raises `network_not_authorised`. There is no socket call in that path. A live HTTPS client was not implemented and was not tested. That remaining limit does not create a bypass: a rejected URL fails before the refusal to send, and an allowed URL still is not sent.
