#!/usr/bin/env python3
"""Read-only video audit. No Claude calls or platform writes; only videos.list on YouTube.

Run: .venv/bin/python scripts/audit_videos.py --report docs/video-audit.md
Use --sample-media to inspect up to six retained long-video artifacts (temporary files removed).
"""
from __future__ import annotations
import argparse
import io
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.db import DB
from pipeline.common import Channel
from pipeline.publish import youtube
from pipeline.script import BANNED_TITLE

logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('googleapiclient').setLevel(logging.ERROR)


def dt(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def duration(value):
    m = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?', value or '')
    return sum(float(v or 0)*n for v, n in zip(m.groups(), (3600, 60, 1))) if m else None


def production_db():
    # Importing pipeline.db loads config through common; never open .env here.
    if os.getenv('DB_BACKEND') == 'sqlite' or not (os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_SERVICE_KEY')):
        raise RuntimeError('Production configuration unavailable; refusing SQLite initialization')
    return DB()


def read_table(db, table):
    """Supabase defaults to 1000 rows. Page explicitly for complete cost/history reads."""
    if not db.sb:
        return db.select(table)
    rows = []
    for start in range(0, 1000000, 500):
        page = db.sb.table(table).select('*').order('id').range(start, start+499).execute().data or []
        rows.extend(page)
        if len(page) < 500:
            return rows
    raise RuntimeError('pagination safety limit')


def gh_json(*args):
    result = subprocess.run(['gh', *args], capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError('GitHub read unavailable')
    return json.loads(result.stdout)


def head(url):
    import requests
    try:
        r = requests.head(url, allow_redirects=True, timeout=20)
        return r.status_code
    except requests.RequestException:
        return 'network-error'


def inspect(content, pubs, articles, costs, truth, checked, *, now=None, heads=None):
    now = now or datetime.now(timezone.utc)
    heads = heads or {}
    findings = []
    def add(severity, cid, problem, evidence, action='Review before retry', kind='owner-only'):
        findings.append(dict(severity=severity, content_id=cid, problem=problem, evidence=str(evidence), action=action, kind=kind))
    by_content = defaultdict(list)
    for p in pubs:
        by_content[p['content_id']].append(p)
    active = {c['id']: c for c in content if c.get('status') != 'killed'}
    article_map = {a['content_id']: a for a in articles}
    for cid, c in active.items():
        ps = by_content[cid]
        live = {p['platform']: p for p in ps if p.get('status') == 'live' and p.get('platform_id')}
        yt = next((p for p in ps if p['platform']=='youtube'), {})
        if c.get('status') in ('rendered','qa_failed','failed'):
            add('high' if c['status']=='qa_failed' else 'medium', cid, 'Content '+c['status'], 'QA='+str(c.get('qa_status')), 'Resume retained artifact after reviewing QA', 're-runnable')
        for p in ps:
            if p.get('status') in ('queued','failed','uploading'):
                add('high' if p['status'] in ('failed','uploading') else 'medium', cid, p['platform']+' '+p['status'], 'publication='+str(p['id'])+'; '+safe_error(p.get('error')), 'Drain quota queue; inspect failures before retry', 're-runnable')
            if p.get('status')=='live' and (not p.get('platform_id') or not p.get('url')):
                add('high', cid, 'Incomplete live publication', p['platform'], 'Restore URL only when platform id is known', 'code-fixable')
        if c.get('status')=='published' and 'youtube' not in live:
            add('high', cid, 'Published content missing live YouTube', yt.get('status','no row'), 'Drain queue or recover artifact; do not reupload known ids', 're-runnable')
        if c['kind']=='long' and c.get('status')=='published':
            children = [s for s in active.values() if s.get('parent_id')==cid]
            if len(children)!=4:
                add('medium', cid, 'Long without four active Shorts', str(len(children))+' active children', 'Review historical two-Short scripts; rebuild needs four saved angles', 'owner-only')
            if cid not in article_map:
                add('medium', cid, 'Long without article', 'No article row', 'Generate article separately when API spend is authorized', 're-runnable')
        if cid in article_map and yt.get('platform_id') and yt.get('status')=='live' and not article_map[cid].get('youtube_id'):
            add('medium', cid, 'Article missing youtube_id', 'Known live id '+yt['platform_id'], 'DB-only backfill', 'code-fixable')
        if c['kind']=='short' and c.get('status') in ('published','rendered'):
            if not c.get('media_url'):
                add('high', cid, 'Short missing media_url', 'Fresh runner cannot restore local file', 'Recover artifact and persist media URL; no fabricated URL', 'code-fixable')
            elif heads.get(c['media_url'],200) not in (200, 206):
                code = heads[c['media_url']]
                add('medium' if code in (403,405,'network-error') else 'high', cid, 'Media HEAD unavailable', 'HTTP '+str(code), 'Verify download; HEAD denial is inconclusive', 'owner-only')
        elif c['kind']=='long' and c.get('status') in ('published','rendered'):
            if not c.get('media_url'):
                add('low', cid, 'Long missing media_url', 'Long recovery relies on retained artifact or private queue', 'Keep recovery media before artifact expiry; public URL is not required for long uploads', 'owner-only')
            elif heads.get(c['media_url'],200) not in (200,206):
                add('medium',cid,'Media HEAD unavailable','HTTP '+str(heads[c['media_url']]),'Verify download; HEAD denial is inconclusive','owner-only')
        v = truth.get(yt.get('platform_id'))
        if yt.get('platform_id') in checked and not v:
            add('high', cid, 'YouTube id inaccessible or deleted', yt['platform_id'], 'Owner verify in Studio; missing items do not prove deletion')
        if not v:
            continue
        status, snippet = v.get('status',{}), v.get('snippet',{})
        if status.get('uploadStatus') in ('deleted','rejected','failed') or v.get('processingDetails',{}).get('processingStatus')=='failed':
            add('critical', cid, 'YouTube processing failure', status.get('uploadStatus'))
        if status.get('privacyStatus') != yt.get('privacy'):
            add('medium', cid, 'Privacy differs from DB', f"DB={yt.get('privacy')}; API={status.get('privacyStatus')}", 'Owner review; audit never changes privacy')
        if status.get('privacyStatus')=='public' and dt(yt.get('publish_at')) and dt(yt['publish_at'])>now:
            add('high', cid, 'Public before DB schedule', yt['publish_at'], 'Owner decide publication policy; public uploads ignore publishAt')
        if status.get('publishAt') and dt(status['publishAt']) != dt(yt.get('publish_at')):
            add('high', cid, 'publishAt differs from DB', 'API='+status['publishAt']+' DB='+str(yt.get('publish_at')))
        if status.get('privacyStatus')=='private' and yt.get('publish_at') and not status.get('publishAt'):
            add('high', cid, 'Private without API schedule', yt['publish_at'])
        if status.get('privacyStatus')=='private' and dt(yt.get('publish_at')) and dt(yt['publish_at'])<now:
            add('high', cid, 'Past schedule still private', yt['publish_at'])
        expected = Channel(c.get('channel') or 'futurework').env('YT_CHANNEL_ID')
        if expected and expected!=snippet.get('channelId'):
            add('critical', cid, 'Wrong YouTube channel', snippet.get('channelId'))
        seconds = duration(v.get('contentDetails',{}).get('duration'))
        if seconds is not None and c.get('duration_sec') and abs(seconds-c['duration_sec'])>max(2,c['duration_sec']*.02):
            add('high', cid, 'Duration mismatch', f"DB={c['duration_sec']}; API={seconds}")
        details=v.get('fileDetails',{}).get('videoStreams',[])
        if c['kind']=='short' and (seconds and seconds>180 or details and details[0].get('widthPixels',0)>=details[0].get('heightPixels',0)):
            add('high', cid, 'Short over 3 minutes or not vertical', f'{seconds}s; streams={details}')
        if not snippet.get('thumbnails'):
            add('medium', cid, 'Missing YouTube thumbnail', yt.get('platform_id'))
        if status.get('containsSyntheticMedia') is not True:
            add('high', cid, 'Synthetic disclosure absent', yt.get('platform_id'), 'Owner review; future upload guard already sets disclosure')
        if not snippet.get('title','').strip() or not snippet.get('description','').strip() or BANNED_TITLE.search(snippet.get('title','')):
            add('high', cid, 'Empty metadata or banned title', snippet.get('title',''))
        if c['kind']=='short' and status.get('privacyStatus')=='public':
            missing={'instagram','facebook'}-live.keys()
            if missing:
                add('high', cid, 'Public Short missing Reels', ', '.join(sorted(missing)), 'Recover media then normal sync follow-up', 're-runnable')
    groups=defaultdict(list)
    for p in pubs:
        if p['content_id'] in active and p.get('platform_id'):
            groups[(p['platform'],p['platform_id'])].append(p['content_id'])
    for key, ids in groups.items():
        if len(ids)>1:
            add('high', ', '.join(ids), 'Shared platform id', key)
    titles=defaultdict(set)
    for vid,v in truth.items():
        s=v.get('snippet',{})
        titles[(s.get('channelId'),s.get('title','').casefold())].add(vid)
    for key, ids in titles.items():
        if len(ids)>1:
            add('high', ', '.join(p['content_id'] for p in pubs if p.get('platform_id') in ids), 'Possible duplicate YouTube upload', ', '.join(sorted(ids)), 'Owner compare footage and decide whether to delete')
    actual_days=defaultdict(list)
    for p in pubs:
        c=active.get(p['content_id']); v=truth.get(p.get('platform_id'),{})
        if c and p['platform']=='youtube' and v.get('status',{}).get('privacyStatus')=='public' and v.get('snippet',{}).get('publishedAt'):
            actual_days[(c['channel'],dt(v['snippet']['publishedAt']).date())].append(c['id'])
    for key,ids in actual_days.items():
        if len(ids)>3:
            add('high',', '.join(ids),'Over three actual public videos per UTC day',key,'Owner review burst; new uploads use private schedules')
    roots=[c for c in active.values() if not c.get('parent_id')]
    for i,c in enumerate(roots):
        for other in roots[i+1:]:
            if c.get('channel')==other.get('channel') and re.sub(r'\W+',' ',c.get('topic','').lower()).strip()==re.sub(r'\W+',' ',other.get('topic','').lower()).strip() and abs((dt(c['created_at'])-dt(other['created_at'])).total_seconds())<14*86400:
                add('medium', c['id'], 'Duplicate topic within 14 days', other['id'], 'Review topic avoidance', 'code-fixable')
    days=defaultdict(list); calendars=defaultdict(list)
    for p in pubs:
        if p['platform']=='youtube' and p.get('status') in ('live','queued') and p['content_id'] in active and p.get('publish_at'):
            c=active[p['content_id']]; when=dt(p['publish_at'])
            days[(c['channel'],when.date())].append(c['id']); calendars[c['channel']].append((when,c['id']))
            if when>now+timedelta(days=30):
                add('medium', c['id'], 'Schedule drift over 30 days', when.isoformat())
    for key, ids in days.items():
        if len(ids)>3:
            add('high', ', '.join(ids), 'Over three YouTube slots per UTC day', key)
    for channel, slots in calendars.items():
        slots.sort()
        for (a,_),(b,cid) in zip(slots,slots[1:]):
            if (b-a).days>7:
                add('medium', cid, 'Channel calendar gap over 7 days', f'{channel}: {a} to {b}')
    spends=defaultdict(list)
    killed={c['id'] for c in content if c.get('status')=='killed'}
    for cost in costs:
        if cost.get('content_id') and cost['content_id'] not in killed: spends[cost['content_id']].append(cost)
    for cid, rows in spends.items():
        total=sum(float(r.get('usd') or 0) for r in rows)
        if total<=0: continue
        if cid not in active or not active[cid].get('file_path'):
            add('medium',cid,'Spend without rendered output', f'${total:.4f}', 'Inspect failure before regeneration', 're-runnable')
        repeated={step:n for step,n in Counter(r['step'] for r in rows).items() if n>1 and step not in ('engage','optimize')}
        if repeated:
            add('medium',cid,'Repeated Claude spend (review)',f'${total:.4f}; {repeated}', 'Check retries/validation; repeated calls alone do not prove waste', 'owner-only')
    return findings


def safe_error(value):
    # Never echo raw errors: requests may contain signed URLs or credentials.
    try:
        e=json.loads(value or '{}')
        if not isinstance(e,dict): return 'unstructured error retained in DB'
        safe={k:e[k] for k in ('http_status','drain_attempts') if isinstance(e.get(k),int)}
        known=youtube.QUOTA_REASONS | {'media_not_recoverable','forbidden','notFound','invalidParameter','upload_uncertain'}
        if e.get('reason') in known:
            safe['reason']=e['reason']
        if e.get('upload_uncertain') is True:
            safe['upload_uncertain']=True
        return '; '.join(f'{k}={v}' for k,v in safe.items()) or 'error details retained in DB'
    except (ValueError,TypeError):
        return 'unstructured error retained in DB'


class RemoteArchive(io.RawIOBase):
    """Seekable range reader to avoid downloading unused footage."""
    def __init__(self, artifact_id, size):
        import requests
        token = subprocess.run(['gh','auth','token'], capture_output=True, text=True, check=True, timeout=15).stdout.strip()
        repo = gh_json('repo','view','--json','nameWithOwner')['nameWithOwner']
        response = requests.get(f'https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip',
                                headers={'Authorization':'Bearer '+token}, allow_redirects=False, timeout=30)
        if response.status_code != 302:
            raise RuntimeError('Artifact redirect unavailable')
        self.url = response.headers['Location']
        self.size, self.pos = size, 0
        self.cache = {}
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        self.pos = offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        return self.pos
    def read(self, size=-1):
        import requests
        size = self.size-self.pos if size<0 else min(size,self.size-self.pos)
        if size<=0: return b''
        key=(self.pos,size)
        if key not in self.cache:
            def fetch(bounds):
                start, count = bounds
                response=requests.get(self.url,headers={'Range':f'bytes={start}-{start+count-1}', 'Accept-Encoding':'identity'},timeout=45,stream=True)
                if response.status_code!=206:
                    response.close()
                    raise RuntimeError('Artifact range read unavailable')
                data=response.content
                if len(data)!=count: raise RuntimeError('Truncated artifact range')
                return data
            chunk=1024*1024
            bounds=[(start,min(chunk,self.pos+size-start)) for start in range(self.pos,self.pos+size,chunk)]
            with ThreadPoolExecutor(max_workers=12) as pool:
                self.cache[key]=b''.join(pool.map(fetch,bounds))
        data=self.cache[key]; self.pos+=len(data)
        return data


def artifact_history(content, publications):
    """Recover older upload IDs that a resume may have overwritten in the DB."""
    available=gh_json('api','repos/{owner}/{repo}/actions/artifacts?per_page=100').get('artifacts',[])
    current={p['content_id']:p.get('platform_id') for p in publications if p['platform']=='youtube'}
    known={c['id']:c for c in content}
    def inspect_archive(a):
        mapping={}; alternates=[]
        if a.get('expired') or not a['name'].startswith('videos-'): return mapping,alternates
        with zipfile.ZipFile(RemoteArchive(a['id'],a['size_in_bytes'])) as z:
            names=z.namelist()
            for n in names:
                if n.endswith('/result.json') or n=='result.json':
                    result=json.loads(z.read(n))
                    cid=result.get('content_id')
                    if cid not in known: continue
                    if any(f.endswith(cid+'/'+cid+'.mp4') for f in names):
                        mapping[cid]={'run_id':a['workflow_run']['id'],'artifact_name':a['name']}
                    for p in result.get('publications',[]):
                        pid=p.get('id'); item=p.get('content_id') or cid
                        if p.get('platform')=='youtube' and pid and item in known and current.get(item)!=pid:
                            alternates.append({'content_id':item,'platform_id':pid,'channel':known[item]['channel'],'artifact':a['name']})
        return mapping,alternates
    mapping={};alternates=[];failures=0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(inspect_archive,a) for a in available]
        for future in futures:
            try:
                m,a=future.result()
                for cid,entry in m.items(): mapping.setdefault(cid,entry)
                alternates.extend(a)
            except Exception: failures+=1
    return mapping,alternates,failures


def sample_artifacts(content, runs, notes, findings, limit=6):
    from pipeline.qa import parse_temporal_output
    sampled=set(); mapping={}
    with tempfile.TemporaryDirectory(prefix='video-audit-') as temp:
        root=Path(temp)
        artifacts=gh_json('api','repos/{owner}/{repo}/actions/artifacts?per_page=100').get('artifacts',[])
        attempted=0
        for artifact in artifacts:
            if len(sampled)>=limit: break
            if artifact.get('expired') or not artifact['name'].startswith('videos-'): continue
            attempted+=1
            if attempted>12: break
            try:
                remote=RemoteArchive(artifact['id'],artifact['size_in_bytes'])
                with zipfile.ZipFile(remote) as z:
                    # Inspect members without extracting arbitrary archive paths.
                    names=z.namelist()
                    candidates=[c for c in content if c['kind']=='long' and c['id'] not in sampled and any(n.endswith(c['id']+'/final.mp4') or n.endswith(c['id']+'/'+c['id']+'.mp4') for n in names)]
                    for c in sorted(candidates,key=lambda c:c['created_at'],reverse=True):
                        if len(sampled)>=limit: break
                        cid=c['id']; name=next(n for n in names if n.endswith(cid+'/final.mp4') or n.endswith(cid+'/'+cid+'.mp4'))
                        print('Sampling retained media: '+cid, file=sys.stderr, flush=True)
                        mapping[cid]={'run_id':artifact['workflow_run']['id'],'artifact_name':artifact['name']}
                        video=root/'sample.mp4'; video.write_bytes(z.read(name))
                        p=json.loads(subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(video)],capture_output=True,text=True,check=True,timeout=30).stdout)
                        streams=p['streams']; v=next(s for s in streams if s['codec_type']=='video'); audio=next((s for s in streams if s['codec_type']=='audio'),{})
                        seconds=float(p['format']['duration'])
                        narration = c.get('duration_sec')
                        voice_names=[n for n in names if n.endswith(cid+'/voice.mp3') or n.endswith(cid+'/narration.mp3')]
                        if voice_names:
                            voice=root/'narration.mp3'; voice.write_bytes(z.read(voice_names[0]))
                            narration=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(voice)],capture_output=True,text=True,check=True,timeout=30).stdout)
                        run=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',str(video),'-vf','blackdetect=d=0:pix_th=0.10,freezedetect=n=-60dB:d=0.1','-an','-f','null','-'],capture_output=True,text=True,check=True,timeout=min(600,max(60,seconds*3)))
                        issues=parse_temporal_output(run.stderr,seconds)
                        evidence=f"{v['width']}x{v['height']}; video={seconds:.2f}s; audio={audio.get('duration','absent/unknown')}s; narration={narration}s (DB fallback when narration absent); temporal={issues}; artifact={artifact['name']}"
                        notes.append(cid+': '+evidence); sampled.add(cid)
                        print('Media sample checked: '+cid, file=sys.stderr, flush=True)
                        if v['width']<1280 or v['height']<720 or not audio or abs(seconds-float(audio.get('duration',seconds)))>2 or narration and abs(seconds-narration)>max(2,seconds*.02) or any(i['severity']=='blocking' for i in issues):
                            findings.append(dict(severity='high',content_id=cid,problem='Artifact media QA failure',evidence=evidence,action='Review and rebuild retained artifact',kind='re-runnable'))
            except Exception as e:
                notes.append('Artifact inspection incomplete: '+artifact['name']+' '+type(e).__name__)
            finally:
                for f in root.iterdir(): f.unlink()
    notes.append(f'Sampled {len(sampled)} recent long videos; all temporary files removed.')
    return mapping


