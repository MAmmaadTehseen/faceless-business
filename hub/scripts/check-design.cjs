const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});const results=[];
 try{for(const theme of ['light','dark']) for(const width of [390,1440]) {
 const context=await browser.newContext({viewport:{width,height:1000},colorScheme:theme,reducedMotion:'reduce'});
 for(const [name,path] of [['home','/'],['channel','/c/futurework'],['article','/a/preview-story-0']]){
 const page=await context.newPage();await page.route('https://www.youtube-nocookie.com/**',route=>route.abort());const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://localhost:3100'+path,{waitUntil:'domcontentloaded'});await page.evaluate(()=>localStorage.removeItem('plainsight-theme'));await page.reload({waitUntil:'domcontentloaded'});await page.evaluate(()=>document.fonts.ready);
 await page.locator('body').evaluate(async()=>{document.querySelectorAll('img').forEach(i=>i.loading='eager');await Promise.race([Promise.all([...document.images].map(i=>i.decode().catch(()=>{}))),new Promise(r=>setTimeout(r,15000))])});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${name}: overflow`);
 assert((await page.locator('.story-card').count())<=12,'card limit');assert.deepEqual(errors,[],'client errors');
 await page.screenshot({path:`design-review/${name}-${width}-${theme}.png`,fullPage:true});
 const metrics=await page.evaluate(()=>{const p=document.querySelector('.article-body');return {background:getComputedStyle(document.documentElement).backgroundColor,bodySize:p&&getComputedStyle(p).fontSize,bodyLine:p&&getComputedStyle(p).lineHeight,measure:p&&p.getBoundingClientRect().width,preloadedFonts:document.querySelectorAll('link[rel=preload][as=font]').length,loadedImages:[...document.images].every(i=>i.complete&&i.naturalWidth>0)}});
 const headers=(await context.request.get('http://localhost:3100'+path)).headers();metrics.preloadedFonts=metrics.preloadedFonts || ((headers.link || '').match(/as="font"/g)||[]).length;assert(metrics.preloadedFonts>0,'preloaded fonts');assert(metrics.loadedImages,'images loaded');await page.waitForTimeout(250);
 if(name==='article'){
 assert.equal(await page.locator('.contents').isVisible(),width>1280);
 await page.locator('details').first().locator('summary').click();assert(await page.locator('details').first().getAttribute('open')!==null);
 const box=page.locator('.video-box');await box.scrollIntoViewIfNeeded();const before=await box.boundingBox();
 await page.evaluate(()=>{window.__embed=false;addEventListener('hub:embed',()=>window.__embed=true)});
 await page.getByRole('button',{name:/Play video/}).click();const after=await box.boundingBox();assert.equal(before.height,after.height);assert(await page.evaluate(()=>window.__embed));assert.equal(await box.locator('iframe').count(),1);
 }
 const old=metrics.background;await page.getByRole('button',{name:/Switch to/}).click();assert.notEqual(await page.evaluate(()=>getComputedStyle(document.documentElement).backgroundColor),old);
 await page.reload({waitUntil:'domcontentloaded'});assert.notEqual(await page.evaluate(()=>getComputedStyle(document.documentElement).backgroundColor),old);
 results.push({page:name,width,theme,...metrics});await page.close();
 }await context.close();}
 fs.writeFileSync('design-review/browser-checks.json',JSON.stringify(results,null,2));console.log('PASS 12 screenshots and browser checks');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
