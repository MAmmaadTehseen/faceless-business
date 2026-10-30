const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});try{
const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(process.env.MOTION_BASE||'http://localhost:3137');await page.waitForTimeout(1000);
await page.locator('.lead-card').hover();await page.waitForTimeout(700);assert.equal(await page.locator('.lead-card').evaluate(el=>Math.round(new DOMMatrix(getComputedStyle(el).transform).m42)),-2,'card lifts two pixels');
await page.reload();await page.waitForTimeout(1000);assert.equal(await page.locator('.eye-open').count(),0,'eye opens only once per session');
await page.evaluate(()=>{window.__transitions=0;const native=document.startViewTransition.bind(document);document.startViewTransition=(...args)=>{window.__transitions++;return native(...args)}});
await page.locator('.lead-card h3 a').click();await page.waitForURL('**/a/preview-story-0');await page.locator('.article-header h1').waitFor();await page.waitForTimeout(3000);assert.equal(await page.evaluate(()=>window.__transitions),1,'native router transition');
await page.getByRole('button',{name:/Switch to/}).click();await page.waitForTimeout(750);assert.equal(await page.evaluate(()=>window.__transitions),2,'native theme transition');
await page.locator('details summary').first().click();await page.waitForTimeout(400);await page.locator('details summary').first().click();await page.waitForTimeout(400);assert.equal(await page.locator('details').first().getAttribute('open'),null,'FAQ close');
const box=page.locator('.video-box');await box.scrollIntoViewIfNeeded();const before=await box.boundingBox();await page.route('https://www.youtube-nocookie.com/**',r=>r.abort());await page.getByRole('button',{name:/Play video/}).click();assert.equal((await box.boundingBox()).height,before.height,'video keeps reserved height');assert.equal(await box.locator('iframe').count(),1);assert.deepEqual(errors,[]);
// Force the unsupported-timeline code path and verify its section observer.
await page.addInitScript(()=>{const native=CSS.supports.bind(CSS);CSS.supports=(...args)=>String(args[0]).includes('animation-timeline')?false:native(...args)});
await page.reload();await page.waitForFunction(()=>document.querySelector('.motion-ready'));await page.locator('#following-the-incentives').evaluate(el=>window.scrollTo({top:el.getBoundingClientRect().top+scrollY-innerHeight*.15,behavior:'instant'}));await page.waitForTimeout(700);assert(await page.locator('.contents a[aria-current]').count()>0);assert(await page.locator('.in-view').count()>0);assert.match(await page.locator('.reading-progress span').getAttribute('style'),/scaleX/,'observer progress fallback');
console.log('PASS native router/theme transitions, FAQ, video stability and observer fallback');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
