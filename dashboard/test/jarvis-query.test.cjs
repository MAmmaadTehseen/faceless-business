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
const query = compile('src/lib/jarvis-query.ts');
const { parseQuery, aggregate } = query;
const { authorized } = compile('src/lib/jarvis-summary.ts');
const CHANNELS = ['futurework', 'tradewinds', 'escapevelocity', 'tentongues'];
const NOW = new Date('2026-11-24T12:00:00Z');
const parse = (qs) => parseQuery(new URLSearchParams(qs), CHANNELS, NOW);

test('window parameters: hours or from/to, strictly', () => {
  const h = parse('hours=2').query;
  assert.equal(h.to.toISOString(), NOW.toISOString());
  assert.equal(h.from.toISOString(), '2026-11-24T10:00:00.000Z');
  assert.deepEqual([h.by, h.channel, h.platform, h.top], ['channel', null, null, 5]);
  assert.ok(parse('hours=0.25').query); assert.ok(parse('hours=2160').query);
  const r = parse('from=2026-11-20T00:00:00Z&to=2026-11-21T00:00:00%2B05:00').query;
  assert.equal(r.to.toISOString(), '2026-11-20T19:00:00.000Z');
  assert.equal(parse('from=2026-11-23T00:00:00.000Z').query.to.toISOString(), NOW.toISOString());
  for (const bad of ['', 'hours=0.2', 'hours=2161', 'hours=abc', 'hours=-1', 'hours=1e2', 'hours=', 'hours=2&from=2026-11-23T00:00:00Z',
    'to=2026-11-23T00:00:00Z', 'from=2026-11-23', 'from=yesterday', 'from=2026-11-23T00:00:00', 'from=2026-13-40T00:00:00Z',
    'from=2026-11-24T12:00:00Z', 'from=2026-11-24T13:00:00Z', 'from=2026-08-01T00:00:00Z', 'hours=1&hours=2', 'hours=1&days=2'])
    assert.ok(parse(bad).error, `should reject ${JSON.stringify(bad)}`);
  assert.ok(parse('from=2026-08-26T12:00:00Z').query, 'exactly 90 days is allowed');
});

test('grouping, filters and top parameters', () => {
  const q = parse('hours=24&by=platform&channel=tradewinds&platform=youtube&top=20').query;
  assert.deepEqual([q.by, q.channel, q.platform, q.top], ['platform', 'tradewinds', 'youtube', 20]);
  for (const by of ['channel', 'platform', 'content', 'none']) assert.equal(parse(`hours=1&by=${by}`).query.by, by);
  for (const bad of ['by=day', 'channel=unknown', 'channel=', 'platform=hub', 'top=0', 'top=21', 'top=2.5', 'top=x'])
    assert.ok(parse(`hours=1&${bad}`).error, `should reject ${bad}`);
});

const pub = (id, over) => ({ id, content_id: `c${id}`, platform: 'youtube', status: 'live', published_at: '2026-11-01T00:00:00Z',
  publish_at: null, status_changed_at: null, channel: 'futurework', title: `T${id}`, ...over });
const snap = (id, publication_id, captured_at, views, likes = 0, comments = 0) => ({ id, publication_id, captured_at, views, likes, comments });
const rows = () => ({
  live: [
    pub(1), // old video with a baseline
    pub(2, { platform: 'instagram', channel: 'tradewinds', published_at: '2026-11-24T08:00:00Z' }), // uploaded inside the window
    pub(3, { channel: 'tradewinds' }), // old video, no snapshot at the window start
    pub(4, { published_at: '2026-11-24T13:00:00Z' }), // published after `to`: ignored
    pub(5), // views fell (deleted counts): clamped to zero
  ],
  failed: [pub(6, { status: 'failed', status_changed_at: '2026-11-24T09:00:00Z', platform: 'facebook' }),
    pub(7, { status: 'failed', status_changed_at: '2026-11-20T09:00:00Z' })],
  scheduled: [pub(8, { status: 'queued', publish_at: '2026-11-24T07:00:00Z' }),
    pub(9, { status: 'live', publish_at: '2026-11-24T11:00:00Z' }), // already public: not scheduled
    pub(10, { status: 'killed', publish_at: '2026-11-24T07:00:00Z' })],
  snapshots: [
    snap(1, 1, '2026-11-24T05:00:00Z', 100, 10, 1), snap(2, 1, '2026-11-24T11:00:00Z', 160, 13, 2),
    snap(3, 2, '2026-11-24T10:00:00Z', 50, 5, 5),
    snap(4, 3, '2026-11-24T09:00:00Z', 30, 1, 0),
    snap(5, 5, '2026-11-24T05:00:00Z', 90), snap(6, 5, '2026-11-24T11:30:00Z', 80),
  ],
  costs: [{ usd: 0.5 }, { usd: 0.25 }, { usd: null }],
  snapshot: { queued: 3, pendingComments: 2, runningJobs: 1, monthSpendUsd: 12.345678, budgetUsd: 100 },
});

