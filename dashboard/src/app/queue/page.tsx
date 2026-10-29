import { db } from "@/lib/supabase";
import { TopicQueueRow } from "@/lib/types";
import { AddTopicForm, QueueRowActions } from "@/components/QueueControls";
import { fmtDate } from "@/lib/format";
import { getChannelFilter } from "@/lib/channel-filter";
import { ChannelBadge } from "@/components/ChannelBadge";

export default async function QueuePage() {
  const channel = await getChannelFilter();
  let q = db().from("topic_queue").select("*").eq("status", "queued")
    .order("priority", { ascending: false }).order("created_at", { ascending: true }).limit(200);
  if (channel !== "all") q = q.eq("channel", channel);
  const { data, error } = await q;
  if (error) return <p className="text-red-500">DB error: {error.message}</p>;
  const rows = (data ?? []) as TopicQueueRow[];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Topic queue <span className="text-sm font-normal text-muted">({rows.length})</span></h1>
      <AddTopicForm defaultChannel={channel === "all" ? undefined : channel} />
      {rows.length === 0 && <p className="text-muted">Queue is empty.</p>}
      <ul className="space-y-2">
        {rows.map((r) => (
          <li key={r.id} className="card flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                {channel === "all" && <ChannelBadge channel={r.channel} />}
                <span className="badge">p{r.priority}</span>
                <span className="badge">{r.added_by}</span>
                <span className="font-medium">{r.topic}</span>
              </div>
              <div className="mt-0.5 text-xs text-muted">
                {r.source_headline && <span>{r.source_headline} · </span>}
                {r.source_url && <a href={r.source_url} target="_blank" rel="noreferrer" className="underline">source</a>}
                {r.source_url && " · "}
                {fmtDate(r.created_at)}
              </div>
            </div>
            <QueueRowActions id={r.id} />
          </li>
        ))}
      </ul>
    </div>
  );
}
