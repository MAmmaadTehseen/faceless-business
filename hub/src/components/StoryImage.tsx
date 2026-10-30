'use client';
import Image from 'next/image';
import { useEffect, useRef, useState } from 'react';
// Reserve geometry before hydration. If an asset disappears after the server probe,
// advance monotonically through the remaining sources; the final local artwork is stable.
export default function StoryImage({sources, alt='', priority=false}: {sources:string[];alt?:string;priority?:boolean}) {
  const [index,setIndex] = useState(0);
  const ref = useRef<HTMLImageElement>(null);
  // An SSR image can fail before React attaches its event handler.
  useEffect(()=>{
    if(ref.current?.complete && !ref.current.naturalWidth) setIndex(i=>Math.min(i+1,sources.length-1));
  },[index,sources]);
  return <Image ref={ref} data-artwork={/^\/(a|artwork)\//.test(sources[index]) ? 'true' : undefined} data-image-source={index} src={sources[index]} alt={alt} width={1200} height={675} sizes="(max-width:700px) 100vw, (max-width:1200px) 66vw, 760px" priority={priority} onError={() => setIndex(i=>Math.min(i+1,sources.length-1))}/>;
}
