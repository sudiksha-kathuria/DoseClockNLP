# DoseClock - Comprehensive Software Testing Report

## Follow-up validation — 23 October 2026

Recorded: 2026-10-23T14:57:01.156850+05:30 (Asia/Kolkata). **This follow-up was executed after the initial Review 3 validation.** It does not establish any earlier testing date. Branch remains `validation/review3-20261023`; no commit or push was made.

The complete regression suite was rerun after correcting the autoplay harness: **75 PASS, 0 FAIL, 0 skipped, 5 NOT TESTED (80 cases)**. This comprises 32 unit/API/database/scheduler, 16 browser/visibility, 15 live HTTP/Snooze, and 12 real audio/cache cases. The same five evidence gaps remain. Three additional targeted autoplay runs passed; these repeat or extend UI10 and are reported separately, not added to the 80-case total.

The original UI10 PASS is **invalidated as complete autoplay evidence**. A wire replay of the unchanged original harness confirms `userGesture=true` on `Runtime.callFunctionOn`, including observations before the first browser click. Historical CDP wire logs do not exist, so the replay is dated as new evidence. The original paused/source/duration observations remain preserved. An injected negative control proves the original assertions also pass with `after_gesture.paused=true`; the corrected test rejects that fixture.

In an initially empty disk profile, with HTTP authentication and no prior browser input, the application's initial unmuted MP3 `play()` rejects with `NotAllowedError`; `currentTime` remains zero. All acceptance-path `Runtime.evaluate` calls explicitly set `userGesture=false`. After a trusted browser click on the application's “Tap here to hear the reminder” prompt, `play()` resolves, the real MP3 is unmuted at volume 1, decoded audio bytes increase, and time advances (0.025409 → 0.320206 seconds in the full rerun). Snooze pauses playback and stops time progression. A separate idle-screen enablement click permits the later reminder to play automatically after transient activation expires. Both default Chromium policy and `document-user-activation-required` were tested; actual launch commands contain no autoplay bypass and omit `--mute-audio`.

No additional application defect was discovered. The corrected baseline reproduction reconfirms the original silent-clip replacement defect, and the existing fix passes. This follow-up changes test harnesses and evidence only; the ten original software fix groups remain supported within their documented scopes.

**Unresolved:** the TTS sentence remains English for all six language codes; generating six MP3s does not verify translations or intelligibility. Multiple-reminder retries remain unsafe: identical id-less requests can acknowledge two different pending medicines. The live rerun reproduces that limitation; its characterization PASS means “limitation reproduced,” not “fixed.” Translation work and a protocol/firmware redesign are outside this focused autoplay correction; neither issue is classified as fixed.

**Still unverified:** actual human hearing/output-device delivery; speech quality, pronunciation and six-language intelligibility; real microphone acknowledgment; genuine LAN timing; physical GPIO/switch classification, LED feedback and ESP32 Wi-Fi/outages; other browsers/mobile platforms, background/sleep behavior and long-term reliability. New uncached synthesis still needs internet, and standalone full offline operation remains unimplemented. Media progression/decoding establishes browser playback state, not that a person heard speech.

See [dated audit and reproduction commands](AUTOPLAY_FOLLOWUP_20261023.md), [full rerun summary](evidence/followup_20261023/regression_summary.json), and [corrected CSV](TEST_RESULTS.csv). Original report/CSV/source snapshots and a SHA-256 manifest are retained under [follow-up originals](evidence/followup_20261023/originals/). Existing raw evidence was preserved byte-for-byte.

## Original Review 3 record (historical)

The following is the original report, retained for chronology. Its original autoplay interpretation is superseded by the follow-up above; original measurements and all other scoped results remain historical evidence.

Recorded: 2026-10-23T02:47:46+05:30 (Asia/Kolkata). Base: `a1230c928a0471aa2a05e0af6b32ee2a64a0cd05`. Branch: `validation/review3-20261023`. Changes are uncommitted and have not been pushed.

