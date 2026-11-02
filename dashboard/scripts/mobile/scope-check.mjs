import {chromium} from '../../../hub/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const browser = await chromium.launch({executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const results=[];
const base='http://localhost:4340';
try {
 for(const width of [390,1280,1440]) {
  const context=await browser.newContext({viewport:{width,height:width===390?844:900}});
  const page=await context.newPage();
  page.on('requestfailed',r=>console.log('REQUEST FAILED',r.url(),r.failure()?.errorText));
  await page.route("**/*", route => ["127.0.0.1", "localhost"].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  for(const density of ['comfortable','compact']) {
   await page.goto(`${base}/?channel=all&platform=instagram`);
   await page.evaluate(d=>{localStorage.setItem('dashboard-density',d);window.dispatchEvent(new Event('dashboard-density-change'));document.documentElement.dataset.density=d},density);
   for(const route of ['/','/content','/inbox','/analytics','/queue','/costs','/automation']) {
    await page.goto(`${base}${route}?channel=all&platform=instagram`);
    await page.waitForTimeout(400);
    assert.equal(await page.locator('h1').count(),1,route);
    const text=await page.locator('main').innerText();
    assert(!text.includes('Application error'),route);
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    assert(!overflow,`${route} overflow at ${width}`);
    const nav=page.locator(width===390?'.mobile-tabs a': 'aside nav a');
    for(const href of await nav.evaluateAll(links=>links.map(a=>a.getAttribute('href')))) {
     assert(href.includes('channel=all')&&href.includes('platform=instagram'),href);
    }
    results.push({width,density,route,hero:await page.locator('.hero-value').first().textContent().catch(()=>null),overflow});
    if(density==='comfortable') await page.screenshot({path:`dashboard/qa/scope/${width}-${route.replaceAll('/','')||'home'}.png`,fullPage:true});
   }
  }
  await page.goto(`${base}/content?channel=all&platform=instagram`);
  const detail=page.locator(width===390?'.mobile-content-row':'.desktop-content-list a[href*="/content/"]').first();
  await detail.click();await page.waitForTimeout(400);
  assert(new URL(page.url()).searchParams.get('platform')==='instagram');
  assert((await page.locator('.hero-label').first().textContent()).includes('instagram'));
  assert(await page.getByText('all uploads are shown below.',{exact:false}).count());
  await page.getByText('← Back to Content').click();
  assert(new URL(page.url()).searchParams.get('platform')==='instagram');
  await page.goto(`${base}/costs`);
  assert(new URL(page.url()).searchParams.get('platform')==='instagram','cookie fallback');
  assert.equal(new URL(page.url()).hostname,'localhost','cookie redirect preserves request host');
  await page.goto(`${base}/costs?channel=tradewinds&platform=facebook`);
  await page.goto(`${base}/queue`);
  assert(new URL(page.url()).searchParams.get('channel')==='tradewinds');
  assert(new URL(page.url()).searchParams.get('platform')==='facebook');
  await page.waitForTimeout(700); // Wait for hydration after a full document navigation.
  await page.getByText('Clear scope ×').click();await page.waitForTimeout(300);
  await page.waitForURL('**/queue?channel=all&platform=all');
  assert(new URL(page.url()).searchParams.get('platform')==='all');
  await page.goto(`${base}/costs`);
  assert(new URL(page.url()).searchParams.get('channel')==='all');
  await context.close();
 }
 const context=await browser.newContext();const page=await context.newPage();
  page.on('requestfailed',r=>console.log('REQUEST FAILED',r.url(),r.failure()?.errorText));
 for(const route of ['/','/content','/inbox','/analytics']) {
  const counts=[];
  for(const channel of ['all','futurework','tradewinds','escapevelocity']) {
   await page.goto(`${base}${route}?channel=${channel}&platform=instagram`);
   counts.push(Number((await page.locator('.hero-value').first().textContent()).replaceAll(',','')));
  }
  assert.equal(counts[0],counts.slice(1).reduce((a,b)=>a+b,0),`${route} sums ${counts}`);
  results.push({route,totals:counts,sumVerified:true});
 }
 for(const tab of ['overview','platforms','channels','formats','categories','engagement','hub']) {
  await page.goto(`${base}/analytics?channel=all&platform=instagram&tab=${tab}`);
  if(tab==='hub') assert(await page.getByText('Hub analytics do not apply to the selected platform.').count());
  else assert(await page.getByText('Watch percentage is available for YouTube only.').count());
 }
 await context.close();
 console.log(JSON.stringify(results,null,2));
} finally {await browser.close();fs.writeFileSync('dashboard/qa/scope/results.json',JSON.stringify(results,null,2));}
