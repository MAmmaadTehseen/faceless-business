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
if phase == 'before':
    for file in ('src/components/ReadingTools.tsx','src/app/globals.css','src/app/layout.tsx','src/app/a/[slug]/page.tsx','src/components/Articles.tsx'):
        (runtime/file).write_bytes(subprocess.check_output(['git','show',f'HEAD:hub/{file}'],cwd=hub))
if not (runtime/'node_modules').exists():
    (runtime/'node_modules').symlink_to(hub/'node_modules', target_is_directory=True)
env = dict(os.environ, HUB_PREVIEW_FIXTURES='1', GOOGLE_SITE_VERIFICATION='local-check', MOTION_BASE='http://localhost:3137')
log = open(hub/f'design-review/motion-{phase}-dev.log','w')
server = subprocess.Popen(['npm','run','dev','--','--port','3137'],cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
try:
    for _ in range(90):
        if server.poll() is not None:
            raise RuntimeError('Dev server exited; see review log')
        try:
            urllib.request.urlopen('http://localhost:3137',timeout=2).close()
            break
        except Exception:
            time.sleep(1)
    subprocess.run(['node','scripts/warm-motion.cjs'],cwd=hub,env=env,check=True)
    if not os.environ.get('MOTION_SCREENSHOTS_ONLY'):
        subprocess.run(['node','scripts/check-motion.cjs',phase],cwd=hub,env=env,check=True)
    if not os.environ.get('MOTION_SCREENSHOTS_ONLY'):
        subprocess.run(['node','scripts/check-seo.mjs','http://localhost:3137','preview-story-0'],cwd=hub,env=env,check=True)
    if phase == 'after':
        subprocess.run(['node','scripts/check-motion-screenshots.cjs'],cwd=hub,env=env,check=True)
        if not os.environ.get('MOTION_SCREENSHOTS_ONLY'):
            subprocess.run(['node','scripts/check-motion-interactions.cjs'],cwd=hub,env=env,check=True)
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
