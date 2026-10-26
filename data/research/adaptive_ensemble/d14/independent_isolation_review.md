# Isolation review

The D.14 child loads the D.12 runner, which loads the D.11 guard installer. Guards and the self-check run before `forex_bot` is imported.

The child environment is synthetic. `LIVE_SAFETY_STATE_PATH` is temporary. `dotenv.load_dotenv` is replaced. `concensus-forecast` entries are removed from `sys.path`. Blocked-worker work runs in the child. The parent timeout is 120 seconds. The parent does not import `app.py`.
