# DoseClock autoplay evidence audit — 23 October 2026

This is a follow-up after the initial Review 3, recorded 2026-10-23T14:57:01.156850+05:30. Base commit remains `a1230c928a0471aa2a05e0af6b32ee2a64a0cd05`; branch is `validation/review3-20261023`. No commit/push. No new application changes were required.

## What the actual calls establish

The initial Review 3 did not retain CDP wire traces. Its exact historical on-wire parameters cannot be independently recovered. The original source, installed Playwright implementation and a newly recorded replay establish the affected mechanism:

- Playwright's installed `CRExecutionContext.evaluateWithArguments` sends `Runtime.callFunctionOn` with `userGesture: true`. The replay retains complete outgoing Runtime/Input parameters in [requests.json](evidence/followup_20261023/original_harness_wire/requests.json). Its clock navigation has **15 true-gesture Runtime calls before the first browser input**. The user's suspected `Runtime.evaluate` method was not the exact method carrying the flag here; `Runtime.callFunctionOn` was.
- Original UI10 used `wait_for_function`, locator evaluation of `paused`, and page evaluation of source/duration. This is unsuitable evidence of a wholly unactivated page. Other UI cases also use Playwright evaluation, but their assertions concern workflow/visual/DB state and make no no-gesture audio claim. Their genuine results remain valid for those scopes. Backend/live/audio generation cases never depend on browser activation.
- Original UI10 required `paused_before`, an MP3 suffix, duration >1 second and pause after Snooze. It did **not** require post-click `paused=false`, a resolved play promise or time progression. The [injected paused-audio control](evidence/followup_20261023/paused_negative_control/results.json) produces original UI10 **PASS with paused=true**; the corrected acceptance test fails it. This is a demonstrated false-pass assertion, not a newly discovered product bug.
- The [synthetic-gesture control](evidence/followup_20261023/synthetic_gesture_control/strict-pending/results.json) first rejects play with `userGesture=false`, then resolves it and advances audio when deliberately evaluated with `userGesture=true` before any trusted click. This deliberately invalid experiment demonstrates the confound and is excluded from acceptance counts.
- Original launch replay used the strict policy and default `--mute-audio`; no no-user-gesture autoplay bypass was found. Muting the output makes human audibility claims unsupported, even when the media timeline runs.

