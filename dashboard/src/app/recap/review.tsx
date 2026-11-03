"use client";
import { useEffect, useState } from "react";
import Batch from "./scan";

type Item = {title: string; description: string; segments: {text: string; scene: number}[]; approved: boolean; discarded: boolean; uploaded: boolean; duration?: number; qa?: {pass: boolean; issues: {text: string}[]}};
type Job = {id: string; status: string; stage: string; piece?: string; percent: number; error?: string; rights: Record<string,string>; plan: {estimate_usd: number; estimate_note: string}; items: Record<string,Item>};
export default function Recap() {
  const [job, setJob] = useState<Job>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [basis, setBasis] = useState("");
  useEffect(() => {
    const id = new URLSearchParams(location.search).get("id");
    if (id) fetch(`/api/recap?id=${id}`).then(r=>r.json()).then(j=>j.id && setJob(j));
  }, []);
  useEffect(() => {
    if (!job) return;
    const timer = setInterval(() => fetch(`/api/recap?id=${job.id}`).then(r=>r.json()).then(j => { if (j.id) setJob(j); }).catch(()=>{}), 2000);
    return () => clearInterval(timer);
  }, [job?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  async function action(payload: object) {
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/recap", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error);
      if (result.id) { setJob(result); history.replaceState(null,"",`/recap?id=${result.id}`); }
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }
  return <main style={{maxWidth:1000, margin:"2rem auto", padding:24}}>
    <h1>Local film review</h1>
    <Batch />
    <p>Rights basis is your responsibility. Source film audio is removed unless you select a low audio bed. Review all five pieces before uploading.</p>
    {error && <p role="alert">{error}</p>}
    {!job && <form onSubmit={e=>{
      e.preventDefault(); const f = new FormData(e.currentTarget);
      void action({action:"create",path:f.get("path"),title:f.get("title"),year:Number(f.get("year")),bed:Number(f.get("bed")),rights:{basis,licence:f.get("licence"),url:f.get("url"),note:f.get("note")}});
    }} style={{display:"grid",gap:16}}>
      <label>Absolute video file path <input name="path" required placeholder="/home/me/films/movie.mp4" /></label>
      <label>Film title <input name="title" required maxLength={200}/></label>
      <label>Year <input name="year" type="number" required min={1888} max={2100}/></label>
      <label>Rights basis <select required value={basis} onChange={e=>setBasis(e.target.value)}><option value="">Select rights basis</option>{["public domain","Creative Commons","written permission","own work"].map(v=><option key={v}>{v}</option>)}</select></label>
      {basis === "Creative Commons" && <><label>Licence <input name="licence" required/></label><label>Licence URL <input name="url" required type="url"/></label></>}
      {basis === "written permission" && <label>Permission note <textarea name="note" required/></label>}
      <label>Original film audio <select name="bed"><option value="0">Removed (default)</option><option value="0.04">Low bed (4%)</option></select></label>
      <button className="btn" disabled={busy}>Validate and estimate</button>
    </form>}
    {job && <>
      <p>Project: {job.id}</p><p>Rights: {Object.entries(job.rights).map(([k,v])=>`${k}: ${v}`).join(" · ")}</p>
      <p>Estimated generation cost: ${job.plan.estimate_usd.toFixed(2)}. {job.plan.estimate_note}</p>
      <p role="status" style={{fontSize:18,fontWeight:600}}>{job.status === "estimated" ? "Not started. Click the button below to begin." : job.status === "running" ? `Generating: ${job.stage} ${job.piece || ""} (${job.percent}%). You can leave this page open.` : job.status === "review" ? "Finished. Review each piece below, then upload." : job.status === "error" ? "Stopped with an error." : job.status}</p>{job.status === "running" && <progress max={100} value={job.percent} style={{width:"100%"}}/>}
      {job.error && <p role="alert">{job.error}</p>}
      {(job.status === "estimated" || job.status === "error") && <button className="btn btn-primary" disabled={busy} onClick={()=>action({action:"generate",id:job.id})}>{busy ? "Starting…" : `Start generating (about $${job.plan.estimate_usd.toFixed(2)})`}</button>}
      {Object.entries(job.items).map(([name,item])=><Piece key={name} name={name} item={item} job={job} disabled={busy || job.status === "running"} action={action}/>)}
      {job.status !== "estimated" && <button className="btn" disabled={busy || job.status === "running" || !Object.values(job.items).some(i=>i.approved && !i.discarded)} onClick={()=>action({action:"upload",id:job.id})}>Upload approved items privately with calendar schedule</button>}
      <p>Regeneration incurs additional cost and clears that piece’s approval. Upload retries reuse existing YouTube publications.</p>
    </>}
  </main>;
}
function Piece({name,item,job,disabled,action}:{name:string;item:Item;job:Job;disabled:boolean;action:(v:object)=>Promise<void>}) {
  const [title,setTitle] = useState(item.title), [description,setDescription] = useState(item.description);
  useEffect(()=>{setTitle(item.title);setDescription(item.description);},[item.title,item.description]);
  return <section style={{border:"1px solid #777",padding:16,margin:"24px 0"}}>
    <h2>{name} {item.approved ? "· Approved" : item.discarded ? "· Discarded" : "· Needs review"} {item.uploaded && "· Uploaded"}</h2>
    {item.duration && <><video controls preload="metadata" style={{maxWidth:"100%",maxHeight:500}} src={`/api/recap?id=${job.id}&file=${name}/video.mp4`}/><p><a href={`/api/recap?id=${job.id}&file=${name}/captions.srt`}>SRT captions</a></p></>}
    <p>QA: {item.qa ? (item.qa.pass ? "passed" : "blocked") : "pending"}</p>{item.qa?.issues.map((v,i)=><p key={i}>{v.text}</p>)}
    <details><summary>Read script</summary>{item.segments.map((s,i)=><p key={i}>{s.text}</p>)}</details>
    <label>Title <input value={title} maxLength={100} onChange={e=>setTitle(e.target.value)} disabled={item.uploaded}/></label>
    <label>Description <textarea value={description} maxLength={4900} onChange={e=>setDescription(e.target.value)} disabled={item.uploaded}/></label>
    <div style={{display:"flex",gap:16,flexWrap:"wrap"}}>
      <button className="btn" disabled={disabled || item.uploaded} onClick={()=>action({action:"review",id:job.id,piece:name,title,description})}>Save edits</button>
      <button className="btn" disabled={disabled || item.uploaded || !item.qa?.pass} onClick={()=>action({action:"review",id:job.id,piece:name,title,description,approved:true})}>Approve</button>
      <button className="btn" disabled={disabled || item.uploaded} onClick={()=>action({action:"review",id:job.id,piece:name,title,description,discarded:true})}>Discard</button>
      <button className="btn" disabled={disabled || item.uploaded} onClick={()=>action({action:"regenerate",id:job.id,piece:name})}>Regenerate this piece (paid)</button>
    </div>
  </section>;
}
