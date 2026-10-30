'use client';
import { useEffect, useState } from 'react';
import { flushSync } from 'react-dom';
import { MotionButton } from './Motion';
import { duration, ease } from '@/lib/motion';
export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const preference = matchMedia('(prefers-color-scheme: dark)');
    const update = () => setDark(document.documentElement.dataset.theme === 'dark' || (!document.documentElement.dataset.theme && preference.matches));
    update(); preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);
  const label = `Switch to ${dark ? 'light' : 'dark'} mode`;
  return <MotionButton className="theme-toggle" aria-label={label} title={label} onClick={(event) => {
    const value = dark ? 'light' : 'dark';
    const apply = () => { document.documentElement.dataset.theme = value; try { localStorage.setItem('plainsight-theme', value); } catch {} flushSync(() => setDark(!dark)); };
    if (!document.startViewTransition || matchMedia('(prefers-reduced-motion: reduce)').matches) { apply(); return; }
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = event.clientX || bounds.left + bounds.width/2, y = event.clientY || bounds.top + bounds.height/2;
    document.documentElement.classList.add('theme-transition');
    const transition = document.startViewTransition(apply);
    void transition.ready.then(() => document.documentElement.animate({clipPath:[`circle(0px at ${x}px ${y}px)`,`circle(${Math.hypot(innerWidth,innerHeight)}px at ${x}px ${y}px)`]}, {duration:duration.opening * 1000,easing:`cubic-bezier(${ease.join(',')})`,pseudoElement:'::view-transition-new(root)'})).catch(()=>{});
    void transition.finished.finally(()=>document.documentElement.classList.remove('theme-transition'));
  }}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><circle className="mode-shape" cx="12" cy="12" r="4" style={{opacity:dark?1:0,transform:dark?'scale(1)':'scale(.5)'}}/><path className="mode-shape" style={{opacity:dark?0:1,transform:dark?'scale(.5)':'scale(1)'}} d="M20 15.2A8.5 8.5 0 0 1 8.8 4 8.5 8.5 0 1 0 20 15.2Z"/><g className="sun-rays" style={{transform:dark?'scale(1)':'scale(0)',opacity:dark?1:0}}><path d="M12 1v3m0 16v3M1 12h3m16 0h3M4.2 4.2l2.1 2.1m11.4 11.4 2.1 2.1M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/></g></svg></MotionButton>;
}
export function ReadingProgress() {
  useEffect(() => {
    const links = [...document.querySelectorAll<HTMLAnchorElement>('.contents a')];
    const sections = [...document.querySelectorAll<HTMLElement>('.article-body h2[id]')];
    const bar = document.querySelector<HTMLElement>('.reading-progress span');
    const native = CSS.supports('animation-timeline: scroll()');
    const observer = new IntersectionObserver(entries => {
      const current = entries.filter(e=>e.isIntersecting).sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top)[0];
      if (!current) return;
      const index = sections.indexOf(current.target as HTMLElement);
      links.forEach(link => { const active = link.hash === `#${current.target.id}`; if(active) link.setAttribute('aria-current','location'); else link.removeAttribute('aria-current'); });
      const indicator = document.querySelector<HTMLElement>('.toc-indicator');
      const active = links.find(l=>l.hash === `#${current.target.id}`);
      if(indicator && active) {indicator.style.transform=`translateY(${active.offsetTop}px) scaleY(${active.offsetHeight})`;}
      if (!native && bar) bar.style.transform=`scaleX(${(index+1)/Math.max(1,sections.length)})`;
    },{rootMargin:'-5% 0px -65% 0px',threshold:0});
    sections.forEach(el=>observer.observe(el));
    return ()=>observer.disconnect();
  },[]);
  return <div className="reading-progress" aria-hidden="true"><span/></div>;
}
