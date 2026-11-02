"""Run from repository root. Invented data only; never loads local environment files."""
from pathlib import Path
import os, subprocess, signal, time, urllib.request
root=Path.cwd()
logs=root/'dashboard/qa/mobile';logs.mkdir(parents=True,exist_ok=True)
(root/'hub/design-review/mobile').mkdir(parents=True,exist_ok=True)
base={**os.environ,'NODE_OPTIONS':f'--require={root}/dashboard/scripts/mobile/without-env.cjs'}
children=[]
def start(command,cwd,env,name):
 child=subprocess.Popen(command,cwd=cwd,env=env,stdout=open(logs/f'{name}.log','w'),stderr=subprocess.STDOUT,start_new_session=True)
 children.append(child)
try:
 start(['python3','dashboard/scripts/mobile/fixture.py'],root,base,'fixture')
 start(['npm','run','dev','--','--hostname','127.0.0.1','--port','4340'],root/'dashboard',{**base,'SUPABASE_URL':'http://127.0.0.1:43992','SUPABASE_SERVICE_KEY':'qa-placeholder','DASHBOARD_SECRET':'qa-placeholder','DASHBOARD_QA_BYPASS':'1','DASHBOARD_QA_DIST':'.next-qa-mobile'},'dashboard')
 start(['npm','run','dev','--','--hostname','127.0.0.1','--port','4341'],root/'hub',{**base,'HUB_PREVIEW_FIXTURES':'1','HUB_QA_DIST':'.next-qa-mobile'},'hub')
 for port in (4340,4341):
  for _ in range(120):
   if any(c.poll() is not None for c in children):raise RuntimeError('QA server failed; inspect dashboard/qa/mobile logs')
   try:
    urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=2);break
   except Exception:time.sleep(.5)
  else:raise RuntimeError('QA server did not start')
 for name in ('check','flows','stress','final-review'):
  subprocess.run(['node',f'dashboard/scripts/mobile/{name}.mjs'],check=True)
finally:
 for child in children:
  try:os.killpg(child.pid,signal.SIGTERM)
  except ProcessLookupError:pass
 for child in children:
  try:child.wait(timeout=10)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL)
