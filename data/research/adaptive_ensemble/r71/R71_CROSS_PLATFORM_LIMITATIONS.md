# R.71 Cross-platform Limitations

`LINUX_INTEGRATION_NOT_VERIFIED`

Windows CPython 3.13.5 ran the eight calculation tests in 0.003s.

WSL2 CPython 3.12.3 ran the same file and stopped in `forex_bot/reconciliation.py` at `import oandapyV20`. pandas, numpy, and psycopg2 are absent. requests is present. No package was installed. The OANDA client and pandas were not replaced with substitutes.

The calculation file imports reconciliation so it can classify a snapshot. That import is why Linux cannot run the file. The profit-protection module itself does not import the OANDA package. This audit did not split the file to manufacture a Linux pass.

A Windows offline pass is not a Linux runtime result and is not a VPS result.
