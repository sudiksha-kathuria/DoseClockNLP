# Committed evidence and retained local archive

Evidence selection prepared on 25 October 2026. The original review date is 9 October; software validations are 23/25 October and the compatibility audit is 24 October. No test has been backdated.

This repository subset includes result records (including genuine failures), compiler logs, timing trials, current speech fixtures, compact autoplay audits and historical source/report snapshots required by reproduction commands. Large Runtime request dumps, JSONL traces, duplicate screenshots, older generated speech and install-download output are retained in the maintainer's local evidence archive. No originals are deleted.

`COMMITTED_EVIDENCE_SHA256SUMS.txt` covers the selected files. Original historical manifests intentionally cover the larger local archive; missing files from those full-archive manifests are not deleted evidence or new failures. `LOCAL_EVIDENCE_INVENTORY.json` records the local-only paths, sizes and hashes; it is an inventory, not a public download location. Ask the maintainer for the complete archive if needed.

The latest software result is 115 PASS / 0 FAIL / 5 NOT TESTED; a separate target build adds one PASS. Three targeted autoplay repeats are non-additive. Physical testing and human hearing/pronunciation remain unverified. The report files retain their older dated sections for chronology.

The blank outer-page `browser/screenshots/UI10.png` is omitted from the latest evidence subset. Use `browser/UI10-clean-profile/final.png` and its playback JSON instead. The five selected screenshots were visually reviewed and contain only dummy accounts/reminders; the six selected MP3s have verified metadata, not human pronunciation approval.
