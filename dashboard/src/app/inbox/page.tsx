import { FilterSheet } from "@/components/FilterSheet";
import Link from "next/link";
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
  searchParams: Promise<{ platform?: string; tab?: string }>;
}) {
  const { platform = "", tab = "pending" } = await searchParams;
  const channel = await getChannelFilter();
  // Channel lives on content, two joins away; over-fetch when filtering and trim in code.
  let q = db()
    .from("comments")
    .select("*")
    .order("posted_at", { ascending: false, nullsFirst: false })
    .limit(channel === "all" ? 200 : 600);
  if (tab === "pending") q = q.in("reply_status", ["new", "drafted"]);
  if (tab === "replied") q = q.eq("reply_status", "sent");
  if (tab === "flagged") q = q.eq("flagged", true);
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
                href={`/inbox?tab=${t}${platform ? `&platform=${platform}` : ""}`}
              >
                {t[0].toUpperCase() + t.slice(1)}
              </Link>
            ))}
          </div>
        }
      />
      <FilterSheet count={Number(!!platform)}><form className="filter-bar mb-4">
        <input type="hidden" name="tab" value={tab} />
        <select name="platform" aria-label="Platform" defaultValue={platform}>
          <option value="">All platforms</option>
          {PLATFORMS.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <button className="btn">Apply</button>
      </form></FilterSheet>
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
