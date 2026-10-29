import { feed } from '@/lib/feed';
import { getChannel } from '@/lib/channels';
export const revalidate = 600;
export async function GET(_: Request, {params}: {params: Promise<{channel:string}>}) { const {channel} = await params; return getChannel(channel) ? feed(channel) : new Response('Not found', {status:404}); }
