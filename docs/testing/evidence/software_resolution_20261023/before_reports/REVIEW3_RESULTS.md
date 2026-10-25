# DoseClock - Review 3 Results

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

Software validation date: 23 October 2026. Base revision `a1230c928a04`; fixes are on `validation/review3-20261023` and are not committed/pushed.

## Methodology

Validation used disposable accounts, dummy medicine labels and temporary SQLite databases. Existing tests were run before changes. Python HTTP simulation exercised the real paired-device endpoint; Chromium exercised the actual frontend. Response times are localhost measurements. The three Snooze trials used the actual five-minute duration without time acceleration. Deterministic clock unit tests are a separate category.

## Final result summary

| Layer | Executed / passed | Failed | Skipped | Not tested |
| --- | --- | --- | --- | --- |
| Unit/API/database/scheduler regressions | 32 | 0 | 0 | 0 |
| Chromium UI + five visibility cycles | 16 | 0 | 0 | 1 |
| Live HTTP/SQLite + real Snooze timing | 15 | 0 | 0 | 3 |
| Real audio generation + controlled cached reuse | 12 | 0 | 0 | 0 |
| Human speech-quality assessment | 0 | 0 | 0 | 1 |
| Total final case records | 75 | 0 | 0 | 5 |

Counting is by final case, not by rerun or sample. **75 executed cases passed; 5 remain NOT TESTED.** There are 32 unittest methods, 16 executed browser cases (including five visibility cycles), 15 live integration/benchmark cases and 12 audio/cache cases. The raw benchmark dataset contains 64 software trials.

## Benchmark results

| Benchmark | Defined criterion | Actual result | Verdict / scope |
| --- | --- | --- | --- |
| Taken correctness | 10 independently due reminders | 10/10 HTTP 200; one new account-owned log each | PASS: simulated HTTP |
| Invalid-token isolation | 10 requests; 401 and no DB changes | 10/10 HTTP 401; whole-DB digest unchanged each time | PASS: simulated HTTP |
| Response time | 30 requests; median <=500 ms; p95 <=1000 ms | 30/30 successful; median 2.086 ms; p95 10.820 ms | PASS: localhost only; genuine LAN NOT TESTED |
| Snooze | 3 reminders; 300-second wait; due within 2 seconds | 3/3 real waits and re-fires, no Taken log, with process restarts | PASS: real software timing |
| Browser visibility | 5 cycles; visible within 20 seconds | 17.019, 17.089, 17.103, 17.082, 17.077 seconds | PASS: real foreground Chromium on loopback |
| Switch classification | 30 physical presses | Teammate reports success; no physical device/evidence available | NOT TESTED independently |
| Outage feedback | 3 Wi-Fi + 3 backend physical trials | 6 backend-stop/recovery HTTP trials passed; physical Wi-Fi/LED feedback unavailable | Software variant PASS; physical criterion NOT TESTED |


## Snooze observations

| Trial | Real elapsed (s) | Observer delay after deadline (s) | Scheduler firing delay (s) | Taken logs | Result |
| --- | --- | --- | --- | --- | --- |
| B04-1 | 300.481146 | 0.479899 | 0.310382 | 0 | PASS |
| B04-2 | 300.171605 | 0.170306 | 0.168049 | 0 | PASS |
| B04-3 | 300.027736 | 0.026330 | 0.021078 | 0 | PASS |


## Failures and corrections

The unchanged original suite passed 9/9 after dependencies were installed. The extended backend baseline then had seven failures (24/31 passed). Browser baseline runs independently reproduced false success on failed Taken/Snooze, stale external acknowledgment and audio defects. Ten software defect groups were corrected with minimal changes to `backend/app.py`, `backend/database.py` and `frontend/static/js/clock.js`. The complete final unittest suite passed 32/32, and all 16 final browser cases passed. Baseline outputs and screenshots remain in the evidence folder.

The edit fix preserves historical dose details using archived time slots. Removed reminders clear their pending state. Browser success now follows confirmed server success, external actions reconcile on polling, and audio unlock keeps the actual reminder file. README setup/behavior notes were updated accordingly.

## Speech and accessibility findings

Six actual gTTS MP3s were generated and parsed successfully. Cached versions were reused unchanged with synthesis disabled. Keyboard Space and browser single-switch scanning selected Taken/Snooze in Chromium. Native autoplay was blocked before a user gesture; the real MP3 played after a click and paused on Snooze. These are software/media observations, not a human listening evaluation.

## Limits of the result

The existing sentence remains English for all six voice codes; six verified translations are not claimed. Human pronunciation/intelligibility and real microphone acknowledgment remain unverified. The device protocol is not retry-safe across multiple pending medicines. Full offline operation is not implemented. No genuine LAN response time was measured.

The teammate's successful physical button test is a reported result, separate from this independent software run. GPIO, physical switch classification, LEDs and ESP32 Wi-Fi remain NOT TESTED here until recorded physical evidence is supplied. The testing report does not attribute the teammate's firmware or hardware testing to another individual.

## Supporting evidence

[Complete report](TEST_REPORT.md), [case-level CSV](TEST_RESULTS.csv), [raw trials](evidence/benchmark_trials.csv), [bug before/after evidence](BUG_REPORT.md), [simulation scope](ESP32_SIMULATION.md) and [video guide](VIDEO_DEMO_GUIDE.md).