test('aggregation: uploads, audience gain, top, spend and exact response shape', () => {
  const q = parse('hours=6').query; // 06:00 to 12:00
  const r = aggregate(q, rows(), NOW);
  assert.deepEqual(Object.keys(r), ['from', 'to', 'by', 'uploads', 'audience', 'top', 'spend', 'snapshot']);
  assert.deepEqual(r.uploads, { live: 1, failed: 1, scheduled: 1, groups: [{ key: 'tradewinds', live: 1, failed: 0 }, { key: 'futurework', live: 0, failed: 1 }] });
  // 1: 160-100, 2: full 50 (new), 3: 30 (no baseline counts from zero), 5: clamped to 0
  assert.equal(r.audience.views, 140); assert.equal(r.audience.likes, 9); assert.equal(r.audience.comments, 6);
  assert.deepEqual(r.audience.groups, [{ key: 'tradewinds', views: 80, likes: 6, comments: 5 }, { key: 'futurework', views: 60, likes: 3, comments: 1 }]);
  assert.deepEqual(r.top.map(t => [t.contentId, t.views]), [['c1', 60], ['c2', 50], ['c3', 30]]);
  assert.deepEqual(r.top[1], { contentId: 'c2', channel: 'tradewinds', title: 'T2', platform: 'instagram', views: 50 });
  assert.deepEqual(r.spend, { usd: 0.75 });
  assert.deepEqual(r.snapshot, { queued: 3, pendingComments: 2, runningJobs: 1, monthSpendUsd: 12.3457, budgetUsd: 100 });
});

test('aggregation: filters, by=none, by=content and top limit', () => {
  const tw = aggregate(parse('hours=6&channel=tradewinds').query, rows(), NOW);
  assert.equal(tw.uploads.live, 1); assert.equal(tw.uploads.failed, 0); assert.equal(tw.audience.views, 80);
  const yt = aggregate(parse('hours=6&platform=youtube&by=platform').query, rows(), NOW);
  assert.equal(yt.uploads.live, 0); assert.equal(yt.audience.views, 90);
  assert.deepEqual(yt.audience.groups, [{ key: 'youtube', views: 90, likes: 4, comments: 1 }]);
  const none = aggregate(parse('hours=6&by=none&top=1').query, rows(), NOW);
  assert.deepEqual([none.uploads.groups, none.audience.groups], [[], []]);
  assert.equal(none.top.length, 1); assert.equal(none.audience.views, 140);
  assert.deepEqual(aggregate(parse('hours=6&by=content').query, rows(), NOW).audience.groups.map(g => g.key), ['c1', 'c2', 'c3']);
  // A window with no snapshot at its end has no gain at all.
  assert.equal(aggregate(parse('from=2026-11-24T00:00:00Z&to=2026-11-24T04:00:00Z').query, rows(), NOW).audience.views, 0);
});

