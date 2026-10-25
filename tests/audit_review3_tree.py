"""Read-only repository file/secrets-candidate audit; never stage/delete files.

Reports locations and classifications, never credential values. Pattern scans
cannot prove absence of every secret. Run from repository root.
"""
import argparse
import collections
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    out=Path(args.output).resolve()
    tracked=set(subprocess.check_output(['git','ls-files'],text=True).splitlines())
    ignored=set(subprocess.check_output(['git','ls-files','--others','--ignored','--exclude-standard'],text=True).splitlines())
    status=subprocess.check_output(['git','status','--short','--branch','--untracked-files=all'],text=True)
    rows=[];findings=[]
    for path in sorted(Path('.').rglob('*')):
        if not path.is_file() or '.git' in path.parts or path.resolve()==out:continue
        name=str(path);size=path.stat().st_size
        evidence=name.startswith('docs/testing/evidence/')
        category=('evidence' if evidence else 'source' if name.startswith(('backend/','frontend/','hardware/'))
                  else 'test' if name.startswith('tests/') else 'documentation_or_configuration')
        recommendation='commit after review'
        if evidence:
            recommendation='commit selectively: reviewed result/log/manifest/screenshot'
            if any(part in path.parts for part in ('before_source','originals')) or path.suffix=='.py':
                recommendation='keep full historical source/helper snapshot local; preserve archive'
            if path.suffix=='.mp3':recommendation='keep generated media local; optional reviewed evidence attachment'
            if path.name=='requests.json' or path.suffix=='.jsonl':recommendation='keep raw protocol trace local; commit compact audit/hash'
        runtime=(path.suffix in ('.db','.sqlite','.sqlite3','.pem','.key','.p12') or path.name in ('.secret_key','.env')
                 or name in ignored or '__pycache__' in path.parts or path.name.startswith('.env.') and path.name!='.env.example')
        if runtime:
            category='runtime_or_possible_secret';recommendation='keep local; do not stage'
            findings.append({'path':name,'kind':'database/key/cache/environment candidate'})
        if size>5*1024*1024:
            recommendation='keep oversized raw evidence local; preserve file and hash'
            findings.append({'path':name,'kind':'oversized >5 MiB','bytes':size})
        if path.suffix in ('.py','.md','.ino','.txt','.log','.json','.jsonl','.csv','.html','.js','.yaml','.yml'):
            text=path.read_text(errors='replace')
            patterns=[r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                r'\b(?:sk-[A-Za-z0-9_-]{35,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16})\b']
            if any(re.search(pattern,text) for pattern in patterns):
                findings.append({'path':name,'kind':'credential-shaped literal: review privately'})
            def scan(value,location=''):
                if isinstance(value,dict):
                    for key,v in value.items():
                        if key.lower().replace('-','_') in ('token','device_token','api_key','secret','password','authorization','cookie','set_cookie') and isinstance(v,str):
                            allowed=(not v or '<' in v or v in ('invalid','invalid-token','deliberately-invalid','dummy-password','test-only','test-only-password','unknown') or v.startswith(('your-','paste-')))
                            if not allowed:findings.append({'path':name,'kind':'sensitive-key string candidate','location':location+'/'+key})
                        scan(v,location+'/'+key)
                elif isinstance(value,list):
                    for i,v in enumerate(value):scan(v,location+'/'+str(i))
            try:
                if path.suffix=='.json':scan(json.loads(text))
                elif path.suffix=='.jsonl':
                    for i,line in enumerate(text.splitlines()):scan(json.loads(line),str(i+1))
            except (ValueError,RecursionError):pass
        # Final status/manifests are populated after this audit. Avoid a
        # circular hash dependency; the final manifest hashes this audit.
        deferred=path.name in ('git_status_after.txt','RESOLUTION_SHA256SUMS.txt')
        rows.append({'path':name,'bytes':size,'tracked':name in tracked,'ignored':name in ignored,'category':category,
                     'recommendation':recommendation,'sha256':None if deferred else hashlib.sha256(path.read_bytes()).hexdigest(),
                     'hash_note':'finalization metadata; see final manifest' if deferred else None})
    result={'recorded_at':datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),
        'branch':subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
        'file_count':len(rows),'total_bytes':sum(r['bytes'] for r in rows),
        'tracked_modifications':sum(line.startswith(' M') for line in status.splitlines()),
        'untracked_files':sum(line.startswith('??') for line in status.splitlines()),
        'staged_changes':subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines(),
        'categories':dict(collections.Counter(r['category'] for r in rows)),'findings':findings,
        'limitations':'Pattern/key scanning plus manual review is not a proof of absence of every secret. Raw private wire logs and downloaded toolchains outside the checkout remain local.',
        'files':rows}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))

if __name__=='__main__':main()