CDP documents `userGesture` as treating evaluation as initiated by a user. [Runtime protocol](https://chromedevtools.github.io/devtools-protocol/tot/Runtime/). Chromium documents user activation and engagement exemptions for autoplay. [Chromium autoplay policy](https://www.chromium.org/audio-video/autoplay/).

| Original artifact | Audit disposition |
| --- | --- |
| `browser_first_attempt` / `browser_audio_baseline`, UI10 | Recorded FAIL with evaluated play returning “allowed”; invalid no-gesture experiments. Retained as harness diagnostics, not proof of natural autoplay permission. |
| `autoplay_baseline_corrected`, UI10 | Silent-source replacement after a real click is genuine and independently reproduced by this follow-up. Its no-gesture precondition lacked adequate isolation. |
| `autoplay_retest` / `browser_final`, UI10 | Recorded PASS is invalidated for the full autoplay claim: gesture-capable observations and no required post-click progression. Source, duration and paused-state observations are preserved. |
| Other original final cases | The 74 executed non-UI10 results retain their documented scopes; five NOT TESTED entries remain. None becomes an audio playback or human listening test by association. |

## Corrected experiments and outcome

Each acceptance scenario launches a separate initially empty temporary disk profile and records the **actual** `Browser.getBrowserCommandLine` arguments. No reused browser profile, UI login click, permission grant, autoplay bypass, media-engagement override or output mute is used. Authentication is HTTP-only. The test observes the native play promise using a wrapper that returns the original promise unchanged and records media events, media errors, volume, mute, ready state, decoded bytes and timeline samples. `Media` domain events are also retained.

Before the first input, the complete targeted wire captures show zero `userGesture=true` calls; the explicit Runtime probes all have `false`. [Targeted wire summary](evidence/followup_20261023/autoplay_wire/summary.json). Playwright screenshot helpers run only after acceptance assertions. The rest of the full browser suite may use Playwright evaluation for non-autoplay assertions; UI10 launches its own fresh profile and uses raw CDP.

| Scenario | Result | Direct evidence |
| --- | --- | --- |
| Strict policy, already-pending initial reminder | PASS: initial `NotAllowedError`, zero progress; trusted prompt click resolves MP3 play and advances time; Snooze stops it | [targeted](evidence/followup_20261023/autoplay_verified/strict-pending/results.json) |
| Default policy, already-pending initial reminder | PASS: same blocked/allowed/progression behavior | [targeted](evidence/followup_20261023/autoplay_verified/default-pending/results.json) |
| Default policy, idle-screen sound enablement then later reminder | PASS: native silent-clip unlock succeeds; next natural 17-second poll plays MP3 with `isActive=false`, `hasBeenActive=true` | [targeted](evidence/followup_20261023/autoplay_verified/default-idle/results.json) |
| Untouched original application under corrected strict test | Expected FAIL: genuine prompt click replaces MP3 with silent WAV, duration 0.000125 s, paused=true | [baseline reproduction](evidence/followup_20261023/original_product_reproduction/strict-pending/results.json) |
| Current application under full regression UI10 | PASS: zero time before input; post-click 0.025409 → 0.320206 s, decoded bytes 2304 → 6144; stops on Snooze | [full-rerun UI10](evidence/followup_20261023/regression_browser/UI10-clean-profile/results.json) |

Trusted clicks use browser input dispatch and are checked as `event.isTrusted=true` with active user activation. They target `#mic-indicator` or idle `#sound-hint`; no JavaScript `element.click()` is used. The synthetic true-gesture control is separate and labelled invalid for acceptance.

Two initial follow-up harness attempts failed before application assertions: command-line inspection needed `--enable-automation`, and early-document instrumentation needed the CDP Page domain enabled. Both attempts and all six diagnostic failures are preserved under `autoplay_before` and `autoplay_corrected`. They are harness failures, excluded from final application totals. The corrected acceptance runs followed both corrections.

## Complete regression rerun

| Layer | PASS | FAIL | NOT TESTED |
| --- | --- | --- | --- |
| Unit/API/database/scheduler | 32 | 0 | 0 |
| Browser, including strengthened UI10 and five visibility cycles | 16 | 0 | 1 |
| Live HTTP/SQLite, real 300-second Snooze and restarts | 15 | 0 | 3 |
| Six real provider MP3s and six cache checks | 12 | 0 | 0 |
| Human speech-quality assessment | 0 | 0 | 1 |
| Full suite total (80 case records) | **75** | **0** | **5** |

The three targeted autoplay repeats are additional evidence and do not inflate this total. Expected baseline/control failures and harness diagnostics are not final application failures. The corrected CSV identifies phases explicitly. The old UI10 row is marked `INVALIDATED`; its exact original CSV and JSON are preserved.

Fresh response samples: 30/30 successful, median 1.562 ms, nearest-rank p95 1.802 ms on loopback. Fresh visibility cycles: 17.021, 17.091, 17.093, 16.983, 16.993 seconds. These are new measurements; original measurements remain in the historical reports.

| Snooze trial | Real elapsed (s) | Scheduler delay (s) | Observer delay (s) | Taken logs |
| --- | --- | --- | --- | --- |
| B04-1 | 300.532973 | 0.504335 | 0.530458 | 0 |
| B04-2 | 300.412869 | 0.379381 | 0.410642 | 0 |
| B04-3 | 300.286933 | 0.251271 | 0.284629 | 0 |

All three trials used the real 300-second wait, no mocked clock, and six process restarts. The real-provider MP3s were generated into a new empty evidence directory; old cached files and provider results were preserved.

## Issue classifications and remaining limits

| Item | Classification | Evidence / implication |
| --- | --- | --- |
| Original silent-clip replacement and missing pause defect | **Fixed** by existing Review 3 change; confirmed again | Original application fails corrected test; current application passes. No additional product fix. |
| Original autoplay assertion/gesture contamination | **Fixed in test harness** | Explicit false-gesture probes, empty profiles, play promises, progression, actual command lines, trusted control clicks; old PASS invalidated. |
| English-only sentence used with six language codes | **Unresolved** | `backend/tts.py` still builds the fixed English sentence. English MP3 generation/cache passes; translation, pronunciation and intelligibility do not follow. Implementing translations is outside this autoplay follow-up. |
| Multiple-reminder retry safety | **Unresolved** | Live rerun `SIM-REPLAY-LIMIT`: identical bodies produce two 200s and two logs. This PASS characterizes the known defect/limitation. Protocol/firmware occurrence IDs/idempotency work is outside this follow-up. |
| Human listening/native-language evaluation and real microphone use | **Unverified / outside available evidence** | No independent listener, output-device recording, participant utterance or native-speaker assessment. |
| Physical ESP32, GPIO, switch/LED/Wi-Fi; independent LAN timing | **Unverified / outside available equipment** | Same three NOT TESTED physical/LAN case records. Teammate report retained separately. |
| Full standalone offline operation | **Unimplemented / outside scope** | Cache reuse with blocked synthesis passes; uncached synthesis needs internet. |
| Other browsers/mobile platforms, background/sleep, long-term reliability | **Unverified / outside this run** | Tested bundled headless Chromium 156.0.8078.4 on this macOS host only. |

The five unchanged NOT TESTED cases are UI-VOICE, HUMAN-SPEECH, B03-LAN, B06-HARDWARE and B07-HARDWARE. Audio-output delivery/human audibility is an explicit additional limitation on software playback evidence, not an executed hearing test.

## Reproduction

From repository root, using the isolated existing virtual environment:

```bash
PY=/private/tmp/doseclock-review3-validation-20261023/venv/bin/python
# Each NEW output directory must be unused to preserve earlier evidence.
$PY -B tests/run_review3_autoplay.py --source . --output /private/tmp/doseclock-autoplay-new-run --audio-cache docs/testing/evidence/audio
$PY -B tests/run_review3_suite.py --source . --output /private/tmp/doseclock-unit-new-run
$PY -B tests/run_review3_browser.py --source . --output /private/tmp/doseclock-browser-new-run --audio-cache docs/testing/evidence/audio --visibility
$PY -B tests/run_review3_live.py --source . --output /private/tmp/doseclock-live-new-run --audio-cache docs/testing/evidence/audio
$PY -B tests/run_review3_audio.py --source . --output /private/tmp/doseclock-audio-new-run
$PY -B tests/run_review3_autoplay_controls.py --source . --output /private/tmp/doseclock-paused-control-new-run --audio-cache docs/testing/evidence/audio --original-harness docs/testing/evidence/followup_20261023/originals/tests/run_review3_browser.py
```

For complete Playwright wire logging, add `DEBUG=pw:protocol,pw:browser` and direct stdout/stderr to a private file, then use `tests/summarize_review3_protocol.py` to retain Runtime/Input requests without HTTP cookies/fixture credentials. The retained extracts are bound to their full private logs with SHA-256 values. New raw CDP acceptance transcripts are alongside each scenario. Full private wire logs remain in `/private/tmp`; original evidence directories remain unchanged.

## Preservation and repository state

`evidence/followup_20261023/original_sha256.json` records the pre-follow-up evidence/source hashes. Original copies of all three requested reports, the browser runner and clock.js are under `originals/`. `git_status_before.txt` and `git_status_after.txt` enumerate tracked changes and untracked testing/evidence files. `preservation_check.json` verifies that every pre-existing evidence file and application source is unchanged by this follow-up. `source_inventory.json` and `FOLLOWUP_SHA256SUMS.txt` identify the final follow-up source and evidence.

The existing tracked changes in README.md, backend/app.py, backend/database.py and frontend/static/js/clock.js belong to the initial validation. Testing scripts, docs and evidence remain untracked as shown by git status; they are not silently omitted. No database/key was created in the checkout. No commit, push or branch switch occurred.
