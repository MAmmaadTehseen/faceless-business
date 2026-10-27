"use client";
import { useState } from "react";
import { Comment } from "@/lib/types";
import { fmtDate } from "@/lib/format";

export function InboxItem({ comment, videoTitle }: { comment: Comment; videoTitle: string }) {
  const [text, setText] = useState(comment.draft_reply ?? "");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [liked, setLiked] = useState(comment.liked);

  async function call(action: "reply" | "skip" | "like") {
    setBusy(action);
    setError("");
    const res = await fetch(`/api/comments/${comment.id}/${action}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: action === "reply" ? JSON.stringify({ text }) : undefined,
    });
    setBusy(null);
    const json = await res.json().catch(() => ({}));
    if (!res.ok) return setError(json.error ?? `Failed (${res.status})`);
    if (action === "like") setLiked(true);
    else setDone(action === "reply" ? "sent" : "skipped");
  }

  if (done) return null;

  return (
    <div className="card space-y-2">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
        <span className="badge">{comment.platform}</span>
        <span className="truncate font-medium text-fg">{videoTitle || "(unknown video)"}</span>
        <span>{fmtDate(comment.posted_at)}</span>
        {comment.flagged && (
          <span className="badge border-red-500/60 bg-red-500/10 text-red-500" title={comment.flag_reason ?? ""}>
            flagged{comment.flag_reason ? `: ${comment.flag_reason}` : ""}
          </span>
        )}
        {liked && <span className="badge">liked</span>}
      </div>
      <p className="text-sm"><b>{comment.author ?? "anon"}</b>: {comment.text}</p>
      <textarea
        className="w-full"
        rows={3}
        value={text}
        placeholder="Reply..."
        onChange={(e) => setText(e.target.value)}
      />
      {error && <p className="text-xs text-red-500">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" disabled={!!busy || !text.trim()} onClick={() => call("reply")}>
          {busy === "reply" ? "Sending..." : "Send"}
        </button>
        <button className="btn" disabled={!!busy} onClick={() => call("skip")}>Skip</button>
        <button className="btn" disabled={!!busy || comment.platform !== "facebook" || liked} onClick={() => call("like")}>
          {busy === "like" ? "..." : liked ? "Liked" : "Like"}
        </button>
      </div>
    </div>
  );
}
