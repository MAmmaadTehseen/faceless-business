import "server-only";

const GRAPH = "https://graph.facebook.com/v21.0";

async function ytAccessToken(): Promise<string> {
  const { YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN } = process.env;
  if (!YT_CLIENT_ID || !YT_CLIENT_SECRET || !YT_REFRESH_TOKEN) throw new Error("YouTube OAuth env vars missing");
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: YT_CLIENT_ID,
      client_secret: YT_CLIENT_SECRET,
      refresh_token: YT_REFRESH_TOKEN,
      grant_type: "refresh_token",
    }),
  });
  const json = await res.json();
  if (!res.ok || !json.access_token) throw new Error(`YouTube token exchange failed: ${JSON.stringify(json)}`);
  return json.access_token as string;
}

async function metaPost(path: string, params: Record<string, string>): Promise<unknown> {
  const token = process.env.META_ACCESS_TOKEN;
  if (!token) throw new Error("META_ACCESS_TOKEN missing");
  const url = new URL(`${GRAPH}/${path}`);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  url.searchParams.set("access_token", token);
  const res = await fetch(url, { method: "POST" });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`Meta API error: ${JSON.stringify(json)}`);
  return json;
}

export async function replyToComment(platform: string, platformCommentId: string, text: string): Promise<void> {
  if (platform === "youtube") {
    const token = await ytAccessToken();
    const res = await fetch("https://www.googleapis.com/youtube/v3/comments?part=snippet", {
      method: "POST",
      headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
      body: JSON.stringify({ snippet: { parentId: platformCommentId, textOriginal: text } }),
    });
    if (!res.ok) throw new Error(`YouTube comments.insert failed: ${await res.text()}`);
    return;
  }
  if (platform === "instagram") {
    await metaPost(`${platformCommentId}/replies`, { message: text });
    return;
  }
  if (platform === "facebook") {
    await metaPost(`${platformCommentId}/comments`, { message: text });
    return;
  }
  throw new Error(`Replies not supported for platform "${platform}"`);
}

export async function likeComment(platform: string, platformCommentId: string): Promise<void> {
  if (platform !== "facebook") throw new Error("Like is only supported for facebook");
  await metaPost(`${platformCommentId}/likes`, {});
}
