"""SIMULATED ESP32 COMMUNICATION; real HTTP, no GPIO/LED/Wi-Fi claims.

A new action selects one firing. Retries MUST reuse the prepared body.
CLI --request-file retains identity without storing the private token.
"""
import argparse,json,os,time,urllib.error,urllib.request,uuid
from pathlib import Path

class ESP32Simulator:
    def __init__(self,host,token=None,timeout=3):
        self.host=host.rstrip('/');self.token=token;self.timeout=timeout

    def _post(self,path,payload,operation):
        request=urllib.request.Request(self.host+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
        start=time.perf_counter()
        try:
            with urllib.request.urlopen(request,timeout=self.timeout) as response:status=response.status;body=response.read().decode()
            error=None
        except urllib.error.HTTPError as e:status=e.code;body=e.read().decode();error=None
        except (OSError,urllib.error.URLError) as e:status=None;body='';error=str(e)
        try:result=json.loads(body) if body else None
        except ValueError:result=body
        return {'label':'SIMULATED ESP32 COMMUNICATION','transport':'real HTTP; identify loopback versus LAN',
            'operation':operation,'token':'<redacted>' if 'token' in payload else '<omitted>',
            'http_status':status,'response':result,'transport_error':error,'duration_ms':(time.perf_counter()-start)*1000}

    def select(self):return self._post('/api/device/reminder',{'token':self.token},'select firing')

    def prepare(self,action):
        selection=self.select()
        if selection['http_status']!=200 or not selection['response'].get('due'):
            raise RuntimeError('No firing selected: '+json.dumps(selection))
        row=selection['response']
        return {'token':self.token,'action':action,'id':row['id'],'fired_at':row['fired_at'],'request_id':uuid.uuid4().hex}

    def action(self,action,token=None,omit_token=False,payload=None):
        if payload is None:
            if token is not None or omit_token or action not in ('taken','snooze'):
                payload={'action':action}
                if not omit_token:payload['token']=self.token if token is None else token
            else:payload=self.prepare(action)
        result=self._post('/api/device/action',payload,'bound action')
        result['action']=payload.get('action')
        result['request_id']=payload.get('request_id')
        return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',required=True);p.add_argument('--action',choices=['taken','snooze'],required=True)
    p.add_argument('--request-file',required=True,help='New file for an intentional action; reuse same file for every retry')
    a=p.parse_args();token=os.environ.get('DOSECLOCK_DEVICE_TOKEN')
    if not token:p.error('Set DOSECLOCK_DEVICE_TOKEN privately; never commit or record it.')
    sim=ESP32Simulator(a.host,token);path=Path(a.request_file)
    if path.exists():
        payload=json.loads(path.read_text())
        if payload.get('action')!=a.action:p.error('Pending request has a different action; retry it unchanged.')
        payload['token']=token
    else:
        payload=sim.prepare(a.action)
        with path.open('x') as f:json.dump({k:v for k,v in payload.items() if k!='token'},f)
    print(json.dumps(sim.action(a.action,payload=payload),indent=2))
