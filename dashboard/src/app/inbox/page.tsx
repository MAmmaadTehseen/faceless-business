import Link from "next/link";
import { db } from "@/lib/supabase";
import { Comment } from "@/lib/types";
import { InboxItem } from "@/components/InboxItem";

const PLATFORMS = ["youtube", "instagram", "facebook"];

export default async function InboxPage({ searchParams }: { searchParams: Promise<{ platform?: string }> }) {
  const { platform = "" } = await searchParams;
  let q = db().from("comments").select("*").in("reply_status", ["new", "drafted"])
    .order("posted_at", { ascending: false, nullsFirst: false }).limit(200);
  if (platform) q = q.eq("platform", platform);
  const { data, error } = await q;
  if (error) return <p className="text-red-500">DB error: {error.message}</p>;
  const comments = (data ?? []) as Comment[];

  // Resolve video titles: publication -> content.
  const pubIds = [...new Set(comments.map((c) => c.publication_id).filter((x): x is number => x != null))];
  const titles = new Map<number, string>();
  if (pubIds.length) {
    const { data: pubs } = await db().from("publications").select("id,content_id,content(title)").in("id", pubIds);
    for (const p of pubs ?? []) {
      const content = p.content as unknown as { title: string } | { title: string }[] | null;
      const t = Array.isArray(content) ? content[0]?.title : content?.title;
      titles.set(p.id, t ?? p.content_id);
    }
  }

  return (
    <div>
      <h1 className="mb-3 text-xl font-semibold">Inbox <span className="text-sm font-normal text-muted">({comments.length})</span></h1>
      <div className="mb-4 flex flex-wrap gap-1 text-sm">
        <Link href="/inbox" className={`btn ${!platform ? "btn-primary" : ""}`}>All</Link>
        {PLATFORMS.map((p) => (
          <Link key={p} href={`/inbox?platform=${p}`} className={`btn ${platform === p ? "btn-primary" : ""}`}>{p}</Link>
        ))}
      </div>
      {comments.length === 0 && <p className="text-muted">Inbox zero.</p>}
      <div className="space-y-3">
        {comments.map((c) => (
          <InboxItem key={c.id} comment={c} videoTitle={c.publication_id != null ? titles.get(c.publication_id) ?? "" : ""} />
        ))}
      </div>
    </div>
  );
}