## Outcome

| Layer | Executed / passed | Failed | Skipped | Not tested |
| --- | --- | --- | --- | --- |
| Unit/API/database/scheduler regressions | 32 | 0 | 0 | 0 |
| Chromium UI + five visibility cycles | 16 | 0 | 0 | 1 |
| Live HTTP/SQLite + real Snooze timing | 15 | 0 | 0 | 3 |
| Real audio generation + controlled cached reuse | 12 | 0 | 0 | 0 |
| Human speech-quality assessment | 0 | 0 | 0 | 1 |
| Total final case records | 75 | 0 | 0 | 5 |

There are **80 final case records: 75 executed and passed, 0 failed, 0 skipped, and 5 NOT TESTED**. The 64 raw software benchmark trials are samples inside these cases, not 64 extra cases. Earlier baseline failures and harness diagnostics are retained separately and are not removed from the evidence. SIM-REPLAY-LIMIT is a characterization check: PASS means the protocol limitation was reproduced, not that retries are safe. See [TEST_RESULTS.csv](TEST_RESULTS.csv), [combined JSON](evidence/combined_results.json) and [raw benchmark trials](evidence/benchmark_trials.csv).

## Repository audit and initial baseline

The remote was fetched and `origin/main` remained at the base hash above. The initial working tree was clean. The original repository has 25 tracked files: Flask routes, the SQLite helper layer, the scheduler/TTS modules, HTML/CSS/JavaScript frontend, two test modules, ESP32 sketch and documentation. The saved [baseline manifest](evidence/baseline_manifest.json) identifies the exact original file hashes.

The original tests contain two database tests and seven hardware-API tests. The first invocation could not import either test module because Werkzeug and the other runtime dependencies were absent: **two loader errors, zero application tests executed** ([initial environment output](evidence/existing_initial_environment.log)). After installing the declared requirements in a temporary virtual environment, the unchanged original suite ran **9/9 PASS** ([original-suite output](evidence/existing_baseline.log)). No earlier CI output or execution artifact was present in the repository. Historical execution of those tests cannot be inferred from their existence. README C01-C13 and the earlier benchmarks were explicitly plans/Not Tested entries.

New regressions exposed seven failing backend cases in an extended baseline of **31 tests: 24 PASS, 7 FAIL** ([corrected regression baseline](evidence/regression_baseline_corrected/results.json)). Browser checks reproduced false Taken/Snooze success, stale external acknowledgments and audio problems. The [bug report](BUG_REPORT.md) maps ten software defect groups to baseline evidence, fixes and retests. One additional post-fix unit test verifies migration of an existing owned history/token fixture, bringing the final unittest suite to 32.

Coverage gaps in the original suite included signup/logout/invalid inputs, malformed JSON, actual concurrent requests, edit-after-history, deleting a due row, current firing metadata, initial audio preparation, real MP3 validity, browser workflows and measured timing. The original audio-failure test patches synthesis while firing only reads cache; it does not test synthesis failure. The original conflict test mocks a failed claim; it is not a real concurrency test. Both original assertions were preserved, and stronger cases were added.

## Isolation and measurement conditions

