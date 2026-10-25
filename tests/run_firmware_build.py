"""Clean ESP32 target build; record compiler exit and the actual firmware.bin.

Set PLATFORMIO_CORE_DIR to reuse a configured environment. Never uploads.
"""
import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', default='hardware')
    parser.add_argument('--output', required=True)
    parser.add_argument('--pio', default='pio')
    args = parser.parse_args()
    project = Path(args.project).resolve()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = datetime.now(ZoneInfo('Asia/Kolkata')).isoformat()
    base = [args.pio, 'run', '--project-dir', str(project), '--environment', 'esp32dev']
    commands = [base + ['--target', 'clean'], base]
    codes = []
    with (out / 'terminal.log').open('w') as log:
        for command in commands:
            codes.append(subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, 'PLATFORMIO_SETTING_ENABLE_TELEMETRY': 'No'}).returncode)
            if codes[-1] != 0:
                break
    binary = project / '.pio/build/esp32dev/firmware.bin'
    result = {'started_at': started, 'finished_at': datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),
        'commands': commands[:len(codes)], 'exit_codes': codes,
        'status': 'PASS' if codes == [0, 0] and binary.is_file() else 'FAIL',
        'scope': 'Clean ESP32 cross-compilation; no upload or physical validation',
        'platformio_core_dir': os.environ.get('PLATFORMIO_CORE_DIR', '<default>'),
        'source_sha256': {p: hashlib.sha256((project / p).read_bytes()).hexdigest()
            for p in ('switch_hub.ino', 'switch_input.h', 'platformio.ini')},
        'firmware_bin_exists': binary.is_file()}
    if binary.is_file():
        result.update(firmware_bin=str(binary), firmware_bin_bytes=binary.stat().st_size,
            firmware_bin_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
