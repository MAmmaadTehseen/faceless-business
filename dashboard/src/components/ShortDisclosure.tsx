'use client';
import { useEffect, useRef } from 'react';
export function ShortDisclosure({ id, summary, children }: {
    id: string;
    summary: React.ReactNode;
    children: React.ReactNode;
}) {
    const ref = useRef<HTMLDetailsElement>(null);
    useEffect(() => {
        function reveal() {
            if (window.location.hash === `#${id}` && ref.current) {
                ref.current.open = true;
                requestAnimationFrame(() => ref.current?.scrollIntoView({ block: 'start' }));
            }
        }
        reveal();
        window.addEventListener('hashchange', reveal);
        return () => window.removeEventListener('hashchange', reveal);
    }, [id]);
    return <details ref={ref} id={id} className="video-short"><summary>{summary}</summary><div className="short-uploads">{children}</div></details>;
}
