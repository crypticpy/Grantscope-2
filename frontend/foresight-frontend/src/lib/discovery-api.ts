/**
 * Discovery API Helpers
 *
 * API functions for interacting with the discovery system backend.
 * Handles pending card reviews, bulk actions, and discovery run management.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Base Card interface
 */
export interface Card {
  id: string;
  name: string;
  slug: string;
  summary: string;
  pillar_id: string;
  stage_id: string;
  horizon: 'H1' | 'H2' | 'H3';
  novelty_score: number;
  maturity_score: number;
  impact_score: number;
  relevance_score: number;
  velocity_score: number;
  risk_score: number;
  opportunity_score: number;
  created_at: string;
  updated_at?: string;
  anchor_id?: string;
  top25_relevance?: string[];
  status: string;
}

/**
 * Discovery run configuration
 */
export interface DiscoveryRunConfig {
  source_types?: string[];
  pillar_focus?: string[];
  max_cards?: number;
}

/**
 * Discovery run metadata - matches backend DiscoveryRun Pydantic model
 */
export interface DiscoveryRun {
  id: string;
  started_at: string;
  completed_at: string | null;
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  triggered_by: 'manual' | 'scheduled' | 'api';
  triggered_by_user: string | null;
  // Discovery metrics
  pillars_scanned: string[] | null;
  priorities_scanned: string[] | null;
  queries_generated: number | null;
  sources_found: number;
  sources_relevant: number | null;
  cards_created: number;
  cards_enriched: number;
  cards_deduplicated: number;
  // Cost and reporting
  estimated_cost: number | null;
  summary_report: Record<string, unknown> | null;
  // Error handling
  error_message: string | null;
  error_details: Record<string, unknown> | null;
  errors?: string[];
  // Timestamps
  created_at: string | null;
  // Run configuration (optional, populated for detailed run info)
  config?: DiscoveryRunConfig;
}

/**
 * Pending card extends Card with discovery-specific fields
 */
export interface PendingCard extends Card {
  ai_confidence: number;
  discovered_at: string;
  source_url?: string;
  source_type?: string;
  discovery_run_id?: string;
  suggested_changes?: {
    field: string;
    current: string;
    suggested: string;
    reason: string;
  }[];
}

/**
 * Score breakdown showing contribution from each scoring factor
 */
export interface ScoreBreakdown {
  novelty: number;
  workstream_relevance: number;
  pillar_alignment: number;
  followed_context: number;
}

/**
 * Personalized card extends Card with discovery score for queue ranking
 */
export interface PersonalizedCard extends Card {
  discovery_score: number;
  score_breakdown?: ScoreBreakdown;
}

/**
 * Review action types
 */
export type ReviewAction = 'approve' | 'reject' | 'edit' | 'defer';

/**
 * Dismiss reasons
 */
export type DismissReason =
  | 'duplicate'
  | 'irrelevant'
  | 'low_quality'
  | 'out_of_scope'
  | 'already_exists'
  | 'other';

// ============================================================================
// Advanced Search Types
// ============================================================================

/**
 * Date range filter for created_at/updated_at filtering
 */
export interface DateRange {
  start?: string; // ISO date string YYYY-MM-DD
  end?: string;   // ISO date string YYYY-MM-DD
}

/**
 * Min/max threshold for a single score field
 */
export interface ScoreThreshold {
  min?: number; // 0-100
  max?: number; // 0-100
}

/**
 * Collection of score threshold filters
 */
export interface ScoreThresholds {
  impact_score?: ScoreThreshold;
  relevance_score?: ScoreThreshold;
  novelty_score?: ScoreThreshold;
  maturity_score?: ScoreThreshold;
  velocity_score?: ScoreThreshold;
  risk_score?: ScoreThreshold;
  opportunity_score?: ScoreThreshold;
}

/**
 * Advanced search filters for intelligence cards.
 * All filters are optional and combined with AND logic.
 */
export interface SearchFilters {
  pillar_ids?: string[];
  goal_ids?: string[];
  stage_ids?: string[];
  horizon?: 'H1' | 'H2' | 'H3' | 'ALL';
  date_range?: DateRange;
  score_thresholds?: ScoreThresholds;
  status?: string;
}

