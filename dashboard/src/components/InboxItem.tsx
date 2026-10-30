"use client";
import { toast } from "./Toast";
import { RelativeTime } from "./RelativeTime";
import { useEffect, useRef, useState } from "react";
import { Comment } from "@/lib/types";
import { fmtDate } from "@/lib/format";

export function InboxItem({
  comment,
  videoTitle,
  owner,
  channel,
  url,
  contentId,
}: {
  comment: Comment;
  videoTitle: string;
  owner: boolean;
  channel?: string | null;
  url?: string;
  contentId?: string;
}) {
  const [open, setOpen] = useState(false);
  const drawer = useRef<HTMLElement>(null);
  const opener = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function keyboard(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
      if (e.key === "Tab") {
        const focusable = drawer.current?.querySelectorAll<HTMLElement>('button:not(:disabled), textarea, a[href]');
        if (!focusable?.length) return;
        const first = focusable[0], last = focusable[focusable.length-1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
    document.addEventListener("keydown", keyboard);
    return () => {document.body.style.overflow = previous; document.removeEventListener("keydown",keyboard); opener.current?.focus();};
  }, [open]);
  const [text, setText] = useState(comment.draft_reply ?? "");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [liked, setLiked] = useState(comment.liked);

  async function call(action: "reply" | "skip" | "like") {
    setBusy(action);
    setError("");
    try {
      const res = await fetch(`/api/comments/${comment.id}/${action}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: action === "reply" ? JSON.stringify({ text }) : undefined,
      });
      setBusy(null);
      const json = await res.json().catch(() => ({}));
      if (!res.ok) return setError(json.error ?? `Failed (${res.status})`);
      toast(
        action === "reply"
          ? "Reply sent"
          : action === "skip"
            ? "Comment skipped"
            : "Comment liked",
      );
      if (action === "like") setLiked(true);
      else { setOpen(false); setDone(action === "reply" ? "sent" : "skipped"); }
    } catch {
      setError("Could not reach the server. Try again.");
      toast("Action failed. Try again.");
    } finally {
      setBusy(null);
    }
  }

  if (done) return null;

  return (
    <div className={`inbox-conversation ${comment.reply_status === "sent" ? "inbox-replied" : ""}`}><span className="avatar" aria-hidden>{(comment.author ?? "A").slice(0,1).toUpperCase()}</span><div className="conversation-copy">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
        <span className="series-dot" title={comment.platform} style={{background:"var(--muted)"}}/>
        <span className="truncate font-medium text-fg">
          {comment.author ?? "Viewer"}
        </span>
        <RelativeTime value={comment.posted_at} />
        <span>{comment.platform}</span>
        {contentId && <a className="btn" href={`/content/${encodeURIComponent(contentId)}`}>View video →</a>}
        {comment.flagged && (
          <span className="status-chip badge-alert" title={comment.flag_reason ?? ""}>
            needs review
          </span>
        )}
        {url && <details className="row-details"><summary>Details</summary><p>{videoTitle || "Unknown video"}</p>
          <a
            className="text-muted"
            href={
              comment.platform === "youtube"
                ? `${url}&lc=${encodeURIComponent(comment.platform_comment_id)}`
                : url
            }
            target="_blank"
            rel="noreferrer"
          >
            Open on platform
          </a></details>
        }
      </div>
      <p className="text-sm conversation-preview">
        {comment.text}
      </p>
      {comment.reply_status === "sent" ? (
        <div className="border-l border-border pl-3 text-sm">
          <p>{comment.reply_text ?? "replied automatically"}</p>
          <span className="text-xs text-muted">
            replied {fmtDate(comment.reply_sent_at ?? null)} ·{" "}
            {comment.reply_text ? "owner" : "auto"}
          </span>
        </div>
      ) : owner &&
        ["new", "drafted", "failed"].includes(comment.reply_status) ? (
        <>
          <button ref={opener} className="btn" onClick={() => setOpen(true)}>Reply →</button>
          {open && <div className="reply-backdrop" onClick={() => setOpen(false)}><section ref={drawer} className="reply-drawer" role="dialog" aria-modal="true" aria-label="Reply to comment" onClick={e => e.stopPropagation()}><button autoFocus className="btn float-right" onClick={() => setOpen(false)}>Close ×</button><h2 className="text-base font-semibold">{comment.author ?? "Viewer"}</h2><p className="text-muted text-sm mt-6">{comment.text}</p>
          <textarea
            className="w-full"
            rows={3}
            value={text}
            placeholder="Reply..."
            onChange={(e) => setText(e.target.value)}
          />
          {error && <p className="text-xs text-alert-fg">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <button
              className="btn btn-primary"
              disabled={!!busy || !text.trim()}
              onClick={() => call("reply")}
            >
              {busy === "reply" ? "Sending..." : "Send"}
            </button>
            <button
              className="btn"
              disabled={!!busy}
              onClick={() => call("skip")}
            >
              Skip
            </button>
            <button
              className="btn"
              disabled={!!busy || comment.platform !== "facebook" || liked}
              onClick={() => call("like")}
            >
              {busy === "like" ? "..." : liked ? "Liked" : "Like"}
            </button>
          </div></section></div>}
        </>
      ) : null}
    </div></div>
  );
}
