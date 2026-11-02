"""Three-channel fixtures for scope QA; no environment files or real services."""
from pathlib import Path
import copy
source = Path(__file__).with_name('fixture.py').read_text()
setup, server = source.split('class Handler', 1)
exec(setup)
for cost in tables['costs']: cost['channel']='futurework'
for index, channel in enumerate(('tradewinds', 'escapevelocity'), 1):
    mapping = {c['id']: channel + '-' + c['id'] for c in list(content)}
    for c in list(content)[:6]:
        if c['channel'] != 'futurework': continue
        row = copy.deepcopy(c)
        row.update(id=mapping[c['id']], channel=channel, parent_id=mapping.get(c['parent_id']))
        content.append(row)
    originals = [p for p in pubs if p['content']['channel'] == 'futurework']
    for p in originals:
        row = copy.deepcopy(p)
        row.update(id=p['id'] + index*100, content_id=mapping[p['content_id']])
        row['content'].update(channel=channel, id=mapping[p['content_id']])
        pubs.append(row)
    for m in list(metrics):
        if m['publication_id'] >= 100: continue
        metrics.append(dict(m,id=m['id']+index*10000,publication_id=m['publication_id']+index*100,views=m['views']*(index+1)))
    for cost in list(tables['costs']):
        if cost['channel']=='futurework': tables['costs'].append(dict(cost,id=cost['id']+index*100,channel=channel,content_id=mapping[cost['content_id']]))
    for c in list(comments):
        if c['id'] >= 100: continue
        comments.append(dict(c,id=c['id']+index*100,publication_id=c['publication_id']+index*100))
exec('class Handler' + server)
