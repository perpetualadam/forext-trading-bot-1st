"""Isolated offline reference model for the R.67A and R.67B contracts.

This module does not import the trading bot, open a socket, or use a database.
An in-memory commit is not a PostgreSQL transaction.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable

ACCOUNT = "ACC-SYNTHETIC"
INSTRUMENT = "EUR_USD"

EXPOSURE_OPEN = "OPEN"
EXPOSURE_PARTIAL = "PARTIALLY_OPEN"
EXPOSURE_FLAT = "FLAT_CONFIRMED"
EXPOSURE_UNKNOWN = "UNKNOWN"
EXPOSURE_STALE = "STALE"
EXPOSURE_CONFLICT = "CONFLICT"

CLOSE_NOT_REQUESTED = "CLOSE_NOT_REQUESTED"
CLOSE_AUTHORISED = "CLOSE_AUTHORISED"
CLOSE_SUBMITTING = "CLOSE_SUBMITTING"
CLOSE_OUTCOME_UNKNOWN = "CLOSE_OUTCOME_UNKNOWN"
CLOSE_PARTIALLY_FILLED = "CLOSE_PARTIALLY_FILLED"
CLOSE_FULLY_CONFIRMED = "CLOSE_FULLY_CONFIRMED"
CLOSE_REJECTED = "CLOSE_REJECTED"
CLOSE_RECONCILIATION_REQUIRED = "CLOSE_RECONCILIATION_REQUIRED"
CLOSE_MANUAL_REVIEW_REQUIRED = "CLOSE_MANUAL_REVIEW_REQUIRED"

ATTR_BOT = "BOT_ATTEMPT_CONFIRMED"
ATTR_EXTERNAL = "EXTERNAL_ACTION_CONFIRMED"
ATTR_UNKNOWN = "UNKNOWN"

PROT_BROKER = "BROKER_PROTECTED"
PROT_LOCAL = "LOCAL_REFERENCE_ONLY"
PROT_UNPROTECTED = "UNPROTECTED_CONFIRMED"
PROT_UNKNOWN = "PROTECTION_UNKNOWN"
PROT_STALE = "PROTECTION_STALE"

BLOCKING = {
    CLOSE_AUTHORISED,
    CLOSE_SUBMITTING,
    CLOSE_OUTCOME_UNKNOWN,
    CLOSE_RECONCILIATION_REQUIRED,
    CLOSE_MANUAL_REVIEW_REQUIRED,
}
TERMINAL_RESOLVED = {CLOSE_FULLY_CONFIRMED, CLOSE_REJECTED, CLOSE_NOT_REQUESTED}


class CommitFailed(Exception):
    """Synthetic durable-commit failure. No broker action is authorised."""


class VersionConflict(Exception):
    """Compare-and-swap lost. The caller must re-read and must not send."""


class LockAcrossIO(Exception):
    """A commit was attempted while a simulated broker wait was in progress."""


def D(value: str | int | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass
class Observation:
    account_id: str
    instrument: str
    book_side: str
    trade_id: str
    broker_units: Decimal
    original_units: Decimal
    reported_units: Decimal | None = None
    local_tracking_id: str | None = None
    provenance: str = "EXTERNAL_UNKNOWN"
    snapshot_id: str | None = None
    reconcile_epoch: int = 0
    snapshot_complete: bool = False
    snapshot_fresh: bool = False
    exposure_zero_reported: bool = False
    exposure: str = EXPOSURE_OPEN
    exposure_attribution: str = ATTR_UNKNOWN
    protection: str = PROT_UNKNOWN
    local_stop_reference: Decimal | None = None
    local_stop_source: str | None = None
    confirmed_broker_stop_price: Decimal | None = None
    broker_stop_order_id: str | None = None
    stop_section_complete: bool = False
    version: int = 0
    pending_close_id: str | None = None
    retired: bool = False
    management: bool = False
    flat_confirmed: bool = False
    conflict: bool = False
    had_units: bool = True


@dataclass
class Grant:
    grant_id: str
    scope: str
    account_id: str
    instrument: str
    book_side: str
    trade_ids: tuple[str, ...]
    units: Decimal | None
    snapshot_id: str
    endpoint: str = "PositionClose"
    source: str = "operator"
    expires_at: datetime | None = None
    revoked: bool = False
    consumed: bool = False
    attempt_id: str | None = None
    process_generation: int = 0


@dataclass
class CloseOp:
    close_operation_id: str
    account_id: str
    instrument: str
    book_side: str
    trade_ids: tuple[str, ...]
    units_authorised: Decimal
    endpoint: str
    grant_id: str
    snapshot_id: str
    state: str = CLOSE_AUTHORISED
    units_confirmed: Decimal = field(default_factory=lambda: D(0))
    fill_transaction_ids: tuple[str, ...] = ()
    attribution: str = ATTR_UNKNOWN
    version: int = 0
    remainder_reconciled: bool = False
    response_epoch: int = 0


@dataclass
class MemoryLedger:
    """Copy-on-write commit. MODEL_TRANSACTION_TESTED. Not PostgreSQL."""

    observations: dict[tuple[str, str, str, str], Observation] = field(default_factory=dict)
    grants: dict[str, Grant] = field(default_factory=dict)
    closes: dict[str, CloseOp] = field(default_factory=dict)
    fail_commits: int = 0
    commit_count: int = 0
    broker_wait: bool = False

    def commit(self, mutator: Callable) -> None:
        if self.broker_wait:
            raise LockAcrossIO("commit during simulated broker wait")
        if self.fail_commits > 0:
            self.fail_commits -= 1
            raise CommitFailed("synthetic commit failure")
        obs = deepcopy(self.observations)
        grants = deepcopy(self.grants)
        closes = deepcopy(self.closes)
        mutator(obs, grants, closes)
        self.observations = obs
        self.grants = grants
        self.closes = closes
        self.commit_count += 1


def _key(account: str, instrument: str, side: str, trade_id: str) -> tuple[str, str, str, str]:
    return (account, instrument, side, trade_id)


def _recompute(obs: Observation) -> None:
    if obs.conflict and not obs.flat_confirmed:
        obs.exposure = EXPOSURE_CONFLICT
        return
    if obs.flat_confirmed:
        obs.exposure = EXPOSURE_FLAT
        return
    if not obs.snapshot_complete or not obs.snapshot_fresh:
        obs.exposure = EXPOSURE_STALE
        return
    if obs.broker_units <= 0:
        obs.exposure = EXPOSURE_UNKNOWN
        return
    if obs.broker_units < obs.original_units:
        obs.exposure = EXPOSURE_PARTIAL
        return
    obs.exposure = EXPOSURE_OPEN


class ReferenceBook:
    def __init__(self, now: datetime | None = None) -> None:
        self.ledger = MemoryLedger()
        self.now = now or datetime(2026, 10, 25, tzinfo=timezone.utc)
        self.process_generation = 1
        self.execution_grants: set[str] = set()
        self.sent: set[str] = set()
        self.recovery_blocked = False
        self.refused: list[str] = []
        self.last_loser = ""
        self._seq = 0

    def _next(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq}"

    def observations(self) -> list[Observation]:
        return list(self.ledger.observations.values())

    def get(self, trade_id: str, side: str = "LONG", instrument: str = INSTRUMENT) -> Observation | None:
        return self.ledger.observations.get(_key(ACCOUNT, instrument, side, trade_id))

    def side_ops(self, side: str, instrument: str = INSTRUMENT) -> list[CloseOp]:
        return [
            op
            for op in self.ledger.closes.values()
            if op.book_side == side and op.instrument == instrument and op.account_id == ACCOUNT
        ]

    def _both_sides_open(self, instrument: str = INSTRUMENT) -> bool:
        longs = shorts = False
        for obs in self.ledger.observations.values():
            if obs.instrument != instrument or obs.retired or obs.broker_units <= 0:
                continue
            if obs.book_side == "LONG":
                longs = True
            elif obs.book_side == "SHORT":
                shorts = True
        return longs and shorts

    def _blocking_op(self, side: str, instrument: str = INSTRUMENT, ignore: str | None = None) -> CloseOp | None:
        for op in self.side_ops(side, instrument):
            if ignore and op.close_operation_id == ignore:
                continue
            if op.state in BLOCKING:
                return op
            if op.state == CLOSE_PARTIALLY_FILLED and not op.remainder_reconciled:
                return op
            if op.state == CLOSE_FULLY_CONFIRMED and not op.remainder_reconciled:
                return op
        return None

    def discover(
        self,
        trade_id: str = "T1",
        units: str = "10000",
        side: str = "LONG",
        snapshot_id: str = "S1",
        epoch: int = 1,
        complete: bool = True,
        fresh: bool = True,
        provenance: str = "EXTERNAL_UNKNOWN",
        instrument: str = INSTRUMENT,
        operator_asserted: bool = False,
    ) -> bool:
        if operator_asserted:
            provenance = "MANUAL_ASSERTED"
        units_d = D(units)

        def mut(obs_map, _grants, _closes) -> None:
            key = _key(ACCOUNT, instrument, side, trade_id)
            current = obs_map.get(key)
            if not complete or not fresh:
                if current is not None:
                    current.snapshot_complete = complete
                    current.snapshot_fresh = fresh
                    current.flat_confirmed = False if not current.flat_confirmed else current.flat_confirmed
                    _recompute(current)
                return
            if current is not None and epoch < current.reconcile_epoch:
                return
            if current is None:
                current = Observation(
                    account_id=ACCOUNT,
                    instrument=instrument,
                    book_side=side,
                    trade_id=trade_id,
                    broker_units=units_d,
                    original_units=units_d,
                    snapshot_id=snapshot_id,
                    reconcile_epoch=epoch,
                    snapshot_complete=True,
                    snapshot_fresh=True,
                    provenance=provenance,
                    had_units=units_d > 0,
                )
                obs_map[key] = current
            else:
                if current.reconcile_epoch > epoch:
                    return
                current.reported_units = units_d
                current.snapshot_id = snapshot_id
                current.reconcile_epoch = epoch
                current.snapshot_complete = True
                current.snapshot_fresh = True
                current.conflict = False
                if units_d == 0:
                    current.exposure_zero_reported = True
                else:
                    current.broker_units = units_d
                    current.exposure_zero_reported = False
                    if current.original_units == 0:
                        current.original_units = units_d
            current.management = False
            current.version += 1
            _recompute(current)

        self.ledger.commit(mut)
        self._strip_management_if_hedged(instrument)
        return self.get(trade_id, side, instrument) is not None

    def _strip_management_if_hedged(self, instrument: str) -> None:
        if not self._both_sides_open(instrument):
            return

        def mut(obs_map, _g, _c) -> None:
            for obs in obs_map.values():
                if obs.instrument == instrument:
                    obs.management = False

        self.ledger.commit(mut)

    def mint_local_id(self, trade_id: str = "T1", side: str = "LONG") -> str | None:
        obs = self.get(trade_id, side)
        if obs is None:
            return None
        local_id = self._next("local")

        def mut(obs_map, _g, _c) -> None:
            row = obs_map[_key(ACCOUNT, obs.instrument, side, trade_id)]
            row.local_tracking_id = local_id
            row.version += 1

        self.ledger.commit(mut)
        return local_id

    def grant_monitor(self, trade_ids: tuple[str, ...] = ("T1",), side: str = "LONG", source: str = "operator") -> str | None:
        if source != "operator":
            self.refused.append("monitor:" + source)
            return None
        if self._both_sides_open():
            self.refused.append("monitor:both_sides")
            return None
        rows = []
        for trade_id in trade_ids:
            obs = self.get(trade_id, side)
            if obs is None or obs.retired or not obs.snapshot_fresh or not obs.snapshot_complete:
                self.refused.append("monitor:snapshot")
                return None
            rows.append(obs)
        snapshot_id = rows[0].snapshot_id or ""
        if any(row.snapshot_id != snapshot_id for row in rows):
            self.refused.append("monitor:snapshot_mismatch")
            return None
        grant_id = self._next("mon")

        def mut(obs_map, grants, _c) -> None:
            grants[grant_id] = Grant(
                grant_id=grant_id,
                scope="MONITOR",
                account_id=ACCOUNT,
                instrument=INSTRUMENT,
                book_side=side,
                trade_ids=tuple(trade_ids),
                units=None,
                snapshot_id=snapshot_id,
                source=source,
                process_generation=self.process_generation,
            )
            for trade_id in trade_ids:
                row = obs_map[_key(ACCOUNT, INSTRUMENT, side, trade_id)]
                row.management = True
                row.version += 1

        self.ledger.commit(mut)
        return grant_id

    def grant_close(
        self,
        trade_ids: tuple[str, ...] = ("T1",),
        units: str = "10000",
        side: str = "LONG",
        source: str = "operator",
        snapshot_id: str | None = None,
    ) -> str | None:
        if source != "operator":
            self.refused.append("close:" + source)
            return None
        if self.recovery_blocked:
            self.refused.append("close:recovery_blocked")
            return None
        if self._both_sides_open():
            self.refused.append("close:both_sides")
            return None
        if self._blocking_op(side) is not None:
            self.refused.append("close:single_flight")
            return None
        rows = []
        for trade_id in trade_ids:
            obs = self.get(trade_id, side)
            if obs is None or obs.retired or not obs.snapshot_fresh or not obs.snapshot_complete:
                self.refused.append("close:snapshot")
                return None
            rows.append(obs)
        bound_snapshot = snapshot_id or rows[0].snapshot_id or ""
        if any((row.snapshot_id or "") != bound_snapshot for row in rows):
            self.refused.append("close:snapshot_mismatch")
            return None
        authorised = D(units)
        available = sum((row.broker_units for row in rows), D(0))
        if authorised <= 0 or authorised > available:
            self.refused.append("close:units")
            return None
        grant_id = self._next("grant")
        op_id = self._next("close")

        def mut(_obs, grants, closes) -> None:
            grants[grant_id] = Grant(
                grant_id=grant_id,
                scope="CLOSE",
                account_id=ACCOUNT,
                instrument=INSTRUMENT,
                book_side=side,
                trade_ids=tuple(trade_ids),
                units=authorised,
                snapshot_id=bound_snapshot,
                source=source,
                attempt_id=op_id,
                process_generation=self.process_generation,
            )
            closes[op_id] = CloseOp(
                close_operation_id=op_id,
                account_id=ACCOUNT,
                instrument=INSTRUMENT,
                book_side=side,
                trade_ids=tuple(trade_ids),
                units_authorised=authorised,
                endpoint="PositionClose",
                grant_id=grant_id,
                snapshot_id=bound_snapshot,
                state=CLOSE_AUTHORISED,
            )

        try:
            self.ledger.commit(mut)
        except CommitFailed:
            self.refused.append("close:commit")
            return None
        self.execution_grants.add(grant_id)
        return op_id

    def revoke(self, grant_id: str) -> None:
        grant = self.ledger.grants.get(grant_id)
        if grant is None:
            return
        op_id = grant.attempt_id

        def mut(obs_map, grants, closes) -> None:
            grants[grant_id].revoked = True
            op = closes.get(op_id or "")
            if op is None:
                return
            if op.state == CLOSE_AUTHORISED:
                op.state = CLOSE_NOT_REQUESTED
                op.version += 1
                for row in obs_map.values():
                    if row.pending_close_id == op.close_operation_id:
                        row.pending_close_id = None
            elif op.state == CLOSE_SUBMITTING and op.close_operation_id not in self.sent:
                op.state = CLOSE_OUTCOME_UNKNOWN
                op.version += 1
                for row in obs_map.values():
                    if row.trade_id in op.trade_ids and row.book_side == op.book_side:
                        row.pending_close_id = op.close_operation_id
                        row.provenance = "CLOSE_AMBIGUOUS"

        self.ledger.commit(mut)
        self.execution_grants.discard(grant_id)

    def expire(self, grant_id: str) -> None:
        grant = self.ledger.grants.get(grant_id)
        if grant is None:
            return
        grant_expired = grant

        def mut(_o, grants, closes) -> None:
            row = grants[grant_id]
            row.expires_at = self.now
            row.revoked = True
            op = closes.get(row.attempt_id or "")
            if op is not None and op.state == CLOSE_AUTHORISED:
                op.state = CLOSE_NOT_REQUESTED
                op.version += 1
            elif op is not None and op.state == CLOSE_OUTCOME_UNKNOWN:
                op.version = op.version

        self.ledger.commit(mut)
        self.execution_grants.discard(grant_id)
        _ = grant_expired

    def pre_send(self, op_id: str) -> bool:
        op = self.ledger.closes.get(op_id)
        if op is None or self.recovery_blocked:
            self.refused.append("presend:blocked")
            return False
        grant = self.ledger.grants.get(op.grant_id)
        if grant is None or grant.consumed or grant.revoked or grant.scope != "CLOSE":
            self.refused.append("presend:grant")
            return False
        if grant_id_not_in_process(grant, self):
            self.refused.append("presend:process")
            return False
        if op.state != CLOSE_AUTHORISED:
            self.refused.append("presend:state")
            return False
        if self._blocking_op(op.book_side, op.instrument, ignore=op_id) is not None:
            self.refused.append("presend:flight")
            return False
        for trade_id in op.trade_ids:
            obs = self.get(trade_id, op.book_side, op.instrument)
            if obs is None or obs.snapshot_id != op.snapshot_id or not obs.snapshot_fresh:
                self.refused.append("presend:snapshot")
                return False
        expected = {row.grant_id: row.consumed for row in self.ledger.grants.values()}

        def mut(obs_map, grants, closes) -> None:
            live_grant = grants[op.grant_id]
            if live_grant.consumed or expected[op.grant_id]:
                raise VersionConflict("grant already consumed")
            live = closes[op_id]
            if live.state != CLOSE_AUTHORISED or live.version != op.version:
                raise VersionConflict("close version")
            other = [
                item
                for item in closes.values()
                if item.book_side == live.book_side
                and item.close_operation_id != op_id
                and (
                    item.state in BLOCKING
                    or (item.state in {CLOSE_PARTIALLY_FILLED, CLOSE_FULLY_CONFIRMED} and not item.remainder_reconciled)
                )
            ]
            if other:
                raise VersionConflict("single flight")
            live_grant.consumed = True
            live.state = CLOSE_SUBMITTING
            live.version += 1
            for trade_id in live.trade_ids:
                row = obs_map[_key(ACCOUNT, live.instrument, live.book_side, trade_id)]
                row.pending_close_id = live.close_operation_id
                row.provenance = "CLOSE_AMBIGUOUS"
                row.version += 1

        try:
            self.ledger.commit(mut)
        except (CommitFailed, VersionConflict) as exc:
            self.last_loser = "reread_no_send"
            self.refused.append("presend:" + type(exc).__name__)
            return False
        self.execution_grants.discard(op.grant_id)
        return True

    def simulate_send(self, op_id: str) -> bool:
        if self.recovery_blocked or op_id in self.sent:
            self.refused.append("send:refused")
            return False
        op = self.ledger.closes.get(op_id)
        if op is None or op.state != CLOSE_SUBMITTING:
            self.refused.append("send:not_submitting")
            return False
        self.ledger.broker_wait = True
        try:
            if self.ledger.broker_wait and False:
                self.ledger.commit(lambda *_: None)
            self.sent.add(op_id)
        finally:
            self.ledger.broker_wait = False
        return True

    def fail_next_commit(self) -> None:
        self.ledger.fail_commits += 1

    def record_response(self, op_id: str, body: dict) -> bool:
        op = self.ledger.closes.get(op_id)
        if op is None:
            return False
        kind = str(body.get("kind") or "")
        response_epoch = int(body.get("epoch") or 0)

        def mut(obs_map, _grants, closes) -> None:
            live = closes[op_id]
            if live.state not in {CLOSE_SUBMITTING, CLOSE_OUTCOME_UNKNOWN, CLOSE_RECONCILIATION_REQUIRED}:
                if kind == "duplicate":
                    return
                raise VersionConflict("response not applicable")
            newest = 0
            for trade_id in live.trade_ids:
                row = obs_map.get(_key(ACCOUNT, live.instrument, live.book_side, trade_id))
                if row is not None:
                    newest = max(newest, row.reconcile_epoch)
            if response_epoch and response_epoch < newest and kind == "fill":
                live.state = CLOSE_MANUAL_REVIEW_REQUIRED
                live.attribution = ATTR_UNKNOWN
                live.version += 1
                for trade_id in live.trade_ids:
                    row = obs_map.get(_key(ACCOUNT, live.instrument, live.book_side, trade_id))
                    if row is not None:
                        row.conflict = True
                        row.flat_confirmed = False
                        _recompute(row)
                return
            _classify_into(live, obs_map, body)

        try:
            self.ledger.commit(mut)
        except CommitFailed:
            self.refused.append("response:commit")
            return False
        except VersionConflict:
            self.last_loser = "reread_no_send"
            self.refused.append("response:conflict")
            return False
        return True

    def reconcile(
        self,
        trades: list[dict],
        snapshot_id: str,
        epoch: int,
        complete: bool = True,
        fresh: bool = True,
        timed_out: bool = False,
        side: str = "LONG",
        instrument: str = INSTRUMENT,
    ) -> None:
        def mut(obs_map, _g, closes) -> None:
            relevant = [
                row
                for row in obs_map.values()
                if row.instrument == instrument and row.book_side == side and not row.retired
            ]
            if timed_out or not complete or not fresh:
                for row in relevant:
                    if epoch < row.reconcile_epoch:
                        continue
                    row.snapshot_complete = complete and not timed_out
                    row.snapshot_fresh = False
                    row.conflict = False
                    _recompute(row)
                return
            by_id = {str(item["trade_id"]): D(item["units"]) for item in trades}
            seen_epoch_guard = False
            for row in relevant:
                if epoch < row.reconcile_epoch:
                    seen_epoch_guard = True
                    continue
                reported = by_id.get(row.trade_id)
                row.snapshot_complete = True
                row.snapshot_fresh = True
                row.reconcile_epoch = epoch
                row.snapshot_id = snapshot_id
                if row.management and snapshot_id != row.snapshot_id:
                    row.management = False
                if reported is None:
                    row.exposure_zero_reported = True
                    row.reported_units = D(0)
                elif reported == 0:
                    row.exposure_zero_reported = True
                    row.reported_units = D(0)
                else:
                    row.reported_units = reported
                    row.exposure_zero_reported = False
                    row.broker_units = reported
                    row.conflict = False
                row.management = False
                row.version += 1
                for op in closes.values():
                    if (
                        op.state == CLOSE_AUTHORISED
                        and op.book_side == side
                        and op.snapshot_id != snapshot_id
                        and row.trade_id in op.trade_ids
                    ):
                        op.state = CLOSE_NOT_REQUESTED
                        op.version += 1
                _recompute(row)
            if seen_epoch_guard:
                return

        self.ledger.commit(mut)
        self._strip_management_if_hedged(instrument)
        self._sync_execution_after_snapshot()

    def _sync_execution_after_snapshot(self) -> None:
        drop = []
        for grant_id in list(self.execution_grants):
            grant = self.ledger.grants.get(grant_id)
            op = self.ledger.closes.get(grant.attempt_id) if grant and grant.attempt_id else None
            if grant is None or grant.revoked or grant.consumed or op is None or op.state != CLOSE_AUTHORISED:
                drop.append(grant_id)
        for grant_id in drop:
            self.execution_grants.discard(grant_id)

    def mark_remainder_from_snapshot(self, op_id: str) -> None:
        op = self.ledger.closes.get(op_id)
        if op is None:
            return
        if op.state not in {CLOSE_PARTIALLY_FILLED, CLOSE_FULLY_CONFIRMED}:
            return

        def mut(obs_map, _g, closes) -> None:
            live = closes[op_id]
            for trade_id in live.trade_ids:
                row = obs_map[_key(ACCOUNT, live.instrument, live.book_side, trade_id)]
                if row.reported_units is None or row.reconcile_epoch <= live.response_epoch:
                    raise VersionConflict("remainder not read")
            live.remainder_reconciled = True
            live.version += 1

        try:
            self.ledger.commit(mut)
        except (CommitFailed, VersionConflict):
            self.refused.append("remainder:unconfirmed")

    def apply_trade_closure(
        self,
        trade_id: str,
        closing_tx_id: str | None,
        actor: str = "unknown",
        side: str = "LONG",
        units_closed: str | None = None,
    ) -> None:
        def mut(obs_map, _g, closes) -> None:
            row = obs_map[_key(ACCOUNT, INSTRUMENT, side, trade_id)]
            if not closing_tx_id:
                row.exposure_zero_reported = True
                _recompute(row)
                return
            unresolved = [
                op
                for op in closes.values()
                if trade_id in op.trade_ids and op.state in {CLOSE_SUBMITTING, CLOSE_OUTCOME_UNKNOWN, CLOSE_RECONCILIATION_REQUIRED}
            ]
            row.flat_confirmed = True
            row.broker_units = D(0)
            row.reported_units = D(0)
            row.exposure_zero_reported = True
            row.snapshot_complete = True
            row.snapshot_fresh = True
            row.had_units = True
            if unresolved:
                row.exposure_attribution = ATTR_UNKNOWN
                row.conflict = False
                for op in unresolved:
                    op.state = CLOSE_MANUAL_REVIEW_REQUIRED
                    op.attribution = ATTR_UNKNOWN
                    op.version += 1
            elif actor == "external":
                row.exposure_attribution = ATTR_EXTERNAL
            elif actor == "bot":
                linked = [
                    op
                    for op in closes.values()
                    if trade_id in op.trade_ids and closing_tx_id in op.fill_transaction_ids
                ]
                row.exposure_attribution = ATTR_BOT if linked else ATTR_UNKNOWN
            else:
                row.exposure_attribution = ATTR_UNKNOWN
            _recompute(row)
            _ = units_closed

        self.ledger.commit(mut)

    def conflict_reads(self, trade_id: str = "T1", side: str = "LONG") -> None:
        def mut(obs_map, _g, closes) -> None:
            row = obs_map[_key(ACCOUNT, INSTRUMENT, side, trade_id)]
            row.conflict = True
            row.flat_confirmed = False
            _recompute(row)
            for op in closes.values():
                if trade_id in op.trade_ids and op.state in {
                    CLOSE_FULLY_CONFIRMED,
                    CLOSE_SUBMITTING,
                    CLOSE_OUTCOME_UNKNOWN,
                    CLOSE_RECONCILIATION_REQUIRED,
                }:
                    op.state = CLOSE_MANUAL_REVIEW_REQUIRED
                    op.attribution = ATTR_UNKNOWN
                    op.version += 1

        self.ledger.commit(mut)

    def apply_protection(
        self,
        trade_id: str = "T1",
        side: str = "LONG",
        stop_section_complete: bool = False,
        stop_order_id: str | None = None,
        stop_price: str | None = None,
        fresh: bool = True,
        local_fallback: str | None = None,
    ) -> None:
        def mut(obs_map, _g, _c) -> None:
            row = obs_map[_key(ACCOUNT, INSTRUMENT, side, trade_id)]
            if local_fallback is not None:
                row.local_stop_reference = D(local_fallback)
                row.local_stop_source = "local_fallback"
            if not fresh:
                if row.protection in {PROT_BROKER, PROT_UNPROTECTED} or row.broker_stop_order_id:
                    row.protection = PROT_STALE
                elif row.local_stop_reference is not None:
                    row.protection = PROT_LOCAL
                else:
                    row.protection = PROT_UNKNOWN
                return
            if local_fallback is not None and not stop_section_complete:
                row.protection = PROT_LOCAL
                return
            if not stop_section_complete:
                row.protection = PROT_UNKNOWN
                return
            row.stop_section_complete = True
            if stop_order_id and stop_price is not None:
                row.broker_stop_order_id = stop_order_id
                row.confirmed_broker_stop_price = D(stop_price)
                row.protection = PROT_BROKER
                return
            row.broker_stop_order_id = None
            row.confirmed_broker_stop_price = None
            row.protection = PROT_UNPROTECTED

        self.ledger.commit(mut)

    def restart(self) -> None:
        self.sent.clear()
        self.execution_grants.clear()
        self.process_generation += 1

        def mut(obs_map, grants, closes) -> None:
            for grant in grants.values():
                if grant.scope == "CLOSE" and not grant.consumed:
                    grant.revoked = True
            for op in closes.values():
                if op.state == CLOSE_AUTHORISED:
                    op.state = CLOSE_NOT_REQUESTED
                    op.version += 1
                elif op.state == CLOSE_SUBMITTING:
                    op.state = CLOSE_OUTCOME_UNKNOWN
                    op.attribution = ATTR_UNKNOWN
                    op.version += 1
            for row in obs_map.values():
                row.management = False
                if row.protection in {PROT_BROKER, PROT_UNPROTECTED}:
                    row.protection = PROT_STALE
                elif row.local_stop_reference is not None and not row.broker_stop_order_id:
                    row.protection = PROT_LOCAL
                elif row.protection == PROT_BROKER:
                    row.protection = PROT_STALE

        try:
            self.ledger.commit(mut)
            self.recovery_blocked = False
        except CommitFailed:
            self.recovery_blocked = True
            self.refused.append("restart:commit")

    def rematch_monitor(self, grant_id: str) -> bool:
        grant = self.ledger.grants.get(grant_id)
        if grant is None or grant.scope != "MONITOR" or grant.revoked:
            return False
        return self.grant_monitor(grant.trade_ids, grant.book_side, source="operator") is not None

    def attempt_drop_local(self, trade_id: str = "T1", side: str = "LONG") -> bool:
        obs = self.get(trade_id, side)
        if obs is None:
            return False
        if obs.broker_units > 0 and not obs.flat_confirmed:
            self.refused.append("drop:exposure_remains")
            return False
        return False

    def retire(self, trade_id: str = "T1", side: str = "LONG") -> bool:
        obs = self.get(trade_id, side)
        if obs is None or not self.may_retire(obs):
            self.refused.append("retire:refused")
            return False

        def mut(obs_map, _g, _c) -> None:
            row = obs_map[_key(ACCOUNT, obs.instrument, side, trade_id)]
            if row.version != obs.version:
                raise VersionConflict("retire")
            row.retired = True
            row.version += 1

        try:
            self.ledger.commit(mut)
        except (CommitFailed, VersionConflict):
            self.refused.append("retire:commit")
            return False
        return True

    def may_retire(self, obs: Observation) -> bool:
        if obs.retired or not obs.flat_confirmed or obs.conflict:
            return False
        if not obs.snapshot_fresh or not obs.snapshot_complete:
            return False
        for op in self.side_ops(obs.book_side, obs.instrument):
            if obs.trade_id not in op.trade_ids and op.trade_ids:
                continue
            if op.state in BLOCKING or op.state == CLOSE_MANUAL_REVIEW_REQUIRED:
                return False
            if op.state == CLOSE_PARTIALLY_FILLED and not op.remainder_reconciled:
                return False
            if op.state in {CLOSE_SUBMITTING, CLOSE_OUTCOME_UNKNOWN, CLOSE_RECONCILIATION_REQUIRED}:
                return False
        if obs.pending_close_id:
            op = self.ledger.closes.get(obs.pending_close_id)
            if op is not None and op.state in BLOCKING | {CLOSE_MANUAL_REVIEW_REQUIRED, CLOSE_PARTIALLY_FILLED}:
                return False
        return True

    def stale_cas(self, trade_id: str = "T1", side: str = "LONG") -> str:
        obs = self.get(trade_id, side)
        if obs is None:
            return "missing"
        stale = obs.version
        self.reconcile(
            trades=[{"trade_id": trade_id, "units": str(obs.broker_units)}],
            snapshot_id="S-NEW",
            epoch=obs.reconcile_epoch + 1,
            side=side,
        )

        def mut(obs_map, _g, _c) -> None:
            row = obs_map[_key(ACCOUNT, INSTRUMENT, side, trade_id)]
            if row.version == stale:
                row.broker_units = D(0)
                row.flat_confirmed = True
            else:
                raise VersionConflict("stale observation")

        try:
            self.ledger.commit(mut)
        except VersionConflict:
            self.last_loser = "reread_no_send"
            return "reread_no_send"
        return "wrote"

    def view(self, trade_id: str = "T1", side: str = "LONG") -> dict[str, object]:
        obs = self.get(trade_id, side)
        op = self._focus_op(trade_id, side)
        send_allowed = bool(
            op
            and op.state == CLOSE_SUBMITTING
            and op.close_operation_id not in self.sent
            and not self.recovery_blocked
        )
        execution = False
        if op is not None:
            grant = self.ledger.grants.get(op.grant_id)
            execution = bool(
                grant
                and grant.grant_id in self.execution_grants
                and not grant.consumed
                and not grant.revoked
                and op.state == CLOSE_AUTHORISED
            )
        attribution = ATTR_UNKNOWN
        if op is not None and op.state != CLOSE_NOT_REQUESTED:
            attribution = op.attribution
        elif obs is not None:
            attribution = obs.exposure_attribution
        return {
            "observation": bool(obs is not None and not obs.retired),
            "management": bool(obs is not None and obs.management and not self._both_sides_open()),
            "execution": execution,
            "send_allowed": send_allowed,
            "another_close_blocked": self._blocking_op(side) is not None,
            "exposure": obs.exposure if obs is not None else EXPOSURE_UNKNOWN,
            "close_state": op.state if op is not None else CLOSE_NOT_REQUESTED,
            "attribution": attribution,
            "protection": obs.protection if obs is not None else PROT_UNKNOWN,
            "may_mark_flat": bool(obs is not None and obs.flat_confirmed),
            "may_retire": bool(obs is not None and self.may_retire(obs)),
            "manual_review": bool(op is not None and op.state == CLOSE_MANUAL_REVIEW_REQUIRED),
            "broker_units": str(obs.broker_units) if obs is not None else None,
            "pending_close_id": obs.pending_close_id if obs is not None else None,
            "provenance": obs.provenance if obs is not None else None,
            "exposure_zero_reported": bool(obs is not None and obs.exposure_zero_reported),
            "confirmed_stop": str(obs.confirmed_broker_stop_price) if obs and obs.confirmed_broker_stop_price is not None else None,
            "local_stop": str(obs.local_stop_reference) if obs and obs.local_stop_reference is not None else None,
        }

    def _focus_op(self, trade_id: str, side: str) -> CloseOp | None:
        ranked = []
        for op in self.side_ops(side):
            if trade_id not in op.trade_ids:
                continue
            ranked.append(op)
        if not ranked:
            return None
        ranked.sort(key=lambda item: item.version)
        open_ops = [op for op in ranked if op.state != CLOSE_NOT_REQUESTED]
        return open_ops[-1] if open_ops else ranked[-1]


def grant_id_not_in_process(grant: Grant, book: ReferenceBook) -> bool:
    if grant.grant_id not in book.execution_grants:
        return True
    if grant.process_generation != book.process_generation:
        return True
    return False


def _classify_into(live: CloseOp, obs_map: dict, body: dict) -> None:
    kind = str(body.get("kind") or "")
    if kind in {"timeout", "lost_ack"}:
        live.state = CLOSE_OUTCOME_UNKNOWN
        live.attribution = ATTR_UNKNOWN
        live.version += 1
        _touch_pending(live, obs_map)
        return
    if kind == "duplicate":
        live.version += 1
        return
    if kind == "reject":
        live.state = CLOSE_REJECTED
        live.attribution = ATTR_UNKNOWN
        live.version += 1
        for trade_id in live.trade_ids:
            row = obs_map.get(_key(live.account_id, live.instrument, live.book_side, trade_id))
            if row is not None and row.pending_close_id == live.close_operation_id:
                row.pending_close_id = None
        return
    if kind != "fill":
        live.state = CLOSE_RECONCILIATION_REQUIRED
        live.attribution = ATTR_UNKNOWN
        live.version += 1
        _touch_pending(live, obs_map)
        return
    fill_units = body.get("units")
    trades = body.get("trades_closed")
    fill_tx = str(body.get("fill_tx_id") or "")
    has_cancel = bool(body.get("cancel"))
    if fill_units is None or not isinstance(trades, list) or not fill_tx:
        live.state = CLOSE_RECONCILIATION_REQUIRED
        live.attribution = ATTR_UNKNOWN
        live.version += 1
        _touch_pending(live, obs_map)
        return
    if fill_tx in live.fill_transaction_ids:
        live.version += 1
        return
    parsed: list[tuple[str, Decimal]] = []
    for item in trades:
        if not isinstance(item, dict) or "trade_id" not in item or "units" not in item:
            live.state = CLOSE_RECONCILIATION_REQUIRED
            live.attribution = ATTR_UNKNOWN
            live.version += 1
            return
        trade_id = str(item["trade_id"])
        if trade_id not in live.trade_ids:
            live.state = CLOSE_RECONCILIATION_REQUIRED
            live.attribution = ATTR_UNKNOWN
            live.version += 1
            _touch_pending(live, obs_map)
            return
        parsed.append((trade_id, D(item["units"])))
    filled = D(fill_units)
    summed = sum((units for _trade, units in parsed), D(0))
    if summed != filled or has_cancel and summed == 0:
        live.state = CLOSE_RECONCILIATION_REQUIRED
        live.attribution = ATTR_UNKNOWN
        live.version += 1
        return
    if summed != filled:
        live.state = CLOSE_RECONCILIATION_REQUIRED
        live.version += 1
        return
    live.fill_transaction_ids = tuple(list(live.fill_transaction_ids) + [fill_tx])
    live.units_confirmed = live.units_confirmed + filled
    epochs = [
        obs_map[_key(live.account_id, live.instrument, live.book_side, trade_id)].reconcile_epoch
        for trade_id in live.trade_ids
        if _key(live.account_id, live.instrument, live.book_side, trade_id) in obs_map
    ]
    live.response_epoch = max(epochs) if epochs else int(body.get("epoch") or 0)
    live.attribution = ATTR_BOT
    if live.units_confirmed == live.units_authorised:
        live.state = CLOSE_FULLY_CONFIRMED
    elif D(0) < live.units_confirmed < live.units_authorised:
        live.state = CLOSE_PARTIALLY_FILLED
    else:
        live.state = CLOSE_RECONCILIATION_REQUIRED
        live.attribution = ATTR_UNKNOWN
    live.version += 1
    _touch_pending(live, obs_map)


def _touch_pending(live: CloseOp, obs_map: dict) -> None:
    for trade_id in live.trade_ids:
        row = obs_map.get(_key(live.account_id, live.instrument, live.book_side, trade_id))
        if row is not None and live.state in BLOCKING | {CLOSE_MANUAL_REVIEW_REQUIRED, CLOSE_PARTIALLY_FILLED, CLOSE_FULLY_CONFIRMED}:
            row.pending_close_id = live.close_operation_id


def utc(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)
