/**
 * Quality API Helpers
 *
 * API functions for interacting with the Source Quality Index (SQI) endpoints.
 * Provides typed access to card quality data including the overall composite
 * score and its five component dimensions.
 *
 * @module quality-api
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// =============================================================================
// Types
// =============================================================================

/**
 * Individual quality component score returned by the API.
 */
export interface QualityComponent {
  /** Component identifier (e.g. "source_authority") */
  name: string;
  /** Component score 0-100 */
  score: number;
  /** Weight of this component in the overall SQI (0-1) */
  weight: number;
}

/**
 * Full quality response from GET /api/v1/cards/:cardId/quality.
 */
export interface CardQualityData {
  /** The card ID */
  card_id: string;
  /** Overall SQI composite score 0-100 */
  overall_score: number;
  /** Quality tier label ("High Confidence" | "Moderate" | "Needs Verification") */
  tier: string;
  /** Number of sources backing this card */
  source_count: number;
  /** Breakdown of the five component scores */
  components: QualityComponent[];
  /** ISO 8601 timestamp of last calculation */
  calculated_at: string;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Fetch the quality data (SQI score and component breakdown) for a card.
 *
 * @param cardId - UUID of the card
 * @param token - Bearer auth token from Supabase session
 * @returns The card quality data including component scores
 * @throws {Error} If the request fails or returns a non-OK status
 *
 * @example
 * ```ts
 * const quality = await getCardQuality(card.id, session.access_token);
 * console.log(quality.overall_score); // 78
 * ```
 */
export async function getCardQuality(
  cardId: string,
  token: string,
): Promise<CardQualityData> {
  const res = await fetch(`${API_BASE_URL}/api/v1/cards/${cardId}/quality`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch quality data");
  return res.json();
}

/**
 * Trigger a recalculation of the quality score for a card.
 *
 * @param cardId - UUID of the card
 * @param token - Bearer auth token from Supabase session
 * @returns The newly calculated card quality data
 * @throws {Error} If the request fails or returns a non-OK status
 *
 * @example
 * ```ts
 * const refreshed = await recalculateCardQuality(card.id, session.access_token);
 * ```
 */
export async function recalculateCardQuality(
  cardId: string,
  token: string,
): Promise<CardQualityData> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/cards/${cardId}/quality/recalculate`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!res.ok) throw new Error("Failed to recalculate quality");
  return res.json();
}
