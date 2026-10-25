# DoseClock - Software Review 3 Video Guide

## Current software-resolution follow-up — 23 October 2026

This earlier October 23 artifact is retained as history and is distinct from
the original October 9 review. The current software result is **99 PASS,
0 FAIL, 5 NOT TESTED**, plus a separate unexecuted ESP32 target-build check
(**6 NOT TESTED including that check**). Unit output is now **54 tests, OK**.
The new protocol requires `id`, `fired_at` and `request_id`; id-less action
messages below describe historical behavior. Current simulator CLI usage also
requires `--request-file`. Six translated templates now replace English-only
regional-language inputs. Human speech quality is still unverified.

Use [current findings and exact safe demonstration commands](SOFTWARE_RESOLUTION_20261023.md)
and [the current protocol](../DEVICE_PROTOCOL.md). Do not rerun the historical
commands below into existing evidence directories. Current measurements and
limits are in the linked report; previous measurements below remain unchanged.

## Earlier October 23 guide (historical)

Use your own face and voice. Name the genuine individual contribution and identify the build as `validation/review3-20261023` (uncommitted validation changes). These steps demonstrate software; do not present Python requests as physical switch input.

## 5-7 minute outline

| Time | Actual material to show |
| --- | --- |
| 0:00-0:20 | Name, register number, actual team number, project title; say physical button testing was reported by the teammate and this segment validates software. |
| 0:20-2:20 | Continuous signup/login, dummy medicine with multiple times, clock reminder, Taken, Logs and a separate Snooze. Use the real application and preserve the uncut input-to-state sequence. |
| 2:20-3:20 | Terminal final suite output (32 tests, OK), final summary CSV and loopback response-time values. Label them localhost. |
| 3:20-4:20 | Before/after network-failure screenshots and the fix: retain alarm, show retry feedback, no false Taken/Snooze success. |
| 4:20-5:20 | Real five-minute Snooze data: three stored deadlines, observed firing timestamps and zero Taken logs. A short clip of a deadline alone is not proof of a five-minute re-fire. |
| 5:20-6:30 | Simulated device HTTP result and account-owned log; acknowledge remaining LAN/physical/speech limitations and describe validation/documentation contributions. |

The separate course literature comparison can use the existing individual report; keep any extension within the course's 5-7 minute limit. If the rubric requires a longer literature segment, shorten repeated terminal narration, not the continuous live input/output demonstration.

## Commands and genuine outputs

```bash
# The actual isolated environment used for this run:
PY=/private/tmp/doseclock-review3-validation-20261023/venv/bin/python
# From repository root; install only in the isolated environment.
$PY -m pip install -r tests/requirements-review3.txt
$PY -m playwright install chromium

# Final complete unittest suite: exports backend/frontend/tests into a temp copy.
$PY -B tests/run_review3_suite.py --source . --output docs/testing/evidence/final_suite
# Real provider audio and parsable MP3s, using the original exported source.
$PY -B tests/run_review3_audio.py --source /private/tmp/doseclock-review3-validation-20261023/baseline --output docs/testing/evidence/audio
# Real local HTTP and SQLite; waits five actual minutes for Snooze.
$PY -B tests/run_review3_live.py --source . --output docs/testing/evidence/live --audio-cache docs/testing/evidence/audio
# Actual headless Chromium, not a DOM mock.
$PY -B tests/run_review3_browser.py --source . --output docs/testing/evidence/browser_final --audio-cache docs/testing/evidence/audio --visibility
```

For a fresh setup, create a virtual environment outside the repository and assign `PY` to its interpreter. The recorded version list is in `evidence/dependency_versions.txt`. The audio command used the original exported TTS module because TTS source was not modified. Do not run a test server against a household database. The test fixture route exists in `tests/validation_server.py` only, binds to 127.0.0.1, requires a random per-run key, and refuses a Git working checkout as its source.


Expected genuine final suite output is `Ran 32 tests` followed by `OK`, backed by `evidence/final_suite/terminal.log`. Report-wide figures are 75 passed cases, 0 final failures, 0 skipped and 5 NOT TESTED; do not describe all 80 as executed. Response median/p95: 2.086/10.820 ms on localhost only. Browser visibility: 17.019-17.103 seconds.

## Screenshots available now

- [Registered two-time medicine and clock](evidence/browser_final/screenshots/UI01.png).
- [Taken and dose history](evidence/browser_final/screenshots/UI02.png).
- [Snooze UI/state case](evidence/browser_final/screenshots/UI03.png).
- [Original false Taken success](evidence/browser_baseline/screenshots/observed_review_taken_network_failure.png).
- [Corrected retry feedback](evidence/browser_final/screenshots/observed_review_taken_network_failure.png).
- [External acknowledgment reconciled](evidence/browser_final/screenshots/UI09.png).
- [Native autoplay/MP3 case](evidence/browser_final/screenshots/UI10.png).
- [Initial visibility cycle](evidence/browser_final/screenshots/B05-1.png).

Screenshots are actual headless Chromium captures. A screenshot supports the observed UI; pair it with the JSON/log state for an acknowledgment claim. No live video recording or physical-board recording was created in this run. For a real-time Snooze demonstration, keep a continuous timing recording and actual timestamps; do not accelerate the clock or imply that this raw data is a video.

## Demonstration boundaries

Safe software claims: account workflows, dummy reminder registration, Taken/Snooze persistence, keyboard/scanning, simulated device HTTP and measured local results. Pending evidence: physical GPIO/LED/Wi-Fi and real microphone/native-speaker evaluation. Never expose pairing tokens, password fields or real medicine data in the recording.
