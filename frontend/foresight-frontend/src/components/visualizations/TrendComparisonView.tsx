/**
 * TrendComparisonView Component
 *
 * Side-by-side comparison view for two trend cards showing:
 * - Dual timeline charts synchronized on the same X-axis
 * - Comparative metrics (score differences)
 * - Stage progression comparison
 * - Card metadata for context
 *
 * Requirements from spec:
 * - Two cards shown side-by-side
 * - Timeline charts synchronized
 * - Metrics comparable
 * - Responsive on tablet/desktop
 */

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowLeftRight,
  AlertCircle,
  Loader2,
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  ExternalLink,
} from "lucide-react";
import { format, parseISO } from "date-fns";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

import { cn } from "../../lib/utils";
import { parseStageNumber } from "../../lib/stage-utils";
import { supabase } from "../../App";
import { useAuthContext } from "../../hooks/useAuthContext";

// Badge components for card metadata
import { PillarBadge } from "../PillarBadge";
import { HorizonBadge } from "../HorizonBadge";
import { StageBadge } from "../StageBadge";

// API and types
import {
  compareCards,
  type CardComparisonResponse,
  type ScoreHistory,
  type CardData,
} from "../../lib/discovery-api";

// Visualization components from phase 6
import {
  ScoreTimelineChart,
  SCORE_CONFIGS,
  type ScoreType,
} from "./ScoreTimelineChart";
import { StageProgressionTimeline } from "./StageProgressionTimeline";

// ============================================================================
// Type Definitions
// ============================================================================

export interface TrendComparisonViewProps {
  /** Card IDs to compare (overrides URL params) */
  cardIds?: [string, string];
  /** Additional className for container */
  className?: string;
  /** Callback when a card is clicked */
  onCardClick?: (cardId: string) => void;
}

interface ScoreDifference {
  scoreType: ScoreType;
  name: string;
  card1Value: number | null;
  card2Value: number | null;
  difference: number | null;
  percentChange: number | null;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Calculate score differences between two cards
 */
function calculateScoreDifferences(
  card1: CardData,
  card2: CardData,
): ScoreDifference[] {
  return SCORE_CONFIGS.map((config) => {
    const card1Value = card1[config.key];
    const card2Value = card2[config.key];

    let difference: number | null = null;
    let percentChange: number | null = null;

    if (card1Value !== null && card2Value !== null) {
      difference = card2Value - card1Value;
      if (card1Value !== 0) {
        percentChange = ((card2Value - card1Value) / card1Value) * 100;
      }
    }

    return {
      scoreType: config.key,
      name: config.name,
      card1Value,
      card2Value,
      difference,
      percentChange,
    };
  });
}

/**
 * Merge score history from two cards for synchronized chart
 * Creates a unified timeline with both cards' data
 */
interface MergedDataPoint {
  date: string;
  timestamp: number;
  card1_maturity: number | null;
  card1_velocity: number | null;
  card1_novelty: number | null;
  card1_impact: number | null;
  card1_relevance: number | null;
  card1_risk: number | null;
  card1_opportunity: number | null;
  card2_maturity: number | null;
  card2_velocity: number | null;
  card2_novelty: number | null;
  card2_impact: number | null;
  card2_relevance: number | null;
  card2_risk: number | null;
  card2_opportunity: number | null;
}

function mergeScoreHistories(
  history1: ScoreHistory[],
  history2: ScoreHistory[],
): MergedDataPoint[] {
  // Collect all unique dates
  const dateMap = new Map<string, MergedDataPoint>();

  // Process card 1 history
  history1.forEach((record) => {
    const dateKey = record.recorded_at;
    const existing = dateMap.get(dateKey);
    const newData = {
      date: dateKey,
      timestamp: new Date(dateKey).getTime(),
      card1_maturity: record.maturity_score,
      card1_velocity: record.velocity_score,
      card1_novelty: record.novelty_score,
      card1_impact: record.impact_score,
      card1_relevance: record.relevance_score,
      card1_risk: record.risk_score,
      card1_opportunity: record.opportunity_score,
      card2_maturity: existing?.card2_maturity ?? null,
      card2_velocity: existing?.card2_velocity ?? null,
      card2_novelty: existing?.card2_novelty ?? null,
      card2_impact: existing?.card2_impact ?? null,
      card2_relevance: existing?.card2_relevance ?? null,
      card2_risk: existing?.card2_risk ?? null,
      card2_opportunity: existing?.card2_opportunity ?? null,
    };
    dateMap.set(dateKey, newData);
  });

  // Process card 2 history
  history2.forEach((record) => {
    const dateKey = record.recorded_at;
    const existing = dateMap.get(dateKey);
    if (existing) {
      existing.card2_maturity = record.maturity_score;
      existing.card2_velocity = record.velocity_score;
      existing.card2_novelty = record.novelty_score;
      existing.card2_impact = record.impact_score;
      existing.card2_relevance = record.relevance_score;
      existing.card2_risk = record.risk_score;
      existing.card2_opportunity = record.opportunity_score;
    } else {
      dateMap.set(dateKey, {
        date: dateKey,
        timestamp: new Date(dateKey).getTime(),
        card1_maturity: null,
        card1_velocity: null,
        card1_novelty: null,
        card1_impact: null,
        card1_relevance: null,
        card1_risk: null,
        card1_opportunity: null,
        card2_maturity: record.maturity_score,
        card2_velocity: record.velocity_score,
        card2_novelty: record.novelty_score,
        card2_impact: record.impact_score,
        card2_relevance: record.relevance_score,
        card2_risk: record.risk_score,
        card2_opportunity: record.opportunity_score,
      });
    }
  });

  // Sort by date ascending
  return Array.from(dateMap.values()).sort((a, b) => a.timestamp - b.timestamp);
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Loading state component
 */
function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px]">
      <Loader2 className="h-12 w-12 text-brand-blue animate-spin mb-4" />
      <p className="text-gray-600 dark:text-gray-300 text-lg">
        Loading comparison data...
      </p>
      <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
        This may take a moment
      </p>
    </div>
  );
}

