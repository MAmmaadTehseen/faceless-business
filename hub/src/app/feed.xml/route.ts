import { feed } from '@/lib/feed';
export const revalidate = 600;
export async function GET() { return feed(); }
