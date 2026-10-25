# DoseClock software-resolution validation — 23 October 2026

Recorded 2026-10-23T16:29:11.766164+05:30, Asia/Kolkata. Original Review 3: 9 October 2026 (date supplied by the user). Every reproduction, fix and rerun in this artifact happened on October 23, after the earlier October 23 validation. Branch: `validation/review3-20261023`; HEAD remains `a1230c928a0471aa2a05e0af6b32ee2a64a0cd05`. No staging/commit/push.

## Findings and fixes

### Multilingual TTS: fixed in software

The old module selected a gTTS voice code but always built the English sentence. Merely changing `lang` does not translate input text. The new `build_reminder_text` has six explicit templates and treats the medicine label as opaque text. Braces, punctuation, Unicode and any numbers in the label are inserted exactly, not interpreted. Schedule times, course state and dosage information are not synthesized or changed.

The cache key hashes the actual sentence and language. Legacy files are retained but are not reused as current content. `/check_reminders` resolves the current content cache instead of exposing the legacy English path stored in an already-due row. Restart the backend to warm translated caches and reload open clock pages after an upgrade. Missing/failed audio leaves the visual reminder usable. Temporary files are published with atomic replacement only after nonempty output; failure/empty output is cleaned up and retryable.

The following are actual inputs observed at the real provider boundary, with new parsable MP3s generated into a new directory:

| Language | Exact provider text | Bytes | Duration (s) |
| --- | --- | --- | --- |
| en | It's time to take your Review dummy. | 20736 | 2.592 |
| hi | आपकी दवा Review dummy लेने का समय हो गया है। | 30528 | 3.816 |
| ta | உங்கள் Review dummy மருந்தை எடுத்துக்கொள்ள வேண்டிய நேரம் இது. | 36096 | 4.512 |
| te | మీ Review dummy మందు తీసుకునే సమయం అయింది. | 31104 | 3.888 |
| kn | ನಿಮ್ಮ Review dummy ಔಷಧಿ ತೆಗೆದುಕೊಳ್ಳುವ ಸಮಯವಾಗಿದೆ. | 38208 | 4.776 |
| bn | আপনার Review dummy ওষুধ খাওয়ার সময় হয়েছে। | 33600 | 4.200 |

All six generated audio files have positive parsed duration/sample rate and retained SHA-256 values. All six cache checks return the same hash/mtime with the provider deliberately unavailable. Unit tests cover exact translations, name preservation, six distinct caches, legacy-cache exclusion, invalid language, partial/empty provider output, cleanup and retry. Valid MP3s and exact text inputs do not establish human pronunciation, intelligibility or independent native-speaker translation quality.

### Multiple-reminder retries: fixed for the new protocol

The pre-fix reproduction sent the identical id-less request twice. Taken returned 200/200 for Pending A then Pending B and made two logs. Snooze returned 200/200 and snoozed both reminders. Both could affect a second reminder when the caller intended only to retry the first. See [the new reproduction of historical code](evidence/software_resolution_20261023/defect_reproduction/results.json); this was not executed on October 9.

The updated protocol selects a firing with `/api/device/reminder`, then requires `id`, exact `fired_at` and unique `request_id` on `/api/device/action`. Device ownership, immutable binding and an existing success receipt are checked under `BEGIN IMMEDIATE`. The transition and receipt commit together. An exact retry returns the original success without another log/course decrement or extending Snooze. Reusing a key with a different binding returns 409. New requests cannot affect an inactive, stale or foreign row. A failed receipt write rolls back the dose transition as well; 503 explicitly asks for an identical retry.

Receipts are per device and persist across backend restart. Migration adds the receipt table without reassigning accounts, changing schedules/history or losing tokens. Browser actions also require firing identity, matching the existing frontend payload. Legacy id-less messages fail closed with 400; old firmware must be upgraded. A new intentional action can select another reminder; a retry cannot silently become that action. See [the complete contract](../DEVICE_PROTOCOL.md).

The simulator preserves prepared bodies for retries. Its CLI request file excludes the token. The updated sketch saves the bound request in ESP32 Preferences before sending, retries uncertain results with the same identity, and resolves that pending request before accepting another action. Server behavior is verified; the firmware target build and physical NVS/reboot/LED/Wi-Fi behavior are not verified here.

## Failures, corrections and retests

