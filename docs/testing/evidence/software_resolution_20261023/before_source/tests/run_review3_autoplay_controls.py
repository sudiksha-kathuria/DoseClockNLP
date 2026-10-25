"""Negative control: old UI10 passes a deliberately paused MP3; new UI10 rejects it.

Mutates only an exported temporary fixture, never the application checkout.
Requires the preserved original browser harness from this follow-up.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True); p.add_argument('--output', required=True)
    p.add_argument('--audio-cache', required=True); p.add_argument('--original-harness', required=True)
    args = p.parse_args()
    src = Path(args.source).resolve(); out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='doseclock-paused-negative-control-') as temp:
        root = Path(temp)
        for name in ('backend', 'frontend'): shutil.copytree(src/name, root/name)
        js = root/'frontend/static/js/clock.js'
        old = js.read_text()
        needle = 'audioUnlocked = true;'
        assert old.count(needle) == 1
        js.write_text(old.replace(needle, needle+'\n      reminderAudio.pause(); // INJECTED NEGATIVE CONTROL ONLY'))
        (out/'injected_change.txt').write_text('Temporary fixture only: pause immediately after successful audio unlock.\n')
        harness = root/'old_browser.py'; shutil.copy2(args.original_harness, harness)
        shutil.copy2(src/'tests/validation_server.py', root/'validation_server.py')
        commands = [
            [sys.executable, '-B', str(harness), '--source', str(root), '--output', str(out/'old_assertion'),
             '--audio-cache', str(Path(args.audio_cache).resolve()), '--only', 'UI10'],
            [sys.executable, '-B', str(src/'tests/run_review3_autoplay.py'), '--source', str(root),
             '--output', str(out/'corrected_assertion'), '--audio-cache', str(Path(args.audio_cache).resolve()), '--only', 'strict-pending']]
        codes = []
        for index, command in enumerate(commands):
            with (out/f'console_{index}.log').open('w') as log:
                codes.append(subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode)
        old_result = json.loads((out/'old_assertion/results.json').read_text())['records'][0]
        corrected = json.loads((out/'corrected_assertion/results.json').read_text())['records'][0]
        passed = old_result['status'] == 'PASS' and old_result['actual']['after_gesture']['paused'] is True and corrected['status'] == 'FAIL'
        result = {'validation_date': '23 October 2026', 'type': 'Injected negative control, not a product defect',
            'old_assertion': old_result, 'corrected_assertion_status': corrected['status'], 'exit_codes': codes,
            'status': 'PASS' if passed else 'FAIL'}
        (out/'results.json').write_text(json.dumps(result, indent=2)); print(result['status'])
        return 0 if passed else 1

if __name__ == '__main__': sys.exit(main())
