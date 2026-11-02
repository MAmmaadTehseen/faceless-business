import {chromium} from '../../../hub/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import {createHmac} from 'node:crypto';
const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});const results=[];
function assert(name,ok){results.push({name,ok});if(!ok)throw Error(name)}
try{
 const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:3,isMobile:true,hasTouch:true});
 const expiry=Date.now()+3600000,data=`${expiry}.owner`;await context.addCookies([{name:'fb_session',value:`${data}.${createHmac('sha256','qa-placeholder').update(data).digest('hex')}`,url:'http://127.0.0.1:4340'}]);
 await context.addInitScript(()=>{window.__qaCLS=0;new PerformanceObserver(list=>{for(const entry of list.getEntries())if(!entry.hadRecentInput)window.__qaCLS+=entry.value}).observe({type:'layout-shift',buffered:true})});
 const page=await context.newPage();const cdp=await context.newCDPSession(page);
 for(const [app,pages]of Object.entries({dashboard:{home:'/',content:'/content',video:'/content/futurework-2026-10-30-changing-work',inbox:'/inbox',queue:'/queue',costs:'/costs',automation:'/automation',login:'/login'},hub:{home:'/',article:'/a/preview-story-0',channel:'/c/futurework',about:'/about',privacy:'/privacy'}})){
 for(const [name,path]of Object.entries(pages)){
 await page.goto(`http://127.0.0.1:${app==='dashboard'?4340:4341}${path}`);await page.waitForTimeout(700);
 await page.screenshot({path:`${app==='dashboard'?'dashboard/qa':'hub/design-review'}/mobile/final-${name}-390.png`,fullPage:true});
 results.push({app,name,cls:await page.evaluate(()=>window.__qaCLS)});
 const geometry=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,small:[...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,summary')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&(r.width<43.5||r.height<43.5)}).map(e=>e.textContent.trim().slice(0,30))}));assert(`${app} ${name} final geometry`,!geometry.overflow&&!geometry.small.length);
 }
 }
 await page.goto('http://127.0.0.1:4340/');await page.locator('.scope-chip').tap();await page.getByRole('dialog').waitFor();
 await page.keyboard.press('Shift+Tab');assert('scope focus trapped',await page.getByRole('dialog').evaluate(e=>e.contains(document.activeElement)));
 await page.getByRole('radio',{name:'Future Work Explained',exact:true}).tap();await page.waitForURL(url=>url.searchParams.get('channel')==='futurework');const platforms=page.getByRole('dialog').locator('details[open]');await platforms.getByRole('button',{name:'instagram',exact:true}).tap();await page.waitForURL(url=>url.searchParams.get('platform')==='instagram');assert('channel and platform scope applies',page.url().includes('channel=futurework')&&page.url().includes('platform=instagram'));
 const h=await page.locator('.sheet-handle').boundingBox();await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:h.x+100,y:h.y+10}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:h.x+100,y:h.y+90}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});assert('dashboard sheet swipe dismisses',await page.getByRole('dialog').count()===0);
 await page.goto('http://127.0.0.1:4340/queue');await page.getByRole('button',{name:'Topic actions',exact:true}).first().tap();assert('queue overflow opens',await page.getByRole('dialog').isVisible());let bumped=false;await page.route('**/api/queue/*/bump',r=>{bumped=true;return r.fulfill({status:200,contentType:'application/json',body:'{}'})});await page.getByRole('button',{name:'Increase priority +5',exact:true}).tap();await page.waitForTimeout(200);assert('queue bump fixture action',bumped);await page.getByRole('dialog').getByRole('button',{name:'Done',exact:true}).tap();
 await page.goto('http://127.0.0.1:4340/content');await page.locator('.mobile-content-tools>summary').tap();assert('content export tools retained',await page.locator('.mobile-content-tools').getByRole('button',{name:'Download CSV',exact:true}).isVisible());
 await page.goto('http://127.0.0.1:4340/analytics');const chart=page.locator('.report-chart svg').first();await chart.waitFor({state:'visible'});await chart.scrollIntoViewIfNeeded();const box=await chart.boundingBox();await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:box.x+10,y:box.y+100}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:box.x+box.width-10,y:box.y+100}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});assert('touch chart readout',await page.locator('.mobile-chart-readout').first().isVisible());
 await page.goto('http://127.0.0.1:4341/a/preview-story-0');await page.evaluate(()=>window.scrollTo(0,600));await page.waitForTimeout(200);assert('reader header hides downward',await page.locator('body>header').evaluate(e=>e.classList.contains('header-away')));await page.evaluate(()=>window.scrollTo(0,300));await page.waitForTimeout(200);assert('reader header returns upward',await page.locator('body>header').evaluate(e=>!e.classList.contains('header-away')));
}finally{await browser.close();fs.writeFileSync('dashboard/qa/mobile/final-review-results.json',JSON.stringify(results,null,2));console.log(results)}
