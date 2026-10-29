import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';
export const metadata: Metadata = {
  metadataBase: new URL('https://hub.ammaad.online'),
  title: { default: 'Plainsight Media', template: '%s | Plainsight Media' },
  description: 'Clear perspectives on work, global power and the frontier of science.',
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><a className="skip" href="#main">Skip to content</a>
    <header><Link className="brand" href="/">PLAIN<span>SIGHT</span><small>MEDIA</small></Link><nav aria-label="Main"><Link href="/">Stories</Link><Link href="/about">About</Link></nav></header>
    <main id="main">{children}</main><footer><p>Plainsight Media · A clearer view of what comes next.</p><Link href="/privacy">Privacy</Link></footer>
  </body></html>;
}
