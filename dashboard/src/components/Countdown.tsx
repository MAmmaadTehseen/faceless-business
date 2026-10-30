"use client";
import { useEffect, useState } from "react";
export function Countdown({at}:{at:string}) {
 const [now,setNow]=useState<number|null>(null);
 useEffect(()=>{setNow(Date.now());const timer=setInterval(()=>setNow(Date.now()),60000);return ()=>clearInterval(timer);},[]);
 if(now===null) return <span>Scheduled</span>;
 const minutes=Math.max(0,Math.ceil((Date.parse(at)-now)/60000));
 return <span>{minutes>=1440 ? `In ${Math.floor(minutes/1440)}d ${Math.floor(minutes%1440/60)}h` : minutes>=60 ? `In ${Math.floor(minutes/60)}h ${minutes%60}m` : `In ${minutes}m`}</span>;
}
