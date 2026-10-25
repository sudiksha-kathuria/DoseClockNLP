# Ayush: ESP32 flashing and physical tests

Prepared 25 October 2026. These are future instructions, not executed hardware
results. No flashing, staging, commit or push occurred during this validation.

## Prepare and build

- Confirm the board is the documented classic ESP32/WROOM-32. The verified target
  is `esp32dev`; a C3/S3/other board needs its own verified configuration.
- Use the latest working source on `validation/review3-20261023`, including
  `switch_hub.ino`, `switch_input.h` and `platformio.ini`. HEAD alone lacks the
  uncommitted changes. Use a disposable Flask database and dummy accounts.
- In a private copy, fill the four sketch constants: SSID, password, reachable
  Flask host and a token paired from the intended account's Logs screen.
  The validation binary contains placeholders and is not a configured upload.
- Use PlatformIO Core 6.2.0 with the supplied pins: Espressif32 6.9.0 / Arduino
  ESP32 2.0.17 / ArduinoJson 7.4.3. Build before any upload; require `SUCCESS`
  and a new nonempty `.pio/build/esp32dev/firmware.bin`.

Example from the repository root (Unix shell; file-copy equivalents work on Windows):

```sh
mkdir -p hardware/private/ayush
cp hardware/switch_hub.ino hardware/switch_input.h hardware/platformio.ini hardware/private/ayush/
# Edit credentials/host/token only in hardware/private/ayush/switch_hub.ino.
pio run --project-dir hardware/private/ayush --environment esp32dev
```

`hardware/private/` and `.pio/` are ignored. Do not share or commit configured
sketches, tokens, session keys, real databases or raw HTTP captures.

## Flash only after approval

- Keep GPIO4 connected to switch tip and GND to sleeve. Confirm the actual
  board's LED pin (configured GPIO2). Identify its serial port with `pio device list`.
- After approval, Ayush can upload the private build and monitor at 115200 baud:

```sh
pio run --project-dir hardware/private/ayush --environment esp32dev --target upload --upload-port PORT
pio device monitor --port PORT --baud 115200
```

Replace `PORT` with the verified device port. Record board/revision, source
hashes, configured binary hash, compiler versions, date and tester. Do not erase
NVS blindly: a valid pending action may need its original identity replayed.

## Acceptance checks using dummy reminders

Start Flask on port 5050 and create two distinguishable reminders due together
for the paired account. Keep another account's reminder due for isolation.
Record IDs, `last_fired_at`, due flags, dose-log counts and Snooze deadlines.

| Check | Required result |
| --- | --- |
| Boot with switch held | No action; stable release >=50 ms and a fresh press required. Three boot blinks mean Wi-Fi connected; check Serial for blocked queue/storage errors. |
| Short press | <600 ms after the 50 ms press debounce: one Taken action/log for selected A; B and the other account unchanged. |
| Intermediate press | 600–1499 ms after press debounce: no action. |
| Hold | >=1500 ms after press debounce: steady LED, release to Snooze A for five minutes; no Taken log; B unchanged. Release debounce must not change the classification. |
| Retry overlap | Hold a successful action response for >3 seconds; press/hold during the retry. The gesture must be discarded, not become Taken/Snooze on B when the retry completes. B needs a new stable release and new press. |
| Lost response / reboot | Same action/ID/firing/request ID on every retry, including after ESP32 and Flask restarts; one effect only. Repeated Snooze must not extend its deadline. |
| Stale selection | Resolve selected A in the browser before forwarding its device action: 409 for A, no automatic retargeting to B. |
| Outages | No success while disconnected. Once a firing is saved, retry only that identity after reconnection. A press before selection while offline is not queued. |
| Corrupt recovery | On a deliberately corrupted disposable test queue, no action POST. Send the exact USB command below: clear state only, then require release/new press. EN alone must retain the fault; failed clearing stays blocked. |
| Valid pending recovery refusal | `CLEAR CORRUPT RETRY` must not discard a valid uncertain action. |

For repeatable lost-response/stale-selection tests, optionally put mitmweb in
front of Flask and point only the private firmware host at laptop port 5051:

```sh
mitmweb --mode reverse:http://127.0.0.1:5050 --listen-host 0.0.0.0 --listen-port 5051
```

Set Intercept filter `~s & ~u /api/device/action` to hold responses after Flask
commits. Clear it to let the next retry receive its receipt. Use
`~q & ~u /api/device/action` to hold requests before Flask receives them, resolve
A through the browser directly on port 5050, then clear interception and observe
409. Redact bearer tokens. Never change the IDs to manufacture a retry.

At 115200 baud, Serial logs show `Bound action <action> id=<id> fired_at=<stamp>
request_id=<key> responded <status>`. Expect 200 with Flask `success:true` for
first application or exact replay, 409 for stale firing, 401 for invalid pairing,
and 400 for legacy/malformed action payloads. A selected transport/5xx failure
must log uncertainty and retain the same binding. Verify Flask JSON and database
state as well as status/LED feedback.

USB recovery requires Serial Monitor's **Newline** setting and exactly:

```text
CLEAR CORRUPT RETRY
```

Only invalid data is eligible. Successful recovery logs `Corrupt retry cleared;
no action sent. Release switch, then press anew.` Check server receipts/history
before a new intentional action: corruption can leave the earlier outcome
unknown. Do not introduce corruption into a real/patient board. Controlled
corruption/persistence-failure injection requires a separate disposable bench
setup; no corruption tool is included in the production sketch.

Read-only observations against the dummy database:

```sh
sqlite3 -readonly backend/schedules.db <<'SQL'
.headers on
SELECT id, medicine_name, user_id, is_due, last_fired_at,
       snoozed_until, days_remaining FROM medicines ORDER BY id;
SELECT medicine_id, COUNT(*) FROM dose_log GROUP BY medicine_id;
SELECT device_id, request_id, medicine_id, fired_at, action FROM device_action_receipts;
SQL
```

Keep a dated checklist with actual serial/Flask/DB results and sanitized captures.
Do not label host simulations, compilation or the earlier old-firmware physical
test as this updated firmware's physical acceptance. Human audio delivery,
pronunciation and microphone use also require separate evidence.
