const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});try{
const results=[];
for(const reduced of [false,true])for(const theme of ['light','dark'])for(const width of [320,375,390,768,1024,1280,1335,1366,1440,1536,1920]){
const context=await browser.newContext({viewport:{width,height:1000},colorScheme:theme,reducedMotion:reduced?'reduce':'no-preference'});
for(const [name,path]of [['home','/'],['channel','/c/futurework'],['article','/a/preview-story-0']]){
const page=await context.newPage();await page.route('https://i.ytimg.com/**',route=>route.fulfill({contentType:'image/svg+xml',path:require('node:path').join(__dirname,'../public/artwork/futurework.svg')}));await page.goto((process.env.MOTION_BASE||'http://localhost:3137')+path,{waitUntil:'domcontentloaded'});await page.evaluate(()=>document.fonts.ready);
await page.evaluate(async()=>{document.querySelectorAll('img').forEach(i=>i.loading='eager');await Promise.race([Promise.all([...document.images].map(i=>i.decode().catch(()=>{}))),new Promise(r=>setTimeout(r,15000))])});
// Omit Next's development-only overlay from the editorial screenshots.
await page.addStyleTag({content:'nextjs-portal{display:none!important}'});
await page.waitForTimeout(800);assert(await page.evaluate(()=>[...document.images].every(i=>i.complete&&i.naturalWidth>0)),'all screenshots must have loaded images');
const overflow=await page.evaluate(()=>({document:document.documentElement.scrollWidth>innerWidth,elements:[...document.querySelectorAll('body *')].filter(el=>{const s=getComputedStyle(el),r=el.getBoundingClientRect();let left=r.left,right=r.right;for(let parent=el.parentElement;parent;parent=parent.parentElement){if(/hidden|clip|auto|scroll/.test(getComputedStyle(parent).overflowX)){const box=parent.getBoundingClientRect();left=Math.max(left,box.left);right=Math.min(right,box.right)}}return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0&&!el.closest('nextjs-portal')&&(right>innerWidth+.5||left<-.5)}).map(el=>({tag:el.tagName,class:el.className,right:el.getBoundingClientRect().right}))}));
results.push({name,width,theme,reduced,...overflow});
require('node:fs').writeFileSync('design-review/editorial-overflow.json',JSON.stringify(results,null,2));
assert(!overflow.document && !overflow.elements.length,JSON.stringify({name,width,theme,reduced,overflow}));
// Freeze offscreen reveal masks only for the static full-page artifact.
await page.addStyleTag({content:'.below-fold-card .card-image{clip-path:none!important}.story-card,.channel-row{opacity:1!important}'});
await page.screenshot({path:`design-review/motion-${name}-${width}-${theme}${reduced?'-reduced':''}.png`,fullPage:true});await page.close();}await context.close();}console.log('PASS',results.length,'screenshots with decoded images and element/document overflow checks');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
