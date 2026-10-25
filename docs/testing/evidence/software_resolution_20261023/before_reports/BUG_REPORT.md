# DoseClock - Bugs, Fixes and Retests

Recorded 2026-10-23T02:47:46+05:30. Ten software defect groups were fixed on `validation/review3-20261023`. No commits/pushes. Original test assertions were not weakened.

## BUG-01: New schedule did not prepare speech

- Before: prepare_audio was never called after a new schedule.
- Fix: Creation and editing enqueue existing background audio preparation.
- Files: `backend/app.py`.
- Regression: `test_creation_multiple_times_and_audio_warming`. **Final PASS**; original output retained.
- Evidence: [baseline assertions/tracebacks](evidence/regression_baseline_corrected/terminal.log), [final suite](evidence/final_suite/results.json).

## BUG-02: Removed medicine could remain due

- Before: Deleting set days_remaining=0 but left is_due and snoozed_until; due lookup did not exclude inactive rows.
- Fix: Clear pending state on removal and exclude inactive/archived rows from active/due queries.
- Files: `backend/database.py`.
- Regression: `test_deleting_due_medicine_clears_alarm_and_preserves_history`. **Final PASS**; original output retained.
- Evidence: [baseline assertions/tracebacks](evidence/regression_baseline_corrected/terminal.log), [final suite](evidence/final_suite/results.json).

## BUG-03: Editing after a logged dose returned 500

- Before: Deleting time-slot rows violated dose_log foreign keys.
- Fix: Add an additive is_archived column; archive old rows and insert replacements transactionally, preserving historical metadata and references.
- Files: `backend/database.py`.
- Regression: `test_edit_after_taken_preserves_historical_details`. **Final PASS**; original output retained.
- Evidence: [baseline assertions/tracebacks](evidence/regression_baseline_corrected/terminal.log), [final suite](evidence/final_suite/results.json).

## BUG-04: Invalid and duplicate schedule times accepted

- Before: 25:00 and other noncanonical/duplicate values could be stored but never scheduled correctly.
- Fix: Validate distinct canonical HH:MM values on create/edit.
- Files: `backend/app.py`.
- Regression: `test_invalid_time_values_rejected`. **Final PASS**; original output retained.
- Evidence: [baseline assertions/tracebacks](evidence/regression_baseline_corrected/terminal.log), [final suite](evidence/final_suite/results.json).

## BUG-05: Malformed JSON/type errors returned 500

- Before: Lists were used as dictionaries and structured tokens were passed to SQLite. A second failing test covers wrong field types.
- Fix: Require JSON objects and validate text token/action/name, time lists, group IDs and positive integer day inputs.
- Files: `backend/app.py`.
- Regression: `test_non_object_json_rejected`. **Final PASS**; original output retained.
- Evidence: [baseline assertions/tracebacks](evidence/regression_baseline_corrected/terminal.log), [final suite](evidence/final_suite/results.json).

## BUG-06: Browser did not receive firing generation

- Before: Routes accepted a firing timestamp, but /check_reminders omitted it and the browser never submitted it.
- Fix: Return fired_at and send it with browser Taken/Snooze; keep stale-generation rejection.
- Files: `backend/app.py; frontend/static/js/clock.js`.
- Regression: `test_stale_firing_generation_is_rejected`. **Final PASS**; original output retained.
- Evidence: [baseline assertions/tracebacks](evidence/regression_baseline_corrected/terminal.log), [final suite](evidence/final_suite/results.json).

## BUG-07: False browser success on failed actions

- Before: Network abort showed Taken success or “Snoozed for 5 minutes” despite unchanged due state; HTTP 409 also showed success.
- Fix: Check HTTP/JSON success, preserve alarm on rejection/transport failure, show retry feedback and prevent overlapping submissions.
- Files: `frontend/static/js/clock.js`.
- Regression: `UI06 / UI07 / UI08`. **Final PASS**; original output retained.
- Evidence: [baseline browser run](evidence/browser_baseline/results.json), [final browser run](evidence/browser_final/results.json).

## BUG-08: External device acknowledgment left stale alarm

- Before: Polling returned early while currentReminder existed.
- Fix: Continue polling and reconcile cleared/replaced firing state; pause audio when an alarm clears.
- Files: `frontend/static/js/clock.js`.
- Regression: `UI09`. **Final PASS**; original output retained.
- Evidence: [baseline browser run](evidence/browser_baseline/results.json), [final browser run](evidence/browser_final/results.json).

## BUG-09: Audio unlock replaced reminder with silence

- Before: A genuine user click changed the real MP3 to the 0.000125-second silent clip; Snooze also lacked reliable pause.
- Fix: Keep the existing audio source on unlock, hide hint only after successful play, and pause on Taken/Snooze/clear.
- Files: `frontend/static/js/clock.js`.
- Regression: `UI10`. **Final PASS**; original output retained.
- Evidence: [corrected native-autoplay baseline](evidence/autoplay_baseline_corrected/results.json), [full final browser run](evidence/browser_final/results.json).

## BUG-10: Missing audio was loaded as a null URL

- Before: A visual-only reminder set the audio src to the literal string null.
- Fix: Avoid playback without a URL, remove stale src and keep visual actions available.
- Files: `frontend/static/js/clock.js`.
- Regression: `UI11`. **Final PASS**; original output retained.
- Evidence: [missing-audio baseline](evidence/browser_audio_baseline/results.json), [final browser run](evidence/browser_final/results.json).

## Direct before/after screenshots

- [False Taken success during a network failure](evidence/browser_baseline/screenshots/observed_review_taken_network_failure.png).
- [Fixed behavior: alarm retained and retry message](evidence/browser_final/screenshots/observed_review_taken_network_failure.png).
- [False Snooze success](evidence/browser_baseline/screenshots/observed_review_snooze_network_failure.png).
- [Fixed Snooze failure feedback](evidence/browser_final/screenshots/observed_review_snooze_network_failure.png).

## Data preservation

The edit fix archives superseded time-slot rows instead of deleting them. The log retains its original medicine label, scheduled time, language and timestamp. Migration adds a column with default zero; the extra final regression reconstructs the preceding schema with an owned log/token fixture, migrates it, and verifies that history, account association and token remain intact. Live tests never open the repository's real database.

## Unresolved limitations

1. **Device replay with multiple due rows:** two identical token/action bodies can acknowledge two different due medicines. This was reproduced over real HTTP. The old protocol has no occurrence/request ID, so the server cannot distinguish a deliberate next action from a retry. No blind retries or arbitrary cooldown were introduced. A protocol/firmware design change is needed for robust retry safety.
2. **Spoken-language content:** the TTS module still uses an English sentence for six language codes. Valid MP3 generation is not evidence of a translated, intelligible message. No translation feature or clinical-language claim was added.
3. **Voice/hardware/LAN evidence:** no real utterance, GPIO, switch, LED, ESP32 Wi-Fi or independent LAN timing result exists in this run. The teammate's report remains separate.
4. **Offline scope:** existing MP3 reuse is verified when synthesis is blocked; uncached speech and standalone offline reminder operation are not provided.

Two scheduler mock errors and the original autoplay probe configuration were harness diagnostics, not software defects; see TEST_REPORT for the corrections and preserved raw output.
