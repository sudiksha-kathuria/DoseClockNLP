"""Real headless Chromium + real loopback Flask. No physical switch or microphone claims."""
import argparse,json,os,secrets,shutil,socket,subprocess,sys,tempfile,time,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
from review3_media import verify_autoplay
from datetime import datetime
from zoneinfo import ZoneInfo

p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--visibility',action='store_true');p.add_argument('--audio-cache');p.add_argument('--only');a=p.parse_args()
out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);(out/'screenshots').mkdir(exist_ok=True)
records=[]
with tempfile.TemporaryDirectory(prefix='doseclock-browser-') as td:
 root=Path(td)
 for name in ['backend','frontend']:shutil.copytree(Path(a.source).resolve()/name,root/name,ignore=shutil.ignore_patterns('__pycache__','*.db','.secret_key'))
 if a.audio_cache:
  for audio in Path(a.audio_cache).glob('*.mp3'):shutil.copy2(audio,root/'frontend/static/audio'/audio.name)
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
 key=secrets.token_hex(20);base=f'http://127.0.0.1:{port}'
 log=(out/'server.log').open('w')
 proc=subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('validation_server.py')),'--source',str(root),'--database',str(root/'browser.db'),'--port',str(port)],env={**os.environ,'DOSECLOCK_FIXTURE_KEY':key,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
 try:
  import urllib.request
  for _ in range(100):
   try:urllib.request.urlopen(base+'/login',timeout=.3);break
   except Exception:time.sleep(.1)
  with sync_playwright() as pw:
   browser=pw.chromium.launch(args=['--autoplay-policy=document-user-activation-required'], ignore_default_args=['--mute-audio']);metadata={'recorded_at':datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),'validation_stage':'23 October 2026 follow-up after initial Review 3','browser':browser.version,'mode':'headless Chromium; loopback Flask; disposable SQLite','microphone':'not available for independent spoken-command validation','autoplay_policy':'document-user-activation-required'}
   def case(cid,feature,fn):
    if a.only and cid not in a.only.split(','):return
    started=time.perf_counter();ctx=browser.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();page.set_default_timeout(5000)
    events=[];page.on('pageerror',lambda e:events.append(str(e)))
    try:
     actual=fn(page);status='PASS'
    except Exception as e:actual={'error':str(e),'traceback':traceback.format_exc()};status='FAIL'
    shot=out/'screenshots'/(cid+'.png')
    try:page.screenshot(path=str(shot),full_page=True)
    except Exception:pass
    records.append({'id':cid,'feature':feature,'expected':feature,'actual':actual,'status':status,'duration_seconds':time.perf_counter()-started,'evidence':'screenshots/'+cid+'.png','page_errors':events})
    (out/'results.json').write_text(json.dumps({'metadata':metadata,'records':records},indent=2));print(cid,status,flush=True);ctx.close()
   def fixture(page,user,operation='state',**extra):
    response=page.request.post(base+'/__review3/fixture',data={'username':user,'operation':operation,**extra},headers={'X-Review3-Fixture':key});assert response.ok,response.text();return response.json()
   def login(page,user,due=True):
    state=fixture(page,user,'due' if due else 'state')
    page.goto(base+'/login');page.locator('#username').fill(user);page.locator('#password').fill('dummy-password');page.get_by_role('button',name='Log in',exact=True).click();page.wait_for_url('**/clock')
    if due:page.wait_for_function("document.querySelector('#alarm-view').classList.contains('visible')")
    return state
   def workflow(page):
    page.goto(base+'/signup');page.locator('#display_name').fill('Review UI');page.locator('#username').fill('review_ui_workflow');page.locator('#password').fill('dummy-password');page.get_by_role('button',name='Create account').click();page.wait_for_url(base+'/')
    page.locator('#medicine_name').fill('UI registration dummy');page.locator('input[name=times]').fill('08:00');page.locator('#add-time-btn').click();page.locator('input[name=times]').nth(1).fill('20:00');page.locator('#days').fill('3');page.get_by_role('button',name='Save reminder').click();page.wait_for_url('**/clock')
    state=fixture(page,'review_ui_workflow');assert len(state['medicines'])==2
    assert page.locator('.clock-sidebar').inner_text().find('UI registration dummy')>=0
    return {'rows':len(state['medicines']),'clock':page.locator('#clock-face').inner_text()}
   def taken(page):
    login(page,'review_ui_taken');page.locator('#taken-btn').click()
    page.wait_for_timeout(1200);state=fixture(page,'review_ui_taken');assert len(state['logs'])==1
    page.goto(base+'/logs');assert 'Review dummy' in page.locator('.logs-table').inner_text();return {'dose_logs':1}
   def snooze(page):
    login(page,'review_ui_snooze');page.locator('#snooze-btn').click();page.wait_for_timeout(300)
    state=fixture(page,'review_ui_snooze');assert not state['logs'];assert state['medicines'][0]['snoozed_until'];assert not state['medicines'][0]['is_due'];return {'deadline':state['medicines'][0]['snoozed_until'],'logs':0}
   def keyboard(page,snooze=False):
    user='review_scan_snooze' if snooze else 'review_scan_taken';login(page,user)
    selector='#snooze-btn' if snooze else '#taken-btn'
    page.wait_for_function("s => document.querySelector(s).classList.contains('scan-highlight')",arg=selector)
    page.keyboard.press('Space');page.wait_for_timeout(300);state=fixture(page,user)
    assert bool(state['logs']) is not snooze
    if snooze:assert state['medicines'][0]['snoozed_until']
    return {'selection':'Snooze' if snooze else 'Taken','space_key':True}
   def failed_action(page,action='taken',http=False):
    user='review_'+action+('_http_failure' if http else '_network_failure');login(page,user)
    route='**/mark_'+action
    if http:page.route(route,lambda r:r.fulfill(status=409,content_type='application/json',body='{"error":"controlled conflict"}'))
    else:page.route(route,lambda r:r.abort('failed'))
    page.locator('#'+action+'-btn').click();page.wait_for_timeout(250)
    state=fixture(page,user);actual={'alarm_visible':'visible' in page.locator('#alarm-view').get_attribute('class'),'success_visible':'visible' in page.locator('#success-flash').get_attribute('class'),'toast':page.locator('#toast').inner_text(),'logs':len(state['logs']),'is_due':state['medicines'][0]['is_due']}
    page.screenshot(path=str(out/'screenshots'/('observed_'+user+'.png')),full_page=True)
    assert actual['alarm_visible'] and not actual['success_visible'] and 'Snoozed' not in actual['toast'],actual
    assert actual['logs']==0 and actual['is_due']==1,actual
    page.unroute(route);page.locator('#'+action+'-btn').click();page.wait_for_timeout(300)
    recovered=fixture(page,user);assert not recovered['medicines'][0]['is_due'];return {'failure':actual,'recovered_after_network_restored':True}
   def external(page):
    user='review_ui_external';login(page,user);token=fixture(page,user,'pair')['token']
    response=page.request.post(base+'/api/device/action',data={'token':token,'action':'taken'});assert response.status==200
    page.wait_for_function("!document.querySelector('#alarm-view').classList.contains('visible')",timeout=19000)
    return {'hardware_message':'SIMULATED ESP32 COMMUNICATION','HTTP':200,'browser_reconciled_without_refresh':True}
   def autoplay(page):
    # Separate empty disk profile; no Playwright evaluation/locator calls in
    # its acceptance path. HTTP authentication does not activate the page.
    def media_fixture(user,operation='state'):
     return fixture(page,user,operation)
    result=verify_autoplay(pw,base,media_fixture,out/'UI10-clean-profile')
    return {'autoplay_before_gesture':result['initial']['audit']['calls'][0],
            'explicit_no_gesture_probe':result['explicit_probe'],
            'playing_samples':[s['media'] for s in result['playing_samples']],
            'stopped_samples':[s['media'] for s in result['stopped_samples']],
            'trusted_gestures':result['trusted_gestures'],
            'profile_initially_empty':result['profile_initially_empty'],
            'human_listening':False,'detail':'UI10-clean-profile/results.json'}
   def unavailable_audio(page):
    user='review_missing_audio';fixture(page,user,'due',name='Uncached visual-only dummy');login(page,user,due=False)
    page.wait_for_function("document.querySelector('#alarm-view').classList.contains('visible')")
    source=page.locator('#reminder-audio').get_attribute('src');assert source is None,{'unexpected_audio_src':source}
    page.locator('#taken-btn').click();page.wait_for_timeout(300);state=fixture(page,user);assert len(state['logs'])==1
    return {'audio_src':source,'visual_alarm_and_taken_usable':True}
   case('UI01','Signup, register two times, clock workflow',workflow)
   case('UI02','Taken button and history persistence',taken)
   case('UI03','Snooze button persists deadline without Taken log',snooze)
   case('UI04','Space selects highlighted Taken',lambda p:keyboard(p,False))
   case('UI05','Single-switch scanning highlights Snooze and Space selects it',lambda p:keyboard(p,True))
   case('UI06','Network failure cannot falsely acknowledge Taken; recovery',lambda p:failed_action(p,'taken'))
   case('UI07','Network failure cannot falsely report Snooze; recovery',lambda p:failed_action(p,'snooze'))
   case('UI08','HTTP rejection cannot falsely acknowledge Taken',lambda p:failed_action(p,'taken',True))
   case('UI09','External device action reconciles visible browser alarm',external)
   case('UI10','Fresh-profile no-gesture play rejects; trusted audio prompt click plays and advances MP3; Snooze stops progression',autoplay)
   case('UI11','Unavailable speech leaves visual reminder and Taken usable',unavailable_audio)
   if a.visibility:
    for i in range(1,6):
     def visibility(page,i=i):
      user='review_visibility_'+str(i);login(page,user,False)
      before=page.locator('#clock-face').inner_text();start=time.perf_counter();prep=fixture(page,user,'scheduled')
      page.wait_for_function("document.querySelector('#alarm-view').classList.contains('visible')",timeout=20000)
      elapsed=time.perf_counter()-start;state=fixture(page,user)
      assert elapsed<=20 and state['medicines'][0]['is_due']==1
      return {'visible_seconds_after_scheduled_fixture':elapsed,'scheduled_time':prep['scheduled_time'],'clock_before':before,'clock_after':page.locator('#clock-face').inner_text()}
     case('B05-'+str(i),'Initial reminder visibility <=20 seconds; real scheduler and browser poll',visibility)
   records.append({'id':'UI-VOICE','feature':'Real spoken acknowledgment','expected':'Actual microphone/transcription and action','actual':'No participant/microphone or recorded utterance available; speech handler not counted as real voice verification.','status':'NOT TESTED','duration_seconds':0,'evidence':'results.json'})
   (out/'results.json').write_text(json.dumps({'metadata':metadata,'records':records},indent=2));browser.close()
 finally:
  proc.terminate();proc.wait(timeout=10);log.close()

sys.exit(1 if any(r['status']=='FAIL' for r in records) else 0)
