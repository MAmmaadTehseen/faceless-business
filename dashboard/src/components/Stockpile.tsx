import { getStockpile } from "@/lib/stockpile";
import { ChannelFilter } from "@/lib/channels";
export async function Stockpile({ channel }: { channel: ChannelFilter }) {
  try {
    const stock = await getStockpile(channel);
    return <section><h2 className="text-base font-semibold mb-3">Stockpile</h2><div className="home-channels">{stock.channels.map(c =>
      <div className="channel-card" key={c.key}><h3 className="font-semibold">{c.name}</h3>
        <p className="mt-2">{c.longs} long videos · {c.shorts} Shorts</p>
        <p className="text-xs text-muted mt-2">{c.days === null ? "Automatic release is off" : `${c.days} days at ${stock.rate} bundles/day`}</p>
        <p className="text-xs text-muted mt-2">{(c.bytes / 1024 ** 3).toFixed(2)} GiB banked in Drive</p></div>)}</div>
      <p className="text-xs text-muted mt-3">Drive account used: {stock.driveUsed === undefined ? "Not checked yet" : `${(stock.driveUsed / 1024 ** 3).toFixed(1)} GiB`}{stock.checkedAt ? ` · checked ${new Date(stock.checkedAt).toLocaleString("en-GB", { timeZone: "UTC" })} UTC` : ""}. Released folders remain in Drive.</p>
    </section>;
  } catch { return <section><h2 className="font-semibold">Stockpile</h2><p className="text-xs text-muted">Stockpile data unavailable.</p></section>; }
}
