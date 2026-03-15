export type ContentStatus = "pending" | "processed" | "approved" | "published" | "failed";

export interface ContentItem {
  id: number;
  source_url: string;
  source_domain?: string | null;
  original_text: string;
  hebrew_draft?: string | null;
  content_type: string;
  status: ContentStatus;
  trend_topic?: string | null;
  copy_count: number;
  scheduled_at?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface ContentListResponse {
  items: ContentItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface BriefStory {
  title: string;
  summary: string;
  sources: string[];
  source_urls: string[];
  source_count: number;
  published_at?: string | null;
  relevance_score?: number;
}

export interface BriefTheme {
  name: string;
  emoji: string;
  takeaway: string;
  stories: BriefStory[];
}

export interface BriefResponse {
  themes: BriefTheme[];
  stories: BriefStory[];
  generated_at?: string | null;
}

export interface Variant {
  angle: string;
  label: string;
  content: string;
  char_count: number;
  is_valid_hebrew: boolean;
  quality_score: number;
}

export interface GeneratePostResponse {
  variants: Variant[];
}

export interface InspirationAccount {
  id: number;
  username: string;
  display_name?: string | null;
  category?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface InspirationPost {
  id: number;
  account_id: number;
  x_post_id: string;
  content?: string | null;
  post_url?: string | null;
  likes: number;
  retweets: number;
  views: number;
  posted_at?: string | null;
  fetched_at: string;
}

export interface InspirationSearchResponse {
  posts: InspirationPost[];
  cached: boolean;
  query: string;
}

export interface StyleExample {
  id: number;
  content: string;
  source_type: string;
  source_url?: string | null;
  topic_tags?: string[] | null;
  word_count: number;
  is_active: boolean;
  approval_count: number;
  rejection_count: number;
  created_at: string;
}

export interface AlertContent {
  title: string;
  summary: string;
  sources: string[];
  source_count: number;
  url?: string | null;
}

export interface AlertItem {
  id: number;
  type: string;
  content: AlertContent;
  delivered: boolean;
  delivered_at?: string | null;
  created_at: string;
}

export interface AlertsResponse {
  alerts: AlertItem[];
}
