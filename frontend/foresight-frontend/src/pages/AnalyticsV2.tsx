/**
 * Enhanced Analytics Dashboard Page
 *
 * Comprehensive analytics dashboard with system-wide and personal statistics.
 * Features:
 * - System-wide stats: sources, discovery, card distributions, trending
 * - Personal stats: following, engagement comparison, pillar affinity
 * - Social discovery: popular cards not followed
 */

import React, { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  Users,
  Eye,
  Database,
  Search,
  Layers,
  Target,
  Zap,
  ArrowRight,
  RefreshCw,
  Star,
  UserCircle,
  Globe,
  Sparkles,
  Heart,
  FolderOpen,
} from "lucide-react";
import { supabase } from "../App";
import { useAuthContext } from "../hooks/useAuthContext";
import { PillarBadge } from "../components/PillarBadge";
import { HorizonBadge } from "../components/HorizonBadge";
import TopDomainsLeaderboard from "../components/analytics/TopDomainsLeaderboard";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ============================================================================
// Type Definitions
// ============================================================================

interface PillarCoverageItem {
  pillar_code: string;
  pillar_name: string;
  count: number;
  percentage: number;
  avg_velocity: number | null;
  trend_direction?: "up" | "down" | "stable";
}

interface StageDistribution {
  stage_id: string;
  stage_name: string;
  count: number;
  percentage: number;
}

interface HorizonDistribution {
  horizon: string;
  label: string;
  count: number;
  percentage: number;
}

interface TrendingTopic {
  name: string;
  count: number;
  trend: string;
  velocity_avg: number | null;
}

interface SourceStats {
  total_sources: number;
  sources_this_week: number;
  sources_by_type: Record<string, number>;
}

interface DiscoveryStats {
  total_discovery_runs: number;
  runs_this_week: number;
  total_searches: number;
  searches_this_week: number;
  cards_discovered: number;
  avg_cards_per_run: number;
}

interface WorkstreamEngagement {
  total_workstreams: number;
  active_workstreams: number;
  unique_cards_in_workstreams: number;
  avg_cards_per_workstream: number;
}

interface FollowStats {
  total_follows: number;
  unique_cards_followed: number;
  unique_users_following: number;
  most_followed_cards: Array<{
    card_id: string;
    card_slug?: string;
    card_name: string;
    follower_count: number;
  }>;
}

interface SystemWideStats {
  total_cards: number;
  active_cards: number;
  cards_this_week: number;
  cards_this_month: number;
  cards_by_pillar: PillarCoverageItem[];
  cards_by_stage: StageDistribution[];
  cards_by_horizon: HorizonDistribution[];
  trending_pillars: TrendingTopic[];
  hot_topics: TrendingTopic[];
  source_stats: SourceStats;
  discovery_stats: DiscoveryStats;
  workstream_engagement: WorkstreamEngagement;
  follow_stats: FollowStats;
  generated_at: string;
}

interface UserFollowItem {
  card_id: string;
  card_slug?: string;
  card_name: string;
  pillar_id: string | null;
  horizon: string | null;
  velocity_score: number | null;
  followed_at: string;
  priority: string;
  follower_count: number;
}

interface PopularCard {
  card_id: string;
  card_slug?: string;
  card_name: string;
  summary: string;
  pillar_id: string | null;
  horizon: string | null;
  velocity_score: number | null;
  follower_count: number;
  is_followed_by_user: boolean;
}

interface UserEngagementComparison {
  user_follow_count: number;
  avg_community_follows: number;
  user_workstream_count: number;
  avg_community_workstreams: number;
  user_percentile_follows: number;
  user_percentile_workstreams: number;
}

interface PillarAffinity {
  pillar_code: string;
  pillar_name: string;
  user_count: number;
  user_percentage: number;
  community_percentage: number;
  affinity_score: number;
}

interface PersonalStats {
  following: UserFollowItem[];
  total_following: number;
  engagement: UserEngagementComparison;
  pillar_affinity: PillarAffinity[];
  popular_not_followed: PopularCard[];
  recently_popular: PopularCard[];
  workstream_count: number;
  cards_in_workstreams: number;
  generated_at: string;
}

// ============================================================================
// API Functions
// ============================================================================

async function fetchSystemStats(token: string): Promise<SystemWideStats> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/analytics/system-stats`,
    {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    },
  );
  if (!response.ok) throw new Error("Failed to fetch system stats");
  return response.json();
}

async function fetchPersonalStats(token: string): Promise<PersonalStats> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/analytics/personal-stats`,
    {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    },
  );
  if (!response.ok) throw new Error("Failed to fetch personal stats");
  return response.json();
}

