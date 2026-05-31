## Context

`PerfectDraftKegFreshnessSensor` (in `sensor.py`) detects a new keg inside `_handle_coordinator_update` using a single signal:

```python
is_new_keg = pours == 0 and float(volume) > KEG_NEW_VOLUME_THRESHOLD and self._last_pours != 0
```

It tracks only `self._last_pours` and persists `keg_inserted_at` + `last_pours` via `RestoreEntity` state attributes. The integration registers only the `sensor` platform (`PLATFORMS = ["sensor"]`).

The detection gap: `numberOfPoursSinceStartup` counts pours since the machine powered on, not since keg insertion. If the user swaps a keg and pours immediately, the first poll already shows `pours >= 1`, so the `pours == 0` branch never fires and the countdown stays stale with no way to correct it.

`kegVolume` is reported in litres against a 6.0 L full keg. It only ever decreases while a keg is in use; a meaningful upward step implies a physical swap (or refill). That makes volume a more reliable change signal than the pour counter.

## Goals / Non-Goals

**Goals:**
- Detect a keg change from volume movement alone, independent of the pour counter.
- Give the user a deterministic manual override that sets "keg changed = now".
- Persist the extra tracking state so detection survives HA restarts.
- No false-backward moves: a detected/forced change only ever sets the insertion date to *now*.

**Non-Goals:**
- Changing the 30-day freshness window or the keg-remaining percentage sensor.
- Detecting partial top-ups or distinguishing keg *brand* changes (the API exposes no per-keg identity).
- Migrating existing persisted state (new attributes default safely when absent).

## Decisions

### D1: Volume-jump triggers in addition to the existing pour-reset signal

Detection becomes an OR of three triggers, evaluated each coordinator update once a previous volume reading exists. Let `pct = kegVolume / 6.0 * 100` and `last_pct` be the previous reading's percentage.

- **(a) Pour reset (unchanged):** `pours == 0` AND `kegVolume > 5.5 L` (~92%) AND `last_pours != 0`.
- **(b) Refill to near-full:** `last_pct < 80` AND `pct >= 95`.
- **(c) Large upward step:** `pct - last_pct >= 50`.

Thresholds as litres for implementation: 80% = 4.8 L, 95% = 5.7 L, 50 points = 3.0 L.

**Rationale:** (b) and (c) are volume-only, so they catch the "swap then pour immediately" case that defeats (a). The two volume triggers overlap deliberately: (b) catches swaps that land near-full even from a moderate level (e.g. 79%→96%), while (c) catches any large jump even if it doesn't reach near-full (e.g. 12%→70%). Keeping (a) preserves the existing, already-deployed behavior.

### D2: "Jump up at least 50%" means 50 percentage points of total capacity, not a relative increase

Interpreted as absolute capacity points (`pct - last_pct >= 50`, i.e. a ≥3.0 L gain), not `pct >= 1.5 * last_pct`.

**Rationale:** A relative rule false-triggers off a near-empty base (2%→3% is a 50% relative jump but physically meaningless). An absolute 3.0 L gain cannot happen without a physical keg swap, so it is both unambiguous and noise-proof. *This is the one interpretation choice in the request; flagged here for review.*

### D3: Track and persist previous volume

Add `self._last_volume` (litres) alongside `self._last_pours`, update it at the end of every `_handle_coordinator_update`, and add it to the restored/exposed state attributes (`last_volume`). On first reading after install/restart, `last_volume` is `None` and triggers (b)/(c) are skipped (no baseline to compare).

**Rationale:** Triggers (b)/(c) need the prior reading. Persisting it avoids a spurious detection on the first poll after every restart.

### D4: Manual control is a `button` entity, not a service

Add a `button` platform with one entity, "Mark Keg Changed". Pressing it records `now()` as the insertion date.

**Alternatives considered:**
- *A `mark_keg_changed` service* (matches the existing `set_poll_interval_seconds` service pattern): rejected as the primary UX because a service is not a visible "control" — it requires Developer Tools or an automation. A button appears directly on the device page and is one tap from a dashboard, matching the user's request for a manual control "as of now".

**Rationale:** A `ButtonEntity` is the idiomatic HA primitive for a stateless "do this now" action and is trivially usable from dashboards and automations.

### D5: Button → sensor coupling via dispatcher signal

The button and freshness sensor are separate entities under the same config entry. The button calls `async_dispatcher_send(hass, f"{DOMAIN}_keg_changed_{machine_id}")`; the freshness sensor subscribes in `async_added_to_hass` (registered through `self.async_on_remove(...)`) and, on receipt, sets `_keg_inserted_at = now()`, rebaselines `_last_pours`/`_last_volume` to current readings, and writes state.

**Alternatives considered:**
- *Shared mutable state on the coordinator*: viable, but couples unrelated concerns into the coordinator and still needs the sensor to react. The dispatcher keeps entities loosely coupled and is the established HA pattern for cross-entity signalling.

### D6: Idempotency and re-trigger guard

A detection/override only ever sets the insertion date to `now()`; it never moves it earlier. After any trigger fires, the baseline (`_last_pours`, `_last_volume`) is updated to the current reading so the same event cannot re-fire on the next poll. Because volume only decreases during use, (b)/(c) will not re-trigger until the next real swap.

## Risks / Trade-offs

- **Volume sensor noise or reconnection blips** → Could a transient high reading after an offline period look like a jump? Mitigation: the thresholds (a ≥15-point rise landing ≥95% for (b), or a ≥50-point rise for (c)) are far larger than measurement jitter, and the first post-restart reading is skipped (no baseline). Residual misfires are correctable and harmless (they only refresh the countdown).
- **Manual button pressed while the keg is unchanged** → It will reset the countdown. Accepted: it is an explicit user action and the button label makes intent clear.
- **Button press before the freshness sensor has loaded** → The dispatcher signal is fire-and-forget; if no subscriber is connected the press is a no-op. Mitigation: both entities are created during the same config-entry setup, so the window is negligible; the user can press again.
- **Overlap between (b) and (c)** → Both may match the same update. Harmless under D6 (single set to `now()`, then rebaseline).
