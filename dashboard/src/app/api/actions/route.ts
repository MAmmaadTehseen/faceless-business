import { NextResponse } from "next/server";
import { isOwner } from "@/lib/role";
import { isChannelKey } from "@/lib/channels";
const workflows: Record<string, string> = {
  sync: "sync.yml",
  engage: "engage.yml",
  produce: "produce.yml",
  shorts: "shorts.yml",
};
async function github(path: string, init: RequestInit = {}) {
  return fetch(
    `https://api.github.com/repos/MAmmaadTehseen/faceless-business/actions/workflows/${path}`,
    {
      ...init,
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${process.env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
    },
  );
}
export async function POST(req: Request) {
  if (!(await isOwner()))
    return NextResponse.json({ error: "Owner only" }, { status: 403 });
  if (!process.env.GITHUB_TOKEN)
    return NextResponse.json({ error: "Not configured" }, { status: 503 });
  const b = await req.json().catch(() => ({}));
  const file =
    typeof b.action === "string" && Object.hasOwn(workflows, b.action)
      ? workflows[b.action]
      : null;
  if (!file)
    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
  const inputs: Record<string, string> = {};
  if (["produce", "shorts"].includes(b.action)) {
    if (!isChannelKey(b.channel))
      return NextResponse.json({ error: "Invalid channel" }, { status: 400 });
    inputs.channel = b.channel;
    inputs.privacy = "private";
  }
  if (b.action === "produce") {
    if (b.privacy !== "private")
      return NextResponse.json(
        { error: "Production stays private pending audit" },
        { status: 400 },
      );
    inputs.privacy = "private";
  }
  try {
    const res = await github(`${file}/dispatches`, {
      method: "POST",
      body: JSON.stringify({ ref: "main", inputs }),
    });
    return res.ok
      ? NextResponse.json({ ok: true, startedAt: new Date().toISOString() })
      : NextResponse.json(
          { error: `GitHub rejected dispatch (${res.status})` },
          { status: 502 },
        );
  } catch {
    return NextResponse.json({ error: "GitHub unavailable" }, { status: 502 });
  }
}
export async function GET(req: Request) {
  if (!(await isOwner()))
    return NextResponse.json({ error: "Owner only" }, { status: 403 });
  if (!process.env.GITHUB_TOKEN)
    return NextResponse.json({ error: "Not configured" }, { status: 503 });
  const key = new URL(req.url).searchParams.get("status") ?? "";
  const file = Object.hasOwn(workflows, key) ? workflows[key] : null;
  if (!file)
    return NextResponse.json({ error: "Invalid workflow" }, { status: 400 });
  try {
    const res = await github(
      `${file}/runs?per_page=1&event=workflow_dispatch&branch=main`,
    );
    if (!res.ok)
      return NextResponse.json(
        { error: "Cannot fetch workflow" },
        { status: 502 },
      );
    const j = await res.json();
    const run = j.workflow_runs?.[0];
    return NextResponse.json(
      run
        ? {
            id: run.id,
            status: run.status,
            conclusion: run.conclusion,
            created_at: run.created_at,
            url: run.html_url,
          }
        : { status: "waiting" },
    );
  } catch {
    return NextResponse.json({ error: "GitHub unavailable" }, { status: 502 });
  }
}
