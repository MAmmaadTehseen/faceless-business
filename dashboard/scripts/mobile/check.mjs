import {chromium} from '../../../hub/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import {createHmac} from 'node:crypto';
const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const results=[];const errors=[];
const routes={dashboard:{home:'/',content:'/content',video:'/content/futurework-2026-10-30-changing-work',inbox:'/inbox',analytics:'/analytics',...Object.fromEntries(['platforms','channels','formats','categories','engagement','hub'].map(t=>['analytics-'+t,'/analytics?tab='+t])),contentEmpty:'/content?q=unmatchable-fixture-query',queue:'/queue',costs:'/costs',automation:'/automation',login:'/login',empty:'/content/empty-video'},hub:{home:'/',channel:'/c/futurework',article:'/a/preview-story-0',about:'/about',privacy:'/privacy'}};
try{
for(const [width,height] of [[320,844],[360,844],[390,844],[430,844],[768,1024],[844,390],[1440,900]]){
 const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:3,isMobile:width<1024,hasTouch:width<1024});
 const expiry=Date.now()+3600000,data=`${expiry}.owner`,token=`${data}.${createHmac('sha256','qa-placeholder').update(data).digest('hex')}`;
 await context.addCookies([{name:'fb_session',value:token,url:'http://127.0.0.1:4340'}]);
 await context.addInitScript(()=>{localStorage.setItem('faceless-install-dismissed','1');window.__qaCLS=0;new PerformanceObserver(list=>{for(const entry of list.getEntries())if(!entry.hadRecentInput)window.__qaCLS+=entry.value}).observe({type:'layout-shift',buffered:true})});
 const page=await context.newPage();
 for(const [app,pages] of Object.entries(routes))for(const theme of app==='hub'?['light','dark']:['dark'])for(const [name,path] of Object.entries(pages)){
 await page.emulateMedia({colorScheme:theme});
 await page.goto(`http://127.0.0.1:${app==='dashboard'?4340:4341}${path}`,{waitUntil:'networkidle'});await page.waitForTimeout(200);
 const checks=await page.evaluate(()=>{
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&!e.closest('[hidden]')};
 const smallTargets=[...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button]')].filter(visible).filter(e=>{const r=e.getBoundingClientRect();return r.height<43.5||r.width<43.5}).map(e=>({text:(e.getAttribute('aria-label')||e.textContent||e.tagName).trim().slice(0,60),w:Math.round(e.getBoundingClientRect().width),h:Math.round(e.getBoundingClientRect().height)}));
 const smallText=[...document.querySelectorAll('body *')].filter(visible).filter(e=>[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())&&parseFloat(getComputedStyle(e).fontSize)<12).map(e=>({text:e.textContent.slice(0,50),size:getComputedStyle(e).fontSize}));
 return {cls:window.__qaCLS??null,overflow:document.documentElement.scrollWidth>innerWidth,smallTargets,smallText,error:document.body.innerText.includes('Application error')||document.title.includes('404')};});
 results.push({app,name,theme,width,height,...checks});fs.writeFileSync('dashboard/qa/mobile/check-progress.json',JSON.stringify(results,null,2));
 if(width===390 || width===1440)await page.screenshot({path:`${app==='dashboard'?'dashboard/qa':'hub/design-review'}/mobile/after-${name}-${width}-${theme}.png`,fullPage:true});
 if(checks.overflow||checks.error||(width<1024&&(checks.smallTargets.length||checks.smallText.length)))errors.push(results.at(-1));
 }
 await context.close();console.log('checked',width,height);
}
}finally{await browser.close();fs.writeFileSync('dashboard/qa/mobile/check-results.json',JSON.stringify({results,errors},null,2));}
console.log('Failures:',errors.length);if(errors.length)process.exitCode=1;
