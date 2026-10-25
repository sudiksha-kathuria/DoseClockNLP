"""SIMULATED ESP32 COMMUNICATION over real HTTP. No GPIO, LED or Wi-Fi claims.

CLI: DOSECLOCK_DEVICE_TOKEN=<private dummy token> python tests/esp32_simulator.py \
       --host http://127.0.0.1:5050 --action taken
Does not automatically retry: an id-less retry may acknowledge another due row.
"""
import argparse,json,os,time,urllib.error,urllib.request

class ESP32Simulator:
    def __init__(self,host,token=None,timeout=3):
        self.host=host.rstrip('/');self.token=token;self.timeout=timeout
    def action(self,action,token=None,omit_token=False):
        payload={'action':action}
        if not omit_token:payload['token']=self.token if token is None else token
        request=urllib.request.Request(self.host+'/api/device/action',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
        start=time.perf_counter()
        try:
            with urllib.request.urlopen(request,timeout=self.timeout) as response:status=response.status;body=response.read().decode()
            error=None
        except urllib.error.HTTPError as e:status=e.code;body=e.read().decode();error=None
        except (OSError,urllib.error.URLError) as e:status=None;body='';error=str(e)
        try:result=json.loads(body) if body else None
        except ValueError:result=body
        return {'label':'SIMULATED ESP32 COMMUNICATION','transport':'real HTTP; caller must identify loopback versus LAN','action':action,'token':'<redacted>' if not omit_token else '<omitted>','http_status':status,'response':result,'transport_error':error,'duration_ms':(time.perf_counter()-start)*1000}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',required=True);p.add_argument('--action',choices=['taken','snooze'],required=True);a=p.parse_args()
    token=os.environ.get('DOSECLOCK_DEVICE_TOKEN')
    if not token:p.error('Set DOSECLOCK_DEVICE_TOKEN privately; do not commit or record it.')
    print(json.dumps(ESP32Simulator(a.host,token).action(a.action),indent=2))
