/**
 * Analytics API Helpers
 *
 * API functions for interacting with the analytics backend endpoints.
 * Provides trend velocity tracking, pillar coverage analysis, and
 * AI-generated strategic insights for the analytics dashboard.
 */

import { API_BASE_URL } from "./config";

// ============================================================================
// Velocity Types
// ============================================================================

/**
 * Individual data point for trend velocity time series.
 * Represents aggregated velocity metrics for a specific date.
 */
export interface VelocityDataPoint {
  date: string; // ISO format (YYYY-MM-DD)
  velocity: number; // Aggregated velocity score
  count: number; // Number of cards contributing to this data point
  avg_velocity_score?: number; // Average velocity score of cards (0-100)
}

/**
 * Response model for the trend velocity analytics endpoint.
 * Contains time-series data showing trend momentum over time.
 */
export interface VelocityResponse {
  data: VelocityDataPoint[];
  count: number; // Total number of data points
  period_start?: string; // ISO date string
  period_end?: string; // ISO date string
  week_over_week_change?: number; // Percentage change vs previous week
  total_cards_analyzed: number;
}

/**
 * Filter parameters for velocity endpoint
 */
export interface VelocityFilters {
  pillar_id?: string;
  stage_id?: string;
  start_date?: string; // ISO date string YYYY-MM-DD
  end_date?: string; // ISO date string YYYY-MM-DD
}

// ============================================================================
// Pillar Coverage Types
// ============================================================================

/**
 * Coverage data for a single strategic pillar.
 * Shows activity distribution for one of the 6 strategic pillars.
 */
export interface PillarCoverageItem {
  pillar_code: string; // Two-letter pillar code (CH, EW, HG, HH, MC, PS)
  pillar_name: string; // Full pillar name
  count: number; // Number of cards in this pillar
  percentage: number; // Percentage of total cards (0-100)
  avg_velocity?: number; // Average velocity score (0-100)
  trend_direction?: "up" | "down" | "stable"; // Trend vs previous period
}

/**
 * Response model for the pillar coverage analytics endpoint.
 * Contains distribution data for heatmap visualization.
 */
export interface PillarCoverageResponse {
  data: PillarCoverageItem[];
  total_cards: number;
  period_start?: string; // ISO date string
  period_end?: string; // ISO date string
}

/**
 * Filter parameters for pillar coverage endpoint
 */
export interface PillarCoverageFilters {
  stage_id?: string;
  start_date?: string; // ISO date string YYYY-MM-DD
  end_date?: string; // ISO date string YYYY-MM-DD
}

// ============================================================================
// Insights Types
// ============================================================================

/**
 * Individual AI-generated strategic insight.
 * Represents an emerging trend with AI-generated insight text.
 */
export interface InsightItem {
  trend_name: string; // Name of the emerging trend
  score: number; // Composite score indicating significance (0-100)
  insight: string; // AI-generated strategic insight text
  pillar_id?: string; // Associated pillar code
  card_id?: string; // UUID of the associated card
  card_slug?: string; // URL slug for navigation
  velocity_score?: number; // Velocity score of the trend (0-100)
}

/**
 * Response model for the AI insights analytics endpoint.
 * Contains top emerging trends with AI-generated insights.
 */
export interface InsightsResponse {
  insights: InsightItem[];
  generated_at?: string; // ISO timestamp
  period_analyzed?: string; // Time period description
  ai_available: boolean; // Whether AI service was available
  fallback_message?: string; // Message if AI unavailable
}

/**
 * Filter parameters for insights endpoint
 */
export interface InsightsFilters {
  pillar_id?: string;
  limit?: number; // Number of insights to return (default: 5)
}

// ============================================================================
// Analytics Filters (Combined)
// ============================================================================

/**
 * Combined filter options for analytics dashboard.
 * Used by AnalyticsFilters component to control all visualizations.
 */
export interface AnalyticsFilterOptions {
  pillar_id?: string;
  stage_id?: string;
  time_period?: "7d" | "30d" | "90d" | "1y";
  start_date?: string;
  end_date?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Helper function for API requests with authentication
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

  return response.json();
}

/**
 * Build URL query string from filter object
 */
function buildQueryString(
  filters: Record<string, string | number | undefined>,
): string {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") {
      params.append(key, String(value));
    }
  }

  const queryString = params.toString();
  return queryString ? `?${queryString}` : "";
}

/**
 * Convert time period to start/end dates
 */
export function timePeriodToDates(period: "7d" | "30d" | "90d" | "1y"): {
  start_date: string;
  end_date: string;
} {
  const endDate = new Date();
  const startDate = new Date();

  switch (period) {
    case "7d":
      startDate.setDate(startDate.getDate() - 7);
      break;
    case "30d":
      startDate.setDate(startDate.getDate() - 30);
      break;
    case "90d":
      startDate.setDate(startDate.getDate() - 90);
      break;
    case "1y":
      startDate.setFullYear(startDate.getFullYear() - 1);
      break;
  }

  return {
    start_date: startDate.toISOString().split("T")[0],
    end_date: endDate.toISOString().split("T")[0],
  };
}

