# G.14.7 network policy integration

`NETWORK_POLICY_NOT_INTEGRATED` does not apply. The state machine calls the G.14.6 URL policy on the requests it actually issues.

## When policy runs

1. `authorize_url(index_url, role="index")` runs in `POLICY_VALIDATED`, before resolution and before any transport exchange.
2. `reject_additional_indexes` runs in the same step.
3. `assess_wheel_candidate` runs during resolution. That function calls `authorize_redirect_chain` for each candidate URL and rejects source distributions, non-wheels, yanked releases, prereleases, and non-`any` platform tags.
4. After `DESTINATION_VALIDATED`, `_request` calls `authorize_redirect_chain` on the accumulated hop list immediately before every `ScriptedTransport.exchange`.
5. A redirect location is appended only after the current response is classified as a redirect. The next loop authorizes the new chain before the next exchange. The transport never chooses the next URL.

## Controls exercised by integration tests

Unapproved index host, unapproved artifact host, HTTPS-to-HTTP downgrade, redirect to a third host, and more than two redirects all fail closed through those functions. The reasons are `unapproved_host`, `unexpected_artifact_host`, `https_downgrade`, `cross_host_redirect`, and `excessive_redirects`.

The same G.14.6 function still rejects userinfo, non-443 ports, localhost, loopback, private and link-local addresses, credential query keys, `http`, `file`, `ftp`, VCS schemes, and artifact paths that do not end in `.whl`. Those checks are inside `authorize_url`, which the workflow calls on every hop. The G.14.7 integration set adds the hop-following cases above; it does not replace the G.14.6 unit cases.

## Boundaries

`pypi.org` and `files.pythonhosted.org` are the proposed hosts already encoded in `tests/g14_4_acquire.py`. They are not approved for use. No test contacts them. The synthetic lock records `source.index_url` as `synthetic://fixture` and `source_approved` as false.

Response policy is separate from URL policy and is documented in `bounded_streaming_review.md`.
