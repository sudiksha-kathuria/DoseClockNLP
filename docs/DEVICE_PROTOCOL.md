# Device actions bound to one reminder firing

Contract established 23 October 2026, after the original October 9 Review 3;
firmware implementation updated 25 October 2026. Upgrade the
backend and firmware together. This contract deliberately rejects legacy
token/action-only messages: without identity, a retry cannot be distinguished
from an intentional action on a second pending reminder.

Both endpoints accept JSON and authenticate `token` against the paired device's
account. Successful responses are `Cache-Control: no-store`.

1. `POST /api/device/reminder` with `{"token":"<private token>"}` returns
   `{"due":false}` or `{"due":true,"id":42,"fired_at":"<timestamp>","medicine_name":"<label>"}`.
   This is a read of the oldest due reminder, not a reservation. Another client
   can resolve it before the action; the subsequent action then fails safely.
2. Generate a new request ID for a deliberate action. Persist the selected
   identity/action/request ID before sending. Submit to `/api/device/action`:

```json
{"token":"<private token>","action":"taken","id":42,"fired_at":"<exact selected timestamp>","request_id":"action-unique-id-001"}
```

`action` is `taken` or `snooze`; `id` is a positive SQLite-range integer;
`fired_at` is the exact selected string. A request ID has 8–128 ASCII letters,
digits, underscores or hyphens. Never regenerate it on a retry. Never reselect
a target on a retry. A different deliberate action needs a new selection and ID.

The database serializes actions with `BEGIN IMMEDIATE`. It first looks for the
paired device's request ID. An exact receipt replay returns its original success
even after the medicine is edited/deleted, a new firing occurs, or the server
restarts. It does not modify current state. A changed binding returns 409. New
requests require an owned, active, currently due row with a matching timestamp.
The dose/Snooze transition and receipt insert commit together; an error rolls
both back. Concurrent copies of one request produce one effect and identical
successes; competing different requests for one firing produce one success.

| Status | Meaning / client action |
| --- | --- |
| 200 | Confirm `success:true`. Applied once or replayed original success. |
| 400 | Invalid/legacy body. Correct the client; no reminder transition. |
| 401 | Credential absent/invalid. Correct pairing. |
| 404 | Target absent or outside the paired account. No transition. |
| 409 | Firing resolved/stale/inactive, or ID reused for a different binding. No new transition. |
| 503 or transport failure | Result unavailable/uncertain. Retry the identical request. |

There is no automatic choice of another medicine on 404/409. A receipt is scoped
to one device, preventing another device/account from replaying its result.
Last-seen metadata may change for valid-token requests even if action validation
fails. Receipts contain reminder labels and timestamps, not bearer tokens.
They are retained; an explicit retention/revocation policy is future work.

Browser `/mark_taken` and `/mark_snooze` require `id` and `fired_at` from
`/check_reminders`; they reject a stale firing with 409. They do not use device
receipts. A lost browser response may therefore lead to a safe 409, never an
action on the next reminder. The UI reconciles state on its next poll.

The sketch uses pinned ArduinoJson 7.4.3 and ESP32 Preferences. Only one uncertain
action is retained. While it exists, new switch gestures are ignored; the
five-second automatic retry loop retains its binding. After blocking work,
including a terminal retry, the switch must be observed released for 50 ms and
pressed anew for 50 ms. Press durations are measured without HTTP/LED blocking;
the <600 ms Taken and >=1500 ms Snooze thresholds are unchanged. IDs use signed
64-bit values throughout. Credentials remain in a private upload copy; pending
JSON omits the token.

A separate persistence marker detects incomplete queue writes. Corrupt data
blocks all sends. The USB-only `CLEAR CORRUPT RETRY` command clears corrupt
saved state without selecting/acknowledging a reminder; it cannot discard a
valid uncertain request and requires a fresh released/pressed cycle afterward.
Valid older saved JSON is migrated by adding the marker without changing its
request binding. Check dose history/receipts before a new action after recovery.

ESP32 target compilation passed on 25 October 2026. Host tests run the production
sketch with simulated GPIO/time/HTTP/NVS and real ArduinoJson. These do not prove
physical storage/power-loss, GPIO, Wi-Fi or LED behavior; board validation remains
required. See [dated firmware validation](testing/FIRMWARE_RESOLUTION_20261025.md).

References: [SQLite transactions](https://www.sqlite.org/lang_transaction.html),
[ArduinoJson 7](https://arduinojson.org/v7/tutorial/deserialization/), and
[ESP32 Preferences](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/preferences.html).
