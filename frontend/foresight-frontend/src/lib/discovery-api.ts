/**
 * Discovery API Helpers
 *
 * API functions for interacting with the discovery system backend.
 * Handles pending card reviews, bulk actions, discovery run management,
 * advanced search, saved searches, trend visualization, and card comparison.
 *
 * @module lib/discovery-api
 */

import { API_BASE_URL } from "./config";

/**
 * Base intelligence card interface.
 *
 * Represents the core data model for a strategic intelligence card
 * with all scoring dimensions and classification metadata.
 */
export interface Card {
  /** Unique card identifier (UUID) */
  id: string;
  /** Display name of the intelligence card */
  name: string;
  /** URL-friendly slug for routing */
  slug: string;
  /** Brief text summary of the card topic */
  summary: string;
  /** Associated strategic pillar code (e.g., 'CH', 'MC', 'HS') */
  pillar_id: string;
  /** Maturity stage identifier (1-8) */
  stage_id: string;
  /** Technology horizon classification */
  horizon: "H1" | "H2" | "H3";
  /** Novelty score (0-100) */
  novelty_score: number;
  /** Maturity score (0-100) */
  maturity_score: number;
  /** Impact score (0-100) */
  impact_score: number;
  /** Relevance score (0-100) */
  relevance_score: number;
  /** Velocity score (0-100) */
  velocity_score: number;
  /** Risk score (0-100) */
  risk_score: number;
  /** Opportunity score (0-100) */
  opportunity_score: number;
  /** ISO 8601 timestamp when the card was created */
  created_at: string;
  /** ISO 8601 timestamp when the card was last updated */
  updated_at?: string;
  /** Reference to an anchor card for derived cards */
  anchor_id?: string;
  /** CMO Top 25 priority alignment codes */
  top25_relevance?: string[];
  /** Card lifecycle status (e.g., 'active', 'pending_review', 'archived') */
  status: string;

  // Grant-specific fields
  deadline?: string | null;
  funding_amount_min?: number | null;
  funding_amount_max?: number | null;
  grantor?: string | null;
  eligibility_text?: string | null;
  grant_type?: string | null;
  source_url?: string | null;
  cfda_number?: string | null;
  category_id?: string | null;
  alignment_score?: number | null;
  grants_gov_id?: string | null;
  sam_opportunity_id?: string | null;
}

/**
 * Configuration for a discovery run.
 *
 * Optional parameters that constrain what the discovery pipeline searches for.
 * Stored alongside the run record for reproducibility.
 */
export interface DiscoveryRunConfig {
  /** Source types to include (e.g., 'rss', 'newsapi', 'tavily') */
  source_types?: string[];
  /** Strategic pillar codes to focus on (e.g., ['CH', 'MC']) */
  pillar_focus?: string[];
  /** Maximum number of cards to create in this run */
  max_cards?: number;
}

/**
 * Discovery run metadata.
 *
 * Tracks the execution and results of a single discovery pipeline run.
 * Matches the backend `DiscoveryRun` Pydantic model.
 */
export interface DiscoveryRun {
  /** Unique run identifier (UUID) */
  id: string;
  /** ISO 8601 timestamp when the run started */
  started_at: string;
  /** ISO 8601 timestamp when the run completed, or null if still running */
  completed_at: string | null;
  /** Current run status */
  status: "running" | "completed" | "failed" | "cancelled";
  /** How the run was initiated */
  triggered_by: "manual" | "scheduled" | "api";
  /** User ID of the user who triggered the run, or null for scheduled runs */
  triggered_by_user: string | null;
  /** Strategic pillars that were scanned in this run */
  pillars_scanned: string[] | null;
  /** Top 25 priorities that were scanned in this run */
  priorities_scanned: string[] | null;
  /** Number of search queries generated for this run */
  queries_generated: number | null;
  /** Total number of sources discovered */
  sources_found: number;
  /** Number of sources that passed relevance triage */
  sources_relevant: number | null;
  /** Number of new cards created from discovered sources */
  cards_created: number;
  /** Number of existing cards enriched with new information */
  cards_enriched: number;
  /** Number of duplicate cards detected and merged */
  cards_deduplicated: number;
  /** Estimated API cost for this run in USD */
  estimated_cost: number | null;
  /** Structured summary report with run statistics */
  summary_report: Record<string, unknown> | null;
  /** Human-readable error message if the run failed */
  error_message: string | null;
  /** Detailed error information for debugging */
  error_details: Record<string, unknown> | null;
  /** List of non-fatal error messages encountered during the run */
  errors?: string[];
  /** ISO 8601 timestamp when the run record was created */
  created_at: string | null;
  /** Run configuration parameters, populated for detailed run views */
  config?: DiscoveryRunConfig;
}

/**
 * A card pending human review from the discovery pipeline.
 *
 * Extends the base Card with discovery-specific metadata including
 * AI confidence, source provenance, and suggested edits.
 */
