import { db } from "@/lib/supabase";
import { rebuildArtifact } from "@/lib/rebuild";
import { recoveryAction } from "@/lib/recovery";
import { NextResponse } from "next/server";
import { isOwner } from "@/lib/role";
import { isChannelKey } from "@/lib/channels";
const workflows: Record<string, string> = {
  sync: "sync.yml",
  retry: "retry.yml",
  rebuild: "produce.yml",
  reproduce: "produce.yml",
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
  const requestId = ["retry", "rebuild", "reproduce"].includes(b.action) ? crypto.randomUUID() : undefined;
  if (["rebuild", "reproduce"].includes(b.action)) {
    const {data: content, error} = await db().from("content").select("*").eq("id", b.content_id).single();
    if (error || !content || content.status === "killed" || content.placeholder)
      return NextResponse.json({error:"Content unavailable"}, {status:400});
    const {data: pubs, error: pubError} = await db().from("publications").select("*").eq("content_id", content.id);
    if (pubError || recoveryAction(content, pubs || []) === "retry")
      return NextResponse.json({error:"Content does not require rebuilding"}, {status:400});
    try {
      const artifact = await rebuildArtifact(content);
      inputs.channel = content.channel;
      const {data: setting, error: settingError} = await db().from("settings").select("value").eq("key", "publish_privacy").maybeSingle();
      if (settingError) throw settingError;
      inputs.privacy = setting?.value || "private";
      inputs.request_id = requestId!;
      if (b.action === "rebuild") {
        if (!artifact) return NextResponse.json({error:"Artifact expired; re-produce from topic"}, {status:409});
        inputs.resume_id = content.id;
        inputs.artifact_run_id = artifact.runId;
        inputs.artifact_name = artifact.name;
        inputs.rerender = "true";
      } else {
        if (artifact) return NextResponse.json({error:"Artifact available; use Rebuild"}, {status:409});
        const {data: top, error: topError} = await db().from("topic_queue").select("priority").eq("channel",content.channel).order("priority",{ascending:false}).limit(1);
        if (topError) throw topError;
        const {error: queueError} = await db().from("topic_queue").insert({channel:content.channel,topic:content.topic,priority:(top?.[0]?.priority || 0)+100,status:"queued",added_by:"user"});
        if (queueError) throw queueError;
        inputs.count = "1";
      }
    } catch {
      return NextResponse.json({error:"Cannot prepare rebuild; artifact or database lookup failed"}, {status:502});
    }
  }
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
  if (b.action === "retry") {
    inputs.request_id = requestId!;
    if (b.ids != null && (typeof b.ids !== "string" || !/^\d+(,\d+)*$/.test(b.ids) || b.ids.length > 5000))
      return NextResponse.json({ error: "Invalid publication IDs" }, { status: 400 });
    if (b.content_id != null && (typeof b.content_id !== "string" || !/^[a-zA-Z0-9_-]{1,200}$/.test(b.content_id)))
      return NextResponse.json({ error: "Invalid content ID" }, { status: 400 });
    if (!b.ids && !b.content_id)
      return NextResponse.json({ error: "Select publications to retry" }, { status: 400 });
    if (b.platform && !["youtube", "instagram", "facebook"].includes(b.platform))
      return NextResponse.json({ error: "Invalid platform" }, { status: 400 });
    if (b.ids) inputs.ids = b.ids;
    if (b.content_id) inputs.content_id = b.content_id;
    if (b.platform) inputs.platform = b.platform;
  }
  try {
    const res = await github(`${file}/dispatches`, {
      method: "POST",
      body: JSON.stringify({ ref: "main", inputs }),
    });
    if (res.ok)
      return NextResponse.json({ ok: true, requestId, startedAt: new Date().toISOString() });
    const detail = await res
      .json()
      .then((j) => (typeof j?.message === "string" ? j.message : ""))
      .catch(() => "");
    return NextResponse.json(
      { error: `GitHub rejected dispatch (${res.status})${detail ? ": " + detail : ""}` },
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
  const artifactId = new URL(req.url).searchParams.get("artifact");
  if (artifactId) {
    try {
      const {data, error} = await db().from("content").select("*").eq("id", artifactId).single();
      if (error || !data) return NextResponse.json({error:"Content unavailable"},{status:404});
      return NextResponse.json({available:!!(await rebuildArtifact(data))});
    } catch { return NextResponse.json({error:"Cannot check artifact availability"},{status:502}); }
  }
  const key = new URL(req.url).searchParams.get("status") ?? "";
  const file = Object.hasOwn(workflows, key) ? workflows[key] : null;
  if (!file)
    return NextResponse.json({ error: "Invalid workflow" }, { status: 400 });
  try {
    const res = await github(
      `${file}/runs?per_page=100&event=workflow_dispatch&branch=main`,
    );
    if (!res.ok)
      return NextResponse.json(
        { error: "Cannot fetch workflow" },
        { status: 502 },
      );
    const j = await res.json();
    const requestId = new URL(req.url).searchParams.get("request_id");
    const run = requestId ? j.workflow_runs?.find((r: {display_title: string}) => r.display_title === `${key === "retry" ? "retry" : "produce"} ${requestId}`) : j.workflow_runs?.[0];
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
