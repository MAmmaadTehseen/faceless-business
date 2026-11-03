import { NextRequest, NextResponse } from "next/server";
import { recapRequestAllowed } from "@/lib/recap-local";
import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";
import { createReadStream } from "node:fs";
import { Readable } from "node:stream";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const root = path.resolve(process.cwd(), "..");
const base = path.join(root, "out", "recap");
const pieces = ["long", "short1", "short2", "short3", "short4"];
async function project(id: string) {
  if (!/^[a-f0-9]{32}$/.test(id)) throw new Error("Invalid project");
  const directory = path.join(base, id);
  if ((await fs.lstat(directory)).isSymbolicLink() || await fs.realpath(directory) !== directory) throw new Error("Invalid project");
  return directory;
}
function worker(args: string[], input?: unknown, batch = false): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(path.join(root, ".venv", "bin", "python"), ["-m", batch ? "pipeline.recap.batch" : "pipeline.recap.worker", ...args], {
      cwd: root, shell: false, env: process.env, stdio: ["pipe", "pipe", "ignore"],
    });
    let output = "";
    child.stdout.on("data", chunk => { output += chunk; });
    child.on("error", () => reject(new Error("Cannot start .venv Python worker")));
    child.stdin.on("error", () => {});
    child.stdin.end(input === undefined ? undefined : JSON.stringify(input));
    child.on("close", code => code === 0 ? resolve(output) : reject(new Error("Worker failed; check project status or local setup")));
  });
}
export async function GET(req: NextRequest) {
  if (!recapRequestAllowed(req)) return new NextResponse(null, { status: 404 });
  try {
    const directory = await project(req.nextUrl.searchParams.get("id") || "");
    const file = req.nextUrl.searchParams.get("file");
    if (file) {
      // Only these generated outputs can be read; never source paths or arbitrary files.
      if (!/^(long|short[1-4])\/(video\.mp4|captions\.srt|thumbnail\.jpg)$/.test(file)) throw new Error("Invalid output");
      const target = path.join(directory, file);
      if (await fs.realpath(target) !== target || !(await fs.stat(target)).isFile()) throw new Error("Invalid output");
      const size = (await fs.stat(target)).size;
      const stream = (start = 0, end = size - 1) => Readable.toWeb(createReadStream(target, { start, end })) as ReadableStream;
      const range = req.headers.get("range");
      const type = file.endsWith(".mp4") ? "video/mp4" : file.endsWith(".srt") ? "application/x-subrip" : "image/jpeg";
      const headers = { "Content-Type": type, "Cache-Control": "no-store", "Accept-Ranges": "bytes" };
      if (range) {
        const match = /^bytes=(\d+)-(\d*)$/.exec(range);
        if (!match) return new NextResponse(null, { status: 416 });
        const start = Number(match[1]), end = Math.min(match[2] ? Number(match[2]) : size - 1, size - 1);
        if (start > end) return new NextResponse(null, { status: 416 });
        return new NextResponse(stream(start, end), { status: 206, headers: { ...headers, "Content-Range": `bytes ${start}-${end}/${size}`, "Content-Length": String(end-start+1) } });
      }
      return new NextResponse(stream(), { headers });
    }
    const state = JSON.parse(await fs.readFile(path.join(directory, "state.json"), "utf8"));
    delete state.source;
    try { Object.assign(state, JSON.parse(await worker(["spend", "--id", state.id]))); }
    catch { state.spend_usd = null; }
    state.rights = JSON.parse(await fs.readFile(path.join(directory, "rights.json"), "utf8"));
    return NextResponse.json(state, { headers: { "Cache-Control": "no-store" } });
  } catch { return NextResponse.json({ error: "Project or output not found" }, { status: 404 }); }
}
export async function POST(req: NextRequest) {
  if (!recapRequestAllowed(req)) return new NextResponse(null, { status: 404 });
  try {
    const body = await req.json();
    if (body.action === "create") {
      const output = await worker(["create"], body);
      const result = JSON.parse(output.trim().split("\n").at(-1)!);
      return NextResponse.json(result, { status: result.error ? 400 : 200 });
    }
    if (["scan", "batch-edit", "batch-start", "batch-resume"].includes(body.action)) {
      if (typeof body.folder !== "string" || !path.isAbsolute(body.folder)) throw new Error("Absolute folder required");
      const args = ["--folder", body.folder];
      if (body.action === "batch-edit") args.push("--edit");
      if (body.action === "batch-start" || body.action === "batch-resume") {
        args.push(body.action === "batch-start" ? "--approve" : "--run");
        if (body.autoNew && body.action === "batch-start") args.push("--auto-new");
        // Detached process survives a dashboard restart; OS locks prevent parallel batches.
        const child = spawn(path.join(root, ".venv", "bin", "python"), ["-m", "pipeline.recap.batch", ...args], {
          cwd: root, shell: false, detached: true, stdio: "ignore", env: process.env,
        });
        child.on("error", () => {}); child.unref();
        return NextResponse.json({started:true});
      }
      const output = await worker(args, body.action === "batch-edit" ? body : undefined, true);
      return NextResponse.json(JSON.parse(output.trim().split("\n").at(-1)!));
    }
    const directory = await project(body.id);
    if (!["generate", "regenerate", "rerender", "review", "upload"].includes(body.action)) throw new Error("Invalid action");
    if (["regenerate", "review"].includes(body.action) && !pieces.includes(body.piece)) throw new Error("Invalid piece");
    const args = [body.action, "--id", body.id];
    if (body.excludeScene !== undefined) {
      if (body.action !== "rerender" || !Number.isInteger(body.excludeScene) || body.excludeScene < 0) throw new Error("Invalid excluded scene");
      args.push("--exclude-scene", String(body.excludeScene));
    }
    if (body.piece && !pieces.includes(body.piece)) throw new Error("Invalid piece");
    if (body.piece) args.push("--piece", body.piece);
    if (body.action !== "review") {
      // Atomically reserve a launch. Python holds the project lock throughout work.
      const launch = path.join(directory, "launch");
      const handle = await fs.open(launch, "wx").catch(() => { throw new Error("Project is busy"); });
      await handle.close();
      void worker(args).catch(() => {}).finally(() => fs.unlink(launch).catch(() => {}));
      return NextResponse.json({ started: true });
    }
    await worker(args, body);
    return NextResponse.json({ saved: true });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Invalid request" }, { status: 400 });
  }
}
