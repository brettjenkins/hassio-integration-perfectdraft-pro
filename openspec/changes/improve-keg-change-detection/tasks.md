## 1. Detection constants and platform registration

- [ ] 1.1 In `const.py`, add detection thresholds: `KEG_REFILL_LOW_PCT = 80`, `KEG_REFILL_FULL_PCT = 95`, `KEG_JUMP_PCT = 50` (document litre equivalents 4.8 / 5.7 / 3.0 L against the 6.0 L keg)
- [ ] 1.2 In `const.py`, add `"button"` to `PLATFORMS`

## 2. Volume-based detection in the freshness sensor

- [ ] 2.1 In `sensor.py`, add `self._last_volume: float | None = None` to `PerfectDraftKegFreshnessSensor.__init__`
- [ ] 2.2 Restore `last_volume` from state attributes in `async_added_to_hass` (alongside `keg_inserted_at` and `last_pours`)
- [ ] 2.3 Expose `last_volume` in `extra_state_attributes`
- [ ] 2.4 In `_handle_coordinator_update`, compute current/previous percentages and add trigger (b): `last_pct < KEG_REFILL_LOW_PCT AND pct >= KEG_REFILL_FULL_PCT`
- [ ] 2.5 Add trigger (c): `pct - last_pct >= KEG_JUMP_PCT`; keep existing trigger (a) unchanged; OR the three triggers, guarding (b)/(c) on `self._last_volume is not None`
- [ ] 2.6 On any trigger, set `_keg_inserted_at = now()`; always update `_last_pours` and `_last_volume` to current readings at the end of the handler so events do not re-fire

## 3. Manual keg-change button

- [ ] 3.1 Create `button.py` with `async_setup_entry` adding one `PerfectDraftKegResetButton` (CoordinatorEntity), `_attr_has_entity_name = True`, `translation_key = "mark_keg_changed"`, unique ID `{machine_id}_mark_keg_changed`, shared `DeviceInfo`
- [ ] 3.2 In `async_press`, send `async_dispatcher_send(hass, f"{DOMAIN}_keg_changed_{machine_id}")`
- [ ] 3.3 In `sensor.py`, subscribe the freshness sensor to that signal in `async_added_to_hass` via `self.async_on_remove(async_dispatcher_connect(...))`; on receipt set `_keg_inserted_at = now()`, rebaseline `_last_pours`/`_last_volume` to current readings, and call `async_write_ha_state()`

## 4. Translations

- [ ] 4.1 Add `entity.button.mark_keg_changed.name = "Mark Keg Changed"` to `strings.json`
- [ ] 4.2 Mirror the same entry in `translations/en.json`

## 5. Build and verify

- [ ] 5.1 Syntax-check all modified/new files
- [ ] 5.2 Unit-test the three detection triggers and the no-baseline guard against representative `(last_pours, last_volume) → (pours, volume)` transitions (incl. the "swap then immediate pour" case: pours 1, volume jump)
- [ ] 5.3 Build zip, deploy to HA: verify the button appears on the device, pressing it resets the freshness countdown to 30, and a simulated volume jump sets the insertion date (manual — user)
- [ ] 5.4 Bump `manifest.json` version and commit
