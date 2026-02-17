/**
 * InsightsPanel Component
 *
 * Displays AI-generated strategic insights for the analytics dashboard.
 * Shows top emerging trends with scores and AI-generated insight text.
 * Handles loading states, empty states, and AI service unavailability fallback.
 */

import React from "react";
import { Link } from "react-router-dom";
import {
  Sparkles,
  TrendingUp,
  AlertCircle,
  Lightbulb,
  ArrowRight,
  Zap,
} from "lucide-react";
import { getPillarByCode } from "../../data/taxonomy";
import { PillarBadge } from "../PillarBadge";

/**
 * Individual insight item from the analytics API
 */
export interface InsightItem {
  trend_name: string;
  score: number;
  insight: string;
  pillar_id?: string;
  card_id?: string;
  card_slug?: string;
  velocity_score?: number;
}

/**
 * Response structure from /api/v1/analytics/insights endpoint
 */
export interface InsightsResponse {
  insights: InsightItem[];
  generated_at?: string;
  period_analyzed?: string;
  ai_available: boolean;
  fallback_message?: string;
}

interface InsightsPanelProps {
  /** Insights data from API */
  data: InsightsResponse | null;
  /** Whether data is currently loading */
  loading?: boolean;
  /** Error message if fetch failed */
  error?: string | null;
  /** Optional title override */
  title?: string;
  /** Maximum number of insights to display */
  maxInsights?: number;
}

/**
 * Get score color based on value (0-100)
 */
const getScoreColor = (score: number): string => {
  if (score >= 80) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 60) return "text-blue-600 dark:text-blue-400";
  if (score >= 40) return "text-amber-600 dark:text-amber-400";
  return "text-gray-600 dark:text-gray-400";
};

/**
 * Get score background color for badge
 */
const getScoreBgColor = (score: number): string => {
  if (score >= 80) return "bg-emerald-100 dark:bg-emerald-900/30";
  if (score >= 60) return "bg-blue-100 dark:bg-blue-900/30";
  if (score >= 40) return "bg-amber-100 dark:bg-amber-900/30";
  return "bg-gray-100 dark:bg-gray-700";
};

/**
 * Loading skeleton for insights
 */
const InsightSkeleton: React.FC = () => (
  <div className="animate-pulse space-y-4">
    {[1, 2, 3].map((i) => (
      <div
        key={i}
        className="bg-white dark:bg-dark-surface rounded-lg p-4 border border-gray-100 dark:border-gray-700"
      >
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 bg-gray-200 dark:bg-gray-600 rounded-full" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-gray-200 dark:bg-gray-600 rounded w-3/4" />
            <div className="h-3 bg-gray-200 dark:bg-gray-600 rounded w-full" />
            <div className="h-3 bg-gray-200 dark:bg-gray-600 rounded w-2/3" />
          </div>
        </div>
      </div>
    ))}
  </div>
);

/**
 * Empty state when no insights available
 */
const EmptyState: React.FC = () => (
  <div className="text-center py-8">
    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-gray-100 dark:bg-gray-700 mb-4">
      <Lightbulb className="h-6 w-6 text-gray-400" />
    </div>
    <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-1">
      No insights available
    </h3>
    <p className="text-sm text-gray-500 dark:text-gray-400">
      Insights will appear when there is sufficient trend data to analyze.
    </p>
  </div>
);

/**
 * Fallback message when AI service is unavailable
 */
const AIUnavailableFallback: React.FC<{ message?: string }> = ({ message }) => (
  <div className="flex items-start gap-3 p-4 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700">
    <AlertCircle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
    <div>
      <h4 className="text-sm font-medium text-amber-800 dark:text-amber-200">
        Insights temporarily unavailable
      </h4>
      <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
        {message ||
          "AI-powered insights are currently unavailable. Showing summary data instead."}
      </p>
    </div>
  </div>
);

/**
 * Error state display
 */
const ErrorState: React.FC<{ error: string }> = ({ error }) => (
  <div className="flex items-start gap-3 p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700">
    <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
    <div>
      <h4 className="text-sm font-medium text-red-800 dark:text-red-200">
        Failed to load insights
      </h4>
      <p className="text-sm text-red-700 dark:text-red-300 mt-1">{error}</p>
    </div>
  </div>
);

/**
 * Individual insight card
 */
