import {chromium} from '../../../hub/node_modules/playwright/index.mjs';
import fs from 'node:fs';
const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});const results=[];
try{for(const width of [320,390,768,1440])for(const density of ['comfortable','compact']){
 const c=await browser.newContext({viewport:{width,height:844},deviceScaleFactor:3,isMobile:width<1024,hasTouch:width<1024});
 await c.addInitScript(d=>localStorage.setItem('dashboard-density',d),density);const p=await c.newPage();
 for(const [app,path]of [['dashboard','/content'],['hub','/a/preview-story-0']]){
 await p.goto(`http://127.0.0.1:${app==='dashboard'?4340:4341}${path}`);await p.waitForTimeout(400);
 await p.evaluate(()=>{const long='A very long story title about the changing relationship between work, institutions, technology and the choices that shape ordinary lives across generations';document.querySelectorAll('h1,.mobile-content-copy>strong,.report-title>div>a').forEach(el=>el.textContent=long);const prose=document.querySelector('.article-body');if(prose){const table=document.createElement('table');table.innerHTML='<tbody><tr>'+Array.from({length:8},()=>'<td>VeryLongUnbrokenFixtureValueForTableOverflow</td>').join('')+'</tr></tbody>';prose.append(table);const link=document.createElement('a');link.href='https://example.com';link.textContent='https://example.com/'+ 'long-path-segment'.repeat(15);prose.append(link)}});
 const overflow=await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth);results.push({app,width,density,overflow});if(width===390)await p.screenshot({path:`${app==='dashboard'?'dashboard/qa':'hub/design-review'}/mobile/stress-${density}.png`,fullPage:true});
 }
 await c.close();
}}finally{await browser.close();fs.writeFileSync('dashboard/qa/mobile/stress-results.json',JSON.stringify(results,null,2))}
console.log(results);if(results.some(r=>r.overflow))process.exitCode=1;