- All application imports and live servers used exported temporary source copies. Unit tests use disposable SQLite files/caches. No original schedule database, key or audio cache was created or modified in the working checkout.
- The application port for each live run was ephemeral on **127.0.0.1**. This is loopback, not a wireless LAN measurement.
- The simulator uses real `POST /api/device/action`, `Content-Type: application/json`, a real account-issued bearer token and real SQLite transitions. It has no automatic retry. Test credentials/tokens are dummy and redacted from evidence.
- Controlled fixtures prepare due rows. The five browser visibility cycles use the real one-second scheduler and 17-second frontend poll; their pre-existing schedule fixture is disclosed in the script. These are not GPIO timing trials.
- Response time uses `perf_counter` from POST start through complete response read, excluding LED time. p95 is nearest rank: sorted position 29 of 30. All 30 HTTP attempts succeeded; no failure was discarded.
- Snooze uses the production **300-second** deadline and actual elapsed time. Three trials ran concurrently; six backend restarts occurred during the wait. No test clock was patched for these trials. Deterministic scheduler and repeated-Snooze unit tests separately use clock mocking and are labeled as such.
- Browser runs used actual headless Chromium (156.0.8078.4) at 1440x1000. The final autoplay run explicitly uses `document-user-activation-required`. Headless media decode/play state is not proof that a person heard or understood speech.
- Environment/version details are in [environment.json](evidence/environment.json) and [dependency_versions.txt](evidence/dependency_versions.txt). The desktop remained awake, with no deliberate load generator; browser tests and observation polling ran concurrently. Results are one local session, not a reliability guarantee or load test.
- Empty duration cells in the CSV mean no separate case timer was recorded; they do not mean zero latency. Actual response-time samples, browser timing and Snooze intervals are preserved numerically.

## Benchmarks and actual numbers

| Benchmark | Defined criterion | Actual result | Verdict / scope |
| --- | --- | --- | --- |
| Taken correctness | 10 independently due reminders | 10/10 HTTP 200; one new account-owned log each | PASS: simulated HTTP |
| Invalid-token isolation | 10 requests; 401 and no DB changes | 10/10 HTTP 401; whole-DB digest unchanged each time | PASS: simulated HTTP |
| Response time | 30 requests; median <=500 ms; p95 <=1000 ms | 30/30 successful; median 2.086 ms; p95 10.820 ms | PASS: localhost only; genuine LAN NOT TESTED |
| Snooze | 3 reminders; 300-second wait; due within 2 seconds | 3/3 real waits and re-fires, no Taken log, with process restarts | PASS: real software timing |
| Browser visibility | 5 cycles; visible within 20 seconds | 17.019, 17.089, 17.103, 17.082, 17.077 seconds | PASS: real foreground Chromium on loopback |
| Switch classification | 30 physical presses | Teammate reports success; no physical device/evidence available | NOT TESTED independently |
| Outage feedback | 3 Wi-Fi + 3 backend physical trials | 6 backend-stop/recovery HTTP trials passed; physical Wi-Fi/LED feedback unavailable | Software variant PASS; physical criterion NOT TESTED |


### Real Snooze timing

| Trial | Real elapsed (s) | Observer delay after deadline (s) | Scheduler firing delay (s) | Taken logs | Result |
| --- | --- | --- | --- | --- | --- |
| B04-1 | 300.481146 | 0.479899 | 0.310382 | 0 | PASS |
| B04-2 | 300.171605 | 0.170306 | 0.168049 | 0 | PASS |
| B04-3 | 300.027736 | 0.026330 | 0.021078 | 0 | PASS |


The observer values include polling overhead. The scheduler values use the stored database firing timestamp relative to the stored deadline. All three trials have zero Taken logs. Restart persistence was verified using real server processes and the same disposable database/key.

## Speech and offline scope

Six real gTTS requests generated nonempty MP3s parsed with Mutagen, including positive duration/sample-rate metadata. SHA-256 values and provider-request durations are recorded in [audio results](evidence/audio/results.json), with the actual files alongside them. Cached reuse then ran with `tts.gTTS` deliberately raising a connection error: all six returned the same hash/mtime without a synthesis call. This is a controlled synthesis-unavailability experiment, not a physical Wi-Fi disconnect.

The current module passes the fixed English sentence to all six language codes. These results establish generation/file/cache behavior, **not six verified translations or native-language intelligibility**. Human pronunciation testing and real voice acknowledgment are NOT TESTED. New uncached synthesis still requires internet; the application is not a standalone fully offline bedside unit.

## Requirements coverage

