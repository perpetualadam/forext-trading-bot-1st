"""Dependencies for historical scenarios executed against current production code.

These fixtures never replace the safety guard, database locking, cleanup, or
Telegram lifecycle implementation. Existing runners install their network and
filesystem barriers before importing the application.
"""

import sys
import types


def schema_ready_cursor(cls):
    """An installed synthetic schema answers the new read-only readiness query."""
    execute = cls.execute
    fetchone = cls.fetchone

    def tracked_execute(self, sql, *args, **kwargs):
        self._current_fixture_sql = str(sql)
        return execute(self, sql, *args, **kwargs)

    def schema_fetchone(self):
        if "to_regclass('public.trades')" in getattr(self, "_current_fixture_sql", ""):
            return (True,)
        return fetchone(self)

    cls.execute = tracked_execute
    cls.fetchone = schema_fetchone
    return cls


def wire_current_startup(appmod):
    """Bind existing fake ports at their current lazy-import boundaries."""
    appmod._oanda_client = lambda: types.SimpleNamespace(
        build_api=appmod.build_api,
        fetch_account_summary=appmod.fetch_account_summary,
        last_account_summary=lambda: {},
    )
    # Production now imports the task from its owning module at dispatch time.
    bot_loop = sys.modules.get("forex_bot.bot_loop")
    if bot_loop is None:
        bot_loop = types.ModuleType("forex_bot.bot_loop")
        sys.modules[bot_loop.__name__] = bot_loop
    bot_loop.run_bot = appmod.run_bot
