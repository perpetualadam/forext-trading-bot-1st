# Remediation plan

None of the following changes were made in G.14.5. The next work, if authorised, is a separate offline remediation stage. It must not contact a package index.

1. Add an explicit environment allowlist and reject inherited index, find-links, trusted-host, binary-policy, proxy, and certificate overrides. Findings G14.5-01.
2. Add a host and redirect policy that names the index and artifact hosts and rejects other final URLs. Finding G14.5-02.
3. Enforce wheels-only and reject source distributions by content, not only by filename. Finding G14.5-03.
4. Parse wheel ZIP metadata in memory with path and size limits. Finding G14.5-04.
5. Evaluate markers and extras and compare metadata requirements with the selected set. Finding G14.5-05.
6. Reject direct URL and VCS requirements in the inventory parser and preserve markers. Finding G14.5-06.
7. Reject symlink and reparse destinations before resolving them. Finding G14.5-07.

Gate B stays blocked until those controls exist in code and fail closed under tests. A passing design document does not close a finding.
