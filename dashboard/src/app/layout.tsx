import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Shell } from "@/components/Nav";
import { Banners } from "@/components/Banners";
import { getChannelFilter } from "@/lib/channel-filter";

export const metadata: Metadata = { title: "Faceless Dashboard" };
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0b1428" };
export const dynamic = "force-dynamic";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const channel = await getChannelFilter();
  return (
    <html lang="en">
      <body className="min-h-screen">
        <Shell channel={channel} banners={<Banners />}>
          {children}
        </Shell>
      </body>
    </html>
  );
}
