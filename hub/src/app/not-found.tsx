import Link from 'next/link';
import { channels } from '@/lib/channels';
export default function NotFound() { return <section className="hero"><h1>Story not found</h1><p>This page may have moved. Explore the latest stories or choose a channel.</p><nav><Link href="/">Home</Link>{channels.map(c => <Link key={c.key} href={`/c/${c.key}`}>{c.name}</Link>)}</nav></section>; }
