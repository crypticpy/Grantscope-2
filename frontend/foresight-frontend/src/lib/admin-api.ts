/**
 * Admin API Client
 *
 * API functions for the GrantScope2 administration panel.
 * All endpoints require admin or service_role authentication.
 * Follows the existing codebase pattern: native fetch() with API_BASE_URL,
 * token passed in Authorization header.
 *
 * @module lib/admin-api
 */

import { API_BASE_URL } from "./config";

// ============================================================================
// Types -- Settings
// ============================================================================

/** A single system setting record. */
export interface SystemSetting {
  key: string;
  value: unknown;
  description: string | null;
  updated_at: string | null;
}

// ============================================================================
// Types -- Users
// ============================================================================

/** Admin view of a user record. */
export interface AdminUser {
  id: string;
  email: string;
  display_name: string | null;
  department: string | null;
  role: string;
  title: string | null;
  bio: string | null;
  created_at: string;
  last_sign_in_at: string | null;
  profile_completed_at: string | null;
}

/** Payload for creating a new user. */
export interface CreateUserData {
  email: string;
  password: string;
  display_name?: string;
  department?: string;
  role?: string;
}

// ============================================================================
// Types -- Monitoring
// ============================================================================

/** System health summary. */
export interface SystemHealth {
  database: { status: string; latency_ms: number };
  counts: {
    cards: number;
    cards_active: number;
    sources: number;
    users: number;
    research_tasks: number;
    discovery_runs: number;
    workstreams: number;
  };
  worker: {
    queue_depth: {
      queued: number;
      processing: number;
      completed_24h: number;
      failed_24h: number;
    };
    last_completed: string | null;
  };
  embeddings: {
    cards_with_embedding: number;
    cards_without_embedding: number;
    coverage_pct: number;
  };
  descriptions: {
    missing: number;
    thin: number;
    short: number;
    adequate: number;
    comprehensive: number;
  };
}

/** Database statistics. */
export interface DbStats {
  tables: Array<{
    name: string;
    row_count: number;
    total_size: string;
    index_size: string;
  }>;
  total_size: string;
  connection_pool: {
    size: number;
    checked_out: number;
    overflow: number;
  };
}

// ============================================================================
// Types -- Jobs
// ============================================================================

