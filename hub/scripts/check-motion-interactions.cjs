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
await page.locator('details summary').first().click();await page.waitForTimeout(700);await page.locator('details summary').first().click();await page.waitForTimeout(700);assert.equal(await page.locator('details').first().getAttribute('open'),null,'FAQ close');
const box=page.locator('.video-box');await box.scrollIntoViewIfNeeded();const before=await box.boundingBox();await page.route('https://www.youtube-nocookie.com/**',r=>r.abort());await page.getByRole('button',{name:/Play video/}).click();assert.equal((await box.boundingBox()).height,before.height,'video keeps reserved height');assert.equal(await box.locator('iframe').count(),1);assert.deepEqual(errors,[]);
await page.locator('.article-pagination').evaluate(el=>window.scrollTo({top:el.getBoundingClientRect().top+scrollY-innerHeight/2,behavior:'instant'}));
await page.locator('.back-top.visible').waitFor();await page.waitForTimeout(700);
assert(await page.locator('.reading-progress').evaluate(el=>el.classList.contains('complete')),'progress hands off to completion button');
await page.locator('.back-top').click();await page.waitForFunction(()=>scrollY<2);
console.log('PASS completion capsule and back-to-top navigation');
// Force the unsupported-timeline code path and verify its section observer.
await page.addInitScript(()=>{const native=CSS.supports.bind(CSS);CSS.supports=(...args)=>String(args[0]).includes('animation-timeline')?false:native(...args)});
await page.reload();await page.waitForFunction(()=>document.querySelector('.motion-ready'));await page.locator('#following-the-incentives').evaluate(el=>window.scrollTo({top:el.getBoundingClientRect().top+scrollY-innerHeight*.15,behavior:'instant'}));await page.waitForTimeout(700);assert(await page.locator('.contents a[aria-current]').count()>0);assert(await page.locator('.in-view').count()>0);assert.match(await page.locator('.reading-progress span').getAttribute('style'),/scaleX/,'observer progress fallback');
// Simulate disappearance after the server availability probe. No broken image
// survives even if YouTube and the generated article artwork both fail.
await page.route('https://i.ytimg.com/**',route=>route.fulfill({status:404,body:''}));
await page.route('**/_next/image?*',route=>route.fulfill({status:500,body:''}));
await page.route('**/a/*/opengraph-image*',route=>route.fulfill({status:500,body:''}));
await page.reload({waitUntil:'networkidle'});
await page.waitForFunction(()=>{const img=document.querySelector('.hero-frame img');return img && new URL(img.currentSrc || img.src,location.href).pathname.startsWith('/artwork/')&&img.complete&&img.naturalWidth>0}).catch(async error=>{console.log('Image fallback DOM:',await page.locator('.hero-frame').innerHTML());throw error});
console.log('PASS disappearing remote/OG images recover to branded artwork');
console.log('PASS native router/theme transitions, FAQ, video stability and observer fallback');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
