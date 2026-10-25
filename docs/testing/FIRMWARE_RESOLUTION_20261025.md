# DoseClock firmware resolution — 25 October 2026

Recorded 2026-10-25T15:02:04.567127+05:30, Asia/Kolkata. Branch `validation/review3-20261023`; no staging, commit, push or hardware flashing. Original Review 3 was October 9, the retained software validation was October 23 and the read-only compatibility audit was October 24. This document records new work on October 25.

## Implemented changes

- Replaced the failing ArduinoJson member-proxy inequality with explicit Boolean type checking/extraction.
- Extracted the switch state machine to `hardware/switch_input.h`. Initial/blocked input is disarmed. A continuous 50 ms release and new 50 ms press are required. While pending, gestures are ignored; automatic retries preserve the original tuple. Both before and after blocking HTTP/LED work the input is inhibited, so an overlapping hold is discarded rather than shortened into Taken or applied to B.
- HTTP/status blinks occur outside measured gestures. Thresholds remain <600 ms Taken, >=1500 ms Snooze and no action between them, measured from completed press debounce. Release debounce adds no time to that measurement. Millis subtraction handles wraparound.
- Device IDs are positive signed int64 throughout JSON validation, selection, persistence and transmission. The request protocol and 32-hex-character per-action request ID are unchanged. Valid older saved queues gain only a persistence marker and retain the original binding.
- A `pending_set` marker is persisted before JSON; neither action POST nor new selection is allowed after a failed/incomplete write. Marker/body/type/schema failures block all sends. Successful/rejected completion removes saved state; removal uncertainty remains bound or fails closed.
- USB-only `CLEAR CORRUPT RETRY` (115200 baud, newline) clears only corrupt saved state in the sketch's namespace. It never selects or acknowledges a reminder, works during Wi-Fi startup, refuses valid uncertain requests, and requires fresh release/new press. Failed clear stays blocked. Check server history before a new action after corruption because the earlier outcome can be unknown.
- Serial action messages expose action/ID/firing/request ID/status for physical evidence, excluding token/body. Boot blinks establish Wi-Fi connection only; serial queue/storage errors still block input.
- Added pinned `hardware/platformio.ini`, an ignored `.pio/` path, a clean-build evidence runner and actual-production-sketch host fault tests. The unittest export now includes hardware sources and excludes private/build directories. Browser/autoplay runners use the actual execution date instead of a hardcoded October 23 label. Backend/Flask/TTS/browser application source was not changed.

## Failures preserved and compiler result

The October 24 dependency-complete compiler failure is retained under `historical_audit_20261024/`; it is not described as an October 25 execution. The first October 25 new-project attempt installed dependencies but reported “Nothing to build” because the source filter excluded the generated `.ino.cpp`. Its log and source hashes remain under `compiler/`. The filter was corrected, then the project was cleaned and rebuilt completely.

The final clean and build commands both exited **0**. PlatformIO Core **6.2.0**, Espressif32 **6.9.0**, Arduino ESP32 **2.0.17** (package `3.20017.241212+sha.dcc1105b`), Xtensa **8.4.0+2021r2-patch5**, ArduinoJson **7.4.3**, target **esp32dev**. Output:

- `hardware/.pio/build/esp32dev/firmware.bin`: **942,784 bytes**.
- SHA-256: `8230c11ee9deb02a8aa277a251c23bff6ec12beddff616db395862bfe28f0c3d`.
- Compiler report: RAM **46,940 / 327,680 bytes**; flash **936,213 / 1,310,720 bytes**. These are linker/build figures, not physical runtime measurements.
- The build contains placeholder Wi-Fi/host/token constants. A private configured build is required before any approved upload; its hash will differ.

[Compiler log](evidence/firmware_resolution_20261025/compiler_retest/terminal.log) and [machine-readable result/source hashes](evidence/firmware_resolution_20261025/compiler_retest/results.json). Binary/build directories remain local and ignored.

## Final regression counts