/** A background job record. */
export interface AdminJob {
  id: string;
  task_type: string;
  status: string;
  card_id: string | null;
  card_name: string | null;
  user_id: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/** Query parameters for job listing. */
export interface JobQueryParams {
  status?: string;
  task_type?: string;
  limit?: number;
  offset?: number;
}

/** Aggregated job statistics. */
export interface JobStats {
  by_status: {
    queued: number;
    processing: number;
    completed: number;
    failed: number;
  };
  by_type: {
    update: number;
    deep_research: number;
    workstream_analysis: number;
    card_analysis: number;
  };
  completed_24h: number;
  failed_24h: number;
  avg_duration_seconds: number | null;
}

// ============================================================================
// Types -- Taxonomy
// ============================================================================

/** Full taxonomy data set. */
export interface TaxonomyData {
  pillars: TaxonomyItem[];
  goals: TaxonomyGoal[];
  anchors: TaxonomyItem[];
  stages: TaxonomyItem[];
}

/** A taxonomy item (pillar, anchor, stage). */
export interface TaxonomyItem {
  id: string;
  name: string;
  code?: string;
  description?: string;
  color?: string;
  sort_order?: number;
}

/** A taxonomy goal, linked to a pillar. */
export interface TaxonomyGoal {
  id: string;
  pillar_id: string;
  name: string;
  description?: string;
  sort_order?: number;
}

// ============================================================================
// Types -- Content
// ============================================================================

/** Content statistics summary. */
export interface ContentStats {
  description_quality: {
    missing: number;
    thin: number;
    short: number;
    adequate: number;
    comprehensive: number;
    total: number;
  };
  embedding_coverage: {
    with_embedding: number;
    without_embedding: number;
    total: number;
  };
  by_status: Record<string, number>;
  by_pillar: Record<string, number>;
  by_origin: Record<string, number>;
  average_scores: {
    impact: number | null;
    relevance: number | null;
    alignment: number | null;
  };
}

/** Description quality distribution. */
export interface DescriptionQuality {
  missing: number;
  thin: number;
  short: number;
  adequate: number;
  comprehensive: number;
  total: number;
}

/** Result of a description enrichment operation. */
export interface EnrichmentResult {
  enriched: number;
  skipped: number;
  errors: number;
}

/** Parameters for purging cards. */
export interface PurgeParams {
  max_age_days: number;
  min_quality_score?: number;
  dry_run?: boolean;
}

/** Result of a card purge operation. */
export interface PurgeResult {
  affected_count: number;
  dry_run: boolean;
  criteria: Record<string, unknown>;
}

// ============================================================================
// Types -- Discovery
// ============================================================================

/** Discovery pipeline configuration. */
export interface DiscoveryConfig {
  settings: Record<string, unknown>;
  defaults: Record<string, unknown>;
}

/** A single discovery run record. */
export interface DiscoveryRun {
  id: string;
  status: string;
  triggered_by: string | null;
  started_at: string | null;
  completed_at: string | null;
  stats: {
    queries_generated: number | null;
    sources_found: number | null;
    sources_relevant: number | null;
    cards_created: number | null;
    cards_enriched: number | null;
    cards_deduplicated: number | null;
  };
  estimated_cost: number | null;
  error_message: string | null;
  created_at: string | null;
}

/** A blocked discovery topic. */
export interface DiscoveryBlock {
  id: string;
  topic: string;
  reason: string | null;
  block_type: string;
  keywords: string[] | null;
  is_active: boolean;
  blocked_by_count: number;
  first_blocked_at: string | null;
  last_blocked_at: string | null;
  created_at: string | null;
}

// ============================================================================
// Types -- Sources
// ============================================================================

/** Source configuration. */
export interface SourceConfig {
  search_provider: unknown;
  online_search_enabled: unknown;
  max_results: unknown;
  timeout_seconds: unknown;
  source_weights: unknown;
  dedup_threshold: unknown;
  source_categories: unknown;
  max_sources_per_run: unknown;
}

/** Source health status. */
export interface SourceHealthStatus {
  providers: Array<{
    name: string;
    status: "healthy" | "degraded" | "offline";
    message: string;
  }>;
}

// ============================================================================
// Types -- RSS
// ============================================================================

/** An RSS feed record. */
export interface RssFeed {
  id: string;
  url: string;
  name: string;
  category: string;
  pillar_id: string | null;
  check_interval_hours: number;
  status: string;
  last_checked_at: string | null;
  error_count: number;
  last_error: string | null;
  feed_title: string | null;
  articles_found_total: number;
  articles_matched_total: number;
  created_at: string;
  updated_at: string;
}

/** Payload for creating an RSS feed. */
export interface RssFeedCreate {
  url: string;
  name: string;
  category?: string;
  pillar_id?: string | null;
  check_interval_hours?: number;
}

// ============================================================================
// Types -- AI
// ============================================================================

/** AI model configuration. */
export interface AiConfig {
  model_deployment: string | null;
  temperature: unknown;
  max_tokens: unknown;
  max_tool_rounds: unknown;
  max_online_searches: unknown;
  chat_rate_limit: unknown;
  embedding_deployment: string | null;
  mini_deployment: string | null;
}

/** AI usage period stats. */
export interface AiUsagePeriod {
  total: number;
  completed: number;
  failed: number;
  by_type: Record<string, number>;
}

/** AI usage statistics. */
export interface AiUsageStats {
  period_24h: AiUsagePeriod;
  period_7d: AiUsagePeriod;
  period_30d: AiUsagePeriod;
}

// ============================================================================
// Types -- Scheduler
// ============================================================================

/** A scheduled job definition. */
export interface SchedulerJob {
  id: string;
  name: string;
  trigger: string;
  schedule: string;
  enabled: boolean;
  last_run: string | null;
  next_run: string | null;
  status: string;
}

/** Scheduler global status. */
export interface SchedulerStatus {
  running: boolean;
  jobs_count: number;
  uptime_seconds: number;
}

// ============================================================================
// Types -- Quality
// ============================================================================

/** Quality score distribution across tiers. */
export interface QualityDistribution {
  high: number;
  moderate: number;
  low: number;
  unscored: number;
  total: number;
  avg_score: number;
}

/** Quality scoring weight configuration. */
export interface QualityWeights {
  source_authority: number;
  source_diversity: number;
  corroboration: number;
  recency: number;
  municipal_specificity: number;
}

// ============================================================================
// Types -- Notifications
// ============================================================================

/** Notification system configuration. */
export interface NotificationConfig {
  email_enabled: boolean;
  digest_enabled: boolean;
  smtp_configured: boolean;
  default_frequency: string;
}

/** Summary of user notification preferences. */
export interface NotificationPreferencesSummary {
  total_users: number;
  daily_count: number;
  weekly_count: number;
  none_count: number;
}

// ============================================================================
// API Helper
// ============================================================================

/**
 * Generic admin API request helper with authentication.
 *
 * @param path - API endpoint path (without base URL, e.g. "/api/v1/admin/settings")
 * @param token - Bearer auth token (gs2_token)
 * @param options - Fetch options (method, body, headers, etc.)
 * @returns Typed response from the API
 * @throws {Error} With message from API response or generic error
 */
async function adminFetch<T>(
  path: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ message: "Request failed" }));
    throw new Error(
      error.message || error.detail || `Admin API error: ${response.status}`,
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// ============================================================================
// Settings
// ============================================================================

/** Fetch all system settings. Admin only. */
export async function fetchSettings(token: string): Promise<SystemSetting[]> {
  return adminFetch<SystemSetting[]>("/api/v1/admin/settings", token);
}

/** Update a single system setting. Admin only. */
export async function updateSetting(
  token: string,
  key: string,
  value: unknown,
  description?: string,
): Promise<void> {
  await adminFetch<unknown>(`/api/v1/admin/settings/${key}`, token, {
    method: "PUT",
    body: JSON.stringify({
      value,
      ...(description !== undefined ? { description } : {}),
    }),
  });
}

// ============================================================================
// Users
// ============================================================================

/** Fetch all users. Admin only. */
export async function fetchUsers(token: string): Promise<AdminUser[]> {
  const data = await adminFetch<{
    users: AdminUser[];
    total: number;
    page: number;
    page_size: number;
  }>("/api/v1/admin/users", token);
  return data.users;
}

/** Create a new user. Admin only. */
export async function createUser(
  token: string,
  data: CreateUserData,
): Promise<AdminUser> {
  return adminFetch<AdminUser>("/api/v1/admin/users", token, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** Update an existing user. Admin only. */
export async function updateUser(
  token: string,
  userId: string,
  data: Partial<AdminUser>,
): Promise<AdminUser> {
  return adminFetch<AdminUser>(`/api/v1/admin/users/${userId}`, token, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/** Reset a user's password. Admin only. */
export async function resetUserPassword(
  token: string,
  userId: string,
  password: string,
): Promise<void> {
  await adminFetch<unknown>(
    `/api/v1/admin/users/${userId}/reset-password`,
    token,
    {
      method: "POST",
      body: JSON.stringify({ new_password: password }),
    },
  );
}

// ============================================================================
// Monitoring
// ============================================================================

/** Fetch system health status. Admin only. */
export async function fetchSystemHealth(token: string): Promise<SystemHealth> {
  return adminFetch<SystemHealth>("/api/v1/admin/monitoring/health", token);
}

/** Fetch database statistics. Admin only. */
export async function fetchDbStats(token: string): Promise<DbStats> {
  return adminFetch<DbStats>("/api/v1/admin/monitoring/db-stats", token);
}

// ============================================================================
// Jobs
// ============================================================================

/** Fetch background jobs with optional filtering. Admin only. */
export async function fetchJobs(
  token: string,
  params?: JobQueryParams,
): Promise<AdminJob[]> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.append("status", params.status);
  if (params?.task_type) searchParams.append("task_type", params.task_type);
  if (params?.limit !== undefined)
    searchParams.append("page_size", String(params.limit));
  if (params?.offset !== undefined)
    searchParams.append("page", String(params.offset + 1));
  const qs = searchParams.toString();
  const data = await adminFetch<{
    jobs: AdminJob[];
    total: number;
    page: number;
    page_size: number;
  }>(`/api/v1/admin/jobs${qs ? `?${qs}` : ""}`, token);
  return data.jobs;
}

/** Fetch aggregated job statistics. Admin only. */
export async function fetchJobStats(token: string): Promise<JobStats> {
  return adminFetch<JobStats>("/api/v1/admin/jobs/stats", token);
}

/** Retry a failed job. Admin only. */
export async function retryJob(token: string, taskId: string): Promise<void> {
  await adminFetch<unknown>(`/api/v1/admin/jobs/${taskId}/retry`, token, {
    method: "POST",
  });
}

/** Cancel a queued or running job. Admin only. */
export async function cancelJob(token: string, taskId: string): Promise<void> {
  await adminFetch<unknown>(`/api/v1/admin/jobs/${taskId}/cancel`, token, {
    method: "POST",
  });
}

/** Retry all failed jobs. Admin only. */
export async function retryAllFailed(
  token: string,
): Promise<{ retried: number }> {
  return adminFetch<{ retried: number }>(
    "/api/v1/admin/jobs/retry-all-failed",
    token,
    { method: "POST" },
  );
}

// ============================================================================
// Taxonomy
// ============================================================================

/** Fetch all taxonomy data (pillars, goals, anchors, stages). */
export async function fetchTaxonomy(token: string): Promise<TaxonomyData> {
  return adminFetch<TaxonomyData>("/api/v1/taxonomy", token);
}

/** Create a new pillar. Admin only. */
export async function createPillar(
  token: string,
  data: Partial<TaxonomyItem>,
): Promise<TaxonomyItem> {
  return adminFetch<TaxonomyItem>("/api/v1/admin/taxonomy/pillars", token, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** Update a pillar. Admin only. */
export async function updatePillar(
  token: string,
  id: string,
  data: Partial<TaxonomyItem>,
): Promise<TaxonomyItem> {
  return adminFetch<TaxonomyItem>(
    `/api/v1/admin/taxonomy/pillars/${id}`,
    token,
    { method: "PATCH", body: JSON.stringify(data) },
  );
}

/** Delete a pillar. Admin only. */
export async function deletePillar(token: string, id: string): Promise<void> {
  await adminFetch<unknown>(`/api/v1/admin/taxonomy/pillars/${id}`, token, {
    method: "DELETE",
  });
}

/** Create a new goal. Admin only. */
export async function createGoal(
  token: string,
  data: Partial<TaxonomyGoal>,
): Promise<TaxonomyGoal> {
  return adminFetch<TaxonomyGoal>("/api/v1/admin/taxonomy/goals", token, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** Update a goal. Admin only. */
export async function updateGoal(
  token: string,
  id: string,
  data: Partial<TaxonomyGoal>,
): Promise<TaxonomyGoal> {
  return adminFetch<TaxonomyGoal>(`/api/v1/admin/taxonomy/goals/${id}`, token, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/** Delete a goal. Admin only. */
export async function deleteGoal(token: string, id: string): Promise<void> {
  await adminFetch<unknown>(`/api/v1/admin/taxonomy/goals/${id}`, token, {
    method: "DELETE",
  });
}

// ============================================================================
// Content
// ============================================================================

/** Fetch content statistics. Admin only. */
export async function fetchContentStats(token: string): Promise<ContentStats> {
  return adminFetch<ContentStats>("/api/v1/admin/content/stats", token);
}

/** Fetch description quality distribution. Admin only. */
export async function fetchDescriptionQuality(
  token: string,
): Promise<DescriptionQuality> {
  return adminFetch<DescriptionQuality>(
    "/api/v1/admin/description-quality",
    token,
  );
}

/** Trigger description enrichment. Admin only. */
export async function enrichDescriptions(
  token: string,
  maxCards?: number,
  threshold?: number,
): Promise<EnrichmentResult> {
  const params = new URLSearchParams();
  if (maxCards !== undefined) params.append("max_cards", String(maxCards));
  if (threshold !== undefined)
    params.append("threshold_chars", String(threshold));
  const qs = params.toString();
  return adminFetch<EnrichmentResult>(
    `/api/v1/admin/enrich-descriptions${qs ? `?${qs}` : ""}`,
    token,
    { method: "POST" },
  );
}

/** Purge cards matching criteria. Admin only. */
export async function purgeCards(
  token: string,
  params: PurgeParams,
): Promise<PurgeResult> {
  return adminFetch<PurgeResult>("/api/v1/admin/content/purge", token, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

/** Bulk update card status. Admin only. */
export async function bulkUpdateStatus(
  token: string,
  cardIds: string[],
  status: string,
): Promise<void> {
  await adminFetch<unknown>("/api/v1/admin/content/bulk-status", token, {
    method: "POST",
    body: JSON.stringify({ card_ids: cardIds, new_status: status }),
  });
}

/** Trigger re-analysis of cards. Admin only. */
export async function reanalyzeCards(
  token: string,
  cardIds: string[],
): Promise<void> {
  await adminFetch<unknown>("/api/v1/admin/content/reanalyze", token, {
    method: "POST",
    body: JSON.stringify({ card_ids: cardIds }),
  });
}

/** Trigger a manual content scan. Admin only. */
export async function triggerScan(
  token: string,
): Promise<{ status: string; message: string; cards_queued: number }> {
  return adminFetch<{ status: string; message: string; cards_queued: number }>(
    "/api/v1/admin/scan",
    token,
    { method: "POST" },
  );
}

// ============================================================================
// Discovery
// ============================================================================

/** Fetch discovery pipeline configuration. Admin only. */
export async function fetchDiscoveryConfig(
  token: string,
): Promise<DiscoveryConfig> {
  return adminFetch<DiscoveryConfig>("/api/v1/admin/discovery/config", token);
}

/** Update discovery pipeline configuration. Admin only. */
export async function updateDiscoveryConfig(
  token: string,
  settings: Record<string, unknown>,
): Promise<void> {
  await adminFetch<unknown>("/api/v1/admin/discovery/config", token, {
    method: "PUT",
    body: JSON.stringify({ settings }),
  });
}

/** Fetch recent discovery runs. Admin only. */
export async function fetchDiscoveryRuns(
  token: string,
): Promise<DiscoveryRun[]> {
  const data = await adminFetch<{ runs: DiscoveryRun[]; total: number }>(
    "/api/v1/admin/discovery/runs",
    token,
  );
  return data.runs;
}

/** Trigger a new discovery run. Admin only. */
export async function triggerDiscovery(
  token: string,
): Promise<{ id: string; status: string; message: string }> {
  return adminFetch<{ id: string; status: string; message: string }>(
    "/api/v1/admin/discovery/trigger",
    token,
    { method: "POST" },
  );
}

/** Fetch blocked discovery topics. Admin only. */
export async function fetchDiscoveryBlocks(
  token: string,
): Promise<DiscoveryBlock[]> {
  const data = await adminFetch<{ blocks: DiscoveryBlock[]; total: number }>(
    "/api/v1/admin/discovery/blocks",
    token,
  );
  return data.blocks;
}

/** Add a blocked discovery topic. Admin only. */
export async function addDiscoveryBlock(
  token: string,
  topic: string,
): Promise<void> {
  await adminFetch<unknown>("/api/v1/admin/discovery/blocks", token, {
    method: "POST",
    body: JSON.stringify({ topic }),
  });
}

/** Remove a blocked discovery topic. Admin only. */
export async function removeDiscoveryBlock(
  token: string,
  blockId: string,
): Promise<void> {
  await adminFetch<unknown>(
    `/api/v1/admin/discovery/blocks/${blockId}`,
    token,
    { method: "DELETE" },
  );
}

// ============================================================================
// Sources
// ============================================================================

/** Fetch source configuration. Admin only. */
export async function fetchSourceConfig(token: string): Promise<SourceConfig> {
  return adminFetch<SourceConfig>("/api/v1/admin/sources/config", token);
}

/** Update source configuration. Admin only. */
export async function updateSourceConfig(
  token: string,
  config: Partial<SourceConfig>,
): Promise<void> {
  await adminFetch<unknown>("/api/v1/admin/sources/config", token, {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

/** Fetch source health status. Admin only. */
export async function fetchSourceHealth(
  token: string,
): Promise<SourceHealthStatus> {
  return adminFetch<SourceHealthStatus>("/api/v1/admin/sources/health", token);
}

// ============================================================================
// RSS
// ============================================================================

/** Fetch all RSS feeds. Admin only. */
export async function fetchRssFeeds(token: string): Promise<RssFeed[]> {
  const data = await adminFetch<{ feeds: RssFeed[]; total: number }>(
    "/api/v1/admin/rss/feeds",
    token,
  );
  return data.feeds;
}

/** Add a new RSS feed. Admin only. */
export async function addRssFeed(
  token: string,
  data: RssFeedCreate,
): Promise<RssFeed> {
  return adminFetch<RssFeed>("/api/v1/admin/rss/feeds", token, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** Update an RSS feed. Admin only. */
export async function updateRssFeed(
  token: string,
  feedId: string,
  data: Partial<RssFeed>,
): Promise<RssFeed> {
  return adminFetch<RssFeed>(`/api/v1/admin/rss/feeds/${feedId}`, token, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/** Delete an RSS feed. Admin only. */
export async function deleteRssFeed(
  token: string,
  feedId: string,
): Promise<void> {
  await adminFetch<unknown>(`/api/v1/admin/rss/feeds/${feedId}`, token, {
    method: "DELETE",
  });
}

/** Trigger a manual check of a specific RSS feed. Admin only. */
export async function checkRssFeed(
  token: string,
  feedId: string,
): Promise<void> {
  await adminFetch<unknown>(
    `/api/v1/admin/rss/feeds/${feedId}/check-now`,
    token,
    { method: "POST" },
  );
}

// ============================================================================
// AI
// ============================================================================

/** Fetch AI configuration. Admin only. */
export async function fetchAiConfig(token: string): Promise<AiConfig> {
  return adminFetch<AiConfig>("/api/v1/admin/ai/config", token);
}

/** Update AI configuration. Admin only. */
export async function updateAiConfig(
  token: string,
  config: Partial<AiConfig>,
): Promise<void> {
  await adminFetch<unknown>("/api/v1/admin/ai/config", token, {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

/** Fetch AI usage statistics. Admin only. */
export async function fetchAiUsage(token: string): Promise<AiUsageStats> {
  return adminFetch<AiUsageStats>("/api/v1/admin/ai/usage", token);
}

// ============================================================================
// Scheduler
// ============================================================================

/** Fetch all scheduler jobs. Admin only. */
export async function fetchSchedulerJobs(
  token: string,
): Promise<SchedulerJob[]> {
  return adminFetch<SchedulerJob[]>("/api/v1/admin/scheduler/jobs", token);
}

/** Toggle a scheduler job on or off. Admin only. */
export async function toggleSchedulerJob(
  token: string,
  jobId: string,
): Promise<void> {
  await adminFetch<unknown>(
    `/api/v1/admin/scheduler/jobs/${jobId}/toggle`,
    token,
    { method: "POST" },
  );
}

/** Trigger immediate execution of a scheduler job. Admin only. */
export async function triggerSchedulerJob(
  token: string,
  jobId: string,
): Promise<void> {
  await adminFetch<unknown>(
    `/api/v1/admin/scheduler/jobs/${jobId}/trigger`,
    token,
    { method: "POST" },
  );
}

/** Fetch scheduler global status. Admin only. */
export async function fetchSchedulerStatus(
  token: string,
): Promise<SchedulerStatus> {
  return adminFetch<SchedulerStatus>("/api/v1/admin/scheduler/status", token);
}

// ============================================================================
// Quality
// ============================================================================

/** Fetch quality score distribution across tiers. Admin only. */
export async function fetchQualityDistribution(
  token: string,
): Promise<QualityDistribution> {
  return adminFetch<QualityDistribution>(
    "/api/v1/admin/quality/distribution",
    token,
  );
}

/** Fetch quality scoring weight configuration. Admin only. */
export async function fetchQualityWeights(
  token: string,
): Promise<QualityWeights> {
  return adminFetch<QualityWeights>("/api/v1/admin/quality/weights", token);
}

/** Update quality scoring weights. Admin only. */
export async function updateQualityWeights(
  token: string,
  weights: QualityWeights,
): Promise<void> {
  await adminFetch<unknown>("/api/v1/admin/quality/weights", token, {
    method: "PUT",
    body: JSON.stringify(weights),
  });
}

/** Trigger recalculation of all quality scores. Admin only. */
export async function recalculateAllQuality(token: string): Promise<void> {
  await adminFetch<unknown>("/api/v1/admin/quality/recalculate-all", token, {
    method: "POST",
  });
}

// ============================================================================
// Notifications
// ============================================================================

/** Fetch notification system configuration. Admin only. */
export async function fetchNotificationConfig(
  token: string,
): Promise<NotificationConfig> {
  return adminFetch<NotificationConfig>(
    "/api/v1/admin/notifications/config",
    token,
  );
}

/** Fetch aggregated notification preferences summary. Admin only. */
export async function fetchNotificationPreferences(
  token: string,
): Promise<NotificationPreferencesSummary> {
  return adminFetch<NotificationPreferencesSummary>(
    "/api/v1/admin/notifications/preferences",
    token,
  );
}

/** Send a test notification email. Admin only. */
export async function sendTestEmail(token: string): Promise<void> {
  await adminFetch<unknown>("/api/v1/admin/notifications/test-email", token, {
    method: "POST",
  });
}
