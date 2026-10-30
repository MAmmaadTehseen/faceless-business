'use client';
import { useAnimate } from 'motion/react-mini';
import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { flushSync } from 'react-dom';
import { duration, ease, editorial } from '@/lib/motion';


export function MotionRuntime() {
  const path = usePathname();
  const router = useRouter();
  useEffect(() => {
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    if (!document.startViewTransition && !reduced.matches) document.querySelector('main')?.animate([{opacity:.85},{opacity:1}],{duration:duration.normal*1000});
    let observer: IntersectionObserver | undefined;
    document.querySelectorAll('.article-body p').forEach(el=>{if(el.getBoundingClientRect().top>innerHeight) el.classList.add('below-fold')});
    document.querySelectorAll<HTMLElement>('.takeaways li').forEach((el,i)=>el.style.setProperty('--tick',String(i)));
    document.querySelectorAll('.story-card:not(.lead-card)').forEach(el=>{if(el.getBoundingClientRect().top>innerHeight)el.classList.add('below-fold-card')});
    const targets = document.querySelectorAll('.channel-row,.story-card:not(.lead-card),.evidence-box,.video-play,.below-fold,.takeaways,blockquote');
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
      if (url.origin !== location.origin || url.hash || url.pathname === location.pathname || /\.(xml|png)$/.test(url.pathname) || reduced.matches) return;
      if (!document.startViewTransition) {
        const main=document.querySelector('main');
        main?.animate([{opacity:1},{opacity:.85}],{duration:duration.fast*1000});
        return;
      }
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
    // Height is deliberately animated only after an explicit FAQ interaction.
    const faqAnimations = new Map<HTMLDetailsElement, Animation>();
    const closeAnswer = (event: MouseEvent) => {
      const summary = (event.target as Element).closest('summary');
      const details = summary?.parentElement as HTMLDetailsElement | null;
      if (!details || reduced.matches) return;
      event.preventDefault();
      const old = faqAnimations.get(details);
      const from = details.getBoundingClientRect().height;
      old?.cancel();
      const opening = !details.open || details.dataset.closing === 'true';
      details.dataset.closing = String(!opening);
      details.open = true;
      const to = opening ? details.scrollHeight : summary!.getBoundingClientRect().height + 40;
      details.style.overflow='clip';
      const animation = details.animate([{height:`${from}px`},{height:`${to + (to-from)*.025}px`,offset:.8},{height:`${to}px`}],{duration:editorial.faqMaxMs,easing:'cubic-bezier(.22,1,.36,1)'});
      faqAnimations.set(details,animation);
      void animation.finished.then(()=>{details.open=opening;details.style.overflow='';delete details.dataset.closing;faqAnimations.delete(details)}).catch(()=>{});
    };
    let frame=0;
    const fine = matchMedia('(pointer:fine) and (hover:hover)');
    const dot=document.createElement('span'); dot.className='cursor-dot';dot.setAttribute('aria-hidden','true');document.body.append(dot);
    const reset = () => {document.querySelectorAll<HTMLElement>('[data-pointer-motion]').forEach(el=>{el.style.removeProperty('--tilt-x');el.style.removeProperty('--tilt-y');el.style.removeProperty('translate');delete el.dataset.pointerMotion});};
    const pointer = (event: PointerEvent) => {
      if(reduced.matches || !fine.matches || event.pointerType==='touch') return;
      cancelAnimationFrame(frame);
      frame=requestAnimationFrame(()=>{
        reset();
        const target=event.target as Element;
        dot.classList.add('active');dot.classList.toggle('over-link',!!target.closest('a,button,.story-card'));
        dot.style.transform=`translate3d(${event.clientX}px,${event.clientY}px,0)`;
        const card=target.closest<HTMLElement>('.story-card');
        const magnetic=target.closest<HTMLElement>('header .brand,.masthead a,.channel-header .socials a');
        const el=card||magnetic;
        if(!el)return;
        const bounds=el.getBoundingClientRect(), x=(event.clientX-bounds.left)/bounds.width-.5,y=(event.clientY-bounds.top)/bounds.height-.5;
        el.dataset.pointerMotion='true';
        const radius=Math.max(1,Math.hypot(x*2,y*2));
        if(card){el.style.setProperty('--tilt-x',`${-y*editorial.tilt*2/radius}deg`);el.style.setProperty('--tilt-y',`${x*editorial.tilt*2/radius}deg`)}
        else el.style.translate=`${x*editorial.magnetic*2/radius}px ${y*editorial.magnetic*2/radius}px`;
      });
    };
    const leave=()=>{cancelAnimationFrame(frame);reset();dot.classList.remove('active')};
    const preference=()=>{if(reduced.matches){leave();document.getAnimations().forEach(a=>a.cancel());targets.forEach(el=>el.classList.remove('motion-ready'))}};
    reduced.addEventListener('change',preference);
    document.addEventListener('pointermove',pointer,{passive:true});document.addEventListener('pointerleave',leave);
    document.addEventListener('click',closeAnswer);
    document.addEventListener('click',navigate,true);
    return () => {cancelAnimationFrame(frame);reset();dot.remove();faqAnimations.forEach(a=>a.cancel());reduced.removeEventListener('change',preference);document.removeEventListener('pointermove',pointer);document.removeEventListener('pointerleave',leave);observer?.disconnect(); targets.forEach(el=>el.classList.remove('motion-ready')); document.removeEventListener('click',navigate,true); document.removeEventListener('click',closeAnswer);};
  },[path,router]);
  return null;
}

export function MotionButton({children, ...props}: React.ComponentProps<'button'>) {
  const [scope,animate] = useAnimate<HTMLButtonElement>();
  const press = (scale:number) => {
    if (!scope.current || matchMedia('(prefers-reduced-motion:reduce)').matches) return;
    animate(scope.current,{transform:`scale(${scale})`},{duration:duration.fast,ease:[...ease]});
  };
  return <button {...props} ref={scope}
    onPointerDown={event=>{props.onPointerDown?.(event);press(.98)}}
    onPointerUp={event=>{props.onPointerUp?.(event);press(1)}}
    onPointerLeave={event=>{props.onPointerLeave?.(event);press(1)}}
    onPointerCancel={event=>{props.onPointerCancel?.(event);press(1)}}>{children}</button>;
}
