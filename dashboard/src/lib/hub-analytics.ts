import 'server-only';
import {db} from './supabase';
import {ChannelFilter} from './channels';
export type HubAnalytics = {
 total:{views:number;uniques:number;sessions:number;youtube:number};seconds:number;scroll:number;bounce:number;
 articles:{slug:string;views:number;uniques:number;seconds:number;embeds:number;youtube:number}[];
 channels:{channel:string;views:number;youtube:number}[];
 daily:{date:string;views:number}[];
 dimensions:{kind:string;name:string;value:number}[];
};
export async function getHubAnalytics(channel:ChannelFilter,days=28,all=false):Promise<HubAnalytics|null>{
 if(!process.env.SUPABASE_URL||!process.env.SUPABASE_SERVICE_KEY)return null;
 const until=new Date();
 // All time still has explicit bounds, starting before this site's launch.
 const since=all?'2026-01-01T00:00:00Z':new Date(until.getTime()-days*86400000).toISOString();
 try{
 const {data,error}=await db().rpc('hub_analytics',{since,until_ts:until.toISOString(),channel_key:channel==='all'?null:channel});
 if(error||!data)return null;
 const a=data as HubAnalytics;
 const counts=new Map(a.daily.map(d=>[d.date,d.views]));
 a.daily=[];
 for(let t=Date.parse(since.slice(0,10)+'T00:00:00Z');t<until.getTime();t+=86400000){const date=new Date(t).toISOString().slice(0,10);a.daily.push({date,views:counts.get(date)||0});}
 return a;
 }catch{return null;}
}
