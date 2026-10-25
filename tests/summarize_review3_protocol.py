"""Keep actual Runtime/Input wire requests without HTTP credentials/cookies.

Usage: --input private DEBUG=pw:protocol log --output new evidence directory.
Raw logs stay at the supplied private location; sha256 binds the extract to it.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path

def main():
    p = argparse.ArgumentParser(); p.add_argument('--input', required=True); p.add_argument('--output', required=True)
    args = p.parse_args(); source = Path(args.input); out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    commands = []; launches = []; cases = []
    for line in source.read_text().splitlines():
        if '<launching>' in line: launches.append(line)
        if line.startswith(('UI', 'B05-', 'strict-', 'default-')): cases.append(line)
        if 'SEND ► ' not in line: continue
        try: command = json.loads(line.split('SEND ► ', 1)[1])
        except ValueError: continue
        if command.get('method') in ('Runtime.evaluate', 'Runtime.callFunctionOn',
                'Input.dispatchMouseEvent', 'Input.dispatchKeyEvent', 'Page.navigate'):
            commands.append(command)
    (out/'requests.json').write_text(json.dumps(commands, indent=2))
    (out/'launch.txt').write_text('\n'.join(launches)+'\n')
    (out/'console.log').write_text('\n'.join(cases)+'\n')
    groups = collections.defaultdict(list)
    for command in commands: groups[command.get('sessionId')].append(command)
    sessions = []
    for session, rows in groups.items():
        navs = [i for i, r in enumerate(rows) if r['method'] == 'Page.navigate']
        if not navs: continue
        start = navs[-1]
        end = next((i for i in range(start, len(rows)) if rows[i]['method'].startswith('Input.')), len(rows))
        calls = [r for r in rows[start:end] if r['method'].startswith('Runtime.')]
        sessions.append({'sessionId': session, 'navigation': rows[start]['params']['url'],
            'runtime_before_first_input': len(calls),
            'userGesture_true': sum(r['params'].get('userGesture') is True for r in calls),
            'userGesture_false': sum(r['params'].get('userGesture') is False for r in calls),
            'userGesture_omitted': sum('userGesture' not in r['params'] for r in calls)})
    (out/'summary.json').write_text(json.dumps({'source_private_path': str(source),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'scope': 'Actual outgoing Runtime/Input/navigation calls; HTTP credentials excluded. Last navigation to first browser input per session.',
        'sessions': sessions}, indent=2))

if __name__ == '__main__': main()