/**
 * Error state component
 */
function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] text-center px-4">
      <AlertCircle className="h-16 w-16 text-red-400 mb-4" />
      <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
        Comparison Failed
      </h2>
      <p className="text-gray-600 dark:text-gray-300 max-w-md mb-4">
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center px-4 py-2 bg-brand-blue text-white rounded-lg hover:bg-brand-dark-blue transition-colors"
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          Try Again
        </button>
      )}
    </div>
  );
}

/**
 * Invalid params state
 */
function InvalidParamsState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] text-center px-4">
      <ArrowLeftRight className="h-16 w-16 text-gray-400 mb-4" />
      <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
        Select Two Signals to Compare
      </h2>
      <p className="text-gray-600 dark:text-gray-300 max-w-md mb-4">
        Please select exactly two signals to compare their trends and metrics
        side-by-side.
      </p>
      <Link
        to="/discover"
        className="inline-flex items-center px-4 py-2 bg-brand-blue text-white rounded-lg hover:bg-brand-dark-blue transition-colors"
      >
        Go to Discover
      </Link>
    </div>
  );
}

/**
 * Card header component with metadata
 */
interface CardHeaderProps {
  card: CardData;
  label: string;
  onCardClick?: (cardId: string) => void;
}

function CardHeader({ card, label, onCardClick }: CardHeaderProps) {
  const stageNumber = parseStageNumber(card.stage_id);

  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg shadow p-4">
      <div className="flex items-start justify-between mb-3">
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          {label}
        </span>
        {onCardClick && (
          <button
            onClick={() => onCardClick(card.id)}
            className="text-brand-blue hover:text-brand-dark-blue transition-colors"
            title="View opportunity details"
          >
            <ExternalLink className="h-4 w-4" />
          </button>
        )}
      </div>

      <Link to={`/signals/${card.slug}`} className="block group">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white group-hover:text-brand-blue transition-colors line-clamp-2">
          {card.name}
        </h3>
      </Link>

      {card.summary && (
        <p className="text-sm text-gray-600 dark:text-gray-300 mt-2 line-clamp-2">
          {card.summary}
        </p>
      )}

      <div className="flex items-center flex-wrap gap-2 mt-3">
        {card.pillar_id && <PillarBadge pillarId={card.pillar_id} size="sm" />}
        {card.horizon && <HorizonBadge horizon={card.horizon} size="sm" />}
        {stageNumber && <StageBadge stage={stageNumber} size="sm" showName />}
      </div>
    </div>
  );
}

