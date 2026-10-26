# G.14.4 package source policy

No index was contacted. No pip configuration file was read. No environment variable was read.

## Proposal, not an approval

The candidate sole index is the public index `https://pypi.org/simple`.

That URL is a proposal. It is not approved.

Classification: `PACKAGE_SOURCE_APPROVAL_REQUIRED`

## Rules once a source is approved

- One explicit index URL. The host default pip index is not acceptable by inheritance.
- No corporate or local mirror is proposed. None was named.
- The public index does not require authentication. No credential may be added, and none was read.
- Redirects are rejected unless the operator later names the exact allowed host. An unapproved host is a stop.
- Additional `--extra-index-url` values are prohibited.
- Unapproved `--find-links` locations are prohibited.
- Direct URL requirements are prohibited.
- VCS requirements are prohibited.
- Pre-releases are rejected unless a later approval names one package.
- Yanked releases are rejected.
- Source distributions are rejected. A missing wheel stops with `COMPATIBLE_WHEEL_UNAVAILABLE`.
- Dependency confusion is limited by one index, PEP 503 normalized names, and rejection of any second index.

Future commands must pass `--index-url` explicitly and must not rely on `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, or trusted-host settings from the machine.
