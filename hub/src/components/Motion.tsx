'use client';
import { LazyMotion, MotionConfig } from 'motion/react';
import * as m from 'motion/react-m';
import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { flushSync } from 'react-dom';
import { duration, spring } from '@/lib/motion';

const loadFeatures = () => import('./motion-features').then(module => module.default);

export function MotionRuntime() {
  const path = usePathname();
  const router = useRouter();
  useEffect(() => {
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    let observer: IntersectionObserver | undefined;
    const targets = document.querySelectorAll('.channel-row,.story-card:not(.lead-card),.evidence-box,.video-play');
    if (!reduced.matches) {
      observer = new IntersectionObserver(entries => entries.forEach(entry => {
        if (entry.isIntersecting) { entry.target.classList.add('in-view'); observer?.unobserve(entry.target); }
      }), {threshold:.12});
      targets.forEach(el => { el.classList.add('motion-ready'); observer!.observe(el); });
      try { if (!sessionStorage.getItem('plainsight-eye')) { document.querySelector('.brand-mark')?.classList.add('eye-open'); sessionStorage.setItem('plainsight-eye','1'); } } catch {}
    }
    const navigate = (event: MouseEvent) => {
      const link = (event.target as Element).closest<HTMLAnchorElement>('a[href]');
      if (!link || event.defaultPrevented || event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.target || link.hasAttribute('download')) return;
      const url = new URL(link.href);
      if (url.origin !== location.origin || url.hash || url.pathname === location.pathname || /\.(xml|png)$/.test(url.pathname) || !document.startViewTransition || reduced.matches) return;
      event.preventDefault();
      // Only the chosen card receives names: repeated cards never collide.
      const card = link.closest('.story-card');
      const image = card?.querySelector<HTMLElement>('.card-image');
      const title = card?.querySelector<HTMLElement>('h3');
      if (image) image.style.viewTransitionName = 'story-image';
      if (title) title.style.viewTransitionName = 'story-title';
      const transition = document.startViewTransition(async () => {
        flushSync(() => router.push(url.pathname + url.search));
        // Wait for the streamed server route to commit, without scroll listeners.
        await new Promise<void>(resolve => {
          const watcher = new MutationObserver(() => { if (location.pathname === url.pathname && !document.contains(card)) { watcher.disconnect(); clearTimeout(timeout); resolve(); } });
          const timeout = setTimeout(() => { watcher.disconnect(); resolve(); }, 2500);
          watcher.observe(document.querySelector('main')!, {childList:true,subtree:true});
        });
      });
      void transition.finished.finally(() => { if (image) image.style.viewTransitionName=''; if (title) title.style.viewTransitionName=''; }).catch(()=>{});
    };
    const closeAnswer = (event: MouseEvent) => {
      const summary = (event.target as Element).closest('summary');
      const details = summary?.parentElement as HTMLDetailsElement | null;
      if (!details?.open || reduced.matches) return;
      const answer = details.querySelector('p');
      if (!answer) return;
      event.preventDefault();
      const animation = answer.animate([{opacity:1,transform:'translateY(0)'},{opacity:0,transform:'translateY(-5px)'}],{duration:duration.fast*1000});
      void animation.finished.then(()=>{details.open=false}).catch(()=>{});
    };
    document.addEventListener('click',closeAnswer);
    document.addEventListener('click',navigate,true);
    return () => {observer?.disconnect(); targets.forEach(el=>el.classList.remove('motion-ready')); document.removeEventListener('click',navigate,true); document.removeEventListener('click',closeAnswer);};
  },[path,router]);
  return null;
}

export function MotionButton({children, ...props}: React.ComponentProps<typeof m.button>) {
  return <LazyMotion features={loadFeatures} strict><MotionConfig reducedMotion="user"><m.button {...props} whileTap={{scale:.98}} transition={spring}>{children}</m.button></MotionConfig></LazyMotion>;
}