export interface PendingCard extends Card {
  /** AI confidence score for this card's classification (0-1) */
  ai_confidence: number;
  /** ISO 8601 timestamp when the card was discovered */
  discovered_at: string;
  /** URL of the primary source that generated this card */
  source_url?: string;
  /** Type of the source (e.g., 'rss', 'newsapi', 'tavily') */
  source_type?: string;
  /** ID of the discovery run that created this card */
  discovery_run_id?: string;
  /** AI-suggested field modifications for reviewer consideration */
  suggested_changes?: SuggestedChange[];
}

/**
 * An AI-suggested change to a card field.
 *
 * Generated during discovery when AI analysis identifies potential
 * improvements to card metadata for reviewer consideration.
 */
export interface SuggestedChange {
  /** The card field name to modify (e.g., 'pillar_id', 'stage_id') */
  field: string;
  /** Current value of the field */
  current: string;
  /** AI-suggested replacement value */
  suggested: string;
  /** Explanation of why this change is recommended */
  reason: string;
}

/**
 * Breakdown of the discovery score showing contribution from each scoring factor.
 *
 * Used to explain why a card was ranked at a particular position in the
 * personalized discovery queue.
 */
export interface ScoreBreakdown {
  /** Novelty component: higher for recently created or unseen cards (0-1) */
  novelty: number;
  /** Workstream relevance: match against user's active workstream filters (0-1) */
  workstream_relevance: number;
  /** Pillar alignment: match against user's active strategic pillars (0-1) */
  pillar_alignment: number;
  /** Followed context: similarity to cards the user has followed (0-1) */
  followed_context: number;
}

/**
 * A card with personalized discovery scoring for queue ranking.
 *
 * Extends the base Card with a composite discovery_score and optional
 * breakdown showing how each factor contributed to the ranking.
 */
export interface PersonalizedCard extends Card {
  /** Composite discovery score used for queue ordering (0-100) */
  discovery_score: number;
  /** Optional breakdown of the discovery score components */
  score_breakdown?: ScoreBreakdown;
}

/**
 * Review action types
 */
export type ReviewAction = "approve" | "reject" | "edit" | "defer";

/**
 * Dismiss reasons
 */
export type DismissReason =
  | "duplicate"
  | "irrelevant"
  | "low_quality"
  | "out_of_scope"
  | "already_exists"
  | "other";

// ============================================================================
// Advanced Search Types
// ============================================================================

/**
 * Date range filter for created_at/updated_at filtering.
 *
 * Both bounds are optional -- omitting either creates an open-ended range.
 */
export interface DateRange {
  /** Start date (inclusive) in ISO format YYYY-MM-DD */
  start?: string;
  /** End date (inclusive) in ISO format YYYY-MM-DD */
  end?: string;
}

/**
 * Min/max threshold for filtering a single score field.
 *
 * Both bounds are optional -- omitting either creates an open-ended range.
 */
export interface ScoreThreshold {
  /** Minimum score value (0-100, inclusive) */
  min?: number;
  /** Maximum score value (0-100, inclusive) */
  max?: number;
}

/**
 * Collection of score threshold filters for all seven scoring dimensions.
 *
 * Each threshold is optional -- only provided thresholds are applied.
 */
export interface ScoreThresholds {
  /** Impact score threshold filter */
  impact_score?: ScoreThreshold;
  /** Relevance score threshold filter */
  relevance_score?: ScoreThreshold;
  /** Novelty score threshold filter */
  novelty_score?: ScoreThreshold;
  /** Maturity score threshold filter */
  maturity_score?: ScoreThreshold;
  /** Velocity score threshold filter */
  velocity_score?: ScoreThreshold;
  /** Risk score threshold filter */
  risk_score?: ScoreThreshold;
  /** Opportunity score threshold filter */
  opportunity_score?: ScoreThreshold;
}

/**
 * Advanced search filters for intelligence cards.
 *
 * All filters are optional and combined with AND logic when applied.
 */
export interface SearchFilters {
  /** Filter by strategic pillar codes */
  pillar_ids?: string[];
  /** Filter by strategic goal identifiers */
  goal_ids?: string[];
  /** Filter by maturity stage identifiers */
  stage_ids?: string[];
  /** Filter by technology horizon, or 'ALL' for no horizon filter */
  horizon?: "H1" | "H2" | "H3" | "ALL";
  /** Filter by creation/update date range */
  date_range?: DateRange;
  /** Filter by score thresholds across dimensions */
  score_thresholds?: ScoreThresholds;
  /** Filter by card lifecycle status */
  status?: string;
}

/**
 * Request model for advanced card search.
 *
 * Supports both text-based and vector (semantic) search with optional filters.
 */
export interface AdvancedSearchRequest {
  /** Free-text search query */
  query?: string;
  /** Structured filters to apply */
  filters?: SearchFilters;
  /** Whether to use vector (semantic) search instead of text search */
  use_vector_search?: boolean;
  /** Maximum number of results to return */
  limit?: number;
  /** Number of results to skip for pagination */
  offset?: number;
}

