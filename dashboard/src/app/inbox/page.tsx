import { AutoFilters } from "@/components/AutoFilters";
import { CHANNELS, parseChannelFilter } from "@/lib/channels";
import { FilterSheet } from "@/components/FilterSheet";
import { ReplaceLink as Link } from "@/components/ReplaceLink";
import { db } from "@/lib/supabase";
import { isOwner } from "@/lib/role";
import { Comment } from "@/lib/types";
import { InboxItem } from "@/components/InboxItem";
import { getChannelFilter } from "@/lib/channel-filter";
import { PageHeader } from "@/components/PageHeader";

const PLATFORMS = ["youtube", "instagram", "facebook"];

export default async function InboxPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const sp = await searchParams;
  const { platform = "", tab = "pending", days = "all" } = sp;
  const channel = parseChannelFilter(sp.channel);
  // Channel lives on content, two joins away; over-fetch when filtering and trim in code.
  let q = db()
    .from("comments")
    .select("*")
    .order("posted_at", { ascending: false, nullsFirst: false })
    .limit(channel === "all" ? 200 : 600);
  if (tab === "pending") q = q.in("reply_status", ["new", "drafted"]);
  if (tab === "replied") q = q.eq("reply_status", "sent");
  if (tab === "flagged") q = q.eq("flagged", true);
  if ([1, 7, 30].includes(Number(days))) q = q.gte("posted_at", new Date(Date.now() - Number(days) * 86400000).toISOString());
  const owner = await isOwner();
  const urls = new Map<number, string>();
  if (platform) q = q.eq("platform", platform);
  const { data, error } = await q;
  if (error) return <p className="text-alert-fg">DB error: {error.message}</p>;
  let comments = (data ?? []) as Comment[];

  // Resolve video titles and channels: publication -> content.
  const pubIds = [
    ...new Set(
      comments
        .map((c) => c.publication_id)
        .filter((x): x is number => x != null),
    ),
  ];
  const titles = new Map<number, string>();
  const channels = new Map<number, string | null>();
  if (pubIds.length) {
    const { data: pubs } = await db()
      .from("publications")
      .select("id,content_id,url,platform,platform_id,content(title,channel)")
      .in("id", pubIds);
    type C = { title: string; channel: string | null };
    for (const p of pubs ?? []) {
      const content = p.content as unknown as C | C[] | null;
      const row = Array.isArray(content) ? content[0] : content;
      const url =
        p.platform === "youtube" && p.platform_id
          ? `https://www.youtube.com/watch?v=${encodeURIComponent(p.platform_id)}`
          : p.url;
      if (url) urls.set(p.id, url);
      titles.set(p.id, row?.title ?? p.content_id);
      channels.set(p.id, row?.channel ?? null);
    }
  }
  if (channel !== "all") {
    comments = comments
      .filter(
        (c) =>
          c.publication_id != null &&
          channels.get(c.publication_id) === channel,
      )
      .slice(0, 200);
  }

  if (sp.q?.trim()) comments = comments.filter(c => `${c.author ?? ""} ${c.text} ${titles.get(c.publication_id ?? 0) ?? ""}`.toLowerCase().includes(sp.q.trim().toLowerCase()));
  return (
    <div>
      <PageHeader
        title="Inbox"
        count={comments.length}
        action={
          <div className="flex flex-wrap gap-2">
            {["pending", "replied", "flagged", "all"].map((t) => (
              <Link
                className={`btn ${tab === t ? "btn-primary" : ""}`}
                key={t}
                scroll={false}
                href={`?${new URLSearchParams({ ...sp, tab: t })}`}
              >
                {t[0].toUpperCase() + t.slice(1)}
              </Link>
            ))}
          </div>
        }
      />
      <FilterSheet count={[platform, sp.q, days !== "all", channel !== "all"].filter(Boolean).length}><AutoFilters key={JSON.stringify({ ...sp, q: undefined })} className="filter-bar mb-4">
        <select name="channel" aria-label="Channel" defaultValue={channel}><option value="all">All channels</option>{CHANNELS.map(c => <option key={c.key} value={c.key}>{c.short}</option>)}</select>
        <input name="q" aria-label="Search comments" placeholder="Search comments…" defaultValue={sp.q ?? ""} />
        <select name="platform" aria-label="Platform" defaultValue={platform}><option value="">All platforms</option>{PLATFORMS.map(p => <option key={p}>{p}</option>)}</select>
        <select name="days" aria-label="Date range" defaultValue={days}>{[["1", "Last 24 hours"], ["7", "7 days"], ["30", "30 days"], ["all", "All time"]].map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select>
        <span className="badge">{[platform, sp.q, days !== "all", channel !== "all"].filter(Boolean).length} active</span><Link className="badge" scroll={false} href={`/inbox?channel=all&tab=${tab}`}>Clear</Link>
      </AutoFilters></FilterSheet>
      {comments.length === 0 && (
        <div className="card text-sm text-ok-fg">
          No comments in this tab. Try another tab or platform.
        </div>
      )}
      <div className="space-y-3">
        {comments.map((c) => (
          <InboxItem
            key={c.id}
            comment={c}
            owner={owner}
            channel={channels.get(c.publication_id ?? 0)}
            url={urls.get(c.publication_id ?? 0)}
            videoTitle={
              c.publication_id != null
                ? (titles.get(c.publication_id) ?? "")
                : ""
            }
          />
        ))}
      </div>
    </div>
  );
}