/**
 * Request model for advanced card search
 */
export interface AdvancedSearchRequest {
  query?: string;
  filters?: SearchFilters;
  use_vector_search?: boolean;
  limit?: number;
  offset?: number;
}

/**
 * Individual search result with relevance score
 */
export interface SearchResultItem {
  id: string;
  name: string;
  slug: string;
  summary?: string;
  description?: string;
  pillar_id?: string;
  goal_id?: string;
  anchor_id?: string;
  stage_id?: string;
  horizon?: string;
  novelty_score?: number;
  maturity_score?: number;
  impact_score?: number;
  relevance_score?: number;
  velocity_score?: number;
  risk_score?: number;
  opportunity_score?: number;
  status?: string;
  created_at?: string;
  updated_at?: string;
  // Search-specific fields
  search_relevance?: number; // Vector similarity score (0-1)
  match_highlights?: string[];
}

/**
 * Response model for advanced search results
 */
export interface AdvancedSearchResponse {
  results: SearchResultItem[];
  total_count: number;
  query?: string;
  filters_applied?: SearchFilters;
  search_type: 'vector' | 'text';
}

// ============================================================================
// Saved Search Types
// ============================================================================

/**
 * Query configuration stored in saved searches
 */
export interface SavedSearchQueryConfig {
  query?: string;
  filters?: SearchFilters;
  use_vector_search?: boolean;
}

/**
 * Request model for creating a saved search
 */
export interface SavedSearchCreate {
  name: string;
  query_config: SavedSearchQueryConfig;
}

/**
 * Request model for updating a saved search
 */
export interface SavedSearchUpdate {
  name?: string;
  query_config?: SavedSearchQueryConfig;
}

/**
 * Response model for a saved search record
 */
export interface SavedSearch {
  id: string;
  user_id: string;
  name: string;
  query_config: SavedSearchQueryConfig;
  created_at: string;
  last_used_at: string;
  updated_at?: string;
}

/**
 * Response model for listing saved searches
 */
export interface SavedSearchList {
  saved_searches: SavedSearch[];
  total_count: number;
}

// ============================================================================
// Search History Types
// ============================================================================

/**
 * Response model for a search history record
 */
export interface SearchHistoryEntry {
  id: string;
  user_id: string;
  query_config: SavedSearchQueryConfig;
  executed_at: string;
  result_count: number;
}

/**
 * Request model for recording a search in history
 */
export interface SearchHistoryCreate {
  query_config: SavedSearchQueryConfig;
  result_count: number;
}

/**
 * Response model for listing search history
 */
export interface SearchHistoryList {
  history: SearchHistoryEntry[];
  total_count: number;
}

/**
 * Helper function for API requests
 */
async function apiRequest<T>(
  endpoint: string,
  token: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }));
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
export async function fetchPendingReviewCards(token: string): Promise<PendingCard[]> {
  return apiRequest<PendingCard[]>('/api/v1/cards/pending-review', token);
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
  }
): Promise<PendingCard[]> {
  const params = new URLSearchParams();
  if (filters?.pillar_id) params.append('pillar_id', filters.pillar_id);
  if (filters?.min_confidence !== undefined) params.append('min_confidence', String(filters.min_confidence));
  if (filters?.max_confidence !== undefined) params.append('max_confidence', String(filters.max_confidence));
  if (filters?.source_type) params.append('source_type', filters.source_type);

  const queryString = params.toString();
  const endpoint = `/api/v1/cards/pending-review${queryString ? `?${queryString}` : ''}`;

  return apiRequest<PendingCard[]>(endpoint, token);
}

/**
 * Review a single card
 */
export async function reviewCard(
  token: string,
  cardId: string,
  action: ReviewAction,
  updates?: Partial<Card>
): Promise<void> {
  return apiRequest<void>(`/api/v1/cards/${cardId}/review`, token, {
    method: 'POST',
    body: JSON.stringify({ action, updates }),
  });
}

/**
 * Bulk review multiple cards with the same action
 */
