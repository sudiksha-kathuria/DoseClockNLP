"""Build the dated addendum from preserved originals and actual follow-up results.

Run from repository root. Original logs and snapshots are never rewritten.
"""
import collections
import csv
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('docs/testing/evidence/followup_20261023')
docs = Path('docs/testing')
def read(name): return json.loads((root/name).read_text())
unit = read('regression_unit/results.json')
browser = read('regression_browser/results.json')
live = read('regression_live/results.json')
audio = read('regression_audio/results.json')
assert len(live['records']) == 18, 'Wait for all three real Snooze deadlines'
latest = unit['records'] + browser['records'] + live['records'] + audio['records']
counts = collections.Counter(r['status'] for r in latest)
counts['NOT TESTED'] += 1  # HUMAN-SPEECH remains unverified, carried forward explicitly.
assert counts == {'PASS': 75, 'NOT TESTED': 5}, counts
targeted = read('autoplay_verified/results.json')
assert all(r['status'] == 'PASS' for r in targeted['records'])
stamp = datetime.now(ZoneInfo('Asia/Kolkata')).isoformat()
media = read('regression_browser/UI10-clean-profile/results.json')
m1, m2 = [s['media'] for s in media['playing_samples']]
response = next(r['actual'] for r in live['records'] if r['id'] == 'B03-LOCAL')
visibility = [r['actual']['visible_seconds_after_scheduled_fixture'] for r in browser['records'] if r['id'].startswith('B05-')]
snoozes = sorted((r for r in live['records'] if r['id'].startswith('B04-')), key=lambda r: r['id'])

summary = {'validation_date': '23 October 2026', 'recorded_at': stamp,
    'chronology': 'Follow-up executed after initial Review 3; not backdated',
    'full_regression': {'PASS':75,'FAIL':0,'SKIP':0,'NOT TESTED':5}, 'full_regression_case_count': 80,
    'targeted_autoplay_repeats': {'PASS': 3, 'counted_again_in_full_regression': False},
    'product_changes_this_followup': [], 'historical_UI10_evidence': 'INVALIDATED for full autoplay claim; observations preserved',
    'unresolved': ['English-only message for six language codes', 'Multiple-reminder retry safety'],
    'not_tested': ['UI-VOICE', 'HUMAN-SPEECH', 'B03-LAN', 'B06-HARDWARE', 'B07-HARDWARE']}
(root/'regression_summary.json').write_text(json.dumps(summary, indent=2))

common = f'''## Follow-up validation — 23 October 2026

Recorded: {stamp} (Asia/Kolkata). **This follow-up was executed after the initial Review 3 validation.** It does not establish any earlier testing date. Branch remains `validation/review3-20261023`; no commit or push was made.

The complete regression suite was rerun after correcting the autoplay harness: **75 PASS, 0 FAIL, 0 skipped, 5 NOT TESTED (80 cases)**. This comprises 32 unit/API/database/scheduler, 16 browser/visibility, 15 live HTTP/Snooze, and 12 real audio/cache cases. The same five evidence gaps remain. Three additional targeted autoplay runs passed; these repeat or extend UI10 and are reported separately, not added to the 80-case total.

The original UI10 PASS is **invalidated as complete autoplay evidence**. A wire replay of the unchanged original harness confirms `userGesture=true` on `Runtime.callFunctionOn`, including observations before the first browser click. Historical CDP wire logs do not exist, so the replay is dated as new evidence. The original paused/source/duration observations remain preserved. An injected negative control proves the original assertions also pass with `after_gesture.paused=true`; the corrected test rejects that fixture.

In an initially empty disk profile, with HTTP authentication and no prior browser input, the application's initial unmuted MP3 `play()` rejects with `NotAllowedError`; `currentTime` remains zero. All acceptance-path `Runtime.evaluate` calls explicitly set `userGesture=false`. After a trusted browser click on the application's “Tap here to hear the reminder” prompt, `play()` resolves, the real MP3 is unmuted at volume 1, decoded audio bytes increase, and time advances ({m1['currentTime']:.6f} → {m2['currentTime']:.6f} seconds in the full rerun). Snooze pauses playback and stops time progression. A separate idle-screen enablement click permits the later reminder to play automatically after transient activation expires. Both default Chromium policy and `document-user-activation-required` were tested; actual launch commands contain no autoplay bypass and omit `--mute-audio`.

No additional application defect was discovered. The corrected baseline reproduction reconfirms the original silent-clip replacement defect, and the existing fix passes. This follow-up changes test harnesses and evidence only; the ten original software fix groups remain supported within their documented scopes.

**Unresolved:** the TTS sentence remains English for all six language codes; generating six MP3s does not verify translations or intelligibility. Multiple-reminder retries remain unsafe: identical id-less requests can acknowledge two different pending medicines. The live rerun reproduces that limitation; its characterization PASS means “limitation reproduced,” not “fixed.” Translation work and a protocol/firmware redesign are outside this focused autoplay correction; neither issue is classified as fixed.

**Still unverified:** actual human hearing/output-device delivery; speech quality, pronunciation and six-language intelligibility; real microphone acknowledgment; genuine LAN timing; physical GPIO/switch classification, LED feedback and ESP32 Wi-Fi/outages; other browsers/mobile platforms, background/sleep behavior and long-term reliability. New uncached synthesis still needs internet, and standalone full offline operation remains unimplemented. Media progression/decoding establishes browser playback state, not that a person heard speech.

See [dated audit and reproduction commands](AUTOPLAY_FOLLOWUP_20261023.md), [full rerun summary](evidence/followup_20261023/regression_summary.json), and [corrected CSV](TEST_RESULTS.csv). Original report/CSV/source snapshots and a SHA-256 manifest are retained under [follow-up originals](evidence/followup_20261023/originals/). Existing raw evidence was preserved byte-for-byte.

## Original Review 3 record (historical)

The following is the original report, retained for chronology. Its original autoplay interpretation is superseded by the follow-up above; original measurements and all other scoped results remain historical evidence.

'''
for filename in ('TEST_REPORT.md', 'REVIEW3_RESULTS.md'):
    original = (root/'originals/docs/testing'/filename).read_text()
    heading, body = original.split('\n', 1)
    (docs/filename).write_text(heading+'\n\n'+common+body.lstrip())

