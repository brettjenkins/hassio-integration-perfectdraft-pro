## MODIFIED Requirements

### Requirement: Keg freshness sensor
The integration SHALL track keg freshness as a 30-day countdown from insertion, detected client-side and persisted across restarts. A keg change SHALL be detected by monitoring the coordinator data for a pour-count reset OR an upward jump in keg volume between consecutive readings, so that a swap is recognized even when the pour count never reads 0 (e.g. the user pours immediately after swapping).

#### Scenario: New keg detected via pour reset
- **WHEN** `details.numberOfPoursSinceStartup` is 0 AND `details.kegVolume` is greater than 5.5L AND the previous pour count was not 0
- **THEN** the sensor SHALL record the current UTC timestamp as the keg insertion date

#### Scenario: New keg detected via refill to near-full
- **WHEN** a previous volume reading exists AND the previous remaining volume was below 80% of capacity AND the current remaining volume is at least 95% of capacity
- **THEN** the sensor SHALL record the current UTC timestamp as the keg insertion date

#### Scenario: New keg detected via large volume jump
- **WHEN** a previous volume reading exists AND the current remaining volume exceeds the previous remaining volume by at least 50 percentage points of capacity (a gain of at least 3.0L)
- **THEN** the sensor SHALL record the current UTC timestamp as the keg insertion date

#### Scenario: No false trigger on first reading
- **WHEN** the integration produces its first volume reading after install or restart and no previous volume reading is available
- **THEN** the volume-jump triggers SHALL NOT fire

#### Scenario: Detection never moves the date backward
- **WHEN** any detection trigger fires
- **THEN** the sensor SHALL set the insertion date to the current time only
- **THEN** the sensor SHALL update its tracked previous pour count and previous volume to the current readings so the same event does not re-trigger on the next update

#### Scenario: Freshness countdown
- **WHEN** a keg insertion date is known
- **THEN** the sensor SHALL report `30 - days_since_insertion`, minimum 0
- **THEN** it SHALL have unit d and icon mdi:calendar-clock

#### Scenario: No insertion date known
- **WHEN** no keg insertion has been detected since the integration was installed
- **THEN** the sensor SHALL report as unavailable

#### Scenario: HA restart
- **WHEN** Home Assistant restarts
- **THEN** the sensor SHALL restore the keg insertion date, last pour count, and last volume from the previous session's state attributes

## ADDED Requirements

### Requirement: Manual keg-change button
The integration SHALL expose a button entity that, when pressed, records the current time as the keg insertion date, providing a deterministic manual override for keg-change detection.

#### Scenario: Button press records insertion
- **WHEN** the user presses the "Mark Keg Changed" button
- **THEN** the keg freshness sensor SHALL set the keg insertion date to the current UTC timestamp
- **THEN** the freshness countdown SHALL report 30 days

#### Scenario: Override rebaselines detection
- **WHEN** the button is pressed
- **THEN** the sensor SHALL update its tracked previous pour count and previous volume to the latest readings so automatic detection does not immediately re-fire

#### Scenario: Button entity presentation
- **WHEN** entities are created
- **THEN** the integration SHALL register the `button` platform
- **THEN** the button SHALL belong to the same device as the machine's sensors
- **THEN** the button SHALL have a stable unique ID following the `{machine_id}_{entity_key}` pattern and a translated name "Mark Keg Changed"
