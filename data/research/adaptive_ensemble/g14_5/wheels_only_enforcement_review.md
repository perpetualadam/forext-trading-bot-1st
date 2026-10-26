# Wheels-only enforcement

The production Dockerfile uses `--prefer-binary`. That flag still allows a source distribution. The G.14.4 acquisition helper does not pass `--only-binary=:all:` because it does not invoke pip at all.

The verifier rejects filenames ending in `.tar.gz`, `.tar.bz2`, and `.zip`, and it checks a limited set of wheel tags in the filename. A `.whl` suffix is not a wheel. The verifier accepts non-zip bytes when the hash and size match.

Classification: `WHEELS_ONLY_ENFORCEMENT_INCOMPLETE`.

No source distribution was built and no wheel code was executed during this review.
