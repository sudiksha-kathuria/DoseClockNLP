"""Export source to a temporary copy before running the complete unittest suite.

Usage: python tests/run_review3_suite.py --source . --output docs/testing/evidence/final_suite
Never imports the application from the user's working checkout.
"""
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile,time,unittest
from datetime import datetime,timezone
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',default='.');parser.add_argument('--output',required=True)
    args=parser.parse_args();src=Path(args.source).resolve();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if '--isolated' not in sys.argv:
        with tempfile.TemporaryDirectory(prefix='doseclock-unit-') as tmp:
            dest=Path(tmp)
            for name in ['backend','frontend','hardware','tests']:
                shutil.copytree(src/name,dest/name,ignore=shutil.ignore_patterns('__pycache__','*.db','.secret_key','*.mp3','.pio','private','.venv'))
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','DOSECLOCK_UNIT_CHILD':'1'}
            result=subprocess.run([sys.executable,'-B',str(dest/'tests/run_review3_suite.py'),'--source',str(dest),'--output',str(out),'--isolated'],cwd=dest,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (out/'terminal.log').write_text(result.stdout);print(result.stdout,end='');return result.returncode


# The small child entry avoids exposing an application import in the parent.
if __name__=='__main__' and '--isolated' in sys.argv:
    sys.argv.remove('--isolated')
    parser=argparse.ArgumentParser();parser.add_argument('--source');parser.add_argument('--output');args=parser.parse_args()
    out=Path(args.output);records=[]
    class Result(unittest.TextTestResult):
        def startTest(self,test):self.started=time.perf_counter();super().startTest(test)
        def addSuccess(self,test):super().addSuccess(test);self.record(test,'PASS','')
        def addFailure(self,test,err):super().addFailure(test,err);self.record(test,'FAIL',self._exc_info_to_string(err,test))
        def addError(self,test,err):super().addError(test,err);self.record(test,'FAIL',self._exc_info_to_string(err,test))
        def addSubTest(self,test,subtest,err):
            super().addSubTest(test,subtest,err)
            if err is not None:
                detail=str(subtest)+'\n'+self._exc_info_to_string(err,test)
                prior=next((r for r in records if r['id']==test.id()),None)
                if prior:prior['actual']+='\n'+detail
                else:self.record(test,'FAIL',detail)
        def addSkip(self,test,reason):super().addSkip(test,reason);self.record(test,'SKIP',reason)
        def record(self,test,status,detail):
            prior=next((r for r in records if r['id']==test.id()),None)
            if prior:
                if status=='FAIL':prior['status']='FAIL'
                prior['duration_seconds']=time.perf_counter()-self.started
                if detail:prior['actual']+='\n'+detail
            else:records.append({'id':test.id(),'status':status,'duration_seconds':time.perf_counter()-self.started,'actual':detail or 'All assertions met'})
    suite=unittest.defaultTestLoader.discover(str(Path(args.source)/'tests'),pattern='test*.py')
    result=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
    assert len(records)==result.testsRun, 'Each unittest method must have exactly one case record'
    payload={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'environment':'temporary exported source; disposable SQLite and audio caches','tests_run':result.testsRun,'passed':sum(r['status']=='PASS' for r in records),'failed':sum(r['status']=='FAIL' for r in records),'failure_assertions':len(result.failures)+len(result.errors),'skipped':len(result.skipped),'records':records}
    (out/'results.json').write_text(json.dumps(payload,indent=2))
    sys.exit(0 if result.wasSuccessful() else 1)
elif __name__=='__main__':sys.exit(main())
