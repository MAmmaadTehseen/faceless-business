export type Content = {
  id: string;
  kind: "long" | "short";
  parent_id: string | null;
  topic: string;
  title: string;
  qa_status: string;
  status: string;
  claude_cost_usd: number | null;
  created_at: string;
};

export type Publication = {
  id: number;
  content_id: string;
  platform: string;
  platform_id: string | null;
  url: string | null;
  privacy: string | null;
  status: string;
  published_at: string | null;
  error: string | null;
};

export type Metric = {
  id: number;
  publication_id: number;
  captured_at: string;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  ctr: number | null;
  avg_view_duration_sec: number | null;
  impressions: number | null;
};

export type Comment = {
  id: number;
  publication_id: number | null;
  platform: string;
  platform_comment_id: string;
  author: string | null;
  text: string;
  posted_at: string | null;
  flagged: boolean;
  flag_reason: string | null;
  draft_reply: string | null;
  reply_status: string;
  liked: boolean;
};

export type TopicQueueRow = {
  id: number;
  topic: string;
  source_url: string | null;
  source_headline: string | null;
  priority: number;
  status: string;
  added_by: string;
  created_at: string;
};

export type Cost = {
  id: number;
  at: string;
  step: string;
  content_id: string | null;
  model: string | null;
  usd: number | null;
};

export type Run = {
  id: number;
  started_at: string;
  finished_at: string | null;
  workflow: string | null;
  status: string | null;
  log: string | null;
};

export type Settings = {
  pipeline_paused: boolean;
  long_videos_per_run: number;
  shorts_per_long: number;
  auto_reply: { youtube: boolean; instagram: boolean; facebook: boolean };
  auto_like: { facebook: boolean };
  max_replies_per_day: number;
  reply_tone_notes: string;
  monthly_budget_usd: number;
  publish_privacy: "private" | "public";
  niche_keywords: string[];
  tts_voice: string;
};

export const DEFAULT_SETTINGS: Settings = {
  pipeline_paused: false,
  long_videos_per_run: 1,
  shorts_per_long: 2,
  auto_reply: { youtube: true, instagram: true, facebook: true },
  auto_like: { facebook: true },
  max_replies_per_day: 40,
  reply_tone_notes: "",
  monthly_budget_usd: 95,
  publish_privacy: "private",
  niche_keywords: [],
  tts_voice: "",
};
