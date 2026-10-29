import { db } from "@/lib/supabase";
import { TopicQueueRow } from "@/lib/types";
import { AddTopicForm, QueueRowActions } from "@/components/QueueControls";
import { fmtDate } from "@/lib/format";
import { getChannelFilter } from "@/lib/channel-filter";
import { ChannelBadge } from "@/components/ChannelBadge";
import { PageHeader } from "@/components/PageHeader";

export default async function QueuePage() {
  const channel = await getChannelFilter();
  let q = db().from("topic_queue").select("*").eq("status", "queued")
    .order("priority", { ascending: false }).order("created_at", { ascending: true }).limit(200);
  if (channel !== "all") q = q.eq("channel", channel);
  const { data, error } = await q;
  if (error) return <p className="text-alert-fg">DB error: {error.message}</p>;
  const rows = (data ?? []) as TopicQueueRow[];

  return (
    <div className="space-y-5">
      <PageHeader title="Topic queue" count={rows.length} blurb="Topics the pipeline will turn into videos, highest priority first. +5 bumps a topic up; Kill drops it." />
      <section className="card">
        <div className="section-title mb-2">Add a topic</div>
        <AddTopicForm key={channel} defaultChannel={channel === "all" ? undefined : channel} />
      </section>
      {rows.length === 0 && (
        <div className="card card-alert text-sm text-alert-fg">Queue is empty. The next scheduled run will have nothing to produce.</div>
      )}
      <ol className="space-y-2">
        {rows.map((r, i) => (
          <li key={r.id} className="card flex flex-wrap items-start justify-between gap-3">
            <div className="flex min-w-0 flex-1 items-start gap-3">
              <span className="mt-0.5 w-6 shrink-0 text-right font-mono text-xs text-faint">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  {channel === "all" && <ChannelBadge channel={r.channel} short />}
                  <span className="badge badge-accent">p{r.priority}</span>
                  <span className="badge">{r.added_by}</span>
                  <span className="font-medium">{r.topic}</span>
                </div>
                <div className="mt-1 text-xs text-muted">
                  {r.source_headline && <span>{r.source_headline} · </span>}
                  {r.source_url && <a href={r.source_url} target="_blank" rel="noreferrer" className="text-accent-fg underline">source</a>}
                  {r.source_url && " · "}
                  {fmtDate(r.created_at)}
                </div>
              </div>
            </div>
            <QueueRowActions id={r.id} />
          </li>
        ))}
      </ol>
    </div>
  );
}
