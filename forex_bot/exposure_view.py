"""Pure R.87C offline design model. No production imports or authority grants.

Evidence is supplied by a caller; this module cannot authenticate broker claims.
Production policy has no approved default. No existing caller uses this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, order=True)
class Partition:
    venue: str
    environment: str
    account: str


@dataclass(frozen=True)
class Row:
    partition: Partition
    symbol: str
    side: str
    units: float
    trade_ids: tuple[str, ...] = ()
    kind: str = "observation"
    observation_only: bool = True


@dataclass(frozen=True)
class Policy:
    # None is deliberately fail closed; fixture approval is not broker evidence.
    budget: float | None = None
    continuity_verified: bool = False
    single_writer_verified: bool = False
    symbols: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Snapshot:
    partition: Partition
    generation: int
    latest_generation: int
    started: float
    accepted: float
    rows: tuple[Row, ...] = ()
    status: str = "COMPLETE"
    watermark: int | None = None
    epoch: str = ""
    cut_verified: bool = False
    pending: tuple[Row, ...] | None = None


@dataclass(frozen=True)
class Event:
    partition: Partition
    epoch: str
    sequence: int
    action: str  # OPEN/CLOSE; simplified full-slot events, not a broker adapter
    row: Row


@dataclass(frozen=True)
class Coverage:
    events: tuple[Event, ...] = ()
    through: int | None = None
    verified: bool = False


@dataclass(frozen=True)
class Decision:
    valid: bool
    reason: str
    partition: Partition
    generation: int
    managed_revision: int
    age: float | None
    slots: tuple[tuple[str, str], ...] = ()
    provenance: tuple[tuple[str, str, str], ...] = ()

    def count(self, direction: str) -> int | None:
        if not self.valid:
            return None
        return sum(usd_direction(*slot) == direction for slot in self.slots)


def canonical(symbol: str) -> str:
    return symbol.upper().replace("/", "_").replace("-", "_")


def _finite_number(value: object) -> bool:
    """Accept only finite builtin int/float values, without coercion.

    bool is deliberately excluded. Huge integers can overflow math.isfinite's
    float conversion; this validation helper must never leak that exception.
    Decimal, complex, strings and arbitrary numeric objects need an adapter.
    """
    if type(value) not in (int, float):
        return False
    try:
        return isfinite(value)
    except OverflowError:
        return False


def _nonnegative_integer(value: object) -> bool:
    return type(value) is int and value >= 0


def usd_direction(symbol: str, side: str) -> str | None:
    base, quote = canonical(symbol).split("_")
    if quote == "USD":
        return "LONG" if side == "SELL" else "SHORT"
    if base == "USD":
        return "LONG" if side == "BUY" else "SHORT"
    return None


def row_key(row: Row, partition: Partition, policy: Policy) -> tuple[str, str]:
    if row.partition != partition:
        raise ValueError("PARTITION_MISMATCH")
    symbol = canonical(row.symbol)
    if (symbol not in policy.symbols or len(symbol.split("_")) != 2
            or row.side not in {"BUY", "SELL"}
            or not _finite_number(row.units) or row.units < 0
            or any(not isinstance(t, str) or not t for t in row.trade_ids)
            or len(set(row.trade_ids)) != len(row.trade_ids)):
        raise ValueError("SNAPSHOT_MALFORMED")
    return symbol, row.side


def evaluate(partition: Partition, snapshot: Snapshot | None, *, now: float,
             policy: Policy = Policy(), managed: tuple[Row, ...] = (),
             managed_revision: int = 0, coverage: Coverage = Coverage()) -> Decision:
    """Validate immutable synthetic evidence. Never mutates or adopts a row.

    Sequence adjacency here is a synthetic protocol, NOT an assertion that OANDA
    transaction IDs are contiguous. A real adapter must establish coverage itself.
    """
    generation = snapshot.generation if snapshot else -1
    age = None

    def deny(reason: str) -> Decision:
        return Decision(False, "EXPOSURE_" + reason, partition, generation,
                        managed_revision, age)

    if not all((partition.venue, partition.environment, partition.account)):
        return deny("PARTITION_MISMATCH")
    if policy.budget is None:
        return deny("FRESHNESS_POLICY_UNAPPROVED")
    if not _finite_number(policy.budget) or policy.budget < 0:
        return deny("FRESHNESS_POLICY_UNAPPROVED")
    if not policy.single_writer_verified:
        return deny("WRITER_UNPROVEN")
    if not snapshot:
        return deny("SNAPSHOT_MISSING")
    if snapshot.partition != partition:
        return deny("PARTITION_MISMATCH")
    if snapshot.status != "COMPLETE":
        return deny("SNAPSHOT_" + snapshot.status)
    if not all(_nonnegative_integer(v) for v in (
            snapshot.generation, snapshot.latest_generation, managed_revision)):
        return deny("SNAPSHOT_MALFORMED")
    if ((snapshot.watermark is not None and not _nonnegative_integer(snapshot.watermark))
            or (coverage.through is not None and not _nonnegative_integer(coverage.through))):
        return deny("ORDERING_UNPROVEN")
    if snapshot.generation != snapshot.latest_generation:
        return deny("VIEW_CHANGED")
    if not all(_finite_number(v) for v in (now, snapshot.started, snapshot.accepted)):
        return deny("SNAPSHOT_STALE")
    age = now - snapshot.started
    if snapshot.accepted < snapshot.started or now < snapshot.accepted or not 0 <= age <= policy.budget:
        return deny("SNAPSHOT_STALE")
    if not policy.continuity_verified:
        return deny("ORDERING_UNPROVEN")
    if snapshot.pending is None:
        return deny("PENDING_EXPOSURE_UNKNOWN")
    # External pending intents require an identity/link adapter. This prototype
    # deliberately refuses to assume they are covered by local reservations.
    if snapshot.pending:
        return deny("PENDING_EXPOSURE_UNRESOLVED")
    slots: dict[tuple[str, str], Row] = {}
    sources: dict[tuple[str, str], str] = {}
    identities: dict[str, tuple[str, str]] = {}

    def install(row: Row, source: str, *, duplicate: bool = False) -> None:
        key = row_key(row, partition, policy)
        if row.kind != "observation" or not row.observation_only:
            raise ValueError("IDENTITY_CONFLICT")
        if duplicate and any(s[0] == key[0] for s in slots):
            raise ValueError("SNAPSHOT_MALFORMED")
        if row.units == 0:
            return
        if any(s[0] == key[0] and s != key for s in slots):
            raise ValueError("IDENTITY_CONFLICT")
        for trade in row.trade_ids:
            if trade in identities and identities[trade] != key:
                raise ValueError("IDENTITY_CONFLICT")
            identities[trade] = key
        slots[key], sources[key] = row, source

    try:
        seen: set[str] = set()
        for row in snapshot.rows:
            symbol = canonical(row.symbol)
            if symbol in seen:
                raise ValueError("SNAPSHOT_MALFORMED")
            seen.add(symbol)
            install(row, "snapshot", duplicate=True)
        if coverage.events or coverage.through is not None:
            if (not snapshot.cut_verified or snapshot.watermark is None
                    or not snapshot.epoch or not coverage.verified
                    or coverage.through is None or coverage.through < snapshot.watermark):
                raise ValueError("ORDERING_UNPROVEN")
            expected = snapshot.watermark + 1
            for event in coverage.events:
                if (event.partition != partition or event.epoch != snapshot.epoch
                        or not _nonnegative_integer(event.sequence)
                        or event.sequence != expected):
                    raise ValueError("ORDERING_UNPROVEN")
                expected += 1
                key = row_key(event.row, partition, policy)
                if event.action == "OPEN":
                    # No trade-level lifecycle model exists. An OPEN must never
                    # replace an occupied slot: CLOSE of the new trade would
                    # otherwise erase earlier still-open trades from exposure.
                    if key in slots:
                        raise ValueError("IDENTITY_CONFLICT")
                    install(event.row, "event")
                elif event.action == "CLOSE" and key in slots and slots[key] == event.row:
                    del slots[key]
                    sources.pop(key)
                else:
                    raise ValueError("IDENTITY_CONFLICT")
            if expected - 1 != coverage.through:
                raise ValueError("ORDERING_UNPROVEN")
        for row in managed:
            if row.kind in {"paper", "simulated", "window_paper"}:
                continue
            key = row_key(row, partition, policy)
            if row.units == 0:
                continue
            if row.kind != "managed" or row.observation_only or key not in slots:
                raise ValueError("IDENTITY_CONFLICT")
            broker = slots[key]
            if row.units != broker.units or not set(row.trade_ids) <= set(broker.trade_ids):
                raise ValueError("IDENTITY_CONFLICT")
            sources[key] += "+managed"
    except ValueError as exc:
        return deny(str(exc))
    except (TypeError, AttributeError, OverflowError):
        return deny("SNAPSHOT_MALFORMED")
    return Decision(True, "OK", partition, generation, managed_revision, age,
                    tuple(sorted(slots)), tuple((*k, sources[k]) for k in sorted(slots)))
