"""Dashboard-only scope QA, cleanup by owned process group IDs."""
from pathlib import Path
import os, subprocess, signal, time, urllib.request, sys
root=Path.cwd()
logs=root/'dashboard/qa/scope'; logs.mkdir(parents=True,exist_ok=True)
base={**os.environ,'NODE_OPTIONS':f'--require={root}/dashboard/scripts/mobile/without-env.cjs'}
children=[]
try:
 for command,env,name in [(['python3','dashboard/scripts/mobile/scope-fixture.py'],base,'fixture'),(['npm','--prefix','dashboard','run','dev','--','--hostname','127.0.0.1','--port','4340'],{**base,'SUPABASE_URL':'http://127.0.0.1:43992','SUPABASE_SERVICE_KEY':'qa-placeholder','DASHBOARD_SECRET':'qa-placeholder','DASHBOARD_QA_BYPASS':'1','DASHBOARD_QA_DIST':'.next-qa-scope'},'dashboard')]:
  children.append(subprocess.Popen(command,cwd=root,env=env,stdout=open(logs/f'{name}.log','w'),stderr=subprocess.STDOUT,start_new_session=True))
 for attempt in range(120):
  if any(c.poll() is not None for c in children): raise RuntimeError('QA process exited')
  try: urllib.request.urlopen('http://127.0.0.1:4340/?channel=all&platform=instagram',timeout=2);break
  except Exception: time.sleep(.5)
 else: raise RuntimeError('QA server timeout')
 subprocess.run(['node','dashboard/scripts/mobile/'+(sys.argv[1] if len(sys.argv)>1 else 'scope-check')+'.mjs'],check=True)
finally:
 for child in children:
  try: os.killpg(child.pid,signal.SIGTERM)
  except ProcessLookupError: pass
 for child in children:
  try: child.wait(timeout=10)
  except subprocess.TimeoutExpired: os.killpg(child.pid,signal.SIGKILL)
