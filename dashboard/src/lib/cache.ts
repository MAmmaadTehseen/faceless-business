import "server-only";
import { revalidateTag, unstable_cache } from "next/cache";

/** Sync refreshes metrics every 6 h; cached reads live that long unless a sync or a write revalidates them. */
export const DATA_TAG = "data";
const SIX_HOURS = 6 * 3600;

export function cached<A extends unknown[], R>(name: string, fn: (...args: A) => Promise<R>) {
  return (...args: A) => unstable_cache(() => fn(...args), [name, JSON.stringify(args)], { revalidate: SIX_HOURS, tags: [DATA_TAG] })();
}

export function refreshData() {
  revalidateTag(DATA_TAG);
}
