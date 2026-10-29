import Link from "next/link";
import { db } from "@/lib/supabase";
import { Content, Metric, Publication } from "@/lib/types";
import { fmtDate, fmtNum, fmtSec } from "@/lib/format";
import { getChannelFilter } from "@/lib/channel-filter";
import { ChannelBadge } from "@/components/ChannelBadge";

type Search = { kind?: string; platform?: string; days?: string };

const PLATFORMS = ["youtube", "instagram", "facebook", "tiktok"];

export default async function ContentPage({ searchParams }: { searchParams: Promise<Search> }) {
  const sp = await searchParams;
  const kind = sp.kind ?? "";
  const platform = sp.platform ?? "";
  const days = sp.days ?? "";
  const channel = await getChannelFilter();
  const showChannel = channel === "all";

  let q = db().from("content").select("id,channel,kind,parent_id,topic,title,qa_status,status,claude_cost_usd,created_at")
    .order("created_at", { ascending: false }).limit(300);
  if (channel !== "all") q = q.eq("channel", channel);
  if (days) q = q.gte("created_at", new Date(Date.now() - Number(days) * 86400_000).toISOString());
  const { data: contentRows, error } = await q;
  if (error) return <p className="text-red-500">DB error: {error.message}</p>;
  const content = (contentRows ?? []) as Content[];

  const ids = content.map((c) => c.id);
  const { data: pubRows } = ids.length
    ? await db().from("publications").select("*").in("content_id", ids)
    : { data: [] };
  let pubs = (pubRows ?? []) as Publication[];
  if (platform) pubs = pubs.filter((p) => p.platform === platform);

  // Latest metrics row per publication.
  const pubIds = pubs.map((p) => p.id);
  const { data: metricRows } = pubIds.length
    ? await db().from("metrics").select("*").in("publication_id", pubIds).order("captured_at", { ascending: false })
    : { data: [] };
  const latest = new Map<number, Metric>();
  for (const m of (metricRows ?? []) as Metric[]) if (!latest.has(m.publication_id)) latest.set(m.publication_id, m);

  const pubsByContent = new Map<string, Publication[]>();
  for (const p of pubs) pubsByContent.set(p.content_id, [...(pubsByContent.get(p.content_id) ?? []), p]);

  // Nest shorts under their parent long when the parent is in the list.
  const byId = new Set(ids);
  const children = new Map<string, Content[]>();
  const roots: Content[] = [];
  for (const c of content) {
    if (c.kind === "short" && c.parent_id && byId.has(c.parent_id)) {
      children.set(c.parent_id, [...(children.get(c.parent_id) ?? []), c]);
    } else roots.push(c);
  }
  const visible = (c: Content) => {
    if (platform && !(pubsByContent.get(c.id)?.length)) return false;
    return true;
  };
  const matchesKind = (c: Content) => !kind || c.kind === kind;

  const rows = roots.filter((c) => {
    const kids = (children.get(c.id) ?? []).filter(matchesKind).filter(visible);
    return (matchesKind(c) && visible(c)) || kids.length > 0;
  });

  return (
    <div>
      <h1 className="mb-3 text-xl font-semibold">Content</h1>
      <form className="mb-4 flex flex-wrap gap-2 text-sm">
        <select name="kind" defaultValue={kind}>
          <option value="">All kinds</option>
          <option value="long">Long</option>
          <option value="short">Short</option>
        </select>
        <select name="platform" defaultValue={platform}>
          <option value="">All platforms</option>
          {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select name="days" defaultValue={days}>
          <option value="">All time</option>
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
        </select>
        <button className="btn">Apply</button>
        {(kind || platform || days) && <Link href="/" className="btn">Clear</Link>}
      </form>

      {rows.length === 0 && <p className="text-muted">No content yet.</p>}
      <div className="space-y-3">
        {rows.map((c) => (
          <ContentCard key={c.id} c={c} pubs={pubsByContent} latest={latest}
            kids={(children.get(c.id) ?? []).filter(matchesKind).filter(visible)}
            dim={!(matchesKind(c) && visible(c))} showChannel={showChannel} />
        ))}
      </div>
    </div>
  );
}

function ContentCard({ c, pubs, latest, kids, dim, showChannel }: {
  c: Content; pubs: Map<string, Publication[]>; latest: Map<number, Metric>; kids: Content[]; dim: boolean; showChannel: boolean;
}) {
  return (
    <div className="card">
      <ContentRow c={c} pubs={pubs.get(c.id) ?? []} latest={latest} dim={dim} showChannel={showChannel} />
      {kids.length > 0 && (
        <div className="mt-2 space-y-2 border-l-2 border-border pl-3">
          {kids.map((k) => <ContentRow key={k.id} c={k} pubs={pubs.get(k.id) ?? []} latest={latest} dim={false} />)}
        </div>
      )}
    </div>
  );
}

function statusColor(s: string) {
  if (s === "published" || s === "live" || s === "passed") return "text-green-600 dark:text-green-400";
  if (s === "failed" || s === "killed") return "text-red-500";
  return "text-muted";
}

function ContentRow({ c, pubs, latest, dim, showChannel = false }: {
  c: Content; pubs: Publication[]; latest: Map<number, Metric>; dim: boolean; showChannel?: boolean;
}) {
  return (
    <div className={dim ? "opacity-50" : ""}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        {showChannel && <ChannelBadge channel={c.channel} />}
        <span className="badge uppercase">{c.kind}</span>
        <span className="font-medium">{c.title}</span>
      </div>
      <div className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-muted">
        <span>{c.topic}</span>
        <span className={statusColor(c.status)}>status: {c.status}</span>
        <span className={statusColor(c.qa_status)}>qa: {c.qa_status}</span>
        <span>{fmtDate(c.created_at)}</span>
      </div>
      {pubs.length > 0 && (
        <ul className="mt-1.5 space-y-1 text-xs">
          {pubs.map((p) => {
            const m = latest.get(p.id);
            return (
              <li key={p.id} className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="badge">{p.platform}</span>
                <span className="text-muted">{p.privacy ?? "-"}</span>
                <span className={statusColor(p.status)}>{p.status}</span>
                {p.url && <a href={p.url} target="_blank" rel="noreferrer" className="text-accent underline">link</a>}
                {m ? (
                  <span className="text-muted">
                    {fmtNum(m.views)} views · {fmtNum(m.likes)} likes · {fmtNum(m.comments)} comments
                    {p.platform === "youtube" && (
                      <> · CTR {m.ctr != null ? `${(m.ctr * (m.ctr <= 1 ? 100 : 1)).toFixed(1)}%` : "-"} · avg {fmtSec(m.avg_view_duration_sec)}</>
                    )}
                  </span>
                ) : <span className="text-muted">no metrics</span>}
                {p.error && <span className="text-red-500">{p.error}</span>}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