/**
 * Individual search result with relevance score.
 *
 * Contains card data along with search-specific metadata such as
 * vector similarity scores and text match highlights.
 */
export interface SearchResultItem {
  /** Unique card identifier (UUID) */
  id: string;
  /** Display name of the card */
  name: string;
  /** URL-friendly slug */
  slug: string;
  /** Brief card summary */
  summary?: string;
  /** Extended card description */
  description?: string;
  /** Strategic pillar code */
  pillar_id?: string;
  /** Strategic goal identifier */
  goal_id?: string;
  /** Anchor card reference */
  anchor_id?: string;
  /** Maturity stage identifier */
  stage_id?: string;
  /** Technology horizon */
  horizon?: string;
  /** Novelty score (0-100) */
  novelty_score?: number;
  /** Maturity score (0-100) */
  maturity_score?: number;
  /** Impact score (0-100) */
  impact_score?: number;
  /** Relevance score (0-100) */
  relevance_score?: number;
  /** Velocity score (0-100) */
  velocity_score?: number;
  /** Risk score (0-100) */
  risk_score?: number;
  /** Opportunity score (0-100) */
  opportunity_score?: number;
  /** Card lifecycle status */
  status?: string;
  /** ISO 8601 creation timestamp */
  created_at?: string;
  /** ISO 8601 last update timestamp */
  updated_at?: string;
  /** Vector similarity score (0-1), populated when semantic search is used */
  search_relevance?: number;
  /** Text snippets with matching terms highlighted */
  match_highlights?: string[];

  // Grant-specific fields
  deadline?: string | null;
  funding_amount_min?: number | null;
  funding_amount_max?: number | null;
  grantor?: string | null;
  eligibility_text?: string | null;
  grant_type?: string | null;
  source_url?: string | null;
  cfda_number?: string | null;
  category_id?: string | null;
  alignment_score?: number | null;
  grants_gov_id?: string | null;
  sam_opportunity_id?: string | null;
}

/**
 * Response model for advanced search results.
 *
 * Contains the matching cards along with pagination metadata
 * and information about how the search was executed.
 */
export interface AdvancedSearchResponse {
  /** List of matching search result items */
  results: SearchResultItem[];
  /** Total number of matching results across all pages */
  total_count: number;
  /** The query string that was searched, if provided */
  query?: string;
  /** The filters that were applied to the search */
  filters_applied?: SearchFilters;
  /** Whether vector (semantic) or text search was used */
  search_type: "vector" | "text";
}

// ============================================================================
// Saved Search Types
// ============================================================================

/**
 * Query configuration stored in saved searches.
 *
 * Captures the full search state (query text, filters, search mode) so
 * it can be replayed later from the saved searches panel.
 */
export interface SavedSearchQueryConfig {
  /** Free-text search query */
  query?: string;
  /** Structured filters to apply */
  filters?: SearchFilters;
  /** Whether to use vector (semantic) search */
  use_vector_search?: boolean;
}

/**
 * Request model for creating a saved search.
 */
export interface SavedSearchCreate {
  /** User-defined name for this saved search */
  name: string;
  /** The query configuration to save */
  query_config: SavedSearchQueryConfig;
}

/**
 * Request model for updating a saved search.
 *
 * All fields are optional -- only provided fields are updated.
 */
export interface SavedSearchUpdate {
  /** Updated name for the saved search */
  name?: string;
  /** Updated query configuration */
  query_config?: SavedSearchQueryConfig;
}

/**
 * A saved search record belonging to a user.
 *
 * Persists a named search configuration that can be quickly re-executed
 * from the saved searches panel.
 */
export interface SavedSearch {
  /** Unique saved search identifier (UUID) */
  id: string;
  /** ID of the user who created this saved search */
  user_id: string;
  /** User-defined name for this saved search */
  name: string;
  /** The stored query configuration */
  query_config: SavedSearchQueryConfig;
  /** ISO 8601 timestamp when this saved search was created */
  created_at: string;
  /** ISO 8601 timestamp when this saved search was last executed */
  last_used_at: string;
  /** ISO 8601 timestamp when this saved search was last modified */
  updated_at?: string;
}

/**
 * Paginated response for listing saved searches.
 */
export interface SavedSearchList {
  /** List of saved search records */
  saved_searches: SavedSearch[];
  /** Total number of saved searches for this user */
  total_count: number;
}

// ============================================================================
// Search History Types
// ============================================================================

/**
 * A search history record capturing a past search execution.
 *
 * Automatically recorded when a user executes a search, enabling
 * quick access to recent searches.
 */
export interface SearchHistoryEntry {
  /** Unique history entry identifier (UUID) */
  id: string;
  /** ID of the user who executed the search */
  user_id: string;
  /** The query configuration that was executed */
  query_config: SavedSearchQueryConfig;
  /** ISO 8601 timestamp when the search was executed */
  executed_at: string;
  /** Number of results returned by this search */
  result_count: number;
}

