# Future network policy

Not in force. No request and no DNS lookup were made. `https://pypi.org/simple` and `files.pythonhosted.org` are not approved.

A later architecture, if one is ever selected, would still need:

- An explicit source approval naming the hosts.
- HTTPS only, with certificate validation left on.
- Redirects fail closed unless they stay on the same approved host and stay HTTPS.
- No IP literals. DNS only under that later approval.
- No implicit proxy. No credentials on acquisition requests.
- Bounded retries, timeouts, response size, and total download size. The numbers belong to the approval that allows a sender, not to this review.
- No extra indexes, direct URLs, VCS, source distributions, source builds, PEP 517 hooks, or installation during acquisition.
- No egress to OANDA or to any host outside the approval.
- The application `NETWORK_DISABLED` flag remains the only control that exists in code. It is not an OS or guest firewall. Guest network mode was not observed for VM, WSL, or Docker.

`REAL_HTTPS_SENDER_ABSENT` and `PACKAGE_SOURCE_APPROVAL_REQUIRED` stay. Network approval is not granted.
