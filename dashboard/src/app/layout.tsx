import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { Banners } from "@/components/Banners";

export const metadata: Metadata = { title: "Faceless Dashboard" };
export const viewport: Viewport = { width: "device-width", initialScale: 1 };
export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <Nav />
        <main className="mx-auto max-w-5xl px-3 py-4 sm:px-6">
          <Banners />
          {children}
        </main>
      </body>
    </html>
  );
}