export async function bulkReviewCards(
  token: string,
  cardIds: string[],
  action: ReviewAction
): Promise<{ processed: number; errors: string[] }> {
  return apiRequest<{ processed: number; errors: string[] }>('/api/v1/cards/bulk-review', token, {
    method: 'POST',
    body: JSON.stringify({ card_ids: cardIds, action }),
  });
}

/**
 * Dismiss a card with optional reason
 */
export async function dismissCard(
  token: string,
  cardId: string,
  reason?: DismissReason,
  notes?: string
): Promise<void> {
  return apiRequest<void>(`/api/v1/cards/${cardId}/dismiss`, token, {
    method: 'POST',
    body: JSON.stringify({ reason, notes }),
  });
}

/**
 * Fetch cards similar to a given card (for duplicate detection)
 */
export async function fetchSimilarCards(
  token: string,
  cardId: string,
  threshold?: number
): Promise<Card[]> {
  const params = threshold ? `?threshold=${threshold}` : '';
  return apiRequest<Card[]>(`/api/v1/cards/${cardId}/similar${params}`, token);
}

/**
 * Fetch discovery run history
 */
export async function fetchDiscoveryRuns(
  token: string,
  limit: number = 10
): Promise<DiscoveryRun[]> {
  return apiRequest<DiscoveryRun[]>(`/api/v1/discovery/runs?limit=${limit}`, token);
}

/**
 * Fetch a specific discovery run
 */
export async function fetchDiscoveryRun(
  token: string,
  runId: string
): Promise<DiscoveryRun> {
  return apiRequest<DiscoveryRun>(`/api/v1/discovery/runs/${runId}`, token);
}

/**
 * Discovery run configuration - matches backend DiscoveryConfigRequest model
 */
export interface DiscoveryConfigRequest {
  max_queries_per_run?: number;
  max_sources_total?: number;
  auto_approve_threshold?: number;
  pillars_filter?: string[];
  dry_run?: boolean;
}

/**
 * Discovery system configuration (from backend env vars)
 */
export interface DiscoveryConfig {
  max_queries_per_run: number;
  max_sources_total: number;
  max_sources_per_query: number;
  auto_approve_threshold: number;
  similarity_threshold: number;
}

/**
 * Fetch current discovery configuration from server
 */
export async function fetchDiscoveryConfig(token: string): Promise<DiscoveryConfig> {
  return apiRequest<DiscoveryConfig>('/api/v1/discovery/config', token);
}

/**
 * Trigger a new discovery run
 */
export async function triggerDiscoveryRun(
  token: string,
  config?: DiscoveryConfigRequest
): Promise<{ run_id: string }> {
  return apiRequest<{ run_id: string }>('/api/v1/discovery/run', token, {
    method: 'POST',
    body: JSON.stringify(config || {}),
  });
}

/**
 * Cancel an in-progress discovery run
 */
export async function cancelDiscoveryRun(
  token: string,
  runId: string
): Promise<void> {
  return apiRequest<void>(`/api/v1/discovery/runs/${runId}/cancel`, token, {
    method: 'POST',
  });
}

/**
 * Get count of pending cards (lightweight endpoint)
 */
