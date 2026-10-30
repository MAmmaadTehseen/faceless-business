import { ReplaceLink as Link } from "@/components/ReplaceLink";
import { AutoFilters } from "@/components/AutoFilters";
import { FilterSheet } from "@/components/FilterSheet";
import { CHANNELS, parseChannelFilter } from "@/lib/channels";
import { ScheduledTopic } from "@/components/ScheduledTopic";
import { Section } from "@/components/Section";
import { isOwner } from "@/lib/role";
import { db } from "@/lib/supabase";
import { TopicQueueRow } from "@/lib/types";
import { AddTopicForm, QueueRowActions } from "@/components/QueueControls";
import { fmtDate } from "@/lib/format";
import { getChannelFilter } from "@/lib/channel-filter";
import { ChannelBadge } from "@/components/ChannelBadge";
import { PageHeader } from "@/components/PageHeader";

export default async function QueuePage({ searchParams }: { searchParams: Promise<Record<string, string>> }) {
  const sp = await searchParams;
  const owner = await isOwner();
  const channel = parseChannelFilter(sp.channel);
  let q = db()
    .from("topic_queue")
    .select("*")
    .eq("status", "queued")
    .order("priority", { ascending: false })
    .order("created_at", { ascending: true })
    .order("id", { ascending: true });
  if (channel !== "all") q = q.eq("channel", channel);
  const allRows: TopicQueueRow[] = [];
  for (let offset = 0; ; offset += 500) {
    const { data, error } = await q.range(offset, offset + 499);
    if (error) return <p className="text-alert-fg">DB error: {error.message}</p>;
    allRows.push(...((data ?? []) as TopicQueueRow[]));
    if ((data ?? []).length < 500) break;
  }
  const schedules: Record<string, { days: number[]; hour: number }> = { futurework: { days: [1,3,5], hour: 6 }, tradewinds: { days: [2,4,6], hour: 11 }, escapevelocity: { days: [1,4,0], hour: 16 } };
  const positions = new Map<string, number>();
  const slots = new Map<number, { at: string; run: number }>();
  const now = Date.now();
  for (const row of allRows) {
    const run = (positions.get(row.channel) ?? 0) + 1;
    positions.set(row.channel, run);
    const schedule = schedules[row.channel];
    if (!schedule) continue;
    const date = new Date(now); date.setUTCHours(schedule.hour, 0, 0, 0);
    let found = 0;
    while (true) { if (date.getTime() > now && schedule.days.includes(date.getUTCDay())) { found++; if (found === run) break; } date.setUTCDate(date.getUTCDate() + 1); }
    slots.set(row.id, { at: date.toISOString(), run });
  }
  const rows = allRows.filter(r => (!sp.source || r.added_by === sp.source) && (!sp.q || r.topic.toLowerCase().includes(sp.q.trim().toLowerCase())));
  const count = [channel !== "all", sp.source, sp.q?.trim()].filter(Boolean).length;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Topic queue"
        count={rows.length}
        blurb="Topics the pipeline will turn into videos, highest priority first. +5 bumps a topic up; Kill drops it."
      />
      <p className="text-xs text-muted">Scheduled estimates use each channel’s next UTC cron slots, one topic per run. +5 can change queue order and dates.</p>
      <FilterSheet count={count}><AutoFilters key={JSON.stringify({ ...sp, q: undefined })}><select name="channel" aria-label="Channel" defaultValue={channel}><option value="all">All channels</option>{CHANNELS.map(c => <option key={c.key} value={c.key}>{c.short}</option>)}</select><select name="source" aria-label="Source" defaultValue={sp.source ?? ""}><option value="">All sources</option>{[...new Set(allRows.map(r => r.added_by))].map(v => <option key={v}>{v}</option>)}</select><input name="q" aria-label="Search topics" placeholder="Search topics…" defaultValue={sp.q ?? ""}/><span className="badge">{count} active</span><Link href="/queue?channel=all" scroll={false} className="badge">Clear</Link></AutoFilters></FilterSheet>
      {owner && (
        <Section title="Add a topic">
          <AddTopicForm
            key={channel}
            defaultChannel={channel === "all" ? undefined : channel}
          />
        </Section>
      )}
      {rows.length === 0 && (
        <div className="card border-warn/50 text-sm text-warn-fg">
          Queue is empty. The next scheduled run will have nothing to produce.
        </div>
      )}
      <ol className="card divide-y divide-border">
        {rows.map((r, i) => (
          <li
            key={r.id}
            className="py-3 flex flex-wrap items-start justify-between gap-3"
          >
            <div className="flex min-w-0 flex-1 items-start gap-3">
              <span className="mt-0.5 w-6 shrink-0 text-right font-mono text-xs text-faint">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  {channel === "all" && (
                    <ChannelBadge channel={r.channel} short />
                  )}
                  <span className="badge badge-warn">p{r.priority}</span>
                  {slots.has(r.id) && <ScheduledTopic {...slots.get(r.id)!} />}
                  <span className="badge">{r.added_by}</span>
                  <span className="font-medium">{r.topic}</span>
                </div>
                <div className="mt-1 text-xs text-muted">
                  {r.source_headline && <span>{r.source_headline} · </span>}
                  {r.source_url && (
                    <a
                      href={r.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-accent-fg underline"
                    >
                      source
                    </a>
                  )}
                  {r.source_url && " · "}
                  {fmtDate(r.created_at)}
                </div>
              </div>
            </div>
            {owner && <QueueRowActions id={r.id} />}
          </li>
        ))}
      </ol>
    </div>
  );
}
