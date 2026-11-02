import {chromium} from '../../../hub/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const base='http://localhost:4340';
try {
 const c=await browser.newContext({viewport:{width:390,height:844}});const p=await c.newPage();
 await p.goto(`${base}/?channel=all&platform=all`);
 await p.locator('.scope-chip').click();
 await p.getByRole('radiogroup',{name:'Platform scope'}).getByRole('radio',{name:'Instagram',exact:true}).click();
 await p.waitForURL('**/?channel=all&platform=instagram');
 assert((await p.locator('.scope-chip').textContent()).includes('All channels / Instagram'));
 await p.waitForFunction(()=>document.querySelector('.unread-badge')?.textContent==='9');
 assert.equal(await p.locator('.unread-badge').textContent(),'9');
 await p.getByRole('radiogroup',{name:'Channel filter'}).getByRole('radio',{name:'Trade Winds Report',exact:true}).click();
 await p.waitForURL('**/?channel=tradewinds&platform=instagram');
 await p.waitForFunction(()=>document.querySelector('.unread-badge')?.textContent==='3');
 await p.screenshot({path:'dashboard/qa/scope/mobile-selector.png',fullPage:true});
 await c.close();
 const d=await browser.newContext({viewport:{width:1280,height:900}});const page=await d.newPage();
 await page.goto(`${base}/content?channel=all&platform=all`);
 const group=page.locator('aside').getByRole('radiogroup',{name:'Platform scope'});
 await group.getByRole('radio',{name:'Instagram',exact:true}).click();
 await page.waitForURL('**/content?channel=all&platform=instagram');
 await page.locator('aside nav').getByText('Analytics',{exact:true}).click();
 await page.waitForURL('**/analytics?channel=all&platform=instagram');
 for(const tab of ['platforms','channels','formats','categories','engagement']) {
  await page.goto(`${base}/analytics?channel=all&platform=instagram&tab=${tab}`);
  const event=page.waitForEvent('download');await page.getByRole('button',{name:'Download CSV'}).first().click();
  const dl=await event;const stream=await dl.createReadStream();let csv='';for await(const chunk of stream)csv+=chunk;
  assert(!csv.includes('Watch %'),tab);
  assert(csv.split('\n').length>1,tab);
  if(tab==='platforms') {assert(csv.includes('instagram'));assert(!csv.includes('youtube'));assert(!csv.includes('facebook'));}
  console.log(`${tab}: scoped CSV downloaded; unsupported watch column absent`);
 }
 await d.close();
 console.log('Mobile and desktop scope controls, independence, unread badge and sidebar navigation passed.');
} finally {await browser.close();}
