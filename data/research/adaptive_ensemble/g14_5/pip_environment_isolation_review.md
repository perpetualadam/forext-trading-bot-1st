# Pip environment isolation

`tests/g14_4_acquire.py` does not build a subprocess environment. It therefore does not filter `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, `PIP_FIND_LINKS`, `PIP_TRUSTED_HOST`, `PIP_CONFIG_FILE`, `PIP_PRE`, `PIP_NO_BINARY`, `PIP_ONLY_BINARY`, proxy variables, or certificate overrides.

No environment values were read for this review. No pip configuration file and no netrc file was opened.

`PIP_CONFIG_FILE` pointing at an empty file would not be sufficient. Environment variables and a copied host environment can still change the index, binary policy, proxy, and trust settings.

A future acquisition process should start from a small allowlist. On Windows that allowlist may need `SYSTEMROOT`, `PATH`, and `TEMP` so the process can start. It must not copy the rest of the host environment, and it must not disable TLS verification.

This isolation is documented here. It is not implemented in the current helper.
