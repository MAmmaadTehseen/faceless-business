"""Local PostgREST stand-in. Uses only invented records and no credentials."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import datetime as dt
import json
now = dt.datetime.now(dt.timezone.utc)
def stamp(days=0): return (now + dt.timedelta(days=days)).isoformat()
long_id='futurework-2026-10-30-changing-work'
content=[dict(id=long_id, channel='futurework', kind='long', parent_id=None, title='The skills that matter when AI does the routine work',topic='How automation changes the tasks inside a job',status='published',qa_status='passed',qa_notes='Narration and footage passed all checks.',thumbnail_path='http://127.0.0.1:43992/preview.svg',created_at=stamp(-10))]
for n in range(1,5):
 content.append(dict(content[0],id=f'{long_id}-short-{n}',kind='short',parent_id=long_id,title=['Why tasks change before jobs disappear','The skill that connects people and AI','What a changing job actually looks like','Where to start learning this week'][n-1]))
pubs=[]
for i,c in enumerate(content):
 for j,p in enumerate(['youtube','instagram','facebook']):
  status='failed' if (i,j)==(2,1) else 'queued' if (i,j)==(3,2) else 'scheduled' if i==4 else 'live'
  pubs.append(dict(id=i*3+j+1,content_id=c['id'],platform=p,platform_id='fixture',url=None if status in ['failed','queued'] else 'https://example.com/video',privacy='scheduled' if status=='scheduled' else 'public',status=status,publish_at=stamp(2) if status=='scheduled' else None,published_at=stamp(-9+i) if status=='live' else None,error='Upload timed out after three attempts.' if status=='failed' else None,content=dict(c)))
metrics=[]
for p in pubs:
 if p['status']!='live':continue
 for d in range(10):
  metrics.append(dict(id=p['id']*100+d,publication_id=p['id'],captured_at=stamp(-9+d),views=(d+1)*p['id']*245,likes=(d+1)*p['id']*12,comments=(d+1)*p['id'],shares=2,ctr=48+d/3,avg_view_duration_sec=90,impressions=None))
comments=[dict(id=n,publication_id=n,platform=pubs[n-1]['platform'],platform_comment_id=f'fixture-{n}',author=['Alex','Sam','Jordan'][n%3],text='Which skills would you focus on first if your everyday work is changing?',posted_at=stamp(-n/24),flagged=False,flag_reason=None,draft_reply='Start with one task you already understand. Compare the tool’s result against your own judgement.',reply_status='drafted',liked=False) for n in range(1,11)]
content[3]['parent_id']=None  # legacy suffix-only link
content[4]['id']='reference-linked-short'  # explicit parent without a numeric suffix
for p in pubs:
 if p['content_id'].endswith('-short-4'):p['content_id']='reference-linked-short'
content.append(dict(content[0],id='empty-video',title='A video awaiting its first metrics',status='draft'))
tables=dict(content=content,publications=pubs,metrics=metrics,comments=comments,costs=[dict(id=i,content_id=c['id'],step='article' if i==0 else 'script',usd=.32,at=stamp(-9)) for i,c in enumerate(content)],articles=[dict(id='fixture',content_id=long_id,slug='changing-work',published_at=stamp(-9))],runs=[dict(id=42,channel='futurework',workflow='produce',status='ok',started_at=stamp(-10),finished_at=stamp(-9),github_url='https://github.com/example/channel/actions/runs/42',stages=[dict(stage=s,at=stamp(-10+i/1440)) for i,s in enumerate(['ideate','script','voice','footage','render','QA','upload','article'])],log=json.dumps(dict(results=[dict(content_id=long_id)])))],settings=[],topic_queue=[dict(id=i,channel="futurework",topic="How changing tools affect the skills people need at work "+str(i),priority=10-i,status="queued",added_by="owner",created_at=stamp(-1),source_url=None,source_headline=None) for i in range(1,5)])
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path=='/shutdown':
   self.respond(b'fixture stopped');self.server.stopped=True;return
  if self.path=='/preview.svg':
   body=b'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540"><rect width="960" height="540" fill="#242830"/><path d="M0 420L420 80L960 420V540H0" fill="#363c46"/><text x="70" y="235" fill="#f5f5f7" font-family="sans-serif" font-size="52">THE WORK IS CHANGING</text><text x="70" y="305" fill="#adb1ba" font-family="sans-serif" font-size="30">What comes next?</text></svg>'
   self.respond(body,'image/svg+xml');return
  parsed=urlparse(self.path); name=parsed.path.split('/')[-1];qs=parse_qs(parsed.query); data=list(tables.get(name,[]))
  for key,values in qs.items():
   value=values[0]
   if value.startswith('eq.'):data=[r for r in data if str(r.get(key))==value[3:]]
   if value=='is.null':data=[r for r in data if r.get(key) is None]
   if value.startswith('in.'):data=[r for r in data if str(r.get(key)) in value[3:].strip('()').split(',')]
   if value.startswith('like.'):
    needle=value[5:].replace('%','').replace('\\','');data=[r for r in data if needle in str(r.get(key,''))]
   if value.startswith('gte.'):data=[r for r in data if str(r.get(key,''))>=value[4:]]
  for order in reversed(qs.get('order',[''])[0].split(',')):
   if order:
    key=order.split('.')[0];data.sort(key=lambda r:str(r.get(key) or ''),reverse='.desc' in order)
  start=int(qs.get('offset',['0'])[0]);limit=int(qs.get('limit',['1000'])[0]);data=data[start:start+limit]
  if 'application/vnd.pgrst.object+json' in self.headers.get('Accept',''):data=data[0] if data else None
  self.respond(json.dumps(data).encode())
 def respond(self,body,kind='application/json'):
  self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',43992),Handler)
server.stopped=False
while not server.stopped:server.handle_request()
server.server_close()
