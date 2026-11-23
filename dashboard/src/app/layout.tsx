import { headers } from "next/headers";
import { recapEnabled } from "@/lib/recap-local";
import { getScope } from "@/lib/server-scope";
import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Pwa } from "@/components/Pwa";
import { ToastHost } from "@/components/Toast";
import { Shell } from "@/components/Nav";
import { Banners } from "@/components/Banners";
import { getPendingComments } from "@/lib/data";
import { getChannelFilter } from "@/lib/channel-filter";

// Fonts load from Google at runtime: build-time next/font fetching failed on Vercel.
const FONTS = "https://fonts.googleapis.com/css2?family=Big+Shoulders:wght@600;800&family=JetBrains+Mono:wght@400;600&family=Schibsted+Grotesk:wght@400;500;600;700&display=swap";
const fontLinks = <><link rel="preconnect" href="https://fonts.googleapis.com" /><link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" /><link rel="stylesheet" href={FONTS} /></>;
// Runs before paint so a saved light/dark choice never flashes the other theme.
const themeInit = `try{var t=localStorage.getItem("dashboard-theme");if(t)document.documentElement.dataset.theme=t}catch(e){}`;

export const metadata: Metadata = {
  title: "Faceless Dashboard",
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: '16x16 32x32 48x48' },
      { url: '/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
    ],
    shortcut: '/favicon.ico',
    apple: [{ url: '/icons/apple-touch-icon.png', sizes: '180x180', type: 'image/png' }],
    other: [{ rel: 'mask-icon', url: '/safari-pinned-tab.svg', color: '#2563eb' }],
  },
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Faceless" },
  manifest: '/manifest.json',
};
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#eceeea" }, { media: "(prefers-color-scheme: dark)", color: "#14181a" }],
  viewportFit: "cover",
};
export const dynamic = "force-dynamic";

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (recapEnabled() && (await headers()).get("x-local-recap") === "1") {
    return <html lang="en"><head>{fontLinks}</head><body className="min-h-screen">{children}</body></html>;
  }
  const scope = await getScope();
  const channel = scope.channel;
  const unread = await getPendingComments(channel, 200, scope.platform === "all" ? "" : scope.platform).then(rows=>rows.length).catch(()=>0);
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeInit }} />{fontLinks}</head>
      <body className="min-h-screen">
        <ToastHost />
        <Pwa />
        <Shell unread={unread} channel={channel} banners={<Banners />}>
          {children}
        </Shell>
      </body>
    </html>
  );
}
