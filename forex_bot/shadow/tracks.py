"""Explicit research-track labels. Never mix Track A and Track B statistics."""

from __future__ import annotations

TRACK_A = "A"
TRACK_B = "B"
TRACK_A_LABEL = "ORIGINAL_BOT_REPLAY"
TRACK_B_LABEL = "EXPERIMENTAL_HEURISTIC"


class TrackMixError(ValueError):
    """Raised when Track A and Track B results are combined."""


def assert_single_track(track: str, expected: str) -> None:
    if track != expected:
        raise TrackMixError(f"expected track {expected}, got {track}")


def refuse_mixed_stats(tracks: list[str]) -> None:
    uniq = {t for t in tracks if t}
    if len(uniq) > 1:
        raise TrackMixError("Track A and Track B statistics must not be combined")
