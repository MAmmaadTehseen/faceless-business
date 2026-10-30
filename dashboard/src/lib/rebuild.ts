import 'server-only';
const base = 'https://api.github.com/repos/MAmmaadTehseen/faceless-business/actions';
async function get(path: string) {
  const r = await fetch(`${base}/${path}`, {cache:'no-store', headers:{Authorization:`Bearer ${process.env.GITHUB_TOKEN}`, Accept:'application/vnd.github+json'}});
  if (!r.ok) throw new Error(`Artifact lookup failed (${r.status})`);
  return r;
}
// ZIP central-directory names can be inspected without decompressing media.
export function zipNames(data: Buffer) {
  const names: string[] = [];
  for (let i = 0; i + 46 <= data.length; i++) {
    if (data.readUInt32LE(i) !== 0x02014b50) continue;
    const n = data.readUInt16LE(i + 28), extra = data.readUInt16LE(i + 30), comment = data.readUInt16LE(i + 32);
    names.push(data.subarray(i + 46, i + 46 + n).toString());
    i += 45 + n + extra + comment;
  }
  return names;
}
export async function rebuildArtifact(content: {id:string; qa_notes?:string | null}) {
  let notes: {artifact_run_id?:string; artifact_name?:string} = {};
  try { notes = JSON.parse(content.qa_notes || '{}'); } catch {}
  const runs = await (await get('workflows/produce.yml/runs?per_page=100')).json();
  const ids = [...new Set([notes.artifact_run_id, ...runs.workflow_runs.map((r:{id:number}) => String(r.id))].filter(Boolean))];
  for (const id of ids) {
    const j = await (await get(`runs/${id}/artifacts?per_page=100`)).json();
    for (const a of j.artifacts) {
      if (a.expired || !a.name.startsWith(`videos-${content.id.split('-')[0]}-`) || (a.expires_at && Date.parse(a.expires_at) <= Date.now())) continue;
      const data = Buffer.from(await (await get(`artifacts/${a.id}/zip`)).arrayBuffer());
      if (zipNames(data).some(n => n.startsWith(`out/${content.id}/`) || n.startsWith(`${content.id}/`))) return {runId:String(id), name:a.name};
    }
  }
  return null;
}
