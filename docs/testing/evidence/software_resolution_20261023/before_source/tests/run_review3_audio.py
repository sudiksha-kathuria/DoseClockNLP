"""Real gTTS generation and MP3 metadata checks, then controlled offline-cache reuse."""
import argparse,hashlib,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from mutagen.mp3 import MP3
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args()
sys.path.insert(0,str(Path(a.source).resolve()/'backend'));import tts
out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);tts.AUDIO_DIR=str(out)
records=[]
for lang,name in tts.LANGUAGES:
 start=time.perf_counter()
 try:
  relative=tts.get_or_create_audio('Review dummy',lang);f=out/Path(relative).name;info=MP3(f).info
  assert f.stat().st_size>0 and info.length>0
  digest=hashlib.sha256(f.read_bytes()).hexdigest();mtime=f.stat().st_mtime_ns
  actual={'language_code':lang,'bytes':f.stat().st_size,'duration_seconds':info.length,'sample_rate':info.sample_rate,'sha256':digest,'spoken_template':"It's time to take your Review dummy.",'human_pronunciation_verified':False}
  status='PASS'
 except Exception as e:status='FAIL';actual={'error':str(e),'human_pronunciation_verified':False};f=None
 records.append({'id':'AUDIO-'+lang,'feature':name+' audio generation and MP3 validity','expected':'Nonempty parsable MP3 with positive duration','actual':actual,'status':status,'duration_seconds':time.perf_counter()-start,'evidence':f.name if f else 'results.json'})
 if f:
  start=time.perf_counter()
  with patch('tts.gTTS',side_effect=ConnectionError('controlled synthesis unavailable')) as synth:
   cached=tts.get_or_create_audio('Review dummy',lang);assert not synth.called
  unchanged=f.stat().st_mtime_ns==mtime and hashlib.sha256(f.read_bytes()).hexdigest()==digest
  records.append({'id':'CACHE-'+lang,'feature':name+' cached reuse with synthesis unavailable','expected':'Same file/hash/mtime without a synthesis call','actual':{'unchanged':unchanged,'gTTS_calls':synth.call_count,'scope':'synthesis disabled by controlled injection; not a physical network outage'},'status':'PASS' if unchanged else 'FAIL','duration_seconds':time.perf_counter()-start,'evidence':f.name})
 print(lang,status,flush=True)
 (out/'results.json').write_text(json.dumps({'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'text_scope':'Existing fixed English sentence with six language codes; not verified translated speech','records':records},indent=2))
