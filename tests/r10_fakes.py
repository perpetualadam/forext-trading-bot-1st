"""Deterministic stand-ins for the startup dependencies traced in forex_bot.app.

These objects record calls locally. They do not open sockets, construct an
OANDA client, connect to PostgreSQL, or send a message.
"""

from __future__ import annotations

from typing import Any


_RESOURCES = {"persistence", "broker", "market_data", "messaging", "health", "scheduler"}


class OfflineServices:
    """Fake dependencies used only by the explicit offline startup call."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.readable = True
        self.fail = ""
        self.interrupt = ""
        self.missing = ""
        self.use_provider = False
        self.provider_rows: Any = None
        self.reconciliation_unavailable = False
        self.schedule_status = "recorded_not_started"
        self.schedule_awaitable = False
        self.cleanup_raise = False
        self.cleanup_error = ""
        self.config_valid = True
        self.unexpected = False
        self.calls: list[str] = []
        self.closed: list[str] = []
        self.open: list[str] = []
        self.rejected: list[str] = []
        self.messages: list[str] = []
        self.market_snapshot = {
            "bid": 1.25,
            "ask": 1.2502,
            "exposure": "unknown",
            "read_only": True,
        }
        self.lifecycle: dict[str, Any] = {}
        self.symbols = ["EUR_USD"]

    def _touch(self, name: str) -> None:
        self.calls.append(name)
        if self.missing == name:
            raise RuntimeError("missing required dependency")
        if self.interrupt == name:
            raise RuntimeError("initialization interrupted")
        if self.fail == name:
            raise RuntimeError(f"{name} failed")
        if name in _RESOURCES:
            self.open.append(name)

    def validate_config(self) -> None:
        self._touch("validate_config")
        if self.unexpected:
            raise RuntimeError("unexpected application state")
        if not self.config_valid:
            raise ValueError("invalid fake configuration")

    def verify_safety(self) -> None:
        self._touch("verify_safety")
        from forex_bot.app import StartupSafetyAbort
        from forex_bot.live_safety import initialise_fail_closed, live_safety_initialised

        initialise_fail_closed()
        if not live_safety_initialised():
            raise StartupSafetyAbort("safety state is not startup-compatible")

    def init_persistence(self) -> None:
        self._touch("persistence")

    def recover_orders(self) -> Any:
        self.calls.append("recovery_provider")
        if self.fail == "recovery":
            raise RuntimeError("recovery provider failed")
        if self.fail == "recovery_incomplete":
            return {"incomplete": True}
        if self.provider_rows is not None:
            return self.provider_rows
        return self.rows

    def init_broker(self) -> None:
        self._touch("broker")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        self.rejected.append("submit_order")
        raise RuntimeError("fake broker rejects order submission")

    def close_position(self, *_args: object, **_kwargs: object) -> None:
        self.rejected.append("close_position")
        raise RuntimeError("fake broker rejects position closing")

    def init_market_data(self) -> dict[str, Any]:
        self._touch("market_data")
        if self.reconciliation_unavailable:
            from forex_bot.app import ReconciliationUnavailable

            raise ReconciliationUnavailable("reconciliation unavailable")
        return dict(self.market_snapshot)

    def init_messaging(self) -> None:
        self._touch("messaging")

    def send_message(self, text: str) -> None:
        self.messages.append(text)
        raise RuntimeError("fake messaging does not send")

    def init_health(self) -> None:
        self._touch("health")

    def schedule_trading(self) -> Any:
        self.calls.append("schedule")
        if self.fail == "schedule":
            raise RuntimeError("scheduler refused")
        if self.missing == "schedule":
            raise RuntimeError("missing required dependency")
        self.open.append("scheduler")
        status = self.schedule_status
        if self.schedule_awaitable:
            async def _finished() -> Any:
                return status

            return _finished()
        return status

    def close_opened(self, names: list[str]) -> list[str]:
        if self.cleanup_raise:
            self.cleanup_raise = False
            raise RuntimeError("cleanup failed")
        errors: list[str] = []
        if self.cleanup_error:
            errors.append(self.cleanup_error)
        for name in names:
            if name in self.open:
                self.open.remove(name)
                self.closed.append(name)
        return errors

    def ports(self):
        from forex_bot.app import StartupPorts, _CALL_RECOVERY

        rows = _CALL_RECOVERY if self.use_provider else self.rows
        return StartupPorts(
            mode="offline",
            validate_config=self.validate_config,
            verify_safety=self.verify_safety,
            init_persistence=self.init_persistence,
            recover_orders=self.recover_orders,
            recovery_rows=rows,
            recovery_readable=self.readable,
            init_broker=self.init_broker,
            init_market_data=self.init_market_data,
            init_messaging=self.init_messaging,
            init_health=self.init_health,
            schedule_trading=self.schedule_trading,
            close_opened=self.close_opened,
            symbols=lambda: list(self.symbols),
            lifecycle=self.lifecycle,
        )
