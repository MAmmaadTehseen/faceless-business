'use client';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
export function MobileHeader() {
 useEffect(()=>{let last=window.scrollY;const header=document.querySelector<HTMLElement>('body>header');const scroll=()=>{const y=window.scrollY;header?.classList.toggle('header-away',y>last && y>80);last=y;};window.addEventListener('scroll',scroll,{passive:true});return()=>window.removeEventListener('scroll',scroll);},[]);
 return null;
}
export function MobileReading({ headings, next }: { headings: {id:string;text:string}[]; next?: {slug:string;title:string} }) {
 const [open,setOpen]=useState(false),[nearEnd,setNearEnd]=useState(false),[shared,setShared]=useState(false);
 const sheet=useRef<HTMLElement>(null),start=useRef(0);
 useEffect(()=>{const end=document.querySelector('.article-pagination');if(!end)return;const observer=new IntersectionObserver(entries=>setNearEnd(entries.some(e=>e.isIntersecting||e.boundingClientRect.top<0)),{rootMargin:'0px 0px 180px'});observer.observe(end);return()=>observer.disconnect();},[]);
 useEffect(()=>{if(!open)return;const previous=document.activeElement as HTMLElement;const overflow=document.body.style.overflow;document.body.style.overflow='hidden';sheet.current?.querySelector('button')?.focus();const key=(e:KeyboardEvent)=>{if(e.key==='Escape')setOpen(false);if(e.key==='Tab'){const items=[...(sheet.current?.querySelectorAll<HTMLElement>('button,a')??[])];if(e.shiftKey&&document.activeElement===items[0]){e.preventDefault();items.at(-1)?.focus()}if(!e.shiftKey&&document.activeElement===items.at(-1)){e.preventDefault();items[0]?.focus()}}};document.addEventListener('keydown',key);return()=>{document.body.style.overflow=overflow;document.removeEventListener('keydown',key);previous?.focus()};},[open]);
 const links=headings.map(h=><a key={h.id} href={`#${h.id}`} onClick={()=>setOpen(false)}>{h.text}</a>);
 async function share(){try{if(navigator.share)await navigator.share({title:document.title,url:location.href});else {await navigator.clipboard.writeText(location.href);setShared(true)}}catch{}}
 return <><details className="mobile-contents"><summary>In this article</summary><nav>{links}</nav></details><button className={`floating-contents ${nearEnd?'end':''}`} onClick={()=>setOpen(true)} aria-haspopup="dialog">In this article ☰</button>{nearEnd&&<div className="reading-bottom-bar"><button onClick={share}>{shared?'Link copied':'Share ↗'}</button>{next&&<a href={`/a/${next.slug}`} aria-label={`Next story: ${next.title}`}>Next story →</a>}</div>}{open&&createPortal(<div className="toc-backdrop" onClick={()=>setOpen(false)}><section ref={sheet} role="dialog" aria-modal="true" aria-label="In this article" className="toc-sheet" onClick={e=>e.stopPropagation()}><div className="toc-handle" onTouchStart={e=>{start.current=e.touches[0].clientY}} onTouchEnd={e=>{if(e.changedTouches[0].clientY-start.current>60)setOpen(false)}}><span/></div><div className="toc-sheet-heading"><h2>In this article</h2><button onClick={()=>setOpen(false)}>Done</button></div><nav>{links}</nav></section></div>,document.body)}</>;
}
