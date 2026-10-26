# R.48 offline transport tests

The tests use synthetic dictionaries. They do not use a credential and they do not open a connection.

## Attempt 1

2 failed, 4 passed. The source scan rejected the module because a docstring contained the word the scan forbids. The spread assertion expected `2` and the formatter returned `2.0`. No safety check was removed.

## Attempt 2

1 failed, 5 passed. The spread assertion passed. A second docstring still contained the forbidden word. The scan stayed in place.

## Attempt 3

6 passed. The docstrings no longer contain that word. The spread for bid 1.10000 and ask 1.10020 at pip location -4 is the text `2`, labelled `POINT_IN_TIME_API_SNAPSHOT`. That label belongs to the synthetic example only.

Covered on the passing run: GET-only, the live host, the two path patterns, rejection of order and history paths, rejection of redirects, a constant exception that does not echo a supplied secret, no connection attempt, no account identifier in the redacted record, dropped unexpected fields, missing pip location left as `MISSING`, a bad top-level shape rejected, and gain and loss factors kept apart.

The R.8–R.42 application suite was not run. Those tests import modules that read `OANDA_ACCESS_TOKEN` from the environment. Running them would cross the credential gate. R.28 PostgreSQL scripts were not run.
