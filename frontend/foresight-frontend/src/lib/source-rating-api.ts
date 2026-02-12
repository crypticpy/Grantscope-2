/**
 * Source Rating API Client
 *
 * API functions for rating sources and retrieving aggregate rating data.
 * Follows the same patterns as discovery-api.ts for consistency.
 *
 * @module lib/source-rating-api
 */

import { API_BASE_URL } from "./config";

/**
 * A single user's rating of a source.
 */
export interface SourceRating {
  /** Unique identifier for this rating */
  id: string;
  /** The source being rated */
  source_id: string;
  /** The user who submitted the rating */
  user_id: string;
  /** Quality rating on a 1-5 scale */
  quality_rating: number;
  /** Relevance categorization */
  relevance_rating: "high" | "medium" | "low" | "not_relevant";
  /** Optional free-text comment */
  comment: string | null;
  /** Timestamp when the rating was created */
  created_at: string;
  /** Timestamp when the rating was last updated */
  updated_at: string;
}

/**
 * Aggregate rating data for a source, including the current user's rating.
 */
export interface SourceRatingAggregate {
  /** The source these ratings are for */
  source_id: string;
  /** Average quality rating across all users (1-5 scale) */
  avg_quality: number;
  /** Total number of ratings submitted */
  total_ratings: number;
  /** Distribution of relevance ratings (e.g. { high: 3, medium: 2, low: 1, not_relevant: 0 }) */
  relevance_distribution: Record<string, number>;
  /** The current authenticated user's rating, or null if they haven't rated */
  current_user_rating: SourceRating | null;
}

/**
 * Payload for creating or updating a source rating.
 */
export interface RateSourcePayload {
  /** Quality rating on a 1-5 scale */
  quality_rating: number;
  /** Relevance categorization */
  relevance_rating: string;
  /** Optional free-text comment */
  comment?: string;
}

/**
 * Submit or update a rating for a source.
 *
 * If the user has already rated this source, the existing rating is updated.
 * Otherwise a new rating is created.
 *
 * @param sourceId - The ID of the source to rate
 * @param data - The rating data to submit
 * @param token - Bearer token for authentication
 * @returns The created or updated rating
 * @throws Error if the API request fails
 */
export async function rateSource(
  sourceId: string,
  data: RateSourcePayload,
  token: string,
): Promise<SourceRating> {
  const res = await fetch(`${API_BASE_URL}/api/v1/sources/${sourceId}/rate`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorText = await res.text().catch(() => "Unknown error");
    throw new Error(`Failed to rate source: ${res.status} ${errorText}`);
  }
  return res.json();
}

/**
 * Retrieve aggregate rating data for a source.
 *
 * Returns the average quality rating, total count, relevance distribution,
 * and the current user's own rating if they have submitted one.
 *
 * @param sourceId - The ID of the source to get ratings for
 * @param token - Bearer token for authentication
 * @returns Aggregate rating data including the current user's rating
 * @throws Error if the API request fails
 */
export async function getSourceRatings(
  sourceId: string,
  token: string,
): Promise<SourceRatingAggregate> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/sources/${sourceId}/ratings`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );
  if (!res.ok) {
    const errorText = await res.text().catch(() => "Unknown error");
    throw new Error(`Failed to get ratings: ${res.status} ${errorText}`);
  }
  return res.json();
}

/**
 * Delete the current user's rating for a source.
 *
 * @param sourceId - The ID of the source whose rating to delete
 * @param token - Bearer token for authentication
 * @throws Error if the API request fails
 */
export async function deleteSourceRating(
  sourceId: string,
  token: string,
): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/v1/sources/${sourceId}/rate`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    const errorText = await res.text().catch(() => "Unknown error");
    throw new Error(`Failed to delete rating: ${res.status} ${errorText}`);
  }
}
