"use client";
import { useState } from 'react';
import Image from 'next/image';
export default function Video({id, title}: {id:string; title:string}) {
  const [active, setActive] = useState(false);
  const src = `https://www.youtube-nocookie.com/embed/${id}`;
  return <section aria-label="Video"><h2>Watch the video</h2><div className="video-box">{active ? <iframe src={`${src}?autoplay=1`} title={`Watch: ${title}`} allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowFullScreen referrerPolicy="strict-origin-when-cross-origin"/> : <button className="video-play" aria-label={`Play video: ${title}`} onClick={() => {window.dispatchEvent(new CustomEvent('hub:embed', {detail:{href:src}})); setActive(true);}}><Image src={`https://i.ytimg.com/vi/${id}/hqdefault.jpg`} alt="" fill sizes="(max-width: 800px) 100vw, 780px"/><span aria-hidden="true">▶</span></button>}</div></section>;
}
