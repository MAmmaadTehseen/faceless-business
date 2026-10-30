// Exercise the server's fallback ordering without network, credentials or fixtures.
const fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript'),assert=require('node:assert/strict');
const source=ts.transpileModule(fs.readFileSync(require('node:path').join(__dirname,'../src/lib/article-image.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const exportsObject={};let requests=[],statuses={};
vm.runInNewContext(source,{exports:exportsObject,require(name){if(name==='server-only')return {};if(name==='next/cache')return {unstable_cache:f=>f};if(name==='react')return {cache:f=>f};throw Error(name)},Date,process:{env:{SUPABASE_URL:'https://media.example.test'}},AbortSignal,fetch:async url=>{requests.push(url);return {ok:statuses[url]===200,headers:{get:()=> 'image/jpeg'}}}});
const a={slug:'example-story',channel:'futurework',youtube_id:null};
(async()=>{
assert.deepEqual(Array.from(exportsObject.imageCandidates(a)),['/a/example-story/opengraph-image','/artwork/futurework.svg']);
assert.equal((await exportsObject.articleImage(a)).real,false);assert.equal(requests.length,0,'missing ID makes no YouTube request');
const video={...a,youtube_id:'aqz-KE-bpKQ'};let candidates=exportsObject.imageCandidates(video);
statuses[candidates[1]]=200;assert.equal((await exportsObject.articleImage(video)).sources[0],candidates[1],'404 maxres falls through to hqdefault');
statuses={};const missing={...video,youtube_id:'xxxxxxxxxxx'};assert.equal((await exportsObject.articleImage(missing)).sources[0],'/a/example-story/opengraph-image');
const stored={...video,thumbnail_path:'articles/example/thumbnail.jpg'};candidates=exportsObject.imageCandidates(stored);statuses[candidates[0]]=200;
assert.equal((await exportsObject.articleImage(stored)).sources[0],'https://media.example.test/storage/v1/object/public/media/articles/example/thumbnail.jpg');
assert.equal((await exportsObject.articleImage(stored)).real,true);
assert(!exportsObject.imageCandidates({...a,thumbnail_path:'https://untrusted.example/pixel'}).some(s=>s.includes('untrusted')));
console.log('PASS missing ID, maxres 404, hqdefault 404, stored thumbnail preference and URL allowlist');
})().catch(error=>{console.error(error);process.exitCode=1});
