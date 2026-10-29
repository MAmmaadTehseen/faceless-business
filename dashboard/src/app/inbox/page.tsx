import Link from "next/link";
import { db } from "@/lib/supabase";
import { Comment } from "@/lib/types";
import { InboxItem } from "@/components/InboxItem";
import { getChannelFilter } from "@/lib/channel-filter";
import { PageHeader } from "@/components/PageHeader";

const PLATFORMS = ["youtube", "instagram", "facebook"];

export default async function InboxPage({ searchParams }: { searchParams: Promise<{ platform?: string }> }) {
  const { platform = "" } = await searchParams;
  const channel = await getChannelFilter();
  // Channel lives on content, two joins away; over-fetch when filtering and trim in code.
  let q = db().from("comments").select("*").in("reply_status", ["new", "drafted"])
    .order("posted_at", { ascending: false, nullsFirst: false }).limit(channel === "all" ? 200 : 600);
  if (platform) q = q.eq("platform", platform);
  const { data, error } = await q;
  if (error) return <p className="text-alert-fg">DB error: {error.message}</p>;
  let comments = (data ?? []) as Comment[];

  // Resolve video titles and channels: publication -> content.
  const pubIds = [...new Set(comments.map((c) => c.publication_id).filter((x): x is number => x != null))];
  const titles = new Map<number, string>();
  const channels = new Map<number, string | null>();
  if (pubIds.length) {
    const { data: pubs } = await db().from("publications").select("id,content_id,content(title,channel)").in("id", pubIds);
    type C = { title: string; channel: string | null };
    for (const p of pubs ?? []) {
      const content = p.content as unknown as C | C[] | null;
      const row = Array.isArray(content) ? content[0] : content;
      titles.set(p.id, row?.title ?? p.content_id);
      channels.set(p.id, row?.channel ?? null);
    }
  }
  if (channel !== "all") {
    comments = comments
      .filter((c) => c.publication_id != null && channels.get(c.publication_id) === channel)
      .slice(0, 200);
  }

  return (
    <div>
      <PageHeader title="Inbox" count={comments.length} blurb="Comments waiting for a reply. Drafts are pre-written by Claude; edit, send or skip."
        action={
          <div className="flex flex-wrap gap-1 text-sm">
            <Link href="/inbox" className={`btn ${!platform ? "btn-primary" : ""}`}>All</Link>
            {PLATFORMS.map((p) => (
              <Link key={p} href={`/inbox?platform=${p}`} className={`btn ${platform === p ? "btn-primary" : ""}`}>{p}</Link>
            ))}
          </div>
        } />
      {comments.length === 0 && <div className="card text-sm text-ok-fg">Inbox zero. Every comment has been answered or skipped.</div>}
      <div className="space-y-3">
        {comments.map((c) => (
          <InboxItem key={c.id} comment={c} videoTitle={c.publication_id != null ? titles.get(c.publication_id) ?? "" : ""} />
        ))}
      </div>
    </div>
  );
}
