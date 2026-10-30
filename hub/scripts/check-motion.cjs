const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
process.chdir(require('node:path').join(__dirname,'..'));
const phase=process.argv[2]||'after';
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});const results=[];try{
for(const reduced of [false,true])for(const theme of ['light','dark'])for(const width of [390,1440]){
const context=await browser.newContext({viewport:{width,height:1000},colorScheme:theme,reducedMotion:reduced?'reduce':'no-preference'});
await context.addInitScript({content:fs.readFileSync(require.resolve('web-vitals').replace(/web-vitals\.umd\.cjs$/, 'web-vitals.iife.js'),'utf8') + `;window.__vitals={LCP:0,CLS:0,INP:0};for(const key of ['LCP','CLS','INP'])webVitals['on'+key](metric=>window.__vitals[key]=metric.value,{reportAllChanges:true});`});
for(const [name,path]of [['home','/'],['channel','/c/futurework'],['article','/a/preview-story-0']]){
const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('https://www.youtube-nocookie.com/**',r=>r.abort());await page.goto((process.env.MOTION_BASE || 'http://localhost:3137')+path,{waitUntil:'networkidle'});await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(800);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow');if(reduced)assert.equal(await page.evaluate(()=>document.getAnimations().filter(a=>a.playState==='running').length),0,'reduced motion has no running animations');
await page.evaluate(async()=>{for(let y=0;y<document.body.scrollHeight;y+=700){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,30))}window.scrollTo(0,0)});await page.waitForTimeout(700);
if(phase==='after')await page.screenshot({path:`design-review/motion-${name}-${width}-${theme}${reduced?'-reduced':''}.png`,fullPage:true});
await page.getByRole('button',{name:/Switch to/}).click();await page.waitForTimeout(750);if(name==='article'){await page.locator('details summary').first().click();assert(await page.locator('details').first().getAttribute('open')!==null)}
console.log(name,width,theme,reduced);results.push({name,width,theme,reduced,...await page.evaluate(()=>window.__vitals)});assert.deepEqual(errors,[]);await page.close();}await context.close();}
fs.writeFileSync(`design-review/motion-${phase}-vitals.json`,JSON.stringify(results,null,2));console.log('PASS',results.length,'motion scenarios');}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