test('loader filters in SQL and never pages the metrics table', async () => {
  const calls = [];
  const builder = (table, log) => new Proxy({}, { get: (_, op) => op === 'then'
    ? (res) => res({ data: table === 'publications' && !log.head ? [{ id: 1, content_id: 'c1', platform: 'youtube', status: 'live', published_at: '2026-11-24T08:00:00Z', content: { channel: 'futurework', title: 'T' } }] : [], count: 1, error: null })
    : (...args) => { log.ops.push([op, ...args]); if (op === 'select' && args[1]?.head) log.head = true; return builder(table, log); } });
  const db = () => ({
    from: (table) => { const log = { table, ops: [] }; calls.push(log); return builder(table, log); },
    rpc: (name, args) => { calls.push({ table: `rpc:${name}`, ops: [args] }); return Promise.resolve({ data: [], error: null }); },
  });
  const { loadQueryRows } = compile('src/lib/jarvis-data.ts', { 'server-only': {}, './supabase': { db }, './content-data': { latestMetrics: async () => [] } });
  const q = parse('hours=2&channel=futurework&platform=youtube').query;
  const out = await loadQueryRows(q, NOW);
  assert.equal(out.live.length, 1); assert.equal(out.live[0].channel, 'futurework');
  assert.equal(calls.some(c => c.table === 'metrics'), false);
  const rpc = calls.find(c => c.table === 'rpc:metric_snapshots_at');
  assert.deepEqual(rpc.ops[0], { p_ids: [1], p_times: [q.from.toISOString(), q.to.toISOString()] });
  for (const c of calls.filter(c => c.table === 'publications' && !c.head)) {
    assert.ok(c.ops.some(o => o[0] === 'eq' && o[1] === 'content.channel' && o[2] === 'futurework'));
    assert.ok(c.ops.some(o => o[0] === 'eq' && o[1] === 'platform' && o[2] === 'youtube'));
  }
  const costs = calls.find(c => c.table === 'costs' && c.ops.some(o => o[0] === 'lte'));
  assert.ok(costs.ops.some(o => o[0] === 'eq' && o[1] === 'channel'));
});

test('route: 401 without the token, 400 on bad input, both before database access, no-store', async () => {
  const old = process.env.JARVIS_READ_TOKEN; process.env.JARVIS_READ_TOKEN = 'fixture';
  try {
    let reads = 0;
    const { GET, dynamic, runtime } = compile('src/app/api/jarvis/query/route.ts', {
      '@/lib/jarvis-summary': { authorized }, '@/lib/jarvis-query': query, '@/lib/channels': { CHANNEL_KEYS: CHANNELS },
      '@/lib/jarvis-data': { loadQueryRows: async () => { reads++; return rows(); } },
      'next/server': { NextResponse: { json: (body, init) => ({ body, ...init }) } },
    });
    assert.deepEqual([dynamic, runtime], ['force-dynamic', 'nodejs']);
    const req = (token, qs = 'hours=2') => ({ headers: new Headers(token ? { authorization: token } : {}), nextUrl: new URL(`https://fixture.invalid/api/jarvis/query?${qs}`) });
    for (const t of [null, 'Bearer wrong', 'fixture']) {
      const r = await GET(req(t)); assert.equal(r.status, 401); assert.equal(r.headers['Cache-Control'], 'private, no-store');
    }
    assert.equal((await GET(req('Bearer fixture', 'hours=9999'))).status, 400);
    assert.equal(reads, 0);
    const ok = await GET(req('Bearer fixture', 'hours=6'));
    assert.equal(ok.status, undefined); assert.equal(ok.headers['Cache-Control'], 'private, no-store');
    assert.equal(ok.body.by, 'channel'); assert.equal(reads, 1);
    const { GET: broken } = compile('src/app/api/jarvis/query/route.ts', {
      '@/lib/jarvis-summary': { authorized }, '@/lib/jarvis-query': query, '@/lib/channels': { CHANNEL_KEYS: CHANNELS },
      '@/lib/jarvis-data': { loadQueryRows: async () => { throw Error('offline'); } },
      'next/server': { NextResponse: { json: (body, init) => ({ body, ...init }) } },
    });
    assert.equal((await broken(req('Bearer fixture'))).status, 503);
  } finally { if (old === undefined) delete process.env.JARVIS_READ_TOKEN; else process.env.JARVIS_READ_TOKEN = old; }
});