// ============================================================================
// Helper Components
// ============================================================================

interface StatCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  icon: React.ReactNode;
  trend?: number | null;
  linkTo?: string;
  colorClass?: string;
}

const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  trend,
  linkTo,
  colorClass = "text-brand-blue",
}) => {
  const content = (
    <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-5 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg group">
      <div className="flex items-center justify-between">
        <div className="flex items-center">
          <div
            className={`flex-shrink-0 ${colorClass} group-hover:scale-110 transition-transform`}
          >
            {icon}
          </div>
          <div className="ml-3">
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
              {title}
            </p>
            <p className="text-2xl font-semibold text-gray-900 dark:text-white">
              {typeof value === "number" ? value.toLocaleString() : value}
            </p>
            {subtitle && (
              <p className="text-xs text-gray-400 dark:text-gray-500">
                {subtitle}
              </p>
            )}
          </div>
        </div>
        {trend !== undefined && trend !== null && (
          <div
            className={`flex items-center gap-1 text-sm font-medium ${
              trend > 0
                ? "text-emerald-600 dark:text-emerald-400"
                : trend < 0
                  ? "text-red-600 dark:text-red-400"
                  : "text-gray-500"
            }`}
          >
            {trend > 0 ? (
              <TrendingUp className="h-4 w-4" />
            ) : trend < 0 ? (
              <TrendingDown className="h-4 w-4" />
            ) : (
              <Minus className="h-4 w-4" />
            )}
            <span>
              {trend > 0 ? "+" : ""}
              {trend.toFixed(0)}%
            </span>
          </div>
        )}
      </div>
    </div>
  );
  if (linkTo) return <Link to={linkTo}>{content}</Link>;
  return content;
};

const TrendBadge: React.FC<{ trend: string }> = ({ trend }) => {
  if (trend === "up")
    return <TrendingUp className="h-3 w-3 text-emerald-500" />;
  if (trend === "down")
    return <TrendingDown className="h-3 w-3 text-red-500" />;
  return <Minus className="h-3 w-3 text-gray-400" />;
};

