"""Real loopback HTTP/SQLite benchmarks, including a real concurrent five-minute Snooze wait.

No accelerated clock, no physical ESP32. Source is copied to an isolated temp directory.
"""
import argparse,concurrent.futures,hashlib,http.cookiejar,json,math,os,re,secrets,shutil,socket,sqlite3,statistics,subprocess,sys,tempfile,threading,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from esp32_simulator import ESP32Simulator
p=argparse.ArgumentParser();p.add_argument('--source',default='.');p.add_argument('--output',required=True);p.add_argument('--audio-cache');a=p.parse_args()
out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
records=[];samples=[];lock=threading.Lock();server=None

def record(cid,feature,expected,actual,status='PASS',duration=0):
 with lock:
  records.append({'id':cid,'feature':feature,'expected':expected,'actual':actual,'status':status,'duration_seconds':duration,'evidence':'results.json'})
  (out/'results.json').write_text(json.dumps({'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'SIMULATED ESP32 COMMUNICATION: real loopback HTTP + disposable SQLite; no physical hardware','records':records,'response_time_samples':samples},indent=2))
 print(cid,status,flush=True)

with tempfile.TemporaryDirectory(prefix='doseclock-live-') as td:
 root=Path(td);src=Path(a.source).resolve()
 for name in ['backend','frontend']:shutil.copytree(src/name,root/name,ignore=shutil.ignore_patterns('__pycache__','*.db','.secret_key','*.mp3'))
 if a.audio_cache:
  for audio in Path(a.audio_cache).glob('*.mp3'):shutil.copy2(audio,root/'frontend/static/audio'/audio.name)
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();base=f'http://127.0.0.1:{port}'
 key=secrets.token_hex(20);db=root/'live.db';log=(out/'server.log').open('w')
 def start_server():
  global server
  server=subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('validation_server.py')),'--source',str(root),'--database',str(db),'--port',str(port)],env={**os.environ,'DOSECLOCK_FIXTURE_KEY':key,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
  for _ in range(100):
   try:
    with urllib.request.urlopen(base+'/login',timeout=.3):return
   except Exception:time.sleep(.1)
  raise RuntimeError('Live test server did not start')
 def stop_server():
  server.terminate();server.wait(timeout=10)
 def fixture(user,op='state',**extra):
  request=urllib.request.Request(base+'/__review3/fixture',data=json.dumps({'username':user,'operation':op,**extra}).encode(),headers={'Content-Type':'application/json','X-Review3-Fixture':key},method='POST')
  with urllib.request.urlopen(request,timeout=3) as r:return json.load(r)
 def paired(user):
  fixture(user)
  opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  with opener.open(base+'/login',urllib.parse.urlencode({'username':user,'password':'dummy-password'}).encode()) as r:assert r.status==200
  with opener.open(base+'/pair_device',urllib.parse.urlencode({'name':'SIMULATED ESP32 COMMUNICATION'}).encode()) as r:
   body=r.read().decode();assert 'no-store' in r.headers.get('Cache-Control','')
  token=re.search(r'id="paired-token"[^>]*value="([^"]+)"',body).group(1)
  return ESP32Simulator(base,token),opener
 def digest():
  conn=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
  state={t:conn.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall() for t in ['users','medicines','dose_log','devices']};conn.close()
  return hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest()
 start_server()
 try:
  # All three trials use the unmodified 300-second deadline and run concurrently.
  snoozes=[]
  for i in range(1,4):
   user='bench_snooze_'+str(i);sim,_=paired(user);mid=fixture(user,'due')['id'];started=time.perf_counter();response=sim.action('snooze');state=fixture(user);row=next(r for r in state['medicines'] if r['id']==mid)
   assert response['http_status']==200 and not row['is_due'] and not state['logs']
   snoozes.append({'id':i,'user':user,'mid':mid,'start_perf':started,'deadline':row['snoozed_until'],'request':response,'observed':False})
  def watch_snoozes():
   end=time.monotonic()+310;last_progress=0
   while time.monotonic()<end and not all(s['observed'] for s in snoozes):
    for s in snoozes:
     if s['observed']:continue
     try:
      state=fixture(s['user']);row=next(r for r in state['medicines'] if r['id']==s['mid'])
      if row['is_due']:
       wall=datetime.now();delay=(wall-datetime.fromisoformat(s['deadline'])).total_seconds();elapsed=time.perf_counter()-s['start_perf'];server_delay=(datetime.fromisoformat(row['last_fired_at'])-datetime.fromisoformat(s['deadline'])).total_seconds()
       s['observed']=True
       actual={'real_elapsed_seconds':elapsed,'stored_deadline':s['deadline'],'observed_at':wall.isoformat(),'observed_delay_seconds':delay,'server_firing_delay_seconds':server_delay,'taken_logs':len(state['logs']),'request':s['request'],'clock_mocking':False,'backend_restarted_during_wait':True}
       record('B04-'+str(s['id']),'Real 300-second Snooze and restart recovery','Deadline 300 s; backend due observed within 2 s; no Taken log',actual,'PASS' if 299.8<=elapsed<=302.2 and 0<=server_delay<=2 and 0<=delay<=2 and not state['logs'] else 'FAIL',elapsed)
     except Exception:pass  # Intentional short backend outages are recorded separately below.
    elapsed=time.perf_counter()-snoozes[0]['start_perf']
    if elapsed-last_progress>=30:print('Snooze real-time wait',round(elapsed,1),'seconds',flush=True);last_progress=elapsed
    time.sleep(.15)
   for s in snoozes:
    if not s['observed']:record('B04-'+str(s['id']),'Real Snooze re-fire','Observed within 2 s of 300-second deadline','Not observed before wait timeout','FAIL',time.perf_counter()-s['start_perf'])
  watcher=threading.Thread(target=watch_snoozes);watcher.start()

  sim,opener=paired('bench_taken');trial_results=[]
  for i in range(10):
   fixture('bench_taken','due');before=len(fixture('bench_taken')['logs']);response=sim.action('taken');after=len(fixture('bench_taken')['logs'])
   trial_results.append({'trial':i+1,'http_status':response['http_status'],'logs_before':before,'logs_after':after})
  record('B01','Taken correctness over real HTTP','10/10, exactly one new log per fresh due reminder',trial_results,'PASS' if all(t['http_status']==200 and t['logs_after']==t['logs_before']+1 for t in trial_results) else 'FAIL')
  invalid=[]
  for i in range(10):
   before=digest();response=sim.action('taken',token='deliberately-invalid');after=digest();invalid.append({'trial':i+1,'http_status':response['http_status'],'database_digest_before':before,'database_digest_after':after})
  record('B02','Invalid-token isolation','10/10 HTTP 401 and unchanged whole-database digest',invalid,'PASS' if all(t['http_status']==401 and t['database_digest_before']==t['database_digest_after'] for t in invalid) else 'FAIL')
  for i in range(30):
   fixture('bench_taken','due');response=sim.action('taken');samples.append({'trial':i+1,**response})
  durations=[s['duration_ms'] for s in samples if s['http_status']==200];median=statistics.median(durations) if durations else None;p95=sorted(durations)[math.ceil(.95*len(durations))-1] if durations else None
  record('B03-LOCAL','Loopback HTTP response time (LAN variant not measured)','30 successful requests; median <=500 ms, nearest-rank p95 <=1000 ms',{'requests':len(samples),'successes':len(durations),'median_ms':median,'p95_ms':p95,'scope':'127.0.0.1 loopback, not LAN','timer':'perf_counter: POST start through complete body; LED time excluded'},'PASS' if len(durations)==30 and median<=500 and p95<=1000 else 'FAIL')
  record('B03-LAN','Genuine ESP32/LAN response time','Same target measured across independent LAN devices','No ESP32 or second independent LAN client; loopback values are not substituted','NOT TESTED')
  no_due=sim.action('taken');record('SIM-NO-DUE','Paired token without due row','HTTP 404',no_due,'PASS' if no_due['http_status']==404 else 'FAIL')
  missing=sim.action('taken',omit_token=True);record('SIM-MISSING','Missing device token','HTTP 401',missing,'PASS' if missing['http_status']==401 else 'FAIL')
  invalid_action=sim.action('unsupported');record('SIM-ACTION','Unsupported action','HTTP 400',invalid_action,'PASS' if invalid_action['http_status']==400 else 'FAIL')
  fixture('bench_duplicate','due');dup,_=paired('bench_duplicate');first=dup.action('taken');second=dup.action('taken');state=fixture('bench_duplicate')
  record('SIM-DUPLICATE','Sequential repeated single-due request','First 200; repeat 404; one log',{'statuses':[first['http_status'],second['http_status']],'logs':len(state['logs'])},'PASS' if first['http_status']==200 and second['http_status']==404 and len(state['logs'])==1 else 'FAIL')
  fixture('bench_other','due');isolation,_=paired('bench_isolation');before=fixture('bench_other');response=isolation.action('taken');after=fixture('bench_other')
  record('SIM-ISOLATION','Paired device owner isolation','A cannot acknowledge B; 404 and B state unchanged',{'http_status':response['http_status'],'other_account_state_unchanged':before==after},'PASS' if response['http_status']==404 and before==after else 'FAIL')
  con,_=paired('bench_concurrent');fixture('bench_concurrent','due');barrier=threading.Barrier(2)
  def action(_):barrier.wait();return con.action('taken')
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(action,range(2)))
  statuses=sorted(r['http_status'] for r in responses);logs=len(fixture('bench_concurrent')['logs'])
  record('SIM-CONCURRENT','Real concurrent duplicate HTTP requests','Exactly one 200; other 404/409; one log',{'statuses':statuses,'logs':logs},'PASS' if statuses[0]==200 and statuses[1] in (404,409) and logs==1 else 'FAIL')
  replay,_=paired('bench_replay');fixture('bench_replay','due');fixture('bench_replay','due');rr=[replay.action('taken'),replay.action('taken')]
  record('SIM-REPLAY-LIMIT','Documented multiple-due selection limitation','Identical id-less body may select two different due rows',{'statuses':[r['http_status'] for r in rr],'logs':len(fixture('bench_replay')['logs']),'retry_safe':False},'PASS' if len(fixture('bench_replay')['logs'])==2 else 'FAIL')
  outages=[]
  for i in range(6):
   fixture('bench_taken','due');before=len(fixture('bench_taken')['logs']);stop_server();response=sim.action('taken');start_server();after=len(fixture('bench_taken')['logs']);recovery=sim.action('taken')
   outages.append({'trial':i+1,'offline_http_status':response['http_status'],'transport_error':response['transport_error'],'logs_unchanged_during_outage':before==after,'recovery_http_status':recovery['http_status']})
  record('OUTAGE-HTTP','Six real backend-stop/restart trials','No success or new log while stopped; intended action succeeds after restart',outages,'PASS' if all(t['offline_http_status'] is None and t['logs_unchanged_during_outage'] and t['recovery_http_status']==200 for t in outages) else 'FAIL')
  with opener.open(base+'/check_reminders') as r:session_status=r.status
  record('RESTART-SESSION','Browser session and device credential survive process restart','Existing cookie works; existing token authenticated',{'session_http_status':session_status,'token_authenticated_after_restart':outages[-1]['recovery_http_status']==200},'PASS' if session_status==200 else 'FAIL')
  record('B06-HARDWARE','Physical press classification','30 physical short/hold/intermediate trials','Teammate reports it works; independent GPIO/button/LED evidence not supplied','NOT TESTED')
  record('B07-HARDWARE','ESP32 Wi-Fi/backend outage LED feedback','3 Wi-Fi-loss plus 3 backend-loss physical trials','Six backend HTTP-outage simulations were run, but ESP32 Wi-Fi and LED feedback require physical evidence','NOT TESTED')
  watcher.join()
 finally:
  if server and server.poll() is None:stop_server()
  log.close()
