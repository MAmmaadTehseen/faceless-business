import { ChannelMeta, accentCss, channelMeta } from "@/lib/channels";

export function ChannelDot({ meta, className = "" }: { meta: ChannelMeta; className?: string }) {
  return (
    <span
      aria-hidden
      className={`inline-block h-2 w-2 shrink-0 rounded-full ${className}`}
      style={{ backgroundColor: accentCss(meta), boxShadow: `0 0 6px ${accentCss(meta)}` }}
    />
  );
}

/** Brand-coloured pill for a channel key. Renders the raw key when unknown, nothing when null. */
export function ChannelBadge({ channel, short = false }: { channel: string | null | undefined; short?: boolean }) {
  if (!channel) return null;
  const meta = channelMeta(channel);
  if (!meta) return <span className="badge">{channel}</span>;
  return (
    <span
      className="badge"
      title={`@${meta.handle}`}
      style={{ backgroundColor: meta.brand.bg, color: meta.brand.fg, borderColor: `${meta.brand.fg}55` }}
    >
      <ChannelDot meta={meta} />
      {short ? meta.short : meta.name}
    </span>
  );
}