const LoadingSkeleton: React.FC = () => (
  <div className="animate-pulse space-y-6">
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="bg-white dark:bg-[#2d3166] rounded-lg p-5 h-24">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-2" />
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3" />
        </div>
      ))}
    </div>
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {[1, 2].map((i) => (
        <div key={i} className="bg-white dark:bg-[#2d3166] rounded-lg p-6 h-64">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-4" />
          <div className="space-y-3">
            {[1, 2, 3, 4].map((j) => (
              <div
                key={j}
                className="h-8 bg-gray-200 dark:bg-gray-700 rounded"
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  </div>
);

const EmptyState: React.FC<{
  title: string;
  description: string;
  icon: React.ReactNode;
}> = ({ title, description, icon }) => (
  <div className="text-center py-8">
    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-gray-100 dark:bg-gray-700 mb-4">
      {icon}
    </div>
    <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-1">
      {title}
    </h3>
    <p className="text-sm text-gray-500 dark:text-gray-400">{description}</p>
  </div>
);

// ============================================================================
// Section Components
// ============================================================================

const PillarDistribution: React.FC<{ data: PillarCoverageItem[] }> = ({
  data,
}) => {
  const maxCount = Math.max(...data.map((d) => d.count), 1);

  return (
    <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
        <Layers className="h-5 w-5 text-brand-blue" />
        Signals by Pillar
      </h3>
      <div className="space-y-3">
        {data.map((pillar) => (
          <div key={pillar.pillar_code} className="group">
            <div className="flex items-center justify-between text-sm mb-1">
              <div className="flex items-center gap-2">
                <PillarBadge pillarId={pillar.pillar_code} size="sm" />
                <span className="text-gray-600 dark:text-gray-300 hidden sm:inline">
                  {pillar.pillar_name}
                </span>
              </div>
              <div className="flex items-center gap-3 text-gray-500 dark:text-gray-400">
                <span>{pillar.count} signals</span>
                <span className="text-xs">({pillar.percentage}%)</span>
              </div>
            </div>
            <div className="h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-blue rounded-full transition-all duration-500"
                style={{ width: `${(pillar.count / maxCount) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const StageDistributionChart: React.FC<{ data: StageDistribution[] }> = ({
  data,
}) => {
  const maxCount = Math.max(...data.map((d) => d.count), 1);
  const stageColors = [
    "#3B82F6",
    "#8B5CF6",
    "#EC4899",
    "#F59E0B",
    "#10B981",
    "#06B6D4",
    "#6366F1",
    "#EF4444",
  ];

  return (
    <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
        <Target className="h-5 w-5 text-extended-purple" />
        Signals by Maturity Stage
      </h3>
      <div className="space-y-2">
        {data.map((stage, idx) => (
          <div key={stage.stage_id} className="flex items-center gap-3">
            <div
              className="w-20 text-xs text-gray-500 dark:text-gray-400 truncate"
              title={stage.stage_name}
            >
              {stage.stage_name}
            </div>
            <div className="flex-1 h-5 bg-gray-100 dark:bg-gray-700 rounded overflow-hidden">
              <div
                className="h-full rounded transition-all duration-500"
                style={{
                  width: `${(stage.count / maxCount) * 100}%`,
                  backgroundColor: stageColors[idx % stageColors.length],
                }}
              />
            </div>
            <div className="w-16 text-xs text-right text-gray-500 dark:text-gray-400">
              {stage.count} ({stage.percentage}%)
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const HotTopics: React.FC<{ topics: TrendingTopic[]; title: string }> = ({
  topics,
  title,
}) => {
  if (topics.length === 0) {
    return (
      <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Zap className="h-5 w-5 text-extended-orange" />
          {title}
        </h3>
        <EmptyState
          title="No trending topics"
          description="Trending topics will appear as more signals gain velocity."
          icon={<Zap className="h-6 w-6 text-gray-400" />}
        />
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
        <Zap className="h-5 w-5 text-extended-orange" />
        {title}
      </h3>
      <div className="space-y-3">
        {topics.map((topic, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between p-3 bg-gray-50 dark:bg-[#1e2048] rounded-lg"
          >
            <div className="flex items-center gap-3">
              <span className="w-6 h-6 flex items-center justify-center text-sm font-bold text-white bg-gradient-to-br from-brand-blue to-brand-green rounded-full">
                {idx + 1}
              </span>
              <div>
                <div className="font-medium text-gray-900 dark:text-white text-sm">
                  {topic.name}
                </div>
                {topic.velocity_avg && (
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Velocity: {topic.velocity_avg}
                  </div>
                )}
              </div>
            </div>
            <TrendBadge trend={topic.trend} />
          </div>
        ))}
      </div>
    </div>
  );
};

const EngagementComparison: React.FC<{
  engagement: UserEngagementComparison;
}> = ({ engagement }) => (
  <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6">
    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
      <Users className="h-5 w-5 text-brand-blue" />
      Your Engagement vs Community
    </h3>
    <div className="grid grid-cols-2 gap-6">
      <div>
        <div className="text-center mb-2">
          <div className="text-3xl font-bold text-brand-blue">
            {engagement.user_follow_count}
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Signals Following
          </div>
        </div>
        <div className="text-center text-xs text-gray-400">
          Avg: {engagement.avg_community_follows.toFixed(1)} | Top{" "}
          {(100 - engagement.user_percentile_follows).toFixed(0)}%
        </div>
        <div className="mt-2 h-2 bg-gray-100 dark:bg-gray-700 rounded-full">
          <div
            className="h-full bg-brand-blue rounded-full"
            style={{
              width: `${Math.min(engagement.user_percentile_follows, 100)}%`,
            }}
          />
        </div>
      </div>
      <div>
        <div className="text-center mb-2">
          <div className="text-3xl font-bold text-extended-purple">
            {engagement.user_workstream_count}
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Workstreams
          </div>
        </div>
        <div className="text-center text-xs text-gray-400">
          Avg: {engagement.avg_community_workstreams.toFixed(1)} | Top{" "}
          {(100 - engagement.user_percentile_workstreams).toFixed(0)}%
        </div>
        <div className="mt-2 h-2 bg-gray-100 dark:bg-gray-700 rounded-full">
          <div
            className="h-full bg-extended-purple rounded-full"
            style={{
              width: `${Math.min(engagement.user_percentile_workstreams, 100)}%`,
            }}
          />
        </div>
      </div>
    </div>
  </div>
);

const PillarAffinityChart: React.FC<{ affinity: PillarAffinity[] }> = ({
  affinity,
}) => (
  <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6">
    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
      <Heart className="h-5 w-5 text-red-500" />
      Your Pillar Interests
    </h3>
    <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
      How your follows compare to the community average
    </p>
    <div className="space-y-3">
      {affinity.slice(0, 6).map((p) => (
        <div key={p.pillar_code} className="flex items-center gap-3">
          <PillarBadge pillarId={p.pillar_code} size="sm" />
          <div className="flex-1">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-600 dark:text-gray-300">
                You: {p.user_percentage}%
              </span>
              <span className="text-gray-400">
                Community: {p.community_percentage}%
              </span>
            </div>
            <div className="flex h-2 gap-1">
              <div className="flex-1 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-brand-blue rounded-full"
                  style={{ width: `${p.user_percentage}%` }}
                />
              </div>
              <div className="flex-1 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gray-400 rounded-full"
                  style={{ width: `${p.community_percentage}%` }}
                />
              </div>
            </div>
          </div>
          <div
            className={`text-xs font-medium ${p.affinity_score > 0 ? "text-emerald-500" : p.affinity_score < 0 ? "text-gray-400" : ""}`}
          >
            {p.affinity_score > 0 ? "+" : ""}
            {p.affinity_score}%
          </div>
        </div>
      ))}
    </div>
  </div>
);

const PopularCardsSection: React.FC<{
  cards: PopularCard[];
  title: string;
  subtitle: string;
  emptyMessage: string;
}> = ({ cards, title, subtitle, emptyMessage }) => {
  if (cards.length === 0) {
    return (
      <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1 flex items-center gap-2">
          <Star className="h-5 w-5 text-amber-500" />
          {title}
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
          {subtitle}
        </p>
        <EmptyState
          title="No suggestions yet"
          description={emptyMessage}
          icon={<Star className="h-6 w-6 text-gray-400" />}
        />
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1 flex items-center gap-2">
        <Star className="h-5 w-5 text-amber-500" />
        {title}
      </h3>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        {subtitle}
      </p>
      <div className="space-y-3">
        {cards.map((card) => (
          <Link
            key={card.card_id}
            to={`/signals/${card.card_slug || card.card_id}`}
            className="block p-3 bg-gray-50 dark:bg-[#1e2048] rounded-lg hover:bg-gray-100 dark:hover:bg-[#252860] transition-colors"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-gray-900 dark:text-white text-sm truncate">
                    {card.card_name}
                  </span>
                  {card.pillar_id && (
                    <PillarBadge pillarId={card.pillar_id} size="sm" />
                  )}
                  {card.horizon && (
                    <HorizonBadge
                      horizon={card.horizon as "H1" | "H2" | "H3"}
                      size="sm"
                    />
                  )}
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
                  {card.summary}
                </p>
              </div>
              <div className="ml-3 flex items-center gap-1 text-xs text-gray-400">
                <Users className="h-3 w-3" />
                {card.follower_count}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

const AnalyticsV2: React.FC = () => {
  const { user: _user } = useAuthContext();
  const [activeTab, setActiveTab] = useState<"system" | "personal">("system");
  const [systemStats, setSystemStats] = useState<SystemWideStats | null>(null);
  const [personalStats, setPersonalStats] = useState<PersonalStats | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error("Not authenticated");
      }

      const [system, personal] = await Promise.all([
        fetchSystemStats(session.access_token),
        fetchPersonalStats(session.access_token),
      ]);

      setSystemStats(system);
      setPersonalStats(personal);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <BarChart3 className="h-8 w-8 text-brand-blue" />
            <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">
              Analytics
            </h1>
          </div>
        </div>
        <LoadingSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12">
          <div className="text-red-500 mb-4">{error}</div>
          <button
            onClick={loadData}
            className="inline-flex items-center px-4 py-2 bg-brand-blue text-white rounded-md hover:bg-brand-dark-blue"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <BarChart3 className="h-8 w-8 text-brand-blue" />
            <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">
              Analytics
            </h1>
          </div>
          <button
            onClick={loadData}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
            title="Refresh data"
          >
            <RefreshCw className="h-5 w-5" />
          </button>
        </div>
        <p className="text-gray-600 dark:text-gray-400">
          System-wide intelligence and personal engagement insights
        </p>
      </div>

      {/* Tab Switcher */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab("system")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
            activeTab === "system"
              ? "bg-brand-blue text-white"
              : "bg-white dark:bg-[#2d3166] text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#3d4176]"
          }`}
        >
          <Globe className="h-4 w-4" />
          System Overview
        </button>
        <button
          onClick={() => setActiveTab("personal")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
            activeTab === "personal"
              ? "bg-brand-blue text-white"
              : "bg-white dark:bg-[#2d3166] text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#3d4176]"
          }`}
        >
          <UserCircle className="h-4 w-4" />
          Personal Insights
        </button>
      </div>

      {/* System-wide Stats Tab */}
      {activeTab === "system" && systemStats && (
        <div className="space-y-6">
          {/* Top Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Total Signals"
              value={systemStats.active_cards}
              subtitle={`${systemStats.cards_this_week} new this week`}
              icon={<Eye className="h-6 w-6" />}
              linkTo="/discover"
              colorClass="text-brand-blue"
            />
            <StatCard
              title="Sources"
              value={systemStats.source_stats.total_sources}
              subtitle={`${systemStats.source_stats.sources_this_week} this week`}
              icon={<Database className="h-6 w-6" />}
              colorClass="text-extended-purple"
            />
            <StatCard
              title="Discovery Runs"
              value={systemStats.discovery_stats.total_discovery_runs}
              subtitle={`${systemStats.discovery_stats.cards_discovered} signals discovered`}
              icon={<Search className="h-6 w-6" />}
              colorClass="text-emerald-500"
            />
            <StatCard
              title="Community Engagement"
              value={systemStats.follow_stats.total_follows}
              subtitle={`${systemStats.follow_stats.unique_users_following} active users`}
              icon={<Users className="h-6 w-6" />}
              colorClass="text-extended-orange"
            />
          </div>

          {/* Secondary Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Workstreams"
              value={systemStats.workstream_engagement.total_workstreams}
              subtitle={`${systemStats.workstream_engagement.active_workstreams} active`}
              icon={<FolderOpen className="h-6 w-6" />}
              linkTo="/workstreams"
              colorClass="text-brand-blue"
            />
            <StatCard
              title="Signals in Workstreams"
              value={
                systemStats.workstream_engagement.unique_cards_in_workstreams
              }
              subtitle={`Avg: ${systemStats.workstream_engagement.avg_cards_per_workstream}/workstream`}
              icon={<Layers className="h-6 w-6" />}
              colorClass="text-extended-purple"
            />
            <StatCard
              title="Signals Followed"
              value={systemStats.follow_stats.unique_cards_followed}
              subtitle="Unique signals being tracked"
              icon={<Heart className="h-6 w-6" />}
              colorClass="text-red-500"
            />
            <StatCard
              title="Searches"
              value={systemStats.discovery_stats.total_searches}
              subtitle={`${systemStats.discovery_stats.searches_this_week} this week`}
              icon={<Search className="h-6 w-6" />}
              colorClass="text-amber-500"
            />
          </div>

          {/* Distribution Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <PillarDistribution data={systemStats.cards_by_pillar} />
            <StageDistributionChart data={systemStats.cards_by_stage} />
          </div>

          {/* Trending & Hot Topics */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <HotTopics
              topics={systemStats.trending_pillars}
              title="Trending Pillars"
            />
            <HotTopics
              topics={systemStats.hot_topics}
              title="High Velocity Signals"
            />
          </div>

          {/* Most Followed Signals */}
          {systemStats.follow_stats.most_followed_cards.length > 0 && (
            <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                <Star className="h-5 w-5 text-amber-500" />
                Most Followed Signals
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {systemStats.follow_stats.most_followed_cards.map(
                  (card, idx) => (
                    <Link
                      key={card.card_id}
                      to={`/signals/${card.card_slug || card.card_id}`}
                      className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-[#1e2048] rounded-lg hover:bg-gray-100 dark:hover:bg-[#252860] transition-colors"
                    >
                      <span className="w-6 h-6 flex items-center justify-center text-sm font-bold text-white bg-amber-500 rounded-full">
                        {idx + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-gray-900 dark:text-white text-sm truncate">
                          {card.card_name}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {card.follower_count} followers
                        </div>
                      </div>
                    </Link>
                  ),
                )}
              </div>
            </div>
          )}

          {/* Source Intelligence */}
          <TopDomainsLeaderboard />
        </div>
      )}

      {/* Personal Stats Tab */}
      {activeTab === "personal" && personalStats && (
        <div className="space-y-6">
          {/* Engagement Comparison */}
          <EngagementComparison engagement={personalStats.engagement} />

          {/* Your Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Following"
              value={personalStats.total_following}
              icon={<Heart className="h-6 w-6" />}
              linkTo="/discover?filter=following"
              colorClass="text-red-500"
            />
            <StatCard
              title="Workstreams"
              value={personalStats.workstream_count}
              icon={<FolderOpen className="h-6 w-6" />}
              linkTo="/workstreams"
              colorClass="text-brand-blue"
            />
            <StatCard
              title="Signals in Workstreams"
              value={personalStats.cards_in_workstreams}
              icon={<Layers className="h-6 w-6" />}
              colorClass="text-extended-purple"
            />
            <StatCard
              title="Engagement Rank"
              value={`Top ${(100 - personalStats.engagement.user_percentile_follows).toFixed(0)}%`}
              icon={<TrendingUp className="h-6 w-6" />}
              colorClass="text-emerald-500"
            />
          </div>

          {/* Pillar Affinity */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <PillarAffinityChart affinity={personalStats.pillar_affinity} />

            {/* Your Following */}
            <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                <Eye className="h-5 w-5 text-brand-blue" />
                Your Followed Signals
              </h3>
              {personalStats.following.length === 0 ? (
                <EmptyState
                  title="Not following any signals yet"
                  description="Browse the Discover page to find and follow signals that interest you."
                  icon={<Eye className="h-6 w-6 text-gray-400" />}
                />
              ) : (
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {personalStats.following.slice(0, 10).map((item) => (
                    <Link
                      key={item.card_id}
                      to={`/signals/${item.card_slug || item.card_id}`}
                      className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-[#1e2048] transition-colors"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="font-medium text-sm text-gray-900 dark:text-white truncate">
                          {item.card_name}
                        </span>
                        {item.pillar_id && (
                          <PillarBadge pillarId={item.pillar_id} size="sm" />
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        <Users className="h-3 w-3" />
                        {item.follower_count}
                      </div>
                    </Link>
                  ))}
                  {personalStats.following.length > 10 && (
                    <Link
                      to="/discover?filter=following"
                      className="block text-center text-sm text-brand-blue hover:underline py-2"
                    >
                      View all {personalStats.following.length} signals
                    </Link>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Social Discovery */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <PopularCardsSection
              cards={personalStats.popular_not_followed}
              title="Popular Signals You're Missing"
              subtitle="Signals others are following that you haven't discovered yet"
              emptyMessage="You're already following the most popular signals!"
            />
            <PopularCardsSection
              cards={personalStats.recently_popular}
              title="Trending This Week"
              subtitle="Signals gaining followers recently"
              emptyMessage="No new trending signals this week."
            />
          </div>
        </div>
      )}

      {/* Quick Links */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Link
          to="/discover"
          className="flex items-center justify-between p-4 bg-white dark:bg-[#2d3166] rounded-lg shadow hover:shadow-md transition-shadow group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand-blue/10 rounded-lg">
              <Target className="h-5 w-5 text-brand-blue" />
            </div>
            <div>
              <h3 className="font-medium text-gray-900 dark:text-white">
                Discover Signals
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Browse intelligence
              </p>
            </div>
          </div>
          <ArrowRight className="h-5 w-5 text-gray-400 group-hover:text-brand-blue group-hover:translate-x-1 transition-all" />
        </Link>

        <Link
          to="/workstreams"
          className="flex items-center justify-between p-4 bg-white dark:bg-[#2d3166] rounded-lg shadow hover:shadow-md transition-shadow group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-extended-purple/10 rounded-lg">
              <Layers className="h-5 w-5 text-extended-purple" />
            </div>
            <div>
              <h3 className="font-medium text-gray-900 dark:text-white">
                Workstreams
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Manage collections
              </p>
            </div>
          </div>
          <ArrowRight className="h-5 w-5 text-gray-400 group-hover:text-extended-purple group-hover:translate-x-1 transition-all" />
        </Link>

        <Link
          to="/discover/queue"
          className="flex items-center justify-between p-4 bg-white dark:bg-[#2d3166] rounded-lg shadow hover:shadow-md transition-shadow group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-extended-orange/10 rounded-lg">
              <Sparkles className="h-5 w-5 text-extended-orange" />
            </div>
            <div>
              <h3 className="font-medium text-gray-900 dark:text-white">
                Discovery Queue
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Review new signals
              </p>
            </div>
          </div>
          <ArrowRight className="h-5 w-5 text-gray-400 group-hover:text-extended-orange group-hover:translate-x-1 transition-all" />
        </Link>
      </div>

      {/* Footer timestamp */}
      <div className="mt-6 text-center text-xs text-gray-400">
        Last updated:{" "}
        {new Date(systemStats?.generated_at || Date.now()).toLocaleString()}
      </div>
    </div>
  );
};

export default AnalyticsV2;
