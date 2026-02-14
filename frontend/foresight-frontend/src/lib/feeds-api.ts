/**
 * Feeds API Helpers
 *
 * API functions for interacting with the RSS feed management backend.
 * Handles feed CRUD operations, manual checking, and feed item listing.
 *
 * @module lib/feeds-api
 */

import { API_BASE_URL } from "./config";

// ============================================================================
// Types
// ============================================================================

/**
 * RSS feed record with statistics.
 */
export interface Feed {
  /** Unique feed identifier (UUID) */
  id: string;
  /** Feed URL */
  url: string;
  /** User-defined feed name */
  name: string;
  /** Feed category (e.g., 'gov_tech', 'municipal', 'academic') */
  category: string;
  /** Optional strategic pillar alignment */
  pillar_id: string | null;
  /** How often to check the feed, in hours */
  check_interval_hours: number;
  /** Feed status: active, paused, or error */
  status: string;
  /** ISO 8601 timestamp of last successful check */
  last_checked_at: string | null;
  /** Number of consecutive errors */
  error_count: number;
  /** Most recent error message */
  last_error: string | null;
  /** Title from the feed XML */
  feed_title: string | null;
  /** Total articles discovered from this feed */
  articles_found_total: number;
  /** Total articles that matched triage criteria */
  articles_matched_total: number;
  /** ISO 8601 creation timestamp */
  created_at: string;
  /** ISO 8601 last update timestamp */
  updated_at: string;
  /** Number of items discovered in the last 7 days */
  recent_items_7d?: number;
}

/**
 * Individual feed item (article) record.
 */
export interface FeedItem {
  /** Unique item identifier (UUID) */
  id: string;
  /** Parent feed identifier */
  feed_id: string;
  /** Article URL */
  url: string;
  /** Article title */
  title: string;
  /** Article content or excerpt */
  content: string | null;
  /** Article author */
  author: string | null;
  /** ISO 8601 publication timestamp */
  published_at: string | null;
  /** Whether the item has been processed by the pipeline */
  processed: boolean;
  /** Triage result: matched, pending, or irrelevant */
  triage_result: string | null;
  /** Associated card ID if matched */
  card_id: string | null;
  /** ISO 8601 creation timestamp */
  created_at: string;
}

/**
 * Payload for creating a new feed.
 */
export interface CreateFeedPayload {
  /** RSS feed URL (required) */
  url: string;
  /** User-defined feed name (required) */
  name: string;
  /** Feed category */
  category?: string;
  /** Optional strategic pillar alignment */
  pillar_id?: string | null;
  /** How often to check the feed, in hours */
  check_interval_hours?: number;
}

/**
 * Payload for updating an existing feed.
 */
export interface UpdateFeedPayload {
  /** Updated feed name */
  name?: string;
  /** Updated feed URL */
  url?: string;
  /** Updated feed category */
  category?: string;
  /** Updated pillar alignment */
  pillar_id?: string | null;
  /** Updated check interval */
  check_interval_hours?: number;
  /** Updated feed status */
  status?: string;
}

// ============================================================================
// Helper
// ============================================================================

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
    throw new Error(
      error.message || error.detail || `API error: ${response.status}`,
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch all RSS feeds with statistics.
 */
export async function getFeeds(token: string): Promise<Feed[]> {
  return apiRequest<Feed[]>("/api/v1/feeds", token);
}

/**
 * Create a new RSS feed.
 */
export async function createFeed(
  token: string,
  payload: CreateFeedPayload,
): Promise<Feed> {
  return apiRequest<Feed>("/api/v1/feeds", token, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Fetch a single feed with details.
 */
export async function getFeedDetail(
  token: string,
  feedId: string,
): Promise<Feed> {
  return apiRequest<Feed>(`/api/v1/feeds/${feedId}`, token);
}

/**
 * Update an existing feed.
 */
export async function updateFeed(
  token: string,
  feedId: string,
  payload: UpdateFeedPayload,
): Promise<Feed> {
  return apiRequest<Feed>(`/api/v1/feeds/${feedId}`, token, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

/**
 * Delete a feed.
 */
export async function deleteFeed(token: string, feedId: string): Promise<void> {
  return apiRequest<void>(`/api/v1/feeds/${feedId}`, token, {
    method: "DELETE",
  });
}

/**
 * Trigger a manual check of all active feeds.
 */
export async function triggerCheck(
  token: string,
): Promise<{ message: string; feeds_checked: number }> {
  return apiRequest<{ message: string; feeds_checked: number }>(
    "/api/v1/feeds/check",
    token,
    { method: "POST" },
  );
}

/**
 * Fetch items for a specific feed with optional filtering.
 */
export async function getFeedItems(
  token: string,
  feedId: string,
  options?: {
    limit?: number;
    offset?: number;
    triage_result?: string;
  },
): Promise<FeedItem[]> {
  const params = new URLSearchParams();
  if (options?.limit) params.append("limit", String(options.limit));
  if (options?.offset) params.append("offset", String(options.offset));
  if (options?.triage_result)
    params.append("triage_result", options.triage_result);

  const qs = params.toString();
  return apiRequest<FeedItem[]>(
    `/api/v1/feeds/${feedId}/items${qs ? `?${qs}` : ""}`,
    token,
  );
}
