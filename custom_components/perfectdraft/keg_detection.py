"""Pure keg-change detection logic — no Home Assistant dependencies.

Kept import-free so the decision logic can be unit-tested standalone,
without a Home Assistant test harness.
"""
from __future__ import annotations

KEG_TOTAL_VOLUME = 6.0  # litres — a full keg
KEG_NEW_VOLUME_THRESHOLD = 5.5  # litres — "near full" for the pour-reset signal

# Volume-jump thresholds, expressed as percent of a full keg.
KEG_REFILL_LOW_PCT = 80  # previous level below this counts as "low" (4.8 L)
KEG_REFILL_FULL_PCT = 95  # current level at/above this counts as "near full" (5.7 L)
KEG_JUMP_PCT = 50  # an upward step at least this large implies a swap (3.0 L)


def detect_keg_change(
    *,
    last_pours: int | None,
    last_volume: float | None,
    pours: int,
    volume: float,
) -> bool:
    """Return True when the readings indicate a fresh keg was inserted.

    Any single trigger is sufficient:
      (a) pour counter reads 0 while the keg is near full (the original signal);
      (b) remaining volume jumped from below 80% to at least 95% of capacity;
      (c) remaining volume jumped up by at least 50 percentage points.

    Triggers (b) and (c) compare against the previous reading, so they are
    skipped on the first reading after install/restart (``last_volume is None``)
    to avoid a false positive.
    """
    # (a) Pour-reset signal — unchanged from the original behaviour.
    if pours == 0 and volume > KEG_NEW_VOLUME_THRESHOLD and last_pours != 0:
        return True

    if last_volume is None:
        return False

    pct = volume / KEG_TOTAL_VOLUME * 100
    last_pct = last_volume / KEG_TOTAL_VOLUME * 100

    # (b) Refilled to near-full from a low level.
    if last_pct < KEG_REFILL_LOW_PCT and pct >= KEG_REFILL_FULL_PCT:
        return True

    # (c) Large upward jump in remaining volume.
    if pct - last_pct >= KEG_JUMP_PCT:
        return True

    return False