export async function fetchPendingCount(token: string): Promise<number> {
  const result = await apiRequest<{ count: number }>('/api/v1/discovery/pending/count', token);
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
  request: AdvancedSearchRequest
): Promise<AdvancedSearchResponse> {
  return apiRequest<AdvancedSearchResponse>('/api/v1/cards/search', token, {
    method: 'POST',
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
  limit?: number
): Promise<SavedSearchList> {
  const params = new URLSearchParams();
  if (limit !== undefined) params.append('limit', String(limit));
  const queryString = params.toString();
  const endpoint = `/api/v1/saved-searches${queryString ? `?${queryString}` : ''}`;
  return apiRequest<SavedSearchList>(endpoint, token);
}

/**
 * Create a new saved search
 */
export async function createSavedSearch(
  token: string,
  savedSearch: SavedSearchCreate
): Promise<SavedSearch> {
  return apiRequest<SavedSearch>('/api/v1/saved-searches', token, {
    method: 'POST',
    body: JSON.stringify(savedSearch),
  });
}

/**
 * Get a specific saved search by ID (also updates last_used_at)
 */
export async function getSavedSearch(
  token: string,
  searchId: string
): Promise<SavedSearch> {
  return apiRequest<SavedSearch>(`/api/v1/saved-searches/${searchId}`, token);
}

/**
 * Update a saved search
 */
export async function updateSavedSearch(
  token: string,
  searchId: string,
  updates: SavedSearchUpdate
): Promise<SavedSearch> {
  return apiRequest<SavedSearch>(`/api/v1/saved-searches/${searchId}`, token, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

/**
 * Delete a saved search
 */
export async function deleteSavedSearch(
  token: string,
  searchId: string
): Promise<void> {
  return apiRequest<void>(`/api/v1/saved-searches/${searchId}`, token, {
    method: 'DELETE',
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
  limit?: number
): Promise<SearchHistoryList> {
  const params = new URLSearchParams();
  if (limit !== undefined) params.append('limit', String(limit));
  const queryString = params.toString();
  const endpoint = `/api/v1/search-history${queryString ? `?${queryString}` : ''}`;
  return apiRequest<SearchHistoryList>(endpoint, token);
}

/**
 * Record a search in the user's history
 */
export async function recordSearchHistory(
  token: string,
  entry: SearchHistoryCreate
): Promise<SearchHistoryEntry> {
  return apiRequest<SearchHistoryEntry>('/api/v1/search-history', token, {
    method: 'POST',
    body: JSON.stringify(entry),
  });
}

/**
 * Delete a specific search history entry
 */
export async function deleteSearchHistoryEntry(
  token: string,
  entryId: string
): Promise<void> {
  return apiRequest<void>(`/api/v1/search-history/${entryId}`, token, {
    method: 'DELETE',
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
  offset: number = 0
): Promise<PersonalizedCard[]> {
  const params = new URLSearchParams();
  params.append('limit', String(limit));
  params.append('offset', String(offset));

  const queryString = params.toString();
  const endpoint = `/api/v1/me/discovery/queue?${queryString}`;

  return apiRequest<PersonalizedCard[]>(endpoint, token);
}

/**
 * Clear all search history for the current user
 */
export async function clearSearchHistory(token: string): Promise<void> {
  return apiRequest<void>('/api/v1/search-history', token, {
    method: 'DELETE',
  });
}

// ============================================================================
// Trend Visualization & History Types
// ============================================================================

/**
 * Valid relationship types for card relationships in the concept network
 */
export type RelationshipType = 'related' | 'similar' | 'derived' | 'dependent' | 'parent' | 'child';

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
  end_date?: string | null;   // ISO timestamp, filter applied
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
  new_stage_id: number;        // 1-8
  old_horizon: 'H1' | 'H2' | 'H3' | null; // null for first record
  new_horizon: 'H1' | 'H2' | 'H3';
  trigger?: string | null;  // e.g., 'manual', 'auto-calculated', 'score_update'
  reason?: string | null;   // Optional explanation for the stage change
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
  created_at: string;      // ISO timestamp
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
  horizon?: 'H1' | 'H2' | 'H3' | null;
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
  horizon?: 'H1' | 'H2' | 'H3' | null;
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
  endDate?: string
): Promise<ScoreHistoryResponse> {
  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const queryString = params.toString();
  const endpoint = `/api/v1/cards/${cardId}/score-history${queryString ? `?${queryString}` : ''}`;

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
  cardId: string
): Promise<StageHistoryList> {
  return apiRequest<StageHistoryList>(`/api/v1/cards/${cardId}/stage-history`, token);
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
  limit: number = 20
): Promise<RelatedCardsList> {
  const params = new URLSearchParams();
  params.append('limit', String(limit));

  return apiRequest<RelatedCardsList>(
    `/api/v1/cards/${cardId}/related?${params.toString()}`,
    token
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
  endDate?: string
): Promise<CardComparisonResponse> {
  const params = new URLSearchParams();
  params.append('card_ids', `${cardId1},${cardId2}`);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  return apiRequest<CardComparisonResponse>(
    `/api/v1/cards/compare?${params.toString()}`,
    token
  );
}
