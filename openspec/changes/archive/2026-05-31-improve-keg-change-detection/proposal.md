## Why

Keg-change detection currently fires only when `numberOfPoursSinceStartup` resets to 0 while `kegVolume` is near full. This misses a common real-world case: the user swaps the keg and immediately pours a beer, so by the first poll the pour count is already 1 and the reset is never observed. The result is a stale freshness countdown and no reliable way to correct it.

## What Changes

- **Add volume-based detection triggers** to the keg freshness sensor, so a keg change is recognized even when the pour count never reads 0. A change is detected when ANY of these hold:
  - (a) the existing signal: pour count resets to 0 AND volume is near full (unchanged);
  - (b) remaining volume jumps from below 80% to near full (≥95%);
  - (c) remaining volume jumps up by at least 50 percentage points between two readings.
- **Track previous keg volume** across updates (in addition to previous pour count) and persist it via the existing `RestoreEntity` attributes, since triggers (b) and (c) compare consecutive readings.
- **Add a manual "Mark Keg Changed" button** entity that, when pressed, records the current time as the keg insertion timestamp — a deterministic fallback for when automatic detection still misses or misfires.
- **Register the `button` platform** for the integration (currently only `sensor` is registered).
- **Add entity name translations** for the new button in `strings.json` and `translations/en.json`.

## Capabilities

### New Capabilities
<!-- None. The new button is an entity within the existing `entities` capability. -->

### Modified Capabilities
- `entities`: Extend the **Keg freshness sensor** requirement with two additional volume-jump detection triggers and previous-volume persistence; add a new **Manual keg-change button** requirement.

## Impact

- **Modified**: `custom_components/perfectdraft/sensor.py` — add volume-jump detection branches and `last_volume` tracking/restore in `PerfectDraftKegFreshnessSensor`; expose a method/signal handler to set the insertion timestamp on demand.
- **New file**: `custom_components/perfectdraft/button.py` — `PerfectDraftKegResetButton` entity.
- **Modified**: `custom_components/perfectdraft/const.py` — add `"button"` to `PLATFORMS` and detection threshold constants.
- **Modified**: `custom_components/perfectdraft/strings.json` and `translations/en.json` — add the button name under `entity.button`.
- **No breaking changes**: Existing config entries, sensors, and the persisted insertion date continue to work. Detection only adds new ways to trigger; it never moves the insertion date backward.
