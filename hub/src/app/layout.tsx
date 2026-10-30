import type { Metadata, Viewport } from 'next';
import Link from 'next/link';
import localFont from 'next/font/local';
import { channels } from '@/lib/channels';
import { ThemeToggle } from '@/components/ReadingTools';
const serif = localFont({ src: [{path:'../fonts/SourceSerif4-400.ttf',weight:'400'}, {path:'../fonts/SourceSerif4-500.ttf',weight:'500'}, {path:'../fonts/SourceSerif4-600.ttf',weight:'600'}], variable: '--font-serif', display: 'swap', preload: true });
import './globals.css';
import Tracker from '@/components/Tracker';
import { pageMetadata, siteURL } from '@/lib/seo';
export const metadata: Metadata = {
  ...pageMetadata('Plainsight Media', 'Clear perspectives on work, global power and the frontier of science.', '/'),
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: '16x16 32x32 48x48' },
      { url: '/favicon.svg', type: 'image/svg+xml' },
      { url: '/favicon-48x48.png', sizes: '48x48', type: 'image/png' },
      { url: '/favicon-96x96.png', sizes: '96x96', type: 'image/png' },
      { url: '/icon-192.png', sizes: '192x192', type: 'image/png' },
      { url: '/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
    ],
    shortcut: '/favicon.ico',
    apple: [{ url: '/apple-touch-icon.png', sizes: '180x180', type: 'image/png' }],
    other: [{ rel: 'mask-icon', url: '/safari-pinned-tab.svg', color: '#fbbf24' }],
  },
  manifest: '/site.webmanifest',
  metadataBase: new URL(siteURL),
  title: {default: 'Plainsight Media', template: '%s | Plainsight Media'},
  verification: {google: process.env.GOOGLE_SITE_VERIFICATION},
};
export const viewport: Viewport = { themeColor: '#101112' };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="en" className={serif.variable} suppressHydrationWarning><head><script dangerouslySetInnerHTML={{__html: `try{var t=localStorage.getItem('plainsight-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch{}`}}/></head><body><a className="skip" href="#main">Skip to content</a>
    <header><Link className="brand" href="/" aria-label="Plainsight Media home"><svg className="brand-mark" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12 Q12 1 21 12 M3 12 Q12 23 21 12" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"/><circle cx="12" cy="12" r="3" fill="currentColor"/></svg><span className="brand-wordmark">PLAIN<span>SIGHT</span><small>MEDIA</small></span></Link><nav aria-label="Main"><Link href="/">Stories</Link><Link href="/about">About</Link><ThemeToggle/></nav></header>
    <main id="main">{children}</main><footer><div><Link className="footer-brand" href="/">Plainsight Media</Link><p>A clearer view of what comes next.</p></div><nav aria-label="Our channels">{channels.map(c => <Link key={c.key} href={`/c/${c.key}`}>{c.name}</Link>)}</nav><nav aria-label="Legal"><Link href="/about">About</Link><Link href="/privacy">Privacy</Link><Link href="/feed.xml">RSS</Link></nav></footer>
  <Tracker/></body></html>;
}
