"""In-memory simulation only. NOT persistent, process shared, or broker capable."""
from dataclasses import dataclass
from threading import RLock

from exposure_view import Decision, canonical, usd_direction


@dataclass(frozen=True)
class Intent:
    key: str
    slot: tuple[str, str]
    payload: str
    state: str = "RESERVED"


class FakeCoordinator:
    def __init__(self, view: Decision, limit: int = 2, *, clock=lambda: 0.0, deadline=10.0):
        if limit < 0:
            raise ValueError("negative limit")
        self._lock = RLock()
        self.view = view
        self.limit = limit
        self.intents: dict[str, Intent] = {}
        self.generation = view.generation
        self.revision = 0
        self.refreshing = False
        self.failed = False
        self.available = True
        self.clock = clock
        self.deadline = deadline

    def _valid(self):
        return (self.available and self.view.valid and not self.refreshing
                and not self.failed and 0 <= self.clock() <= self.deadline)

    def _slots(self):
        return set(self.view.slots) | {i.slot for i in self.intents.values()}

    def reserve(self, key, symbol, side, payload, *, revision=None):
        with self._lock:
            slot = canonical(symbol), side
            prior = self.intents.get(key)
            if prior:
                return prior if prior.slot == slot and prior.payload == payload else None
            if (not self._valid() or side not in {"BUY", "SELL"}
                    or slot[0] not in {"EUR_USD", "GBP_USD", "AUD_USD", "USD_JPY", "EUR_GBP"}
                    or revision is not None and revision != self.revision):
                return None
            slots = self._slots()
            if any(s[0] == slot[0] and s[1] != side for s in slots):
                return None
            direction = usd_direction(*slot)
            count = sum(usd_direction(*s) == direction for s in slots) if direction else 0
            resulting = sum(usd_direction(*s) == direction for s in slots | {slot}) if direction else 0
            if direction and self.limit and (count >= self.limit or resulting > self.limit):
                return None
            intent = Intent(key, slot, payload)
            self.intents[key] = intent
            self.revision += 1
            return intent

    def dispatch(self, key):
        with self._lock:
            intent = self.intents.get(key)
            if not self._valid() or intent is None or intent.state != "RESERVED":
                return False
            self.intents[key] = Intent(key, intent.slot, intent.payload, "DISPATCHING")
            self.revision += 1
            return True  # no actual transport exists

    def refresh(self):
        with self._lock:
            self.generation += 1
            self.refreshing = True
            self.intents = {k: Intent(k, i.slot, i.payload,
                            "FROZEN" if i.state == "RESERVED" else i.state)
                            for k, i in self.intents.items()}
            self.revision += 1
            return self.generation

    def publish(self, generation, view=None):
        """Complete the active latest refresh once, on success or failure.

        refresh() alone opens a generation. Clearing refreshing consumes that
        completion under the same lock: duplicates and late success after failure
        cannot replace the view, clear failure, or advance the mutation revision.
        """
        with self._lock:
            if (type(generation) is not int or generation < 0
                    or not self.refreshing or generation != self.generation):
                return False
            self.refreshing = False
            self.failed = (
                not isinstance(view, Decision) or not view.valid
                or type(view.generation) is not int or view.generation != generation
                or view.partition != self.view.partition
                or type(view.managed_revision) is not int
                or type(self.view.managed_revision) is not int
                or view.managed_revision < 0
                or view.managed_revision < self.view.managed_revision
            )
            if not self.failed:
                self.view = view
            self.revision += 1
            return not self.failed

    def release_unsent(self, key):
        with self._lock:
            intent = self.intents.get(key)
            if intent is None or intent.state not in {"RESERVED", "FROZEN"}:
                return False
            del self.intents[key]
            self.revision += 1
            return True

    def transfer_fill(self, key, view):
        """Atomically replace one dispatched intent with conservative exposure.

        This fake has no validated terminal-evidence representation. Consequently
        a transfer may add occupied slots but may NEVER remove one. Same-generation
        views must not roll back the managed-book revision. The coordinator's own
        revision is a distinct sequence, advanced only on a successful mutation.
        Caller-supplied evidence remains synthetic, not authenticated broker proof.
        """
        with self._lock:
            intent = self.intents.get(key)
            if (not self._valid() or intent is None or intent.state != "DISPATCHING"
                    or not view.valid or view.partition != self.view.partition
                    or view.generation != self.generation or intent.slot not in view.slots
                    or type(view.managed_revision) is not int
                    or type(self.view.managed_revision) is not int
                    or view.managed_revision < 0
                    or view.managed_revision < self.view.managed_revision
                    or not set(self.view.slots).issubset(view.slots)):
                return False
            self.view = view
            del self.intents[key]
            self.revision += 1
            return True
