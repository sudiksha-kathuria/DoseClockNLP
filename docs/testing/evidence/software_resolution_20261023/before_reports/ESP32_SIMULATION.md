# SIMULATED ESP32 COMMUNICATION

Recorded 2026-10-23T02:47:46+05:30. This validation uses Python, real loopback HTTP, the actual Flask route and disposable SQLite. **It is not physical ESP32 testing.**

## Protocol and setup

Endpoint: `POST /api/device/action`. Header: `Content-Type: application/json`. Body: `{"token":"<private dummy token>","action":"taken"}` or the same body with `snooze`. The pairing credential is issued through the actual authenticated `/pair_device` form. The test uses a disposable signed-in account and confirms the `no-store` pairing response. Evidence contains redacted tokens only.

`tests/esp32_simulator.py` uses urllib, a request timeout and `perf_counter`. HTTP errors retain their real status/body; connection failures have no HTTP status and are not turned into successful acknowledgments. It does not retry automatically. No medicine ID is sent, matching the existing firmware.

The live harness prepares due rows through a separate protected, loopback-only fixture route. Production acknowledgment, authentication, SQLite transactions and scheduler code remain real. Real restarts reuse the same temporary DB and session key. Host address 127.0.0.1 makes these localhost measurements, not ESP32/LAN measurements.

## Executed cases

| Case | Expected / actual | Verdict |
| --- | --- | --- |
| SIM-NO-DUE | {'label': 'SIMULATED ESP32 COMMUNICATION', 'transport': 'real HTTP; caller must identify loopback versus LAN', 'action': 'taken', 'token': '<redacted>', 'http_status': 404, 'response': {'error': 'no reminder is currently due'}, 'transport_error': None, 'durati | PASS |
| SIM-MISSING | {'label': 'SIMULATED ESP32 COMMUNICATION', 'transport': 'real HTTP; caller must identify loopback versus LAN', 'action': 'taken', 'token': '<omitted>', 'http_status': 401, 'response': {'error': 'unknown or missing device token'}, 'transport_error': None, 'dura | PASS |
| SIM-ACTION | {'label': 'SIMULATED ESP32 COMMUNICATION', 'transport': 'real HTTP; caller must identify loopback versus LAN', 'action': 'unsupported', 'token': '<redacted>', 'http_status': 400, 'response': {'error': "action must be 'taken' or 'snooze'"}, 'transport_error': N | PASS |
| SIM-DUPLICATE | {'statuses': [200, 404], 'logs': 1} | PASS |
| SIM-ISOLATION | {'http_status': 404, 'other_account_state_unchanged': True} | PASS |
| SIM-CONCURRENT | {'statuses': [200, 404], 'logs': 1} | PASS |
| SIM-REPLAY-LIMIT | {'statuses': [200, 200], 'logs': 2, 'retry_safe': False} | PASS |
| OUTAGE-HTTP | [{'trial': 1, 'offline_http_status': None, 'transport_error': '<urlopen error [Errno 61] Connection refused>', 'logs_unchanged_during_outage': True, 'recovery_http_status': 200}, {'trial': 2, 'offline_http_status': None, 'transport_error': '<urlopen error [Err | PASS |
| RESTART-SESSION | {'session_http_status': 200, 'token_authenticated_after_restart': True} | PASS |


## Benchmarks

| Benchmark | Defined criterion | Actual result | Verdict / scope |
| --- | --- | --- | --- |
| Taken correctness | 10 independently due reminders | 10/10 HTTP 200; one new account-owned log each | PASS: simulated HTTP |
| Invalid-token isolation | 10 requests; 401 and no DB changes | 10/10 HTTP 401; whole-DB digest unchanged each time | PASS: simulated HTTP |
| Response time | 30 requests; median <=500 ms; p95 <=1000 ms | 30/30 successful; median 2.086 ms; p95 10.820 ms | PASS: localhost only; genuine LAN NOT TESTED |
| Snooze | 3 reminders; 300-second wait; due within 2 seconds | 3/3 real waits and re-fires, no Taken log, with process restarts | PASS: real software timing |
| Browser visibility | 5 cycles; visible within 20 seconds | 17.019, 17.089, 17.103, 17.082, 17.077 seconds | PASS: real foreground Chromium on loopback |
| Switch classification | 30 physical presses | Teammate reports success; no physical device/evidence available | NOT TESTED independently |
| Outage feedback | 3 Wi-Fi + 3 backend physical trials | 6 backend-stop/recovery HTTP trials passed; physical Wi-Fi/LED feedback unavailable | Software variant PASS; physical criterion NOT TESTED |


The separate three Snooze cases waited approximately 300 real seconds. See [raw timing](evidence/live/results.json). Six actual server-stop/restart trials had no HTTP success/new dose log while stopped; explicit post-restart actions succeeded. This does not test LED patterns or physical Wi-Fi reassociation.

## Re-run a single message

```bash
# Use a private disposable account token, not a credential recorded in video.
DOSECLOCK_DEVICE_TOKEN='<private-dummy-token>' python3 tests/esp32_simulator.py --host http://127.0.0.1:5050 --action taken
```

Use one due dummy reminder for a clear first test. Inspect account-scoped dose history alongside the HTTP result. With two due rows, an identical body can select the next row; the simulator deliberately avoids automatic retries.

## Teammate hardware report and evidence needed

The user reports that a teammate has tested the button successfully. That report is not independently marked PASS. Obtain the actual operator/date, board model, firmware revision/core, wiring photo, redacted upload/pairing configuration, switch duration observations, Serial/HTTP output, LED recording and matching account-state before/after evidence. Include the planned 10 short/10 hold/10 intermediate trials and 3 Wi-Fi-loss/3 backend-loss physical trials if claiming those criteria. A commit screenshot establishes Git activity, not GPIO or Wi-Fi correctness.
