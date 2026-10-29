import "server-only";
import { cookies } from "next/headers";
import { CHANNEL_COOKIE, ChannelFilter, parseChannelFilter } from "./channels";

/** Current channel filter from the fb_channel cookie ("all" when unset or invalid). */
export async function getChannelFilter(): Promise<ChannelFilter> {
  const jar = await cookies();
  return parseChannelFilter(jar.get(CHANNEL_COOKIE)?.value);
}
