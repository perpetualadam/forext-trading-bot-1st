# Network host and redirect policy

The proposed index remains `https://pypi.org/simple`. It is not approved. `files.pythonhosted.org` is a proposed artifact host, not an approved host. This stage did not contact either host and did not query DNS.

The roles that a later approval must name separately are the index host, the artifact host, any redirect destination, and any authentication destination. A redirect from an approved index does not approve the destination. Package metadata does not approve extra hosts.

The current acquisition helper has no URL parser, no host allowlist, no port check, no userinfo rejection, no downgrade rejection, and no redirect limit. Pip's own redirect behavior is not this application's policy.

Classification: `ARTIFACT_HOST_POLICY_NOT_ENFORCED`.

A future permission, if the helper is remediated first, must name HTTPS, port 443, the exact hosts, a maximum redirect count of zero unless each hop is on the named list, maximum sizes, timeouts, and a rule that credentials never appear in URLs or logs.
