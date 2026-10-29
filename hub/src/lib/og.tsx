import { ImageResponse } from 'next/og';
export function ogImage(title: string, channel = 'Work / Power / Possibility', color = '#fbbf24') {
  return new ImageResponse(<div style={{display:'flex', flexDirection:'column', justifyContent:'space-between', width:'100%', height:'100%', background:'#101112', color:'#f1f0eb', padding:72, borderTop:`16px solid ${color}`}}><div style={{display:"flex", fontSize:28, color}}>PLAINSIGHT MEDIA · {channel}</div><div style={{fontSize: title.length > 90 ? 48 : 64, lineHeight:1.12, fontWeight:700}}>{title}</div><div style={{fontSize:24, color:'#bfc1bc'}}>A clearer view of what comes next.</div></div>, {width:1200,height:630});
}