/**
 * Score comparison metrics component
 */
interface ScoreComparisonProps {
  differences: ScoreDifference[];
  card1Name: string;
  card2Name: string;
}

function ScoreComparison({
  differences,
  card1Name,
  card2Name,
}: ScoreComparisonProps) {
  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
        <ArrowLeftRight className="h-5 w-5 text-brand-blue" />
        Score Comparison
      </h3>

      {/* Column headers */}
      <div className="grid grid-cols-4 gap-4 mb-3 text-xs font-medium text-gray-500 dark:text-gray-400">
        <div>Metric</div>
        <div className="text-center truncate" title={card1Name}>
          {card1Name}
        </div>
        <div className="text-center truncate" title={card2Name}>
          {card2Name}
        </div>
        <div className="text-center">Difference</div>
      </div>

      <div className="space-y-2">
        {differences.map((diff) => {
          const isPositive = diff.difference !== null && diff.difference > 0;
          const isNegative = diff.difference !== null && diff.difference < 0;
          const isEqual = diff.difference === 0;

          return (
            <div
              key={diff.scoreType}
              className="grid grid-cols-4 gap-4 py-2 border-b border-gray-100 dark:border-gray-700 last:border-0"
            >
              <div className="text-sm font-medium text-gray-700 dark:text-gray-200">
                {diff.name}
              </div>
              <div className="text-center">
                <span className="inline-flex items-center justify-center min-w-[40px] px-2 py-0.5 rounded text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200">
                  {diff.card1Value !== null ? diff.card1Value : "-"}
                </span>
              </div>
              <div className="text-center">
                <span className="inline-flex items-center justify-center min-w-[40px] px-2 py-0.5 rounded text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200">
                  {diff.card2Value !== null ? diff.card2Value : "-"}
                </span>
              </div>
              <div className="text-center">
                {diff.difference !== null ? (
                  <span
                    className={cn(
                      "inline-flex items-center justify-center gap-1 min-w-[60px] px-2 py-0.5 rounded text-sm font-medium",
                      isPositive &&
                        "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300",
                      isNegative &&
                        "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300",
                      isEqual &&
                        "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300",
                    )}
                  >
                    {isPositive && <TrendingUp className="h-3 w-3" />}
                    {isNegative && <TrendingDown className="h-3 w-3" />}
                    {isEqual && <Minus className="h-3 w-3" />}
                    {isPositive && "+"}
                    {diff.difference}
                  </span>
                ) : (
                  <span className="text-gray-400">-</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Synchronized timeline chart for comparing two cards
 */
interface SynchronizedTimelineProps {
  data: MergedDataPoint[];
  card1Name: string;
  card2Name: string;
  selectedScore: ScoreType;
  onScoreChange: (score: ScoreType) => void;
  height?: number;
}

function SynchronizedTimeline({
  data,
  card1Name,
  card2Name,
  selectedScore,
  onScoreChange,
  height = 350,
}: SynchronizedTimelineProps) {
  const scoreConfig = SCORE_CONFIGS.find((c) => c.key === selectedScore);

  // Map score key to chart data keys
  const scoreKeyMap: Record<ScoreType, { card1: string; card2: string }> = {
    maturity_score: { card1: "card1_maturity", card2: "card2_maturity" },
    velocity_score: { card1: "card1_velocity", card2: "card2_velocity" },
    novelty_score: { card1: "card1_novelty", card2: "card2_novelty" },
    impact_score: { card1: "card1_impact", card2: "card2_impact" },
    relevance_score: { card1: "card1_relevance", card2: "card2_relevance" },
    risk_score: { card1: "card1_risk", card2: "card2_risk" },
    opportunity_score: {
      card1: "card1_opportunity",
      card2: "card2_opportunity",
    },
  };

  const keys = scoreKeyMap[selectedScore];

  const formatXAxisTick = (value: string) => {
    try {
      const date = parseISO(value);
      if (data.length > 90) {
        return format(date, "MMM yyyy");
      }
      return format(date, "MMM d");
    } catch {
      return value;
    }
  };

  if (data.length < 2) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-lg shadow p-6">
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <TrendingUp className="h-12 w-12 text-gray-300 dark:text-gray-600 mb-3" />
          <p className="text-gray-500 dark:text-gray-400">
            Not enough historical data for timeline comparison
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-brand-blue" />
          Timeline Comparison
        </h3>

        {/* Score selector */}
        <select
          value={selectedScore}
          onChange={(e) => onScoreChange(e.target.value as ScoreType)}
          className="px-3 py-1.5 text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-dark-surface-elevated text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue focus:border-transparent"
        >
          {SCORE_CONFIGS.map((config) => (
            <option key={config.key} value={config.key}>
              {config.name}
            </option>
          ))}
        </select>
      </div>

      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="currentColor"
              className="text-gray-200 dark:text-gray-700"
              opacity={0.5}
            />
            <XAxis
              dataKey="date"
              tickFormatter={formatXAxisTick}
              tick={{ fontSize: 11 }}
              tickLine={{ stroke: "currentColor" }}
              axisLine={{ stroke: "currentColor" }}
              className="text-gray-500 dark:text-gray-400"
              interval="preserveStartEnd"
              minTickGap={50}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 11 }}
              tickLine={{ stroke: "currentColor" }}
              axisLine={{ stroke: "currentColor" }}
              className="text-gray-500 dark:text-gray-400"
              tickCount={6}
              width={40}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload) return null;
                return (
                  <div className="bg-white dark:bg-dark-surface border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3">
                    <div className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-2 pb-2 border-b border-gray-200 dark:border-gray-700">
                      {format(parseISO(label), "MMM d, yyyy")}
                    </div>
                    <div className="space-y-1.5">
                      {payload.map((item) => (
                        <div
                          key={item.dataKey}
                          className="flex items-center justify-between gap-4 text-xs"
                        >
                          <div className="flex items-center gap-2">
                            <div
                              className="w-2 h-2 rounded-full"
                              style={{ backgroundColor: item.color }}
                            />
                            <span className="text-gray-600 dark:text-gray-300">
                              {item.name}
                            </span>
                          </div>
                          <span className="font-medium text-gray-900 dark:text-gray-100">
                            {item.value !== null
                              ? Math.round(item.value as number)
                              : "-"}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              }}
            />
            <Legend wrapperStyle={{ paddingTop: "20px" }} />
            <Line
              type="monotone"
              dataKey={keys.card1}
              name={card1Name}
              stroke={scoreConfig?.color || "#8884d8"}
              strokeWidth={2}
              dot={data.length <= 30}
              connectNulls
              isAnimationActive={data.length <= 365}
            />
            <Line
              type="monotone"
              dataKey={keys.card2}
              name={card2Name}
              stroke={
                scoreConfig?.color ? `${scoreConfig.color}80` : "#8884d880"
              }
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={data.length <= 30}
              connectNulls
              isAnimationActive={data.length <= 365}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Legend explanation */}
      <div className="mt-4 flex items-center justify-center gap-6 text-xs text-gray-500 dark:text-gray-400">
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-0.5"
            style={{ backgroundColor: scoreConfig?.color || "#8884d8" }}
          />
          <span>Solid line: {card1Name}</span>
        </div>
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-0.5"
            style={{
              backgroundColor: scoreConfig?.color || "#8884d8",
              opacity: 0.5,
              backgroundImage:
                "repeating-linear-gradient(90deg, transparent, transparent 3px, currentColor 3px, currentColor 6px)",
            }}
          />
          <span>Dashed line: {card2Name}</span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * TrendComparisonView - Side-by-side comparison of two trend cards
 *
 * Access via URL: /compare?card_ids=id1,id2
 * Or pass cardIds prop directly
 */
export function TrendComparisonView({
  cardIds: propCardIds,
  className,
  onCardClick,
}: TrendComparisonViewProps) {
  const { user } = useAuthContext();
  const [searchParams] = useSearchParams();

  // State
  const [comparisonData, setComparisonData] =
    useState<CardComparisonResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedScore, setSelectedScore] =
    useState<ScoreType>("maturity_score");

  // Parse card IDs from props or URL
  const cardIds = useMemo((): [string, string] | null => {
    if (propCardIds) return propCardIds;

    const idsParam = searchParams.get("card_ids");
    if (!idsParam) return null;

    const ids = idsParam.split(",").filter(Boolean);
    if (ids.length !== 2) return null;

    return [ids[0], ids[1]];
  }, [propCardIds, searchParams]);

  // Fetch comparison data
  const fetchComparisonData = useCallback(async () => {
    if (!cardIds || !user) return;

    setLoading(true);
    setError(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const token = session?.access_token;

      if (!token) {
        throw new Error("Not authenticated");
      }

      const data = await compareCards(token, cardIds[0], cardIds[1]);
      setComparisonData(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load comparison data";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [cardIds, user]);

  // Load data on mount or when cardIds change
  useEffect(() => {
    fetchComparisonData();
  }, [fetchComparisonData]);

  // Calculate derived data
  const mergedHistory = useMemo(() => {
    if (!comparisonData) return [];
    return mergeScoreHistories(
      comparisonData.card1.score_history,
      comparisonData.card2.score_history,
    );
  }, [comparisonData]);

  const scoreDifferences = useMemo(() => {
    if (!comparisonData) return [];
    return calculateScoreDifferences(
      comparisonData.card1.card,
      comparisonData.card2.card,
    );
  }, [comparisonData]);

  // Render states
  if (!cardIds) {
    return (
      <div
        className={cn("max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8", className)}
      >
        <InvalidParamsState />
      </div>
    );
  }

  if (loading) {
    return (
      <div
        className={cn("max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8", className)}
      >
        <LoadingState />
      </div>
    );
  }

  if (error) {
    return (
      <div
        className={cn("max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8", className)}
      >
        <ErrorState message={error} onRetry={fetchComparisonData} />
      </div>
    );
  }

  if (!comparisonData) {
    return (
      <div
        className={cn("max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8", className)}
      >
        <ErrorState
          message="No comparison data available"
          onRetry={fetchComparisonData}
        />
      </div>
    );
  }

  const { card1, card2 } = comparisonData;

  return (
    <div
      className={cn("max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8", className)}
    >
      {/* Header */}
      <div className="mb-8">
        <Link
          to="/discover"
          className="inline-flex items-center text-sm text-gray-500 dark:text-gray-400 hover:text-brand-blue mb-4 transition-colors"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Discover
        </Link>

        <div className="flex items-center gap-3">
          <ArrowLeftRight className="h-8 w-8 text-brand-blue" />
          <h1 className="text-2xl font-bold text-brand-dark-blue dark:text-white">
            Trend Comparison
          </h1>
        </div>
        <p className="mt-2 text-gray-600 dark:text-gray-300">
          Comparing score trends and progression between two signals
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Generated:{" "}
          {format(
            parseISO(comparisonData.comparison_generated_at),
            "MMM d, yyyy h:mm a",
          )}
        </p>
      </div>

      {/* Card Headers - Side by Side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <CardHeader
          card={card1.card}
          label="Opportunity A"
          onCardClick={onCardClick}
        />
        <CardHeader
          card={card2.card}
          label="Opportunity B"
          onCardClick={onCardClick}
        />
      </div>

      {/* Score Comparison */}
      <div className="mb-8">
        <ScoreComparison
          differences={scoreDifferences}
          card1Name={card1.card.name}
          card2Name={card2.card.name}
        />
      </div>

      {/* Synchronized Timeline */}
      <div className="mb-8">
        <SynchronizedTimeline
          data={mergedHistory}
          card1Name={card1.card.name}
          card2Name={card2.card.name}
          selectedScore={selectedScore}
          onScoreChange={setSelectedScore}
        />
      </div>

      {/* Individual Score Timelines - Side by Side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <ScoreTimelineChart
          data={card1.score_history}
          title={`${card1.card.name} - Score History`}
          height={300}
        />
        <ScoreTimelineChart
          data={card2.score_history}
          title={`${card2.card.name} - Score History`}
          height={300}
        />
      </div>

      {/* Stage Progression - Side by Side */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          Stage Progression Comparison
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
              {card1.card.name}
            </h3>
            <StageProgressionTimeline
              stageHistory={card1.stage_history}
              currentStage={parseStageNumber(card1.card.stage_id) ?? undefined}
              compact
            />
          </div>
          <div>
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
              {card2.card.name}
            </h3>
            <StageProgressionTimeline
              stageHistory={card2.stage_history}
              currentStage={parseStageNumber(card2.card.stage_id) ?? undefined}
              compact
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default TrendComparisonView;
