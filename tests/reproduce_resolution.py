"""Record both historical defects from an exported pre-fix source snapshot."""
import argparse,json,shutil,sys,tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args()
out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
with tempfile.TemporaryDirectory(prefix='doseclock-pre-resolution-') as temp:
 root=Path(temp)
 for name in ('backend','frontend'):shutil.copytree(Path(a.source)/name,root/name,ignore=shutil.ignore_patterns('__pycache__','*.db','.secret_key','*.mp3'))
 sys.path.insert(0,str(root/'backend'))
 import database,tts
 database.DB_PATH=str(root/'dummy.db');database.init_db()
 from app import app
 records=[];c=app.test_client()
 for action in ('taken','snooze'):
  user=database.create_user('review_repro_'+action,'dummy-password','Dummy')
  token=database.create_device_token(user['id'],'Dummy')
  ids=[]
  for name in ('Pending A','Pending B'):
   gid=database.add_medicine(user['id'],name,['08:00'],3,'en');mid=database.get_group(gid)[0]['id'];ids.append(mid);database.mark_fired(mid,None)
  body={'token':token,'action':action};responses=[c.post('/api/device/action',json=body) for _ in range(2)]
  rows=[dict(database.get_medicine(mid)) for mid in ids]
  records.append({'id':'REPRO-IDLESS-'+action,'status':'REPRODUCED','requests_identical':True,'http_statuses':[r.status_code for r in responses],
   'selected_medicines':[r.json.get('medicine_name') for r in responses],'taken_logs':len(database.get_dose_history(user['id'])),
   'due_states':[r['is_due'] for r in rows],'snoozed_rows':sum(bool(r['snoozed_until']) for r in rows),'token':'<redacted>'})
 class Speech:
  def save(self,path):Path(path).write_bytes(b'unit-provider-fixture')
 tts.AUDIO_DIR=str(root/'audio')
 with patch('tts.gTTS',side_effect=lambda **kw:Speech()) as synth:
  for lang,_ in tts.LANGUAGES:
   tts.get_or_create_audio('Review dummy',lang)
   records.append({'id':'REPRO-TEXT-'+lang,'status':'REPRODUCED','provider_arguments':synth.call_args.kwargs,'audio_scope':'provider mocked for input-text observation'})
 result={'recorded_at':datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),'chronology':'New reproduction from pre-fix snapshot; not an October 9 execution','records':records}
 (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
