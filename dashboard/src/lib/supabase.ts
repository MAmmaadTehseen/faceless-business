import "server-only";
import { createClient, SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

// Service-role client. Only ever imported from server components / route handlers.
export function db(): SupabaseClient {
  if (client) return client;
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) throw new Error("SUPABASE_URL / SUPABASE_SERVICE_KEY not set");
  // DB_TIMING=1 logs each request's time and size (diagnostics only).
  const timed: typeof fetch = async (input, init) => {
    const start = Date.now(), res = await fetch(input, init), body = await res.clone().arrayBuffer();
    console.log(`db ${Date.now() - start}ms @${start % 100000} ${body.byteLength}B ${String(input).replace(url, "").slice(0, 140)}`);
    return res;
  };
  client = createClient(url, key, { auth: { persistSession: false }, ...(process.env.DB_TIMING === "1" ? { global: { fetch: timed } } : {}) });
  return client;
}
