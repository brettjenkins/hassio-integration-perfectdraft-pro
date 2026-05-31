"""Unit tests for the pure keg-change detection logic.

Runs with the stdlib only (no Home Assistant): the logic under test lives
in ``keg_detection.py`` which has no Home Assistant imports.
"""
import os
import sys
import unittest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "custom_components", "perfectdraft"),
)

from keg_detection import KEG_TOTAL_VOLUME, detect_keg_change  # noqa: E402


def litres(pct: float) -> float:
    """Convert a remaining percentage to litres against a full keg."""
    return pct / 100 * KEG_TOTAL_VOLUME


class TestKegDetection(unittest.TestCase):
    # --- Trigger (a): pour reset + near full ---
    def test_pour_reset_near_full(self):
        self.assertTrue(
            detect_keg_change(last_pours=12, last_volume=0.2, pours=0, volume=5.9)
        )

    def test_pour_reset_but_empty_is_not_a_change(self):
        self.assertFalse(
            detect_keg_change(last_pours=12, last_volume=5.9, pours=0, volume=0.3)
        )

    # --- Trigger (b): below 80% jumping to >= 95% ---
    def test_refill_to_near_full(self):
        self.assertTrue(
            detect_keg_change(
                last_pours=5, last_volume=litres(30), pours=6, volume=litres(96)
            )
        )

    def test_refill_from_just_below_80(self):
        self.assertTrue(
            detect_keg_change(
                last_pours=5, last_volume=litres(79), pours=5, volume=litres(96)
            )
        )

    def test_moderate_rise_not_reaching_95_and_under_50_jump(self):
        # 30% -> 70%: not (b) [<95] and jump is only 40 points -> no change
        self.assertFalse(
            detect_keg_change(
                last_pours=5, last_volume=litres(30), pours=5, volume=litres(70)
            )
        )

    # --- Trigger (c): >= 50 percentage-point jump ---
    def test_large_jump_below_95(self):
        # 12% -> 70%: jump of 58 points fires (c) even though it lands below 95%
        self.assertTrue(
            detect_keg_change(
                last_pours=5, last_volume=litres(12), pours=5, volume=litres(70)
            )
        )

    def test_swap_then_immediate_pour(self):
        # The motivating case: pour count never reads 0 (it's 1), but volume
        # jumps from ~5% to ~92% -> (c) catches it.
        self.assertTrue(
            detect_keg_change(
                last_pours=20, last_volume=litres(5), pours=1, volume=litres(92)
            )
        )

    # --- No-baseline guard ---
    def test_first_reading_no_volume_baseline(self):
        self.assertFalse(
            detect_keg_change(last_pours=3, last_volume=None, pours=4, volume=5.9)
        )

    def test_first_reading_full_keg_pours_zero_still_fires_a(self):
        # Preserves original behaviour: a fresh full keg seen first, pours 0.
        self.assertTrue(
            detect_keg_change(last_pours=None, last_volume=None, pours=0, volume=5.9)
        )

    # --- Normal operation: no false positives ---
    def test_normal_pour_decrease(self):
        self.assertFalse(
            detect_keg_change(last_pours=5, last_volume=5.0, pours=6, volume=4.7)
        )

    def test_small_upward_noise(self):
        # +10 points, lands at 60%: neither (b) nor (c)
        self.assertFalse(
            detect_keg_change(
                last_pours=5, last_volume=litres(50), pours=5, volume=litres(60)
            )
        )


if __name__ == "__main__":
    unittest.main()
