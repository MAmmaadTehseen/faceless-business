'use client';
import { useEffect, useState } from 'react';
export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => { setDark(document.documentElement.dataset.theme === 'dark' || (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches)); }, []);
  return <button className="theme-toggle" aria-label={`Switch to ${dark ? 'light' : 'dark'} mode`} onClick={() => { const value = dark ? 'light' : 'dark'; document.documentElement.dataset.theme = value; try { localStorage.setItem('plainsight-theme', value); } catch {} setDark(!dark); }}>{dark ? 'Light' : 'Dark'} <span aria-hidden="true">◐</span></button>;
}
export function ReadingProgress() {
  const [progress, setProgress] = useState(0);
  useEffect(() => { const update = () => { const article = document.querySelector('.article-body'); if (!article) return; const bounds = article.getBoundingClientRect(); setProgress(Math.max(0, Math.min(1, -bounds.top / Math.max(1, bounds.height - innerHeight)))); }; update(); addEventListener('scroll', update, {passive:true}); addEventListener('resize', update); return () => { removeEventListener('scroll', update); removeEventListener('resize', update); }; }, []);
  return <div className="reading-progress" aria-hidden="true"><span style={{transform:`scaleX(${progress})`}}/></div>;
}