def report(path, findings, notes, content, pubs, runs, mapping):
    ranks={'critical':0,'high':1,'medium':2,'low':3}
    findings.sort(key=lambda f:(ranks[f['severity']],f['content_id'],f['problem']))
    def esc(s): return str(s).replace('|','\\|').replace('\n',' ')
    lines=['# Video audit', '', 'Generated '+datetime.now(timezone.utc).isoformat()+'. Read-only DB, YouTube videos.list, media HEAD and GitHub reads. No platform writes, DB repairs, workflow dispatches or Claude calls.', '', '## Coverage and limitations', '']+['- '+n for n in notes]
    counts=Counter(f['severity'] for f in findings)
    lines += ['', 'Finding counts (one item can have multiple findings): '+', '.join(f'{level}={counts[level]}' for level in ranks)+'.']
    lines+=['','## Findings','','| Severity | Content id | Problem | Evidence | Recommended action | Classification |','|---|---|---|---|---|---|']
    lines += ['| '+' | '.join(esc(f[k]) for k in ('severity','content_id','problem','evidence','action','kind'))+' |' for f in findings]
    lines+=['','## Per-content inventory','','| Content id | Kind | Status | QA | Platforms |','|---|---|---|---|---|']
    for c in sorted(content,key=lambda c:c['id']):
        platforms=', '.join(p['platform']+':'+p['status'] for p in pubs if p['content_id']==c['id'])
        lines.append('| '+' | '.join(esc(x) for x in (c['id'], 'child Short' if c.get('parent_id') else c['kind'],c['status'],c.get('qa_status'),platforms))+' |')
    lines+=['','## Retry and rebuild commands (not executed)','','Quota queues should drain through normal sync; dispatching produce for a quota-only backlog is unnecessary. These commands require deploying fixes and reviewing quota settings first. retry.yml uses --force and bypasses local quota reservations. Reels retries require recovered media; the Hormuz Short cannot be retried successfully until its media is restored. Resume re-runs Claude QA and may generate articles; owner must authorize that spend. Historical scripts with only two angles cannot create four distinct Shorts without new writing.','']
    affected={f['content_id'] for f in findings if f['problem'] in ('Content qa_failed','Content rendered','Artifact media QA failure','Short missing media_url')}
    for platform in ('youtube','instagram','facebook'):
        ids=[str(p['id']) for p in pubs if p['platform']==platform and p.get('status') in ('failed','queued')]
        if ids:
            lines+=['```bash',f"gh workflow run retry.yml -f ids={','.join(ids)} -f platform={platform}",'```']
    seen=set()
    for cid in sorted(affected):
        c=next((c for c in content if c['id']==cid),None)
        root_id=(c.get('parent_id') or cid) if c else cid
        m=mapping.get(root_id)
        if root_id in seen: continue
        seen.add(root_id)
        if m:
            lines += ['```bash', f"gh workflow run produce.yml -f resume_id={root_id} -f artifact_run_id={m['run_id']} -f artifact_name={m['artifact_name']} -f privacy=private"+(' -f rerender=true' if any(f['content_id']==cid and f['problem']=='Artifact media QA failure' for f in findings) else ''),'```']
        else:
            lines.append('- '+cid+': no verified retained artifact mapping; no safe exact retry command available.')
    lines+=['','## Root causes and code fixes','',
        '- Resume skipped approved Shorts before persisting missing media URLs. Resume and production publication paths now retry persistence from real local media.',
        '- Existing uploads were trusted only when status was live. Known YouTube/Meta IDs now prevent reupload across stale retries; YouTube claims the unique publication before insert and blocks uncertain transport outcomes pending reconciliation.',
        '- Resume reset content to rendered, then returned an existing upload without restoring published state. Reusing an existing ID now restores content state.',
        '- Public uploads ignored the computed future publishAt. New uploads remain private and scheduled unless the owner explicitly sets the boolean youtube_compliance_audit_passed=true. Existing remote privacy is untouched. Public Meta Reels retain their documented immediate behavior.',
        '- Daily responses were validated before being saved or linked to a content row. Paid responses now persist before validation and can be reused from DB metadata on a fresh runner. Historical RuntimeError-only logs cannot identify the exact validation failure; no speculative content rewrite was made.',
        '- Existing articles can now refresh their YouTube link without a retained script artifact and preserve an existing ID when a publication row is temporarily unavailable.',
        '- Temporal ffmpeg QA now has a bounded timeout. Conditional DB repairs correctly match NULL fields in SQLite and Supabase.',
        '- Tests now force a disposable SQLite database and reject HTTP/GitHub CLI traffic. Before isolation was fixed, tests altered live quota settings/reservations; a mock test.mp4 was also uploaded to GitHub release media-20261102 at 2026-11-02T06:51:28Z. Owner review required; no cleanup was performed.',
        '- Repair dry-run: zero deterministic content/article/URL repairs. Optional --restore-quota-defaults --dry-run proposes 100 uploads and 10000 general units; no repairs applied. Never decrement uncertain reservations automatically.',
        '', '## Owner decisions' ,'','- Public-before-schedule videos: decide intended privacy/publishing policy and audit status; no privacy changes made.', '- Possible duplicates: compare in Studio before deciding deletion; videos.list cannot discover unrecorded video IDs. Same-Reel duplicate detection covers DB IDs only, not an external Meta inventory.', '- Deleted/inaccessible IDs and missing owner-only fileDetails cannot be conclusively resolved using videos.list alone.', '- Missing articles need separately authorized Claude spend. Killed placeholder Shorts are intentional and excluded from findings.']
    path.write_text('\n'.join(lines)+'\n')


