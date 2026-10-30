"""Run local fixture QA without loading application environment files.
Runtime is a disposable copy; every child process belongs to one cleanup group.
"""
import os
import pathlib
import shutil
import signal
import subprocess
import time
import urllib.request

hub = pathlib.Path(__file__).resolve().parents[1]
phase = os.environ.get('MOTION_PHASE', 'after')
runtime = pathlib.Path('/tmp') / f'plainsight-motion-{phase}-qa'
shutil.copytree(hub, runtime, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns('node_modules', '.next', '.env*', '.vercel', 'design-review'))
if not (runtime/'node_modules').exists():
    (runtime/'node_modules').symlink_to(hub/'node_modules', target_is_directory=True)
port = os.environ.get('MOTION_PORT', '3137')
base = f'http://localhost:{port}'
env = dict(os.environ, HUB_PREVIEW_FIXTURES='1', GOOGLE_SITE_VERIFICATION='local-check', MOTION_BASE=base)
log = open(hub/f'design-review/motion-{phase}-dev.log','w')
server = subprocess.Popen(['npm','run','dev','--','--port',port],cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
try:
    for _ in range(90):
        if server.poll() is not None:
            raise RuntimeError('Dev server exited; see review log')
        try:
            urllib.request.urlopen(base,timeout=2).close()
            if server.poll() is not None: raise RuntimeError('Dev server exited')
            break
        except Exception:
            time.sleep(1)
    subprocess.run(['node','scripts/warm-motion.cjs'],cwd=hub,env=env,check=True)
    if not os.environ.get('MOTION_SCREENSHOTS_ONLY') and (phase == 'after' or phase.startswith('final')):
        subprocess.run(['node','scripts/check-motion-interactions.cjs'],cwd=hub,env=env,check=True)
    if not os.environ.get('MOTION_SCREENSHOTS_ONLY'):
        subprocess.run(['node','scripts/check-motion.cjs',phase],cwd=hub,env=env,check=True)
    if not os.environ.get('MOTION_SCREENSHOTS_ONLY'):
        subprocess.run(['node','scripts/check-seo.mjs',base,'preview-story-0'],cwd=hub,env=env,check=True)
    if phase == 'after' or phase.startswith('final'):
        subprocess.run(['node','scripts/check-motion-screenshots.cjs'],cwd=hub,env=env,check=True)
finally:
    try:
        os.killpg(server.pid,signal.SIGTERM)
        server.wait(timeout=10)
    except ProcessLookupError:
        pass
    except subprocess.TimeoutExpired:
        os.killpg(server.pid,signal.SIGKILL)
        server.wait()
    log.close()
# Build only after the dev process has stopped: they must not share .next.
with open(hub/f'design-review/motion-{phase}-build.log','w') as build:
    subprocess.run(['npm','run','build'],cwd=runtime,env=env,stdout=build,stderr=subprocess.STDOUT,check=True)
