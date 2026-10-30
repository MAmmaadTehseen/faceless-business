// Run against: HUB_PREVIEW_FIXTURES=1 GOOGLE_SITE_VERIFICATION=local-check npm run dev
// node scripts/check-seo.mjs http://localhost:3000 preview-story-0
import assert from 'node:assert/strict';
const base = process.argv[2] || 'http://localhost:3000';
const slug = process.argv[3] || 'preview-story-0';
const paths = ['/', '/c/futurework', `/a/${slug}`, '/about', '/privacy'];
for (const path of paths) {
 const response = await fetch(base+path); assert.equal(response.status,200,path);
 const html = await response.text();
 assert.match(html, /<link[^>]+rel="canonical"[^>]+href="https?:/i, `${path}: canonical`);
 assert.match(html, /name="google-site-verification"/, `${path}: verification`);
 assert.match(html, /property="og:image"/, `${path}: OG image`);
 assert.match(html, /name="twitter:card"/, `${path}: Twitter card`);
 const data = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].flatMap(m => JSON.parse(m[1]));
 if(path.startsWith('/a/')) for(const type of ['Article','FAQPage','BreadcrumbList','VideoObject']) assert(data.some(d=>d['@type']===type),type);
 if(path==='/') assert(data.some(d=>d['@type']==='Organization'));
 assert.match(html, /\/t\.js/, `${path}: analytics`);
 console.log(`PASS ${path}: metadata, canonical, verification, JSON-LD, analytics`);
}
for(const path of ['/sitemap.xml','/robots.txt','/feed.xml','/c/futurework/feed.xml','/opengraph-image',`/a/${slug}/opengraph-image`]) {
 const response=await fetch(base+path);assert.equal(response.status,200,path);
 const body=await response.text();assert(body.length>0,path);console.log(`PASS ${path}`);
}
const feed=await (await fetch(base+'/feed.xml')).text();assert.match(feed,/<rss/);assert.match(feed,new RegExp(slug));
const sitemap=await (await fetch(base+'/sitemap.xml')).text();assert.match(sitemap,new RegExp(slug));
const page2=await (await fetch(base+'/c/futurework?page=2')).text();assert.match(page2.replace(/<!--.*?-->/g,''),/Page 2 of 2/);
console.log('PASS feeds, sitemap article inclusion and archive pagination');