| Stage | Observed outcome | Disposition |
| --- | --- | --- |
| Extended pre-fix baseline | 33/54 PASS, 21/54 FAIL (58 failing assertions, including subtests) | Genuine missing-behavior baseline; [results](evidence/software_resolution_20261023/baseline_final/results.json) |
| First implementation retest | 40/54 PASS; 14 legacy-contract tests failed | Preserved. Tests were updated for explicit firing identity and durable success replay; id-less behavior was intentionally removed. |
| Initial new autoplay runs | Strict/default pending cases failed fixed 550 ms progress sampling; idle case passed | Preserved actual zero/near-zero early timeline samples. No first-sound latency claim is made. |
| Corrected autoplay sampling | Require observable progression within 6 s, then sustained progression >0.2 s; all 3 scenarios PASS | Paused/stalled media still fail. Negative control reconfirms that the old assertion falsely passes paused audio while the new assertion rejects it. |
| Full final unit rerun | 54/54 PASS | All 22 new methods plus updated original 32. |
| Full final browser rerun | 16 PASS; real microphone case NOT TESTED | Includes five visibility cycles and corrected UI10. |
| Full final live HTTP rerun | 17 PASS; three physical/LAN cases NOT TESTED | Real SQLite/HTTP, 300-second waits, duplicate/restart/outage checks. |
| Real TTS/provider + cache rerun | 12/12 PASS | Six new provider MP3s and six unchanged-cache checks. |
| ESP32 target compile attempt | Initialization exceeded 45 s; toolchain/ArduinoJson not installed | **NOT TESTED**; source compilation did not complete. Raw initialization log retained. |

The original unittest recorder counted failing subtest assertions as failures and could record one parent twice. It now records one case per unittest method and separately reports `failure_assertions`. The first two baseline recorder outputs remain intact as diagnostics. The final baseline is 54 methods = 33 PASS + 21 FAIL, with 58 failing assertions; no assertion was discarded to obtain that count.

## Final counts and actual measurements

| Layer | PASS | FAIL | NOT TESTED |
| --- | --- | --- | --- |
| Unit/API/database/scheduler | 54 | 0 | 0 |
| Browser/visibility | 16 | 0 | 1 |
| Live HTTP/SQLite/Snooze | 17 | 0 | 3 |
| Real TTS and cache | 12 | 0 | 0 |
| Human speech-quality evaluation | 0 | 0 | 1 |
| ESP32 target build | 0 | 0 | 1 |
| Total (105 case records; no skipped cases) | **99** | **0** | **6** |

The pre-existing software suite alone is 99 PASS / 0 FAIL / 5 NOT TESTED. The sixth not-tested entry is newly explicit firmware-build coverage. Three targeted autoplay runs and the negative harness control are separate repeats/control evidence, not extra application cases. Expected historical failures and initialization diagnostics do not inflate final application failure counts.

Final corrected UI10 timeline: 0.088059 → 0.652316 seconds after the trusted audio-prompt click. Initial app play and explicit false-gesture probe both reject with `NotAllowedError`, with no initial timeline progression. Final autoplay and full-browser wire audits show **zero `userGesture=true` Runtime calls before the first browser input**, across all sessions. Every acceptance probe explicitly uses false; actual launch commands have no autoplay bypass or mute flag. The targeted default-policy idle enablement test also plays a later reminder after transient activation expires. Human output delivery/hearing is not claimed.

Final live action POST samples: 30/30 successful; median **1.375 ms**, nearest-rank p95 **1.624 ms**. These are loopback action-POST timings; selecting a firing requires another request that is excluded from this timer. They are not LAN or GPIO measurements. Visibility cycles: 17.012, 17.006, 17.010, 17.009, 17.010 seconds. The final live run includes 7 actual backend restarts, including receipt replay after controlled client-side discard of a successful response. This models response loss; no actual packet-loss injection is claimed.

| Snooze trial | Real elapsed (s) | Scheduler delay (s) | Observer delay (s) | Taken logs |
| --- | --- | --- | --- | --- |
| B04-1 | 300.132117 | 0.118388 | 0.127669 | 0 |
| B04-2 | 301.007602 | 0.983368 | 1.003587 | 0 |
| B04-3 | 300.878681 | 0.852170 | 0.874470 | 0 |

No clock acceleration was used for these waits. Mocked-clock unit cases are separate. All prior October 23 provider files, logs, screenshots, results, hashes and autoplay diagnostics remain unchanged. Before-source/report snapshots and a pre-change hash manifest are retained under `software_resolution_20261023/`.

## Remaining limitations

