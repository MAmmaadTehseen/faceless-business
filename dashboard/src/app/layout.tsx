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
  themeColor: "#0f1115",
  viewportFit: "cover",
};
export const dynamic = "force-dynamic";

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (recapEnabled() && (await headers()).get("x-local-recap") === "1") {
    return <html lang="en"><body className="min-h-screen">{children}</body></html>;
  }
  const scope = await getScope();
  const channel = scope.channel;
  const unread = await getPendingComments(channel, 200, scope.platform === "all" ? "" : scope.platform).then(rows=>rows.length).catch(()=>0);
  return (
    <html lang="en">
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
