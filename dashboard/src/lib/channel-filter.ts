import "server-only";
import { getScope } from "./server-scope";
export async function getChannelFilter() { return (await getScope()).channel; }
