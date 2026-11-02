#!/usr/bin/env python3
"""Conservative DB-only metadata repairs. Defaults to dry-run; never calls platform APIs.

Only repair deterministic URLs, content state backed by a known live publication,
and missing article video IDs. Missing media cannot be guessed or regenerated here.
"""
from __future__ import annotations
import argparse
import json
import logging
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.db import DB
from scripts.audit_videos import read_table, production_db
logging.getLogger('httpx').setLevel(logging.WARNING)


def plan(content, publications, articles):
    repairs=[]
    active={c['id']:c for c in content if c.get('status')!='killed' and not c.get('placeholder')}
    yt={p['content_id']:p for p in publications if p['platform']=='youtube' and p.get('status')=='live' and p.get('platform_id')}
    for p in publications:
        c=active.get(p['content_id'])
        if not c or p.get('status')!='live' or not p.get('platform_id') or p.get('url') or p['platform']!='youtube': continue
        url=('https://youtube.com/shorts/' if c['kind']=='short' else 'https://youtu.be/')+p['platform_id']
        repairs.append({'table':'publications','match':{'id':p['id'],'status':'live','platform_id':p['platform_id'],'url':None},'fields':{'url':url},'reason':'canonical URL from known live YouTube id'})
    for cid,c in active.items():
        if cid in yt and c.get('status')=='rendered' and c.get('qa_status')=='passed':
            repairs.append({'table':'content','match':{'id':cid,'status':'rendered','qa_status':'passed'},'fields':{'status':'published'},'reason':'known live YouTube publication'})
    for a in articles:
        if a['content_id'] in active and a['content_id'] in yt and not a.get('youtube_id'):
            repairs.append({'table':'articles','match':{'id':a['id'],'youtube_id':None},'fields':{'youtube_id':yt[a['content_id']]['platform_id']},'reason':'article link from known live YouTube publication'})
    return repairs


def main():
    ap=argparse.ArgumentParser(__doc__); ap.add_argument('--restore-quota-defaults',action='store_true',help='Explicitly restore documented defaults 100 uploads and 10000 units; never rewinds reservations'); group=ap.add_mutually_exclusive_group(); group.add_argument('--dry-run',action='store_true'); group.add_argument('--apply',action='store_true'); args=ap.parse_args()
    db=production_db()
    changes=plan(*[read_table(db,t) for t in ('content','publications','articles')])
    if args.restore_quota_defaults:
        for key,value in (('youtube_uploads_per_day',100),('youtube_quota_units_per_day',10000)):
            old=db.setting(key)
            if old != value:
                changes.append({'table':'settings','match':{'key':key},'fields':{'value':value},'reason':f'Owner-selected documented quota default; previous value={old}'})
    for change in changes:
        print(json.dumps(change))
        if args.apply:
            # Guard against a concurrent status/ID change since this plan was read.
            current=db.one(change['table'],{k:v for k,v in change['match'].items() if k in ('id','key')})
            if current and all(current.get(k)==v for k,v in change['match'].items()):
                db.update(change['table'],change['match'],change['fields'])
    print(json.dumps({'mode':'apply' if args.apply else 'dry-run','planned':len(changes)}))

if __name__=='__main__': main()
