# Independent isolation review

The D.15 child loads the existing D.14 runner, which loads the D.12 runner, which loads the D.11 guard installer. Guards are installed before `forex_bot` is imported. The D.11 self-check must pass or the child raises. Every D.15 child that reached its assertions had an empty `network_after` list and exit code 0.

The child environment keeps only the Windows process paths needed to start Python, plus a synthetic configuration. `PYTHONPATH` is the project root. `PYTEST_CURRENT_TEST` is set so the existing safety test helpers can run. OANDA tokens are empty. PostgreSQL host is invalid and the port is 1. The safety path is a temporary file created for that child.

The parent test modules do not import `app.py`. They pin all five protected hashes and refuse to launch a child when a hash differs.

A previous stage passing is not the basis of this review. The guards ran again in the D.15 children.