audit = f'''# DoseClock autoplay evidence audit — 23 October 2026

This is a follow-up after the initial Review 3, recorded {stamp}. Base commit remains `a1230c928a0471aa2a05e0af6b32ee2a64a0cd05`; branch is `validation/review3-20261023`. No commit/push. No new application changes were required.

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
| `autoplay_baseline_corrected`, UI10 | Silent-source replacement after a real click is genuine and is independently reproduced by this follow-up. Its no-gesture precondition lacked adequate isolation. |
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
| Current application under full regression UI10 | PASS: zero time before input; post-click {m1['currentTime']:.6f} → {m2['currentTime']:.6f} s, decoded bytes {m1['decodedBytes']} → {m2['decodedBytes']}; stops on Snooze | [full-rerun UI10](evidence/followup_20261023/regression_browser/UI10-clean-profile/results.json) |

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

Fresh response samples: 30/30 successful, median {response['median_ms']:.3f} ms, nearest-rank p95 {response['p95_ms']:.3f} ms on loopback. Fresh visibility cycles: {', '.join(f'{v:.3f}' for v in visibility)} seconds. These are new measurements; original measurements remain in the historical reports.

| Snooze trial | Real elapsed (s) | Scheduler delay (s) | Observer delay (s) | Taken logs |
| --- | --- | --- | --- | --- |
'''
for r in snoozes:
    a=r['actual']; audit += f"| {r['id']} | {a['real_elapsed_seconds']:.6f} | {a['server_firing_delay_seconds']:.6f} | {a['observed_delay_seconds']:.6f} | {a['taken_logs']} |\n"
audit += '''
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
'''
(docs/'AUTOPLAY_FOLLOWUP_20261023.md').write_text(audit)

# Preserve original row observations, qualify historical autoplay, then add new phases.
original_csv = root/'originals/docs/testing/TEST_RESULTS.csv'
with original_csv.open(newline='') as f:
    reader=csv.DictReader(f); fields=reader.fieldnames; rows=list(reader)
for row in rows:
    if row['phase'] == 'final':
        row['phase'] = 'initial_review3_final'
        if row['test_id'] == 'UI10':
            row['status'] = 'INVALIDATED'
            row['actual_result'] = 'Original recorded PASS; invalidated for full autoplay claim after CDP/assertion audit. Original observations: '+row['actual_result']
def append(record, phase, evidence, unit=False):
    rows.append({'test_id': ('UNIT::' if unit else '')+record['id'], 'phase': phase,
        'feature': record.get('feature',record['id']), 'expected_result': record.get('expected','All assertions in named test must hold'),
        'actual_result': json.dumps(record.get('actual'),ensure_ascii=False) if not isinstance(record.get('actual'),str) else record['actual'],
        'status': record['status'], 'duration_seconds': record.get('duration_seconds',''), 'evidence_location': evidence})
for folder, payload, is_unit in [('regression_unit',unit,True), ('regression_browser',browser,False),
        ('regression_live',live,False), ('regression_audio',audio,False)]:
    for record in payload['records']:
        append(record,'followup_final_20261023',f'evidence/followup_20261023/{folder}/results.json',is_unit)
rows.append({'test_id':'HUMAN-SPEECH','phase':'followup_final_20261023','feature':'Six-language pronunciation/intelligibility',
    'expected_result':'Independent human listening in each language','actual_result':'Still unverified; new generation/decoding is not human listening. English-only template unresolved.',
    'status':'NOT TESTED','duration_seconds':'','evidence_location':'AUTOPLAY_FOLLOWUP_20261023.md'})
for r in targeted['records']: append(r,'followup_targeted_repeat_20261023','evidence/followup_20261023/autoplay_verified/'+r['evidence'])
for folder in ('autoplay_before','autoplay_corrected'):
    for r in read(folder+'/results.json')['records']: append(r,'followup_harness_diagnostic_20261023','evidence/followup_20261023/'+folder+'/results.json')
for r in read('original_product_reproduction/results.json')['records']:
    append(r,'followup_original_product_expected_fail_20261023','evidence/followup_20261023/original_product_reproduction/results.json')
for issue,detail in [('LIMIT-TTS-ENGLISH','UNRESOLVED: fixed English sentence for six voice codes; valid MP3s do not establish translations/intelligibility.'),
        ('LIMIT-MULTI-RETRY','UNRESOLVED: identical id-less action requests acknowledge two different due reminders. Characterization PASS is not remediation.')]:
    rows.append({'test_id':issue,'phase':'followup_limitations_20261023','feature':issue,'expected_result':'Explicit issue classification',
        'actual_result':detail,'status':'UNRESOLVED','duration_seconds':'','evidence_location':'AUTOPLAY_FOLLOWUP_20261023.md'})
with (docs/'TEST_RESULTS.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
print(json.dumps(summary,indent=2))