// ============================================================================
// Velocity API Functions
// ============================================================================

/**
 * Fetch trend velocity time-series data
 *
 * Returns velocity metrics aggregated by date for charting
 * trend momentum over the selected time period.
 */
export async function fetchVelocityData(
  token: string,
  filters?: VelocityFilters,
): Promise<VelocityResponse> {
  const queryString = buildQueryString({
    pillar_id: filters?.pillar_id,
    stage_id: filters?.stage_id,
    start_date: filters?.start_date,
    end_date: filters?.end_date,
  });

  return apiRequest<VelocityResponse>(
    `/api/v1/analytics/velocity${queryString}`,
    token,
  );
}

/**
 * Fetch velocity data with time period convenience wrapper
 */
export async function fetchVelocityDataForPeriod(
  token: string,
  period: "7d" | "30d" | "90d" | "1y",
  filters?: Omit<VelocityFilters, "start_date" | "end_date">,
): Promise<VelocityResponse> {
  const { start_date, end_date } = timePeriodToDates(period);

  return fetchVelocityData(token, {
    ...filters,
    start_date,
    end_date,
  });
}

// ============================================================================
// Pillar Coverage API Functions
// ============================================================================

/**
 * Fetch pillar coverage distribution data
 *
 * Returns activity distribution across all 6 strategic pillars
 * for heatmap visualization.
 */
export async function fetchPillarCoverage(
  token: string,
  filters?: PillarCoverageFilters,
): Promise<PillarCoverageResponse> {
  const queryString = buildQueryString({
    stage_id: filters?.stage_id,
    start_date: filters?.start_date,
    end_date: filters?.end_date,
  });

  return apiRequest<PillarCoverageResponse>(
    `/api/v1/analytics/pillar-coverage${queryString}`,
    token,
  );
}

/**
 * Fetch pillar coverage with time period convenience wrapper
 */
export async function fetchPillarCoverageForPeriod(
  token: string,
  period: "7d" | "30d" | "90d" | "1y",
  filters?: Omit<PillarCoverageFilters, "start_date" | "end_date">,
): Promise<PillarCoverageResponse> {
  const { start_date, end_date } = timePeriodToDates(period);

  return fetchPillarCoverage(token, {
    ...filters,
    start_date,
    end_date,
  });
}

// ============================================================================
// Insights API Functions
// ============================================================================

/**
 * Fetch AI-generated strategic insights
 *
 * Returns top emerging trends with AI-generated insight text
 * for executive decision-making. Includes fallback handling
 * when AI service is unavailable.
 */
export async function fetchInsights(
  token: string,
  filters?: InsightsFilters,
): Promise<InsightsResponse> {
  const queryString = buildQueryString({
    pillar_id: filters?.pillar_id,
    limit: filters?.limit,
  });

  return apiRequest<InsightsResponse>(
    `/api/v1/analytics/insights${queryString}`,
    token,
  );
}

/**
 * Fetch insights for a specific pillar
 */
export async function fetchPillarInsights(
  token: string,
  pillarId: string,
  limit: number = 5,
): Promise<InsightsResponse> {
  return fetchInsights(token, {
    pillar_id: pillarId,
    limit,
  });
}

// ============================================================================
// Combined Analytics Fetch
// ============================================================================

/**
 * Fetch all analytics data in parallel
 *
 * Convenience function to load all analytics data for the dashboard
 * in a single call, with shared filter parameters.
 */
export async function fetchAllAnalyticsData(
  token: string,
  filters?: AnalyticsFilterOptions,
): Promise<{
  velocity: VelocityResponse;
  pillarCoverage: PillarCoverageResponse;
  insights: InsightsResponse;
}> {
  // Convert time period to dates if provided
  let dateFilters: { start_date?: string; end_date?: string } = {};
  if (filters?.time_period) {
    dateFilters = timePeriodToDates(filters.time_period);
  } else if (filters?.start_date || filters?.end_date) {
    dateFilters = {
      start_date: filters.start_date,
      end_date: filters.end_date,
    };
  }

  // Fetch all data in parallel
  const [velocity, pillarCoverage, insights] = await Promise.all([
    fetchVelocityData(token, {
      pillar_id: filters?.pillar_id,
      stage_id: filters?.stage_id,
      ...dateFilters,
    }),
    fetchPillarCoverage(token, {
      stage_id: filters?.stage_id,
      ...dateFilters,
    }),
    fetchInsights(token, {
      pillar_id: filters?.pillar_id,
    }),
  ]);

  return {
    velocity,
    pillarCoverage,
    insights,
  };
}
