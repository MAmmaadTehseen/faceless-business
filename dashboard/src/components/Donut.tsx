import { fmtCount } from "@/lib/format";

export type Slice = { label: string; value: number; color: string };

/** Pie/donut drawn with a conic gradient; the centre text scales with the size so it never touches the ring. */
export function Donut({ slices, size = 120, center, sub, label }: { slices: Slice[]; size?: number; center?: React.ReactNode; sub?: string; label: string }) {
  const total = slices.reduce((n, s) => n + Math.max(0, s.value), 0);
  let acc = 0;
  const stops = total ? slices.map(s => { const a = acc / total * 360; acc += Math.max(0, s.value); return `${s.color} ${a}deg ${acc / total * 360}deg`; }).join(",") : "var(--border) 0deg 360deg";
  return <div className="donut" role="img" aria-label={`${label}: ${slices.map(s => `${s.label} ${fmtCount(s.value)}`).join(", ")}`} style={{ width: size, height: size, background: `conic-gradient(${stops})` }}>
    {center !== undefined && <span style={{ fontSize: Math.round(size * 0.17) }}>{center}{sub && <small>{sub}</small>}</span>}
  </div>;
}

export function Legend({ slices, format = fmtCount }: { slices: Slice[]; format?: (n: number) => string }) {
  const total = slices.reduce((n, s) => n + Math.max(0, s.value), 0) || 1;
  return <ul className="cr-legend">{slices.map(s => <li key={s.label}><span className="cr-sw" style={{ background: s.color }} aria-hidden /><span>{s.label}</span><span className="num">{format(s.value)} · {Math.round(s.value / total * 100)}%</span></li>)}</ul>;
}

export function DonutCard({ slices, size = 120, center, sub, label, format }: { slices: Slice[]; size?: number; center?: React.ReactNode; sub?: string; label: string; format?: (n: number) => string }) {
  return <div className="card cr-piebox"><Donut slices={slices} size={size} center={center} sub={sub} label={label} /><Legend slices={slices} format={format} /></div>;
}
