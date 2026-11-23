import { NextResponse } from "next/server";
import { isOwner } from "@/lib/role";
import { refreshData } from "@/lib/cache";

// Refresh = a real sync.yml run. Owner only, one at a time, at most one dispatch every 10 minutes.
const REPO = "MAmmaadTehseen/faceless-business";
const MIN_GAP_MS = 10 * 60_000;
let lastRevalidated = 0;

type Run = { id: number; status: string; conclusion: string | null; created_at: string; updated_at: string; html_url: string };

async function gh(path: string, init: RequestInit = {}) {
  return fetch(`https://api.github.com/repos/${REPO}/${path}`, {
    ...init,
    cache: "no-store",
    headers: { Authorization: `Bearer ${process.env.GITHUB_TOKEN}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json" },
  });
}

async function latestRun(): Promise<Run | null> {
  const res = await gh("actions/workflows/sync.yml/runs?per_page=1");
  if (!res.ok) throw new Error(`GitHub ${res.status}`);
  const run = (await res.json()).workflow_runs?.[0];
  return run ? { id: run.id, status: run.status, conclusion: run.conclusion, created_at: run.created_at, updated_at: run.updated_at, html_url: run.html_url } : null;
}

function state(run: Run | null) {
  if (!run) return { state: "idle" as const, run };
  if (run.status !== "completed") return { state: "running" as const, run };
  // A finished sync wrote new rows: clear cached reads once per finished run.
  const done = Date.parse(run.updated_at);
  if (done > lastRevalidated) { lastRevalidated = done; refreshData(); }
  return { state: run.conclusion === "success" ? "done" as const : "failed" as const, run };
}

export async function GET() {
  if (!(await isOwner())) return NextResponse.json({ error: "Owner only" }, { status: 403 });
  if (!process.env.GITHUB_TOKEN) return NextResponse.json({ error: "Not configured" }, { status: 503 });
  try { return NextResponse.json(state(await latestRun())); }
  catch { return NextResponse.json({ error: "GitHub unavailable" }, { status: 502 }); }
}

export async function POST() {
  if (!(await isOwner())) return NextResponse.json({ error: "Owner only" }, { status: 403 });
  if (!process.env.GITHUB_TOKEN) return NextResponse.json({ error: "Not configured" }, { status: 503 });
  try {
    const run = await latestRun();
    if (run && run.status !== "completed") return NextResponse.json({ ...state(run), note: "A sync is already running" });
    const wait = run ? Date.parse(run.created_at) + MIN_GAP_MS - Date.now() : 0;
    if (wait > 0) return NextResponse.json({ ...state(run), error: `Synced recently. Try again in ${Math.ceil(wait / 60_000)} min.` }, { status: 429 });
    const res = await gh("actions/workflows/sync.yml/dispatches", { method: "POST", body: JSON.stringify({ ref: "main" }) });
    if (!res.ok) return NextResponse.json({ error: `GitHub rejected the sync (${res.status})` }, { status: 502 });
    return NextResponse.json({ state: "running", run: null, startedAt: new Date().toISOString() });
  } catch {
    return NextResponse.json({ error: "GitHub unavailable" }, { status: 502 });
  }
}