/**
 * Request model for recording a search execution in history.
 */
export interface SearchHistoryCreate {
  /** The query configuration that was executed */
  query_config: SavedSearchQueryConfig;
  /** Number of results returned */
  result_count: number;
}

/**
 * Paginated response for listing search history entries.
 */
export interface SearchHistoryList {
  /** List of search history entries, most recent first */
  history: SearchHistoryEntry[];
  /** Total number of history entries for this user */
  total_count: number;
}

/**
 * Helper function for API requests
 */
async function apiRequest<T>(
  endpoint: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
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
    throw new Error(error.message || `API error: ${response.status}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/**
 * Fetch all pending review cards
 */
export async function fetchPendingReviewCards(
  token: string,
  options?: { limit?: number; offset?: number; sort?: "date" | "confidence" },
): Promise<PendingCard[]> {
  const params = new URLSearchParams();
  if (options?.limit) params.append("limit", String(options.limit));
  if (options?.offset) params.append("offset", String(options.offset));
  if (options?.sort) params.append("sort", options.sort);
  const qs = params.toString();
  return apiRequest<PendingCard[]>(
    `/api/v1/cards/pending-review${qs ? `?${qs}` : ""}`,
    token,
  );
}

/**
 * Fetch pending cards with filters
 */
export async function fetchPendingReviewCardsFiltered(
  token: string,
  filters?: {
    pillar_id?: string;
    min_confidence?: number;
    max_confidence?: number;
    source_type?: string;
  },
): Promise<PendingCard[]> {
  const params = new URLSearchParams();
  if (filters?.pillar_id) params.append("pillar_id", filters.pillar_id);
  if (filters?.min_confidence !== undefined)
    params.append("min_confidence", String(filters.min_confidence));
  if (filters?.max_confidence !== undefined)
    params.append("max_confidence", String(filters.max_confidence));
  if (filters?.source_type) params.append("source_type", filters.source_type);

  const queryString = params.toString();
  const endpoint = `/api/v1/cards/pending-review${queryString ? `?${queryString}` : ""}`;

  return apiRequest<PendingCard[]>(endpoint, token);
}

/**
 * Review a single card
 */
export async function reviewCard(
  token: string,
  cardId: string,
  action: ReviewAction,
  updates?: Partial<Card>,
): Promise<void> {
  return apiRequest<void>(`/api/v1/cards/${cardId}/review`, token, {
    method: "POST",
    body: JSON.stringify({ action, updates }),
  });
}

/**
 * Bulk review multiple cards with the same action
 */
export async function bulkReviewCards(
  token: string,
  cardIds: string[],
  action: ReviewAction,
): Promise<{ processed: number; errors: string[] }> {
  return apiRequest<{ processed: number; errors: string[] }>(
    "/api/v1/cards/bulk-review",
    token,
    {
      method: "POST",
      body: JSON.stringify({ card_ids: cardIds, action }),
    },
  );
}

/**
 * Dismiss a card with optional reason
 */
export async function dismissCard(
  token: string,
  cardId: string,
  reason?: DismissReason,
  notes?: string,
): Promise<void> {
  return apiRequest<void>(`/api/v1/cards/${cardId}/dismiss`, token, {
    method: "POST",
    body: JSON.stringify({ reason, notes }),
  });
}

/**
 * Fetch cards similar to a given card (for duplicate detection)
 */
export async function fetchSimilarCards(
  token: string,
  cardId: string,
  threshold?: number,
): Promise<Card[]> {
  const params = threshold ? `?threshold=${threshold}` : "";
  return apiRequest<Card[]>(`/api/v1/cards/${cardId}/similar${params}`, token);
}

/**
 * Fetch discovery run history
 */
export async function fetchDiscoveryRuns(
  token: string,
  limit: number = 10,
): Promise<DiscoveryRun[]> {
  return apiRequest<DiscoveryRun[]>(
    `/api/v1/discovery/runs?limit=${limit}`,
    token,
  );
}

/**
 * Fetch a specific discovery run
 */
export async function fetchDiscoveryRun(
  token: string,
  runId: string,
): Promise<DiscoveryRun> {
  return apiRequest<DiscoveryRun>(`/api/v1/discovery/runs/${runId}`, token);
}

/**
 * Request model for configuring a discovery run.
 *
 * Matches the backend `DiscoveryConfigRequest` Pydantic model.
 * All fields are optional overrides of the system defaults.
 */
export interface DiscoveryConfigRequest {
  /** Maximum number of search queries to generate per run */
  max_queries_per_run?: number;
  /** Maximum total sources to process across all queries */
  max_sources_total?: number;
  /** AI confidence threshold for auto-approving cards (0-1) */
  auto_approve_threshold?: number;
  /** Strategic pillar codes to restrict the scan to */
  pillars_filter?: string[];
  /** If true, simulate the run without creating cards */
  dry_run?: boolean;
}

/**
 * Current discovery system configuration from backend environment.
 *
 * Read-only view of the active system defaults that govern discovery runs.
 */
export interface DiscoveryConfig {
  /** Maximum search queries generated per run */
  max_queries_per_run: number;
  /** Maximum total sources processed across all queries */
  max_sources_total: number;
  /** Maximum sources fetched per individual query */
  max_sources_per_query: number;
  /** AI confidence threshold for auto-approving cards (0-1) */
  auto_approve_threshold: number;
  /** Vector similarity threshold for deduplication (0-1) */
  similarity_threshold: number;
}

/**
 * Fetch current discovery configuration from server
 */
export async function fetchDiscoveryConfig(
  token: string,
): Promise<DiscoveryConfig> {
  return apiRequest<DiscoveryConfig>("/api/v1/discovery/config", token);
}

/**
 * Trigger a new discovery run
 */
export async function triggerDiscoveryRun(
  token: string,
  config?: DiscoveryConfigRequest,
): Promise<{ run_id: string }> {
  return apiRequest<{ run_id: string }>("/api/v1/discovery/run", token, {
    method: "POST",
    body: JSON.stringify(config || {}),
  });
}

/**
 * Cancel an in-progress discovery run
 */
export async function cancelDiscoveryRun(
  token: string,
  runId: string,
): Promise<void> {
  return apiRequest<void>(`/api/v1/discovery/runs/${runId}/cancel`, token, {
    method: "POST",
  });
}

/**
 * Get count of pending cards (lightweight endpoint)
 */
export async function fetchPendingCount(token: string): Promise<number> {
  const result = await apiRequest<{ count: number }>(
    "/api/v1/discovery/pending/count",
    token,
  );
  return result.count;
}

// ============================================================================
// Advanced Search API Functions
// ============================================================================

/**
 * Execute an advanced search with filters and optional vector search
 */
export async function advancedSearch(
  token: string,
  request: AdvancedSearchRequest,
): Promise<AdvancedSearchResponse> {
  return apiRequest<AdvancedSearchResponse>("/api/v1/cards/search", token, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

// ============================================================================
// Saved Searches API Functions
// ============================================================================

/**
 * List all saved searches for the current user
 */
export async function listSavedSearches(
  token: string,
  limit?: number,
): Promise<SavedSearchList> {
  const params = new URLSearchParams();
  if (limit !== undefined) params.append("limit", String(limit));
  const queryString = params.toString();
  const endpoint = `/api/v1/saved-searches${queryString ? `?${queryString}` : ""}`;
  return apiRequest<SavedSearchList>(endpoint, token);
}

/**
 * Create a new saved search
 */
export async function createSavedSearch(
  token: string,
  savedSearch: SavedSearchCreate,
): Promise<SavedSearch> {
  return apiRequest<SavedSearch>("/api/v1/saved-searches", token, {
    method: "POST",
    body: JSON.stringify(savedSearch),
  });
}

/**
 * Get a specific saved search by ID (also updates last_used_at)
 */
export async function getSavedSearch(
  token: string,
  searchId: string,
): Promise<SavedSearch> {
  return apiRequest<SavedSearch>(`/api/v1/saved-searches/${searchId}`, token);
}

/**
 * Update a saved search
 */
export async function updateSavedSearch(
  token: string,
  searchId: string,
  updates: SavedSearchUpdate,
): Promise<SavedSearch> {
  return apiRequest<SavedSearch>(`/api/v1/saved-searches/${searchId}`, token, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

/**
 * Delete a saved search
 */
export async function deleteSavedSearch(
  token: string,
  searchId: string,
): Promise<void> {
  return apiRequest<void>(`/api/v1/saved-searches/${searchId}`, token, {
    method: "DELETE",
  });
}

// ============================================================================
// Search History API Functions
// ============================================================================

/**
 * Get the current user's search history
 */
export async function getSearchHistory(
  token: string,
  limit?: number,
): Promise<SearchHistoryList> {
  const params = new URLSearchParams();
  if (limit !== undefined) params.append("limit", String(limit));
  const queryString = params.toString();
  const endpoint = `/api/v1/search-history${queryString ? `?${queryString}` : ""}`;
  return apiRequest<SearchHistoryList>(endpoint, token);
}

/**
 * Record a search in the user's history
 */
export async function recordSearchHistory(
  token: string,
  entry: SearchHistoryCreate,
): Promise<SearchHistoryEntry> {
  return apiRequest<SearchHistoryEntry>("/api/v1/search-history", token, {
    method: "POST",
    body: JSON.stringify(entry),
  });
}

/**
 * Delete a specific search history entry
 */
export async function deleteSearchHistoryEntry(
  token: string,
  entryId: string,
): Promise<void> {
  return apiRequest<void>(`/api/v1/search-history/${entryId}`, token, {
    method: "DELETE",
  });
}

/**
 * Fetch personalized discovery queue with multi-factor scoring
 *
 * Returns cards ranked by discovery_score, which combines:
 * - Novelty (recent/unseen cards)
 * - Workstream relevance (matching user's workstream filters)
 * - Pillar alignment (cards in user's active pillars)
 * - Followed context (similar to user's followed cards)
 */
export async function fetchPersonalizedDiscoveryQueue(
  token: string,
  limit: number = 20,
  offset: number = 0,
): Promise<PersonalizedCard[]> {
  const params = new URLSearchParams();
  params.append("limit", String(limit));
  params.append("offset", String(offset));

  const queryString = params.toString();
  const endpoint = `/api/v1/me/discovery/queue?${queryString}`;

  return apiRequest<PersonalizedCard[]>(endpoint, token);
}

/**
 * Clear all search history for the current user
 */
export async function clearSearchHistory(token: string): Promise<void> {
  return apiRequest<void>("/api/v1/search-history", token, {
    method: "DELETE",
  });
}

// ============================================================================
// Trend Visualization & History Types
// ============================================================================

/**
 * Valid relationship types for card relationships in the concept network
 */
export type RelationshipType =
  | "related"
  | "similar"
  | "derived"
  | "dependent"
  | "parent"
  | "child";

/**
 * Historical score snapshot for a card at a specific point in time.
 * Used for trend visualization showing how card scores have changed over time.
 * Each record captures all 7 score dimensions.
 */
export interface ScoreHistory {
  id: string;
  card_id: string;
  recorded_at: string; // ISO timestamp
  // All 7 score dimensions (0-100 range)
  maturity_score: number | null;
  velocity_score: number | null;
  novelty_score: number | null;
  impact_score: number | null;
  relevance_score: number | null;
  risk_score: number | null;
  opportunity_score: number | null;
}

/**
 * Response model for score history API endpoint.
 * Returns a list of score snapshots for trend visualization.
 */
export interface ScoreHistoryResponse {
  history: ScoreHistory[];
  card_id: string;
  total_count: number;
  start_date?: string | null; // ISO timestamp, filter applied
  end_date?: string | null; // ISO timestamp, filter applied
}

/**
 * Stage transition record for a card.
 * Represents a single stage change event tracking the transition
 * from one maturity stage (1-8) to another with associated horizon changes (H1/H2/H3).
 */
export interface StageHistory {
  id: string;
  card_id: string;
  changed_at: string; // ISO timestamp
  old_stage_id: number | null; // 1-8, null for first record
  new_stage_id: number; // 1-8
  old_horizon: "H1" | "H2" | "H3" | null; // null for first record
  new_horizon: "H1" | "H2" | "H3";
  trigger?: string | null; // e.g., 'manual', 'auto-calculated', 'score_update'
  reason?: string | null; // Optional explanation for the stage change
}

/**
 * Response model for listing stage history records.
 * Returns chronologically ordered stage transitions for a card.
 */
export interface StageHistoryList {
  history: StageHistory[];
  total_count: number;
  card_id: string;
}

/**
 * Card relationship record representing an edge in the concept network.
 * Connects a source card to a target card with relationship metadata.
 */
export interface CardRelationship {
  id: string;
  source_card_id: string;
  target_card_id: string;
  relationship_type: RelationshipType;
  strength: number | null; // 0-1 weight for edge visualization
  created_at: string; // ISO timestamp
}

/**
 * Extended card model with relationship metadata.
 * Used in concept network visualization to display related cards
 * with their relationship context.
 */
export interface RelatedCard {
  id: string;
  name: string;
  slug: string;
  summary?: string | null;
  pillar_id?: string | null;
  stage_id?: string | null;
  horizon?: "H1" | "H2" | "H3" | null;
  // Relationship context
  relationship_type: RelationshipType;
  relationship_strength: number | null; // 0-1
  relationship_id: string;
}

/**
 * Response model for listing related cards.
 * Returns cards connected to a source card in the concept network.
 */
export interface RelatedCardsList {
  related_cards: RelatedCard[];
  total_count: number;
  source_card_id: string;
}

// ============================================================================
// Card Comparison Types
// ============================================================================

/**
 * Basic card data for comparison view.
 * Contains essential card metadata for side-by-side comparison.
 */
export interface CardData {
  id: string;
  name: string;
  slug: string;
  summary?: string | null;
  pillar_id?: string | null;
  goal_id?: string | null;
  stage_id?: string | null;
  horizon?: "H1" | "H2" | "H3" | null;
  // Current scores for comparison (0-100)
  maturity_score: number | null;
  velocity_score: number | null;
  novelty_score: number | null;
  impact_score: number | null;
  relevance_score: number | null;
  risk_score: number | null;
  opportunity_score: number | null;
  created_at?: string | null; // ISO timestamp
  updated_at?: string | null; // ISO timestamp
}

/**
 * Complete comparison data for a single card.
 * Includes card metadata, score history, and stage history
 * for comprehensive trend comparison visualization.
 */
export interface CardComparisonItem {
  card: CardData;
  score_history: ScoreHistory[];
  stage_history: StageHistory[];
}

/**
 * Response model for card comparison API endpoint.
 * Returns parallel data for two cards to enable synchronized
 * timeline charts and comparative metrics visualization.
 */
export interface CardComparisonResponse {
  card1: CardComparisonItem;
  card2: CardComparisonItem;
  comparison_generated_at: string; // ISO timestamp
}

// ============================================================================
// Trend Visualization & History API Functions
// ============================================================================

/**
 * Fetch score history for a card.
 * Returns historical score snapshots for timeline visualization.
 *
 * @param token - Authentication token
 * @param cardId - UUID of the card
 * @param startDate - Optional start date filter (ISO format YYYY-MM-DD)
 * @param endDate - Optional end date filter (ISO format YYYY-MM-DD)
 * @returns ScoreHistoryResponse with historical score data
 */
export async function getScoreHistory(
  token: string,
  cardId: string,
  startDate?: string,
  endDate?: string,
): Promise<ScoreHistoryResponse> {
  const params = new URLSearchParams();
  if (startDate) params.append("start_date", startDate);
  if (endDate) params.append("end_date", endDate);

  const queryString = params.toString();
  const endpoint = `/api/v1/cards/${cardId}/score-history${queryString ? `?${queryString}` : ""}`;

  return apiRequest<ScoreHistoryResponse>(endpoint, token);
}

/**
 * Fetch stage history for a card.
 * Returns stage transition records for progression visualization.
 *
 * @param token - Authentication token
 * @param cardId - UUID of the card
 * @returns StageHistoryList with stage transition records
 */
export async function getStageHistory(
  token: string,
  cardId: string,
): Promise<StageHistoryList> {
  return apiRequest<StageHistoryList>(
    `/api/v1/cards/${cardId}/stage-history`,
    token,
  );
}

/**
 * Fetch related cards for concept network visualization.
 * Returns cards connected to the source card with relationship metadata.
 *
 * @param token - Authentication token
 * @param cardId - UUID of the source card
 * @param limit - Maximum number of related cards to return (default: 20)
 * @returns RelatedCardsList with related cards and relationship context
 */
export async function getRelatedCards(
  token: string,
  cardId: string,
  limit: number = 20,
): Promise<RelatedCardsList> {
  const params = new URLSearchParams();
  params.append("limit", String(limit));

  return apiRequest<RelatedCardsList>(
    `/api/v1/cards/${cardId}/related?${params.toString()}`,
    token,
  );
}

/**
 * Compare two cards with their historical data.
 * Returns parallel data for side-by-side comparison visualization.
 *
 * @param token - Authentication token
 * @param cardId1 - UUID of the first card
 * @param cardId2 - UUID of the second card
 * @param startDate - Optional start date filter for score history (ISO format YYYY-MM-DD)
 * @param endDate - Optional end date filter for score history (ISO format YYYY-MM-DD)
 * @returns CardComparisonResponse with synchronized data for both cards
 */
export async function compareCards(
  token: string,
  cardId1: string,
  cardId2: string,
  startDate?: string,
  endDate?: string,
): Promise<CardComparisonResponse> {
  const params = new URLSearchParams();
  params.append("card_ids", `${cardId1},${cardId2}`);
  if (startDate) params.append("start_date", startDate);
  if (endDate) params.append("end_date", endDate);

  return apiRequest<CardComparisonResponse>(
    `/api/v1/cards/compare?${params.toString()}`,
    token,
  );
}

// =============================================================================
// Card Assets API
// =============================================================================

/**
 * Asset type enumeration
 */
export type AssetType = "brief" | "research" | "pdf_export" | "pptx_export";

/**
 * Asset data structure returned from the API
 */
export interface CardAsset {
  id: string;
  type: AssetType;
  title: string;
  created_at: string;
  version?: number;
  file_size?: number;
  download_count?: number;
  ai_generated: boolean;
  ai_model?: string;
  status: "ready" | "generating" | "failed";
  metadata?: Record<string, unknown>;
}

/**
 * Response from the card assets endpoint
 */
export interface CardAssetsResponse {
  card_id: string;
  assets: CardAsset[];
  total_count: number;
}

/**
 * Fetch all generated assets for a card.
 *
 * Returns briefs, research reports, and exports associated with the card.
 *
 * @param token - Authentication token
 * @param cardId - Card UUID
 * @returns CardAssetsResponse with list of assets
 */
export async function fetchCardAssets(
  token: string,
  cardId: string,
): Promise<CardAssetsResponse> {
  return apiRequest<CardAssetsResponse>(
    `/api/v1/cards/${cardId}/assets`,
    token,
  );
}

// ============================================================================
// Signal Creation API Functions
// ============================================================================

/**
 * Create a new intelligence card from a topic phrase.
 *
 * The backend uses AI to expand the topic into a fully-formed card with
 * classification, scoring, and initial research context.
 *
 * @param data - Topic string and optional workstream ID
 * @param token - Authentication token
 * @returns The create-from-topic response with card_id, card_name, status, message
 */
export interface CreateCardFromTopicResponse {
  card_id: string;
  card_name: string;
  status: string;
  scan_job_id?: string | null;
  message: string;
}

export async function createCardFromTopic(
  data: { topic: string; workstream_id?: string },
  token: string,
): Promise<CreateCardFromTopicResponse> {
  return apiRequest<CreateCardFromTopicResponse>(
    "/api/v1/cards/create-from-topic",
    token,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
}

/**
 * Get AI-suggested keywords for a given topic phrase.
 *
 * Returns a list of keyword suggestions that can help refine
 * discovery queries and improve card classification.
 *
 * @param topic - The topic phrase to get keyword suggestions for
 * @param token - Authentication token
 * @returns Object containing an array of suggested keyword strings
 */
export async function suggestKeywords(
  topic: string,
  token: string,
): Promise<{ topic: string; suggestions: string[] }> {
  const params = new URLSearchParams();
  params.append("topic", topic);
  return apiRequest<{ topic: string; suggestions: string[] }>(
    `/api/v1/ai/suggest-keywords?${params.toString()}`,
    token,
    { method: "POST" },
  );
}

// ============================================================================
// Source Preferences Types
// ============================================================================

export interface SourcePreferences {
  enabled_categories?: string[];
  preferred_type?: string;
  priority_domains?: string[];
  custom_rss_feeds?: string[];
  keywords?: string[];
}

// ============================================================================
// My Signals API (Personal Intelligence Hub)
// ============================================================================

export interface MySignalCard extends Card {
  is_followed: boolean;
  is_created: boolean;
  is_pinned: boolean;
  personal_notes: string | null;
  follow_priority: string | null;
  followed_at: string | null;
  workstream_names: string[];
  source_preferences?: SourcePreferences;
}

export interface MySignalsStats {
  total: number;
  followed_count: number;
  created_count: number;
  workstream_count: number;
  updates_this_week: number;
  needs_research: number;
}

export interface MySignalsResponse {
  signals: MySignalCard[];
  stats: MySignalsStats;
  workstreams: Array<{ id: string; name: string }>;
}

export async function fetchMySignals(
  token: string,
  options?: {
    sort_by?: string;
    search?: string;
    pillar?: string;
    horizon?: string;
    quality_min?: number;
  },
): Promise<MySignalsResponse> {
  const params = new URLSearchParams();
  if (options?.sort_by) params.append("sort_by", options.sort_by);
  if (options?.search) params.append("search", options.search);
  if (options?.pillar) params.append("pillar", options.pillar);
  if (options?.horizon) params.append("horizon", options.horizon);
  if (options?.quality_min !== undefined && options.quality_min > 0)
    params.append("quality_min", String(options.quality_min));

  const queryString = params.toString();
  const endpoint = `/api/v1/me/signals${queryString ? `?${queryString}` : ""}`;
  return apiRequest<MySignalsResponse>(endpoint, token);
}

export async function pinSignal(
  token: string,
  cardId: string,
): Promise<{ is_pinned: boolean }> {
  return apiRequest<{ is_pinned: boolean }>(
    `/api/v1/me/signals/${cardId}/pin`,
    token,
    { method: "POST" },
  );
}

// ============================================================================
// Card Snapshots — version history for description/summary
// ============================================================================

export interface CardSnapshot {
  id: string;
  field_name: string;
  content?: string;
  content_length: number;
  trigger: string;
  created_at: string;
  created_by: string;
}

export async function fetchCardSnapshots(
  token: string,
  cardId: string,
  fieldName: string = "description",
): Promise<{ snapshots: CardSnapshot[]; card_id: string }> {
  return apiRequest<{ snapshots: CardSnapshot[]; card_id: string }>(
    `/api/v1/cards/${cardId}/snapshots?field_name=${fieldName}`,
    token,
  );
}

export async function fetchCardSnapshot(
  token: string,
  cardId: string,
  snapshotId: string,
): Promise<CardSnapshot> {
  return apiRequest<CardSnapshot>(
    `/api/v1/cards/${cardId}/snapshots/${snapshotId}`,
    token,
  );
}

export async function restoreCardSnapshot(
  token: string,
  cardId: string,
  snapshotId: string,
): Promise<{ restored: boolean; field_name: string; content_length: number }> {
  return apiRequest<{
    restored: boolean;
    field_name: string;
    content_length: number;
  }>(`/api/v1/cards/${cardId}/snapshots/${snapshotId}/restore`, token, {
    method: "POST",
  });
}
