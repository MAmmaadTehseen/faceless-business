import { createHash } from 'node:crypto';
import { createClient } from '@supabase/supabase-js';
export const runtime = 'nodejs';
const limits = new Map<string, {minute:number; count:number}>();
const channels = ['futurework','tradewinds','escapevelocity'];
const targets = ['youtube_embed','youtube_channel','instagram','facebook','article','external'];
const empty = () => new Response(null, {status:204});
const text = (v:unknown, n=200) => typeof v === 'string' ? v.slice(0,n) : null;
export async function POST(req:Request) {
  try {
    if (req.headers.get('dnt') === '1' || req.headers.get('sec-gpc') === '1') return empty();
    const origin=req.headers.get('origin');
    if (origin && origin !== new URL(req.url).origin) return empty();
    const ua=req.headers.get('user-agent') || '';
    if (/bot|crawler|spider|slurp|headless|preview|facebookexternalhit/i.test(ua)) return empty();
    const body=await req.text();
    if (body.length>4096) return empty();
    const b=JSON.parse(body);
    if (!['pageview','heartbeat','click','scroll'].includes(b.event)) return empty();
    if (typeof b.path !== 'string' || !b.path.startsWith('/') || b.path.length>500 || /[?#]/.test(b.path)) return empty();
    if (typeof b.session !== 'string' || !/^[\w-]{1,64}$/.test(b.session)) return empty();
    const ip=(req.headers.get('x-forwarded-for') || '').split(',')[0].trim();
    const visitor=createHash('sha256').update(JSON.stringify([process.env.HUB_HASH_SALT || 'plainsight-cookie-free-v1',new Date().toISOString().slice(0,10),ip,ua])).digest('hex').slice(0,16);
    const minute=Math.floor(Date.now()/60000);
    if(limits.size>10000) for(const [k,v] of limits) if(v.minute!==minute) limits.delete(k);
    if(limits.size>=10000 && !limits.has(visitor)) return empty();
    const limit=limits.get(visitor);
    if(limit?.minute===minute && limit.count>=120) return empty();
    if(!limit || limit.minute!==minute) limits.set(visitor,{minute,count:1}); else limit.count++;
    const url=process.env.SUPABASE_URL,key=process.env.SUPABASE_SERVICE_KEY;
    if(!url || !key) return empty();
    const host=(v:unknown)=>{try{return new URL('https://'+String(v)).hostname.slice(0,253)}catch{return null}};
    let href=null;
    try{const u=new URL(b.href);if(['https:','http:'].includes(u.protocol))href=(u.origin+u.pathname).slice(0,1000)}catch{}
    const integer=(v:unknown,max:number)=>typeof v==='number'&&Number.isFinite(v)?Math.max(0,Math.min(max,Math.floor(v))):null;
    const client=createClient(url,key,{auth:{persistSession:false,autoRefreshToken:false}});
    await client.from('hub_events').insert({event:b.event,path:b.path,slug:text(b.slug),channel:channels.includes(b.channel)?b.channel:null,
      session:b.session,visitor,referrer_host:b.referrer_host?host(b.referrer_host):null,
      utm_source:text(b.utm_source,100),utm_medium:text(b.utm_medium,100),utm_campaign:text(b.utm_campaign,100),
      country:/^[A-Z]{2}$/.test(req.headers.get('x-vercel-ip-country')||'')?req.headers.get('x-vercel-ip-country'):null,
      device:/ipad|tablet|android(?!.*mobile)/i.test(ua)?'tablet':/mobile|iphone|ipod/i.test(ua)?'mobile':'desktop',
      browser:/edg\//i.test(ua)?'Edge':/opr\//i.test(ua)?'Opera':/firefox|fxios/i.test(ua)?'Firefox':/chrome|crios/i.test(ua)?'Chrome':/safari/i.test(ua)?'Safari':'Other',
      seconds:b.event==='heartbeat'?integer(b.seconds,86400):null,percent:b.event==='scroll'?integer(b.percent,100):null,
      target:b.event==='click'&&targets.includes(b.target)?b.target:null,href:b.event==='click'?href:null});
  } catch { /* Analytics must never interrupt a visit or expose request data. */ }
  return empty();
}