| Requirement | Verification | Evidence / qualification |
| --- | --- | --- |
| Signup/login/logout; invalid credentials | VERIFIED in tested environment | API assertions and real signup UI workflow. |
| Account isolation; paired owner | VERIFIED in tested environment | Read/action/delete isolation, real HTTP token-owner isolation. |
| Create/delete, multiple times, course counters | VERIFIED for documented last-slot rule | Invalid times rejected; exact log counts, soft-delete clears due state. |
| Edit with history; existing-schema migration | VERIFIED on dummy legacy fixtures | Historical name/time/language/log preserved; additive archive column. |
| Restart persistence | VERIFIED on disposable live DB | Six real process restarts preserve tokens/session/history; 300-second Snooze survives. |
| Scheduled trigger; multiple due reminders | VERIFIED within covered cases | Deterministic clock unit tests plus real scheduler/browser cycles. |
| Taken duplicate prevention | VERIFIED for a selected firing | Actual concurrent requests log one row. Id-less multi-due replay remains a protocol limitation. |
| Snooze/repeated Snooze | VERIFIED with separate scopes | Three real 300-second trials; repeated Snooze uses a mocked unit clock, not a second 600-second benchmark. |
| Six voice codes, MP3 files, cache reuse | PARTIALLY VERIFIED | Six real MP3s, metadata and hashes; offline synthesis-injection cache checks pass. English sentence remains fixed. |
| Audio failure | VERIFIED for injected failure cases | Partial file cleanup, observed background exception, visual reminder and Taken remain usable. |
| Tap/keyboard/scanning/history/autoplay | VERIFIED in recorded Chromium version | Real browser actions, native autoplay policy and decoded audio state; no human listening claim. |
| Real voice recognition / native-language quality | UNVERIFIED | No independent microphone, participant utterance or native-speaker listening evidence. |
| ESP32 HTTP integration | VERIFIED SIMULATION | Actual endpoint, pairing/authentication, HTTP and SQLite, not physical hardware. |
| Genuine LAN performance / GPIO / LED / ESP32 Wi-Fi | UNVERIFIED independently | No board or second LAN client. Teammate report kept separate. |
| Complete offline operation | NOT IMPLEMENTED as a standalone system | Cached audio reuse works; new synthesis needs internet; host/network remain necessary. |


## Reproduction commands

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

The initial commands were the bundled interpreter's `-B -m unittest discover -s tests -v` in the original exported copy (missing dependencies), followed by the isolated virtual-environment interpreter with the same arguments (9/9). The extended baseline used `tests/run_review3_suite.py --source /private/tmp/doseclock-review3-validation-20261023/baseline --output docs/testing/evidence/regression_baseline_corrected`. Complete outputs and dependency installation logs are retained.

## Diagnostic corrections, separate from software defects

The first new scheduler probes omitted `datetime.fromisoformat` from their mocked clock and produced two harness errors. Adding that real-method side effect corrected the harness without changing acceptance criteria. The raw [first regression results](evidence/regression_baseline/results.json) remain available.

The first autoplay probe called `play()` through Playwright evaluation, which can execute with a CDP user gesture; its “allowed” result was an invalid no-gesture experiment. The corrected test observes the application's own playback, uses the strict native autoplay policy, then performs a real browser click. It reproduced the original silent-clip replacement defect and passed after the fix. [Corrected before](evidence/autoplay_baseline_corrected/results.json), [targeted retest](evidence/autoplay_retest/results.json), and the complete final browser rerun are retained. These harness errors are not counted as product defects or final failures.

## Physical hardware report

The user reports that a teammate tested the physical ESP32 button successfully. No board, serial capture, timestamped trial log or physical input/LED recording was available to independently verify that report. Therefore GPIO, button classification, LED feedback and real ESP32 Wi-Fi remain NOT TESTED here. Required teammate evidence is specified in [ESP32_SIMULATION.md](ESP32_SIMULATION.md). No physical test was attempted.
