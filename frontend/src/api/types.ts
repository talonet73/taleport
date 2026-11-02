// Mirrors backend/taleport/core/settings.py and secrets.py.

export const LANGUAGES = ['it', 'en', 'es'] as const
export type Language = (typeof LANGUAGES)[number]

export const THEMES = ['dark', 'light', 'system'] as const
export type ThemeSetting = (typeof THEMES)[number]

export const AI_MODES = ['chat', 'ollama', 'anthropic', 'openai', 'xai', 'perplexity', 'gemini'] as const
export type AiMode = (typeof AI_MODES)[number]

export const CHAT_SITES = ['claude', 'chatgpt', 'grok', 'perplexity'] as const
export type ChatSite = (typeof CHAT_SITES)[number]

export interface AppSettings {
  language: Language
  theme: ThemeSetting
  default_ai: AiMode
  scan_time: string
  start_with_windows: boolean
  close_to_tray: boolean
  first_run_completed: boolean
  ai_models: Record<string, string>
  ollama_url: string
  chat_site: ChatSite
  chat_prefill: boolean
  ai_auto_insights: boolean
}

// -- AI -----------------------------------------------------------------------------

export type ProviderId = Exclude<AiMode, 'chat'>

export interface ProviderStatus {
  id: ProviderId
  label: string
  model: string
  paid: boolean
  ready: boolean
  code: string | null
  models?: string[]
}

export interface ProvidersResponse {
  default: AiMode
  chat_site: ChatSite
  providers: ProviderStatus[]
}

export interface Handoff {
  site: ChatSite
  url: string
  prompt: string
  prefilled: boolean
  copied: boolean
}

/** Every AI feature answers with a result, or a handoff to the user's chat (+ why). */
export interface AiEnvelope<T> {
  mode: AiMode | 'xai'
  fallback?: string | null
  handoff?: Handoff
  result?: T
  updated?: number
  item_id?: number
  // generator
  batch_id?: string
  drafts?: Draft[]
  draft?: Draft
  truncated?: boolean
}

export interface TopicSuggestion {
  name: string
  description: string
  keywords: Partial<Record<Language, string[]>>
  exclude: string[]
  hashtags: string[]
  sources: WatchedSource[]
  audience: string
  tone: string
  platforms: Platform[]
}

// -- Drafts (mirrors backend/taleport/generator) -------------------------------------

export interface DraftContent {
  title: string
  hook: string
  text: string
  hashtags: string[]
  carousel: string[]
  outline: string[]
  thumbnail_idea: string
  script: { time: string; scene: string; voiceover: string }[]
}

export interface FactWarning {
  kind: 'number' | 'quote' | 'name'
  value: string
}

export interface Draft {
  id: number
  batch_id: string
  topic_id: number | null
  theme_id: number | null
  origin: 'theme' | 'long_content'
  source_label: string
  platform: Platform
  language: Language
  variant: number
  series_index: number | null
  content: DraftContent
  text: string
  edited: boolean
  sources: { title: string; url: string }[]
  fact_warnings: FactWarning[]
  image_idea: string
  image_prompt: string
  status: 'draft' | 'scheduled' | 'published'
  scheduled_at: string | null
  publication: { published_at: string; url: string | null } | null
  ai_mode: string
  created_at: string
}

export interface GenerationResult {
  batch_id: string
  drafts: Draft[]
  truncated?: boolean
}

export interface XReport {
  id: number
  created_at: string
  text: string
  via: 'chat' | 'api'
  citations: string[]
}

export interface AppStatus {
  version: string
  scan_running: boolean
  last_scan_at: string | null
  next_scan_at: string | null
  api_spend_month: number
  api_spend_currency: string
}

export const SECRET_NAMES = ['anthropic', 'openai', 'xai', 'perplexity', 'gemini', 'youtube'] as const
export type SecretName = (typeof SECRET_NAMES)[number]
export type SecretsStatus = Record<SecretName, boolean>

// -- Topics (mirrors backend/taleport/topics/models.py) --------------------------------

export const PLATFORMS = ['linkedin', 'instagram', 'facebook', 'youtube', 'tiktok'] as const
export type Platform = (typeof PLATFORMS)[number]

export const SOURCE_KINDS = ['rss', 'youtube_channel', 'subreddit'] as const
export type SourceKind = (typeof SOURCE_KINDS)[number]

export interface WatchedSource {
  kind: SourceKind
  value: string
}

export interface TopicData {
  name: string
  description: string
  active: boolean
  editions: string[]
  keywords: Partial<Record<Language, string[]>>
  exclude: string[]
  hashtags: string[]
  sources: WatchedSource[]
  audience: string
  tone: string
  platforms: Platform[]
  style_examples: string[]
}

export interface Topic extends TopicData {
  id: number
  position: number
  created_at: string
  updated_at: string
  items_today?: number
}

export interface Edition {
  code: string
  language: Language
  country: string
}

export interface TopicsMeta {
  max_topics: number
  max_style_examples: number
  editions: Edition[]
}

export interface CollectedItem {
  id: number
  source: ItemSource
  url: string
  title: string
  excerpt: string
  language: string | null
  publisher: string
  published_at: string | null
  metrics: Record<string, number | string>
  first_seen_at: string
}

// -- Scans --------------------------------------------------------------------------

export const ITEM_SOURCES = ['news', 'rss', 'youtube', 'reddit', 'trends', 'x_grok'] as const
export type ItemSource = (typeof ITEM_SOURCES)[number]

export type CellState = 'pending' | 'running' | 'done' | 'skipped' | 'error'

export interface ScanCell {
  source: ItemSource
  topic_id: number
  state: CellState
  found: number
  new: number
  code: string | null
  params: Record<string, unknown>
}

export interface ScanSnapshot {
  scan_id: number
  trigger: 'manual' | 'scheduled' | 'catchup'
  status: 'running' | 'completed' | 'partial' | 'failed' | 'cancelled'
  sources: ItemSource[]
  topics: { id: number; name: string }[]
  cells: ScanCell[]
}

// -- Analysis -----------------------------------------------------------------------

export type ThemeTrend = 'up' | 'down' | 'flat' | 'new'

export interface ThemeSummary {
  id: number
  topic_id: number
  day: string
  title: string
  summary: string | null
  origin: 'stats' | 'ai'
  score: number
  trend: ThemeTrend
  item_count: number
  sources: ItemSource[]
  related_terms: string[]
  question_count: number
  representative: { id: number; source: ItemSource; url: string; title: string; publisher: string } | null
  covered: boolean
}

export interface TodayOverview {
  day: string
  stats: {
    items_today: number
    themes_today: number
    posts_generated: number
    posts_published_week: number
  }
  topics: { topic: { id: number; name: string }; items_today: number; themes: ThemeSummary[] }[]
}

export interface ScoreDetails {
  today: number
  yesterday: number | null
  average: number | null
  days_observed: number
  sources: number
  components: { volume: number; growth: number; diversity: number; size: number }
}

export interface ThemeDetail extends ThemeSummary {
  topic: { id: number; name: string } | null
  key: string
  angle: string | null
  score_details: ScoreDetails
  questions: string[]
  items: CollectedItem[]
  x_reports: XReport[]
  trend7: { day: string; count: number }[]
}

export interface QuotaStatus {
  used: number
  limit: number
  remaining: number
  resets_at: string
}
