import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';
import Tracker from '@/components/Tracker';
import { pageMetadata, siteURL } from '@/lib/seo';
export const metadata: Metadata = {
  ...pageMetadata('Plainsight Media', 'Clear perspectives on work, global power and the frontier of science.', '/'),
  metadataBase: new URL(siteURL),
  title: {default: 'Plainsight Media', template: '%s | Plainsight Media'},
  verification: {google: process.env.GOOGLE_SITE_VERIFICATION},
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><a className="skip" href="#main">Skip to content</a>
    <header><Link className="brand" href="/">PLAIN<span>SIGHT</span><small>MEDIA</small></Link><nav aria-label="Main"><Link href="/">Stories</Link><Link href="/about">About</Link></nav></header>
    <main id="main">{children}</main><footer><p>Plainsight Media · A clearer view of what comes next.</p><Link href="/privacy">Privacy</Link></footer>
  <Tracker/></body></html>;
}