The six NOT TESTED cases are **UI-VOICE, HUMAN-SPEECH, B03-LAN, B06-HARDWARE, B07-HARDWARE and FW-BUILD**. These cover actual microphone speech, human/native-language quality, independent LAN timing, physical switch/GPIO/LED/Wi-Fi behavior and the uncompleted ESP32 build. Human audibility/output delivery, independent native-speaker review, mobile/other-browser behavior, background/sleep operation, NVS power-loss/reboot behavior and long-term reliability remain unverified. Firmware must be built and bench-tested before relying on it.

New uncached speech requires internet. Full standalone offline operation is not implemented. The example remains HTTP with bearer tokens; TLS and token revocation are future work. Retry receipts are retained indefinitely; a retention policy is future work. A user who deliberately initiates a new request with a new target/ID can acknowledge the next reminder; idempotency does not infer human intention beyond the preserved request binding.

## Exact demonstration commands

Run from the repository root with the existing isolated interpreter. The output parent must be new; do not overwrite prior evidence.

```bash
cd /Users/pranav/Documents/DoseClock/DoseClockNLP
PY=/private/tmp/doseclock-review3-validation-20261023/venv/bin/python
OUT=/private/tmp/doseclock-review3-demo-20261023
mkdir "$OUT"
$PY -B tests/run_review3_suite.py --source . --output "$OUT/unit"
$PY -B tests/run_review3_audio.py --source . --output "$OUT/audio"
$PY -B tests/run_review3_live.py --source . --output "$OUT/live" --audio-cache "$OUT/audio"
$PY -B tests/run_review3_browser.py --source . --output "$OUT/browser" --audio-cache "$OUT/audio" --visibility
$PY -B tests/run_review3_autoplay.py --source . --output "$OUT/autoplay" --audio-cache "$OUT/audio"
$PY -B tests/audit_review3_tree.py --output "$OUT/git-audit.json"
```

The live command waits at least five real minutes. All application servers use exported temporary source, disposable accounts/SQLite and ephemeral loopback ports. The audio runner imports only TTS and writes into the supplied output directory. For a new interpreter, create a venv outside the checkout, install `tests/requirements-review3.txt`, then run `python -m playwright install chromium`.

To repeat the historical defect reproduction against the retained snapshot:

```bash
$PY -B tests/reproduce_resolution.py --source docs/testing/evidence/software_resolution_20261023/before_source --output "$OUT/historical-reproduction"
```

To repeat the paused-audio false-pass control (diagnostic only; it deliberately runs the original gesture-capable harness):

```bash
$PY -B tests/run_review3_autoplay_controls.py --source . --output "$OUT/paused-control" --audio-cache "$OUT/audio" --original-harness docs/testing/evidence/followup_20261023/originals/tests/run_review3_browser.py
```

For a paired dummy account on a separately running demo server, set the token privately and use a new request file. Reusing the same file demonstrates a retry; a deliberately new action needs a different file.

```bash
$PY -B tests/esp32_simulator.py --host http://127.0.0.1:5050 --action taken --request-file /private/tmp/doseclock-bound-demo.json
```

ESP32 build setup is separate and was not completed here. Install the ESP32 Arduino core and ArduinoJson 7, put the private upload copy in a `switch_hub/` sketch folder, then run `arduino-cli compile --fqbn esp32:esp32:esp32 /path/to/switch_hub`. Use the actual board's FQBN when it differs. A successful build would still not verify physical hardware.

## Individual Review 3 summary

> In a follow-up on 23 October 2026, after the original 9 October Review 3, I corrected DoseClock's multilingual reminder content and cache handling, and implemented occurrence-bound device actions with durable retry receipts. I reproduced the old Taken/Snooze retry defect, added concurrency, stale-state, isolation, rollback and restart regressions, and reran the automated software validation: 99 passed, 0 failed and 5 not tested. Corrected autoplay checks also passed without artificial activation. A separate ESP32 target-build check remains not tested, making six unverified case records in the complete evidence inventory. I do not claim human pronunciation, physical hardware or LAN validation.

## Evidence and git review

[Current summary](evidence/software_resolution_20261023/summary.json), [full case CSV](TEST_RESULTS.csv), [unit](evidence/software_resolution_20261023/regression_unit_complete/results.json), [live](evidence/software_resolution_20261023/regression_live_final/results.json), [browser](evidence/software_resolution_20261023/regression_browser_final/results.json), [audio](evidence/software_resolution_20261023/audio/results.json), [autoplay](evidence/software_resolution_20261023/autoplay_retest/results.json), [firmware build limitation](evidence/software_resolution_20261023/firmware_build/results.json), [git/commit recommendations](GIT_AUDIT_20261023.md). Large raw wire logs and full snapshots are preserved locally; compact audits bind them with hashes. No original evidence was deleted.
