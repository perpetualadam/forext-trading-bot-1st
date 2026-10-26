# D.9 harness independent review

Reviewed read-only:

- `tests/d9_database_concurrency_runner.py`
- `tests/d7_resource_cleanup_runner.py`
- `tests/d8_concurrency_runner.py`
- The D.7, D.8, and D.9 test modules

None of those files were edited.

What was safe to reuse as a pattern, in a new D.10 runner:

- Synthetic child environment with only the Windows process keys plus explicit synthetic settings.
- Fake `dotenv` installed before production import.
- Fake `psycopg2` installed before production import, including `extensions.cursor` and `extensions.connection`.
- Network denials for `socket.connect`, `connect_ex`, `create_connection`, `getaddrinfo`, `gethostbyname`, `urllib.request.urlopen`, `asyncio.open_connection`, `asyncio.start_server`, and the asyncio subprocess helpers as sync functions that raise on call.
- `os.system`, `subprocess.Popen`, and `subprocess.run` denied.
- The narrow Windows `socket.socketpair` self-pipe.
- Filesystem denials for `.env`, credential names, `data/ops`, `v2_shadow`, and `pgdata`, applied to `open`, `Path.open`, `os.open`, replace, rename, remove, unlink, and shutil copy/move/rmtree.
- Self-check uses the guarded `open`, not the saved real open.

What was not reused unchanged:

- D.9 replaces `requests` with a function that always raises. D.10 needs a fake `Session.get` so the real poller can run without a network call.
- D.9 sets `TELEGRAM_COMMANDS=0`, which makes `start_telegram_control` return without a thread. D.10 sets commands on and uses a synthetic token and chat id.
- D.8 does not deny `connect_ex`, `create_connection`, or `asyncio.open_connection`. Those denials were required and are present in the D.10 runner.
- D.9 lifespan replaces `start_telegram_control` and `stop_telegram_control`. D.10 keeps both production functions. One lifespan case wraps stop so it calls the real function and then raises. That case is labelled as an injected exception, not as production stop behaviour.

Guards are installed before `import forex_bot.database` and `import forex_bot.telegram_control`. The lifespan import of `forex_bot.app` happens after the same guards. The self-check passed, including a later connect to the socketpair port, which was denied.