| Layer | PASS | FAIL | NOT TESTED |
| --- | --- | --- | --- |
| Application unit/API/database/scheduler methods | 55 | 0 | 0 |
| Firmware host simulations | 15 | 0 | 0 |
| Chromium UI/visibility | 16 | 0 | 1 |
| Live loopback HTTP/SQLite/Snooze | 17 | 0 | 3 |
| Real six-language MP3/provider and cache checks | 12 | 0 | 0 |
| Human speech/output assessment | 0 | 0 | 1 |
| Software subtotal | **115** | **0** | **5** |
| Clean ESP32 cross-compilation | 1 | 0 | 0 |
| Combined | **116** | **0** | **5** |

No cases were skipped. Three targeted autoplay scenarios pass separately, repeating/extending UI10 and not increasing the total. The CSV's new primary phase is `firmware_resolution_20261025`; repeats use `firmware_autoplay_repeat_20261025`. Prior rows are an unchanged byte prefix, not relabeled latest results.

Host tests include the production `.ino` and actual ArduinoJson 7.4.3, compiled as C++11, with fakes for GPIO/time/HTTP/Preferences/Wi-Fi/Serial. They cover press/debounce boundaries, timer wrap, held/short press across a blocking retry, normal hold without HTTP, same-body retries after restart/503/timeout/invalid 200, full 64-bit IDs, marker/string-write failures, malformed saved data, clear/removal failures, recovery refusal and older saved queues. These are software simulations, not physical presses or flash-driver tests.

The additional Flask test verifies selection, application and exact success replay for IDs 2^31 and 2^63-1. Existing concurrency/account/stale-state/rollback and receipt tests pass unchanged.

## Autoplay, TTS and live evidence

All acceptance-path Runtime evaluations explicitly use `userGesture=false`. UI10 and the three targeted runs each use a fresh disk profile and genuine browser input for enabling audio; actual launch commands have no autoplay bypass or mute flag. The four relevant fresh-profile sessions have zero `userGesture=true` or omitted flags before first input. Ordinary UI helper calls elsewhere in the full browser run include synthetic gestures and are not used as autoplay evidence. See the compact [acceptance wire extract](evidence/firmware_resolution_20261025/autoplay_acceptance_wire.json).

In the current UI10 run, initial `play()` rejects with **NotAllowedError**, unmuted time remains **0**, and the explicit false-gesture probe also rejects. A trusted click on the audio-enablement prompt resolves playback, decodes MP3 audio and advances from **0.071366 to 0.628701 seconds**. Snooze pauses the element and stops time advancement. Default-policy pending and default-policy idle enablement after transient activation expiry also pass. This establishes browser media state, not human hearing.

Real gTTS calls use the translated English/Hindi/Tamil/Telugu/Kannada/Bengali templates with unchanged dummy medicine names. Six new MP3s have positive parsed duration; six cache checks preserve hash/mtime with synthesis disabled. Unit tests also cover provider errors, partial/empty output and retry. No human/native-speaker pronunciation or intelligibility verification is claimed.

All three live Snooze trials used actual 300-second deadlines without clock acceleration, with backend restarts. Actual observations:

| Trial | Real elapsed (s) | Scheduler delay (s) | Observer delay (s) | Taken logs |
| --- | --- | --- | --- | --- |
| B04-1 | 300.267105 | 0.225722 | 0.257379 | 0 |
| B04-2 | 300.134648 | 0.088065 | 0.124308 | 0 |
| B04-3 | 301.113540 | 0.936479 | 1.103609 | 0 |

Live tests include multiple pending reminders, concurrent duplicate requests, wrong-account IDs, controlled successful-response discard and exact retry after actual server restart, plus six backend-stop/recovery trials. They are simulated ESP32 communication using real loopback HTTP/SQLite. They do not model physical radio outages or claim actual packet loss. Thirty action POSTs succeeded; median **1.439 ms**, p95 **1.701 ms**, on loopback only. The selection round trip is excluded from this timing.

## Remaining limits and commit scope

Five NOT TESTED cases remain: UI-VOICE, HUMAN-SPEECH, B03-LAN, B06-HARDWARE and B07-HARDWARE. Physical switch timing/LEDs, Wi-Fi loss, flash/NVS corruption and power loss, actual hearing/microphone use, other boards/core versions, other browsers/mobile/background behavior and long-term reliability remain unverified. Native tests cannot qualify physical NVS guarantees. The device still selects the oldest pending server firing; browser display/audio may lag and selection is not a reservation. Stale selections fail safely, and no new browser synchronization was added. The 64-bit boundary qualification concerns device routes; it is not a browser JavaScript large-integer qualification.

