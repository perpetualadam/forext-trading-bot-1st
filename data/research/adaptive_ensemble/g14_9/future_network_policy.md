# Future network policy

This policy is not in force. It does not approve any host. G.14.9 sent no request and performed no DNS lookup.

Proposed index, not approved: `https://pypi.org/simple`

Proposed artifact host, not approved: `files.pythonhosted.org`

`PACKAGE_SOURCE_APPROVAL_REQUIRED` remains. `REAL_HTTPS_SENDER_ABSENT` remains.

## Rules a later approval would have to include

- One index host, named in the approval, HTTPS only.
- One artifact host, named in the approval, HTTPS only.
- Certificate validation left on. No custom trust store was reviewed, and none may be added in order to make a download succeed.
- Redirects fail closed unless the next URL is on the same approved host and still HTTPS. A redirect to any other host fails.
- DNS and address policy: names resolve only at request time under the approval, results must be public addresses, and the connection must still match the approved host. This stage does not specify a resolver implementation.
- IP literals in URLs are rejected.
- No credentials, cookies, or broker tokens on index or artifact requests.
- No proxy unless a later approval names one. An implicit user-environment proxy is not accepted.
- Timeouts are bounded. The bound is a future parameter, not invented here as a security claim.
- Retries are bounded and never follow a new host.
- Response and download sizes are bounded before the body is stored. The synthetic workflow already has size checks against the injected document. Those numbers are not live limits.
- No additional indexes, direct URLs, VCS URLs, or source distributions.
- No source builds and no PEP 517 hooks during acquisition.
- No package installation in the acquisition step. Installation is a later, separate approval if it is ever considered.
- No inherited host secrets in the request process.
- No egress except the approved hosts. OANDA is not an approved acquisition host.

## Where each control has to live

1. Acquisition application: URL allowlist, HTTPS scheme, redirect rejection, size limits, wheel-only names, refusal to run hooks, refusal to attach credentials. These can be tested with an injected transport. An application check is not an egress firewall.
2. Isolated environment, Option B only: no mounted secrets, no default route until the download phase is separately approved, no production names in the environment. The environment does not exist.
3. Network boundary: deny by default, allow only the approved hosts during the approved phase, and drop everyone else, including the broker. This control was not observed on this host.
4. Independent verification: hash and wheel checks on received bytes, then a comparison with the receiver's own inventory. Verification does not open sockets.

Option A and Option C have nowhere to put control 3 except the host firewall, which was not inspected and must not be edited in a later stage without approval. An application `NETWORK_DISABLED` flag remains the only control that exists today, and it exists because the live sender was not built.

No control in this document authorises a request.
