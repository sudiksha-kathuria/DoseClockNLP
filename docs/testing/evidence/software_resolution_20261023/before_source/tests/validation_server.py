"""Loopback-only live-test host. Test fixture route exists only in this harness.

Supply an exported temporary source tree; never point this at the working repo.
"""
import argparse,json,os,sys
from datetime import datetime,timedelta
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--database',required=True);p.add_argument('--port',required=True,type=int);args=p.parse_args()
source=Path(args.source).resolve()
if (source/'.git').exists():p.error('Use a temporary exported source tree, never a working checkout.')
sys.path.insert(0,str(source/'backend'))
import database,scheduler,tts
from app import app
from flask import request,jsonify
from werkzeug.serving import make_server

database.DB_PATH=str(Path(args.database).resolve());database.init_db()
fixture_key=os.environ['DOSECLOCK_FIXTURE_KEY']
@app.post('/__review3/fixture')
def fixture():
    if request.headers.get('X-Review3-Fixture')!=fixture_key:return jsonify(error='fixture access denied'),403
    d=request.get_json();username=d.get('username','review_default')
    if not username.startswith(('review_','bench_','audio_')):return jsonify(error='dummy accounts only'),400
    user=database.get_user_by_username(username) or database.create_user(username,'dummy-password',username)
    op=d.get('operation','state')
    if op in ('due','scheduled'):
        now=datetime.now();gid=database.add_medicine(user['id'],d.get('name','Review dummy'),[now.strftime('%H:%M')],20,'en')
        mid=database.get_group(gid)[0]['id']
        if op=='due':database.mark_fired(mid,tts.get_cached_audio(d.get('name','Review dummy'),'en'))
        else:
            with database.get_db_connection() as conn:conn.execute('UPDATE medicines SET created_at=? WHERE id=?',((now-timedelta(days=1)).isoformat(),mid))
        return jsonify(id=mid,group_id=gid,scheduled_time=now.strftime('%H:%M'),prepared_at=now.isoformat())
    if op=='rearm':database.mark_fired(int(d['id']),tts.get_cached_audio('Review dummy','en'))
    if op=='pair':return jsonify(token=database.create_device_token(user['id'],'SIMULATED ESP32 COMMUNICATION'))
    if op=='clear':
        for row in database.get_active_medicines(user['id']):database.deactivate_group(row['group_id'])
    rows=database.get_active_medicines(user['id'])
    return jsonify(user_id=user['id'],medicines=[dict(r) for r in rows],logs=[dict(r) for r in database.get_dose_history(user['id'])])

scheduler.init_scheduler()
print(json.dumps({'event':'ready','host':'127.0.0.1','port':args.port,'fixture_route':'test-harness only','physical_hardware':False}),flush=True)
server=make_server('127.0.0.1',args.port,app,threaded=True)
try:server.serve_forever()
finally:
    scheduler.scheduler.shutdown(wait=False)
    server.server_close()
