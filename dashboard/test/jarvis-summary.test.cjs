const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const Module = require('node:module');
function compile(file, mocks = {}) {
  const m = new Module(file, module); m.filename = file; m.paths = module.paths;
  m.require = name => name in mocks ? mocks[name] : require(name);
  m._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, file);
  return m.exports;
}
const { authorized, summarize } = compile('src/lib/jarvis-summary.ts');
test('dedicated token fails closed', () => {
  assert.equal(authorized('Bearer fixture', 'fixture'), true);
  for (const header of [null, 'fixture', 'Bearer wrong', 'Bearer fixture ']) assert.equal(authorized(header, 'fixture'), false);
  assert.equal(authorized('Bearer fixture', undefined), false);
});
test('windowed counts, metric baseline, no sensitive fields and stable idle fingerprint', () => {
  const data = { content: [{id:'a', channel:'futurework', script:'secret'}], publications: [
    {id:1, content_id:'a', platform:'youtube', status:'live', published_at:'2026-11-03T09:30:00Z'},
    {id:2, content_id:'a', platform:'facebook', status:'failed', status_changed_at:'2026-11-03T09:40:00Z', error:'sensitive'},
    {id:3, status:'queued'}, {id:4, status:'failed', status_changed_at:'2026-11-01T09:00:00Z'}], metrics: [
    {id:1, publication_id:1, captured_at:'2026-11-03T08:30:00Z', views:100, likes:10, comments:1},
    {id:2, publication_id:1, captured_at:'2026-11-03T09:55:00Z', views:140, likes:12, comments:3}],
    costs:[{at:'2026-11-03T09:00:00Z', usd:2}], settings:[{key:'monthly_budget_usd', value:95}, {key:'ig_token_futurework', value:'sensitive'}], comments:[{id:1}], runs:[] };
  const s = summarize(data, '1h', new Date('2026-11-03T10:00:00Z'));
  assert.equal(s.uploads.futurework.youtube,1); assert.equal(s.failures,1); assert.equal(s.queued,1);
  assert.deepEqual(s.delta, {views:40, likes:2, comments:2}); assert.equal(s.spend.budgetUsd,95);
  assert.equal(JSON.stringify(s).includes('sensitive'),false); assert.equal(JSON.stringify(s).includes('secret'),false);
  assert.equal(s.lastEventId, summarize(data,'1h',new Date('2026-11-03T12:00:00Z')).lastEventId);
});
test('route rejects requests before database access and uses no-store', async () => {
  const old = process.env.JARVIS_READ_TOKEN; process.env.JARVIS_READ_TOKEN='fixture';
  try {
    let reads=0;
    const { GET } = compile('src/app/api/jarvis/summary/route.ts', {
      '@/lib/jarvis-summary': {authorized,summarize}, '@/lib/supabase': { db:()=>{reads++; throw Error('offline')} },
      'next/server': { NextResponse: { json:(body, init)=>({body,...init}) } },
    });
    const req = (token, window='1h') => ({headers:new Headers({authorization:token}), nextUrl:new URL(`https://fixture.invalid/api/jarvis/summary?window=${window}`)});
    assert.equal((await GET(req('Bearer wrong'))).status,401); assert.equal(reads,0);
    assert.equal((await GET(req('Bearer fixture','bad'))).status,400); assert.equal(reads,0);
    const result = await GET(req('Bearer fixture')); assert.equal(result.status,503); assert.equal(result.headers['Cache-Control'],'private, no-store');
  } finally { if(old===undefined) delete process.env.JARVIS_READ_TOKEN; else process.env.JARVIS_READ_TOKEN=old; }
});
