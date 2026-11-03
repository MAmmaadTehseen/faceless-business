"use client";
import {useState, useEffect} from "react";
type Film = {id?:string; filename:string; normalized_title?:string; year?:number; status:string; title_warning?:boolean; project_id?:string};
type Report = {films:Film[]; estimate_usd:number; note:string};
export default function Batch() {
  const [folder,setFolder]=useState("");
  const [report,setReport]=useState<Report>();
  const [autoNew,setAutoNew]=useState(false);
  const [error,setError]=useState("");
  async function action(action:string, extra:object={}) {
    try {
      const r=await fetch("/api/recap",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action,folder,autoNew,...extra})});
      const data=await r.json(); if (!r.ok) throw new Error(data.error);
      if (data.films) setReport(data); setError("");
    } catch(e) {setError(String(e));}
  }
  useEffect(()=>{const saved=localStorage.getItem("recap-folder"); if(saved) setFolder(saved);},[]);
  useEffect(()=>{if(!report)return; const t=setInterval(()=>void action("scan"),5000);return()=>clearInterval(t);},[report,folder]); // eslint-disable-line react-hooks/exhaustive-deps
  return <details><summary>Scan folder / batch review queue</summary>
    <label>Absolute folder <input value={folder} onChange={e=>{setFolder(e.target.value);setReport(undefined);localStorage.setItem("recap-folder",e.target.value);}}/></label>
    <button className="btn" onClick={()=>action("scan")}>Scan folder</button>
    {error&&<p role="alert">{error}</p>}
    {report&&<><p>Batch estimate: ${report.estimate_usd.toFixed(2)}. {report.note}</p>
      <label><input type="checkbox" checked={autoNew} onChange={e=>setAutoNew(e.target.checked)}/>Allow new eligible files on later batch runs after this approval (additional costs)</label>
      <button className="btn" onClick={()=>action("batch-start")}>Approve estimate and process sequentially</button>
      <button className="btn" onClick={()=>action("batch-resume")}>Resume approved batch</button>
      <p>Missing rights and possible duplicates wait. Failures require Retry and renewed cost approval. Reopen this folder after a restart and Resume.</p>
      {report.films.map((film,i)=><section key={film.id||i} style={{borderBottom:"1px solid #777",padding:12}}>
        <p>{film.filename} · {film.status} {film.title_warning&&"· Warning: title already reviewed on this channel"}</p>
        {film.project_id&&<a href={`/recap?id=${film.project_id}`}>Open review / approve / upload</a>}
        {film.status==="possible duplicate"&&<><button className="btn" onClick={()=>action("batch-edit",{id:film.id,decision:"confirm"})}>Confirm different film</button><button className="btn" onClick={()=>action("batch-edit",{id:film.id,decision:"skip"})}>Skip</button></>}
        {film.status==="failed"&&film.id&&<button className="btn" onClick={()=>action("batch-edit",{id:film.id,retry:true})}>Retry (approve estimate again)</button>}
        {film.status==="needs rights"&&<form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void action("batch-edit",{id:film.id,rights:{basis:f.get("basis"),licence:f.get("licence"),url:f.get("url"),note:f.get("note")}});}}>
          <p>Rights apply to this film only. Title/year must be present in its filename.</p>
          <select name="basis" required><option value="">Rights basis</option>{["public domain","Creative Commons","written permission","own work"].map(v=><option key={v}>{v}</option>)}</select>
          <input name="licence" placeholder="CC licence"/><input name="url" placeholder="CC licence URL"/><input name="note" placeholder="Written permission note"/>
          <button className="btn">Save film rights</button>
        </form>}
      </section>)}
    </>}
  </details>;
}
