"use client";
import { toast } from "./Toast";
import { RelativeTime } from "./RelativeTime";
import { PlatformIcon } from "./PlatformIcon";
import { channelMeta } from "@/lib/channels";
import { useState } from "react";
import { Comment } from "@/lib/types";
import { fmtDate } from "@/lib/format";

export function InboxItem({
  comment,
  videoTitle,
  owner,
  channel,
  url,
}: {
  comment: Comment;
  videoTitle: string;
  owner: boolean;
  channel?: string | null;
  url?: string;
}) {
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
      else setDone(action === "reply" ? "sent" : "skipped");
    } catch {
      setError("Could not reach the server. Try again.");
      toast("Action failed. Try again.");
    } finally {
      setBusy(null);
    }
  }

  if (done) return null;

  return (
    <div className="card space-y-2">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
        <PlatformIcon platform={comment.platform} />
        <span
          className="w-2 h-2 rounded-full"
          title={channelMeta(channel)?.name}
          style={{ background: channelMeta(channel)?.brand.fg }}
        />
        <span className="truncate font-medium text-fg">
          {videoTitle || "(unknown video)"}
        </span>
        <RelativeTime value={comment.posted_at} />
        {comment.flagged && (
          <span className="badge badge-alert" title={comment.flag_reason ?? ""}>
            flagged{comment.flag_reason ? `: ${comment.flag_reason}` : ""}
          </span>
        )}
        {url && (
          <a
            className="text-accent-fg"
            href={
              comment.platform === "youtube"
                ? `${url}&lc=${encodeURIComponent(comment.platform_comment_id)}`
                : url
            }
            target="_blank"
            rel="noreferrer"
          >
            Open on platform
          </a>
        )}
      </div>
      <p className="text-sm">
        <b>{comment.author ?? "anon"}</b>: {comment.text}
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
          </div>
        </>
      ) : null}
    </div>
  );
}