const InsightCard: React.FC<{ insight: InsightItem; index: number }> = ({
  insight,
  index,
}) => {
  const pillar = insight.pillar_id ? getPillarByCode(insight.pillar_id) : null;

  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg p-4 border border-gray-100 dark:border-gray-700 transition-all duration-200 hover:shadow-md hover:border-brand-blue/30">
      <div className="flex items-start gap-3">
        {/* Rank indicator - Austin brand colors */}
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-brand-blue to-brand-green flex items-center justify-center text-white font-semibold text-sm">
          {index + 1}
        </div>

        <div className="flex-1 min-w-0">
          {/* Header with trend name and score */}
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="font-medium text-gray-900 dark:text-white truncate">
                {insight.card_slug ? (
                  <Link
                    to={`/signals/${insight.card_slug}`}
                    className="hover:text-brand-blue transition-colors"
                  >
                    {insight.trend_name}
                  </Link>
                ) : (
                  insight.trend_name
                )}
              </h4>
              {pillar && (
                <PillarBadge
                  pillarId={insight.pillar_id!}
                  size="sm"
                  showIcon={false}
                />
              )}
            </div>

            {/* Score badge */}
            <div
              className={`flex-shrink-0 px-2.5 py-1 rounded-full text-xs font-semibold ${getScoreBgColor(insight.score)} ${getScoreColor(insight.score)}`}
            >
              {insight.score.toFixed(0)}
            </div>
          </div>

          {/* Insight text */}
          <p className="text-sm text-gray-600 dark:text-gray-300 mb-3 line-clamp-3">
            {insight.insight}
          </p>

          {/* Metrics row */}
          <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
            {insight.velocity_score !== undefined && (
              <span className="flex items-center gap-1">
                <Zap className="h-3.5 w-3.5" />
                Velocity: {insight.velocity_score}
              </span>
            )}
            <span className="flex items-center gap-1">
              <TrendingUp className="h-3.5 w-3.5" />
              Score: {insight.score.toFixed(1)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * InsightsPanel - Main component for displaying AI-generated insights
 */
const InsightsPanel: React.FC<InsightsPanelProps> = ({
  data,
  loading = false,
  error = null,
  title = "AI-Generated Insights",
  maxInsights = 5,
}) => {
  // Handle loading state
  if (loading) {
    return (
      <div className="bg-gray-50 dark:bg-dark-surface rounded-lg p-6">
        <div className="flex items-center gap-2 mb-2">
          <Sparkles className="h-5 w-5 text-brand-blue animate-pulse" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {title}
          </h3>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Analyzing top trends and generating strategic insights...
        </p>
        <InsightSkeleton />
      </div>
    );
  }

  // Handle error state
  if (error) {
    return (
      <div className="bg-gray-50 dark:bg-dark-surface rounded-lg p-6">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="h-5 w-5 text-brand-blue" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {title}
          </h3>
        </div>
        <ErrorState error={error} />
      </div>
    );
  }

  // Get insights to display
  const insights = data?.insights?.slice(0, maxInsights) || [];
  const aiAvailable = data?.ai_available ?? true;
  const fallbackMessage = data?.fallback_message;

  return (
    <div className="bg-gray-50 dark:bg-dark-surface rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-brand-blue" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {title}
          </h3>
        </div>
        {data?.generated_at && (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Updated {new Date(data.generated_at).toLocaleString()}
          </span>
        )}
      </div>

      {/* Explanatory blurb */}
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        AI analyzes the highest-scoring trends to surface strategic implications
        for city leadership.
        {data?.period_analyzed &&
          ` Based on ${data.period_analyzed.toLowerCase()}.`}
      </p>

      {/* AI unavailable fallback */}
      {!aiAvailable && (
        <div className="mb-4">
          <AIUnavailableFallback message={fallbackMessage} />
        </div>
      )}

      {/* Insights list or empty state */}
      {insights.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-3">
          {insights.map((insight, index) => (
            <InsightCard
              key={insight.card_id || `insight-${index}`}
              insight={insight}
              index={index}
            />
          ))}
        </div>
      )}

      {/* View all link when there are more insights */}
      {data && data.insights && data.insights.length > maxInsights && (
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <Link
            to="/discover"
            className="inline-flex items-center text-sm font-medium text-brand-blue hover:text-brand-dark-blue transition-colors group"
          >
            View all trends
            <ArrowRight className="ml-1 h-4 w-4 group-hover:translate-x-1 transition-transform" />
          </Link>
        </div>
      )}
    </div>
  );
};

export default InsightsPanel;
