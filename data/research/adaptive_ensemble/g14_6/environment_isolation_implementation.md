# Environment isolation

`build_acquisition_environment` does not read `os.environ` and does not copy the supplied inherited mapping. Any inherited key is rejected. Credential-like names and values are rejected without being copied into the exception text.

The child mapping may contain only caller-supplied Windows basics (`SYSTEMROOT`, `WINDIR`, `TEMP`, `TMP`, `PATHEXT`) plus explicit values: `PIP_CONFIG_FILE` set to the null device, `PIP_NO_INPUT`, `PIP_ONLY_BINARY=:all:`, `PYTHONNOUSERSITE`, and `PYTHONSAFEPATH`. `PATH` is not copied. The interpreter must be an absolute `python` or `python.exe` path. It is not launched in this stage.

`PIP_CONFIG_FILE` alone is not treated as sufficient. Index, proxy, certificate, and startup variables are rejected as well. TLS verification is not disabled, and no custom certificate bundle is set.

No environment values from this machine were read or stored.
