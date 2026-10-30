const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});try{
for(const reduced of [false,true])for(const theme of ['light','dark'])for(const width of [390,1440]){
const context=await browser.newContext({viewport:{width,height:1000},colorScheme:theme,reducedMotion:reduced?'reduce':'no-preference'});
for(const [name,path]of [['home','/'],['channel','/c/futurework'],['article','/a/preview-story-0']]){
const page=await context.newPage();await page.goto((process.env.MOTION_BASE||'http://localhost:3137')+path,{waitUntil:'domcontentloaded'});await page.evaluate(()=>document.fonts.ready);
await page.evaluate(async()=>{document.querySelectorAll('img').forEach(i=>i.loading='eager');await Promise.race([Promise.all([...document.images].map(i=>i.decode().catch(()=>{}))),new Promise(r=>setTimeout(r,15000))])});
// Omit Next's development-only overlay from the editorial screenshots.
await page.addStyleTag({content:'nextjs-portal{display:none!important}'});
await page.waitForTimeout(800);assert(await page.evaluate(()=>[...document.images].every(i=>i.complete&&i.naturalWidth>0)),'all screenshots must have loaded images');
await page.screenshot({path:`design-review/motion-${name}-${width}-${theme}${reduced?'-reduced':''}.png`,fullPage:true});await page.close();}await context.close();}console.log('PASS 24 final screenshots with decoded images');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