def main():
    ap=argparse.ArgumentParser(__doc__); ap.add_argument('--report',type=Path,default=Path('docs/video-audit.md')); ap.add_argument('--sample-media',action='store_true'); ap.add_argument('--media-limit',type=int,choices=range(1,7),default=6); args=ap.parse_args()
    db=production_db()
    content,pubs,articles,costs=[read_table(db,t) for t in ('content','publications','articles','costs')]
    notes=[f'DB inventory: {len(content)} content, {len(pubs)} publications, {len(articles)} articles, {len(costs)} cost rows.']
    notes.append('Verification incident 2026-11-02: pre-existing tests inherited Supabase configuration. Tests wrote youtube_uploads_per_day (0 then 3), youtube_quota_units_per_day (0), and forced quota reservations. Counters must not be rolled back blindly. Test isolation is now enforced in tests/conftest.py. Owner must review/reset quota settings; no corrective live writes performed.')
    history_map={}; alternates=[]
    try:
        history_map,alternates,failures=artifact_history(content,pubs)
        notes.append(f'Retained result.json history: {len(history_map)} mapped longs, {len(alternates)} older/different upload ID records; {failures} archives unavailable.')
    except Exception as e: notes.append('Artifact upload history unavailable: '+type(e).__name__)
    truth={}; checked=set(); calls=0
    for channel in Channel.keys():
        youtube.use_channel(Channel(channel)); ids=sorted({p['platform_id'] for p in pubs if p['platform']=='youtube' and p.get('platform_id') and any(c['id']==p['content_id'] and c['channel']==channel for c in content)})
        ids=sorted(set(ids)|{a['platform_id'] for a in alternates if a['channel']==channel})
        try:
            service=youtube.yt()
            for offset in range(0,len(ids),50):
                batch=ids[offset:offset+50]; calls+=1
                result=service.videos().list(part='snippet,status,contentDetails,processingDetails,fileDetails',id=','.join(batch)).execute()
                truth.update({v['id']:v for v in result.get('items',[])}); checked.update(batch)
        except Exception as e:
            notes.append('YouTube coverage incomplete for '+channel+': '+type(e).__name__)
    notes.append(f'YouTube: {calls} batched videos.list calls; {len(checked)} checked IDs; {len(truth)} accessible videos. Unrecorded uploads cannot be enumerated under videos.list-only constraint.')
    notes.append('Wrong-channel verification uses configured YT_CHANNEL_ID when available; otherwise channelId consistency only. Vertical verification requires owner-visible fileDetails; absent fields are unverified. API thumbnails do not prove a custom thumbnail was set.')
    urls=sorted({c['media_url'] for c in content if c.get('media_url') and c.get('status')!='killed'})
    with ThreadPoolExecutor(max_workers=6) as pool: heads=dict(zip(urls,pool.map(head,urls)))
    findings=inspect(content,pubs,articles,costs,truth,checked,heads=heads)
    if db.setting('youtube_uploads_per_day') in (0,3) or db.setting('youtube_quota_units_per_day')==0:
        findings.append(dict(severity='critical',content_id='quota settings',problem='Test contamination of live quota configuration',evidence='Existing unisolated tests wrote uploads=0/3, general units=0, and quota reservations',action='Owner restore intended quota settings; retain uncertain counters. Use repair --restore-quota-defaults only after review.',kind='owner-only'))
    for a in alternates:
        if a['platform_id'] in truth:
            findings.append(dict(severity='high',content_id=a['content_id'],problem='Earlier artifact upload differs from DB',evidence=a['platform_id']+' remains accessible; '+a['artifact'],action='Owner compare both uploads in Studio before deciding deletion; never automatically delete',kind='owner-only'))
    # Private queue bucket listing is read-only and paginated at each folder.
    references={p[k] for p in pubs for k in ('media_key','thumbnail_key') if p.get(k)}
    try:
        bucket=db.sb.storage.from_('youtube-queue'); pending=['']; files=[]
        while pending:
            prefix=pending.pop(); offset=0
            while True:
                page=bucket.list(prefix,{'limit':100,'offset':offset,'sortBy':{'column':'name','order':'asc'}})
                for obj in page:
                    key=(prefix+'/'+obj['name']).lstrip('/')
                    if obj.get('id'): files.append(key)
                    else: pending.append(key)
                if len(page)<100: break
                offset+=100
        orphaned=sorted(set(files)-references)
        notes.append(f'Private queue: {len(files)} objects; {len(orphaned)} unreferenced objects (never deleted).')
        for key in orphaned: findings.append(dict(severity='low',content_id=key.split('/')[0],problem='Orphan queue object',evidence=key,action='Owner verify no in-flight upload before cleanup',kind='owner-only'))
    except Exception as e: notes.append('Queue listing incomplete: '+type(e).__name__)
    try: runs=gh_json('run','list','--limit','100','--json','databaseId,workflowName,displayTitle,status,conclusion,createdAt,updatedAt')
    except Exception as e: runs=[]; notes.append('Run listing incomplete: '+type(e).__name__)
    notes.append('GitHub recent runs: '+str(len(runs))+'; failed: '+', '.join(str(r['databaseId'])+' '+r['workflowName'] for r in runs if r['conclusion']=='failure'))
    mapping=history_map
    report(args.report,findings,notes,content,pubs,runs,mapping)
    if args.sample_media:
        try: mapping.update(sample_artifacts(content,runs,notes,findings,limit=args.media_limit))
        except Exception as e: notes.append('Artifact sampling unavailable: '+type(e).__name__)
    else: notes.append('Media artifact sampling skipped (use --sample-media).')
    report(args.report,findings,notes,content,pubs,runs,mapping)
    counts=Counter(f['severity'] for f in findings)
    print(json.dumps({'content':len(content),'findings':dict(counts),'report':str(args.report)}))

if __name__=='__main__': main()
