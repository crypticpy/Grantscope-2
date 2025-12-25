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
  anchor_id?: string;
  top25_relevance?: string[];
  status: string;
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
  // Timestamps
  created_at: string | null;
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
