"""Dated follow-up autoplay runs against an isolated export; keeps every attempt."""
import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
from review3_media import verify_autoplay

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True); p.add_argument('--output', required=True)
    p.add_argument('--audio-cache', required=True); p.add_argument('--control', action='store_true')
    p.add_argument('--only', default='strict-pending,default-pending,default-idle')
    args = p.parse_args()
    out = Path(args.output).resolve(); out.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='doseclock-autoplay-export-') as temp:
        root = Path(temp)
        for name in ('backend', 'frontend'):
            shutil.copytree(Path(args.source).resolve()/name, root/name,
                ignore=shutil.ignore_patterns('__pycache__', '*.db', '.secret_key', '*.mp3'))
        for audio in Path(args.audio_cache).glob('*.mp3'):
            shutil.copy2(audio, root/'frontend/static/audio'/audio.name)
        sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
        base = f'http://127.0.0.1:{port}'; key = secrets.token_hex(20)
        def fixture(user, operation='state'):
            req = urllib.request.Request(base+'/__review3/fixture',
                data=json.dumps({'username': user, 'operation': operation}).encode(),
                headers={'Content-Type': 'application/json', 'X-Review3-Fixture': key})
            with urllib.request.urlopen(req, timeout=3) as response: return json.load(response)
        with (out/'server.log').open('w') as log:
            server = subprocess.Popen([sys.executable, '-B', str(Path(__file__).with_name('validation_server.py')),
                '--source', str(root), '--database', str(root/'validation.db'), '--port', str(port)],
                env={**os.environ, 'DOSECLOCK_FIXTURE_KEY': key}, stdout=log, stderr=subprocess.STDOUT)
            try:
                for _ in range(100):
                    try: urllib.request.urlopen(base+'/login', timeout=.3); break
                    except Exception: time.sleep(.1)
                records = []
                with sync_playwright() as pw:
                    for spec in args.only.split(','):
                        policy, scenario = spec.split('-')
                        started = time.perf_counter()
                        try:
                            actual = verify_autoplay(pw, base, fixture, out/spec, policy, scenario, args.control)
                            status = 'PASS'
                        except Exception:
                            status = 'FAIL'; actual = {'traceback': traceback.format_exc()}
                        records.append({'id': 'AUTOPLAY-'+spec, 'status': status, 'actual': actual,
                            'duration_seconds': time.perf_counter()-started, 'evidence': spec+'/results.json'})
                        print(spec, status, flush=True)
                        (out/'results.json').write_text(json.dumps({'validation_date': '23 October 2026',
                            'stage': 'Follow-up after initial Review 3', 'control_only': args.control, 'records': records}, indent=2))
                return 1 if any(r['status'] == 'FAIL' for r in records) else 0
            finally:
                server.terminate(); server.wait(timeout=10)

if __name__ == '__main__': sys.exit(main())
