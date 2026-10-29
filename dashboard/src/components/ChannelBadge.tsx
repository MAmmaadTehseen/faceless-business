import { ChannelMeta, accentCss, channelMeta } from "@/lib/channels";

export function ChannelDot({ meta, className = "" }: { meta: ChannelMeta; className?: string }) {
  return (
    <span
      aria-hidden
      className={`inline-block h-2 w-2 shrink-0 rounded-full ${className}`}
      style={{ backgroundColor: accentCss(meta) }}
    />
  );
}

/** Name + accent dot for a channel key. Renders the raw key when unknown, nothing when null. */
export function ChannelBadge({ channel }: { channel: string | null | undefined }) {
  if (!channel) return null;
  const meta = channelMeta(channel);
  if (!meta) return <span className="badge">{channel}</span>;
  return (
    <span className="badge inline-flex items-center gap-1.5" title={`@${meta.handle}`}>
      <ChannelDot meta={meta} />
      {meta.name}
    </span>
  );
}
