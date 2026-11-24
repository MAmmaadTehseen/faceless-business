import { NextRequest, NextResponse } from "next/server";
import { unstable_cache } from "next/cache";
import { refreshData, DATA_TAG } from "@/lib/cache";
import { COOKIE_NAME, createSessionToken } from "@/lib/auth";
import { db } from "@/lib/supabase";
import { CHANNELS } from "@/lib/channels";

// Called by sync.yml after each sync: when new metrics exist, clear cached reads and render the
// main pages once, so the owner's first visit is served from cache. Public but harmless: it never
// returns data, and without new metrics it only re-renders already cached pages.
export const maxDuration = 60;

const newestMetric = async () => {
  const { data } = await db().from("metrics").select("captured_at").order("captured_at", { ascending: false }).limit(1);
  return (data?.[0]?.captured_at as string | undefined) ?? "";
};
const cachedNewest = unstable_cache(newestMetric, ["warm-newest-metric"], { tags: [DATA_TAG], revalidate: 6 * 3600 });

export async function GET(req: NextRequest) {
  const [fresh, seen] = await Promise.all([newestMetric(), cachedNewest()]);
  const stale = fresh !== seen;
  if (stale) refreshData();
  const cookie = `${COOKIE_NAME}=${await createSessionToken("owner")}`;
  const origin = req.nextUrl.origin;
  const pages = [
    ...["all", ...CHANNELS.map((c) => c.key)].map((channel) => `/?channel=${channel}&platform=all`),
    ...["/content", "/analytics", "/queue", "/inbox", "/automation"].map((p) => `${p}?channel=all&platform=all`),
  ];
  const started = Date.now();
  // Home for "all" first: it loads the shared content, publications and metrics the rest reuse.
  const results = [await render(origin + pages[0], cookie)];
  results.push(...(await Promise.all(pages.slice(1).map((p) => render(origin + p, cookie)))));
  return NextResponse.json({ revalidated: stale, ms: Date.now() - started, pages: pages.map((p, i) => `${results[i]} ${p}`) }, { headers: { "Cache-Control": "no-store" } });
}

async function render(url: string, cookie: string) {
  try { return (await fetch(url, { headers: { cookie }, cache: "no-store", redirect: "manual" })).status; }
  catch { return 0; }
}