New uncached TTS needs internet. Existing HTTP/token lifecycle and receipt-retention limitations remain. A caregiver must check server history after corrupt-state recovery before making a new deliberate action.

Recommended groups, without staging anything:

1. Firmware: `.gitignore`'s `.pio/` addition, `hardware/switch_hub.ino`, `hardware/switch_input.h`, `hardware/platformio.ini`.
2. Regression tooling: `tests/firmware/`, `tests/test_firmware.py`, new 64-bit case in `tests/test_resolution.py`, `tests/run_firmware_build.py`, hardware export/date corrections in the three existing runners. These depend on the earlier validation helpers, which remain separately reviewable untracked work.
3. Documentation and selected evidence: hardware README, protocol, this report, Ayush checklist, report addenda, appended CSV rows, summary/compiler/native/API/audio/browser results, compact acceptance wire data, preservation hashes and small sanitized evidence. Keep historical before-snapshots and logs needed to understand failures.

Keep `.pio/firmware.bin`, ELF/object/toolchain caches, private configured sketches, real credentials/databases and raw protocol logs local. The full 18 MB browser wire request extract and verbose repeated wire traces are retained evidence but should be reviewed separately before choosing whether to commit them; the compact acceptance extract and source SHA-256 preserve the relevant audit link. Do not stage the whole existing untracked tree or mix unrelated pre-existing changes into these groups.

## Exact local reproduction commands

Use a new output parent each time, preserving these artifacts. This workspace has both interpreters and the verified PlatformIO package cache installed:

```sh
cd /Users/pranav/Documents/DoseClock/DoseClockNLP
TEST_PY=/private/tmp/doseclock-review3-validation-20261023/venv/bin/python
PIO=/private/tmp/doseclock-compatibility-audit-20261024/venv/bin/pio
export PLATFORMIO_CORE_DIR=/private/tmp/doseclock-compatibility-audit-20261024/platformio-core-pinned
$PIO run --project-dir hardware --environment esp32dev
export DOSECLOCK_ARDUINOJSON_INCLUDE="$PWD/hardware/.pio/libdeps/esp32dev/ArduinoJson/src"
RUN_DIR=/private/tmp/doseclock-firmware-demo-$(date +%Y%m%d-%H%M%S)
mkdir "$RUN_DIR"
$TEST_PY -B tests/run_review3_suite.py --source . --output "$RUN_DIR/unit"
$TEST_PY -B tests/run_review3_audio.py --source . --output "$RUN_DIR/audio"
$TEST_PY -B tests/run_review3_live.py --source . --output "$RUN_DIR/live" --audio-cache "$RUN_DIR/audio"
$TEST_PY -B tests/run_review3_browser.py --source . --output "$RUN_DIR/browser" --audio-cache "$RUN_DIR/audio" --visibility
$TEST_PY -B tests/run_review3_autoplay.py --source . --output "$RUN_DIR/autoplay" --audio-cache "$RUN_DIR/audio"
$TEST_PY -B tests/run_firmware_build.py --project hardware --output "$RUN_DIR/compiler" --pio "$PIO"
```

These commands do not upload hardware. The optional DEBUG=pw:protocol output should go to a private local file; retain sanitized extracts for sharing. See [Ayush's conditional flashing and physical checklist](AYUSH_FIRMWARE_CHECKLIST_20261025.md).

## Individual Review 3 report text

On 25 October 2026, I corrected the ESP32 ArduinoJson compilation issue, added retry-safe switch re-arming and hold timing, preserved 64-bit firing identities, and implemented USB recovery for invalid saved retries. The complete software regression passed 115 checks with no failures; a separate clean ESP32 target build generated firmware.bin. Five physical/human/LAN checks remain untested. Firmware host tests and HTTP simulation are reported separately from physical testing, which Ayush must perform on the updated build. Earlier October 9/23/24 evidence is retained and no work is backdated.
