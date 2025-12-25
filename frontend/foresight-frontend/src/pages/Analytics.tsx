/**
 * Analytics Dashboard Page
 *
 * Comprehensive analytics dashboard for strategic intelligence visualization.
 * Integrates trend velocity charts, pillar coverage heatmap, and AI-generated insights.
 * Provides interactive filtering by pillar, maturity stage, and time period.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { format, subDays, subMonths, parseISO } from 'date-fns';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  Calendar,
  Filter,
  RefreshCw,
  ArrowRight,
  Activity,
  Target,
  Layers,
} from 'lucide-react';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { pillars, stages, type Pillar, type MaturityStage } from '../data/taxonomy';
import TrendVelocityChart, { type VelocityDataPoint } from '../components/analytics/TrendVelocityChart';
import PillarHeatmap, { type PillarCoverageItem } from '../components/analytics/PillarHeatmap';
import InsightsPanel, { type InsightsResponse } from '../components/analytics/InsightsPanel';

// ============================================================================
// Type Definitions
// ============================================================================

interface AnalyticsFilters {
  pillarId: string | null;
  stageId: string | null;
  timePeriod: '7d' | '30d' | '90d' | '1y';
}

interface AnalyticsStats {
  totalCards: number;
  activeCards: number;
  newThisWeek: number;
  avgVelocity: number;
}

// ============================================================================
// API Constants
// ============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ============================================================================
// API Helper Functions
// ============================================================================

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

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

interface VelocityResponse {
  data: VelocityDataPoint[];
  total_count: number;
  week_over_week_change: number | null;
  period_start: string | null;
  period_end: string | null;
}

interface PillarCoverageResponse {
  data: PillarCoverageItem[];
  total_cards: number;
}

async function fetchVelocityData(
  token: string,
  filters: {
    pillar_id?: string;
    stage_id?: string;
    start_date?: string;
    end_date?: string;
  }
): Promise<VelocityResponse> {
  const params = new URLSearchParams();
  if (filters.pillar_id) params.append('pillar_id', filters.pillar_id);
  if (filters.stage_id) params.append('stage_id', filters.stage_id);
  if (filters.start_date) params.append('start_date', filters.start_date);
  if (filters.end_date) params.append('end_date', filters.end_date);

  const queryString = params.toString();
  const endpoint = `/api/v1/analytics/velocity${queryString ? `?${queryString}` : ''}`;

  return apiRequest<VelocityResponse>(endpoint, token);
}

async function fetchPillarCoverage(
  token: string,
  filters: {
    stage_id?: string;
    start_date?: string;
    end_date?: string;
  }
): Promise<PillarCoverageResponse> {
  const params = new URLSearchParams();
  if (filters.stage_id) params.append('stage_id', filters.stage_id);
  if (filters.start_date) params.append('start_date', filters.start_date);
  if (filters.end_date) params.append('end_date', filters.end_date);

  const queryString = params.toString();
  const endpoint = `/api/v1/analytics/pillar-coverage${queryString ? `?${queryString}` : ''}`;

  return apiRequest<PillarCoverageResponse>(endpoint, token);
}

async function fetchInsights(
  token: string,
  filters: {
    pillar_id?: string;
    limit?: number;
  }
): Promise<InsightsResponse> {
  const params = new URLSearchParams();
  if (filters.pillar_id) params.append('pillar_id', filters.pillar_id);
  if (filters.limit) params.append('limit', String(filters.limit));

  const queryString = params.toString();
  const endpoint = `/api/v1/analytics/insights${queryString ? `?${queryString}` : ''}`;

  return apiRequest<InsightsResponse>(endpoint, token);
}

// ============================================================================
// Time Period Helper
// ============================================================================

function getDateRangeFromPeriod(period: '7d' | '30d' | '90d' | '1y'): { start: Date; end: Date } {
  const end = new Date();
  let start: Date;

  switch (period) {
    case '7d':
      start = subDays(end, 7);
      break;
    case '30d':
      start = subDays(end, 30);
      break;
    case '90d':
      start = subDays(end, 90);
      break;
    case '1y':
      start = subMonths(end, 12);
      break;
    default:
      start = subDays(end, 30);
  }

  return { start, end };
}

// ============================================================================
// Analytics Filters Component
// ============================================================================

interface AnalyticsFiltersProps {
  filters: AnalyticsFilters;
  onFiltersChange: (filters: AnalyticsFilters) => void;
  loading?: boolean;
}

const AnalyticsFiltersComponent: React.FC<AnalyticsFiltersProps> = ({
  filters,
  onFiltersChange,
  loading = false,
}) => {
  const timePeriodOptions: { value: '7d' | '30d' | '90d' | '1y'; label: string }[] = [
    { value: '7d', label: 'Last 7 days' },
    { value: '30d', label: 'Last 30 days' },
    { value: '90d', label: 'Last 90 days' },
    { value: '1y', label: 'Last year' },
  ];

  return (
    <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 mb-6">
      <div className="flex items-center gap-2 mb-4">
        <Filter className="h-5 w-5 text-gray-500 dark:text-gray-400" />
        <h3 className="font-semibold text-gray-900 dark:text-white">Filters</h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Time Period Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Time Period
          </label>
          <div className="flex flex-wrap gap-1">
            {timePeriodOptions.map((option) => (
              <button
                key={option.value}
                onClick={() => onFiltersChange({ ...filters, timePeriod: option.value })}
                disabled={loading}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                  filters.timePeriod === option.value
                    ? 'bg-brand-blue text-white'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Pillar Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Pillar
          </label>
          <select
            value={filters.pillarId || ''}
            onChange={(e) => onFiltersChange({ ...filters, pillarId: e.target.value || null })}
            disabled={loading}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-brand-blue focus:border-brand-blue disabled:opacity-50"
          >
            <option value="">All Pillars</option>
            {pillars.map((pillar) => (
              <option key={pillar.code} value={pillar.code}>
                {pillar.code} - {pillar.name}
              </option>
            ))}
          </select>
        </div>

        {/* Stage Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Maturity Stage
          </label>
          <select
            value={filters.stageId || ''}
            onChange={(e) => onFiltersChange({ ...filters, stageId: e.target.value || null })}
            disabled={loading}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-brand-blue focus:border-brand-blue disabled:opacity-50"
          >
            <option value="">All Stages</option>
            {stages.map((stage) => (
              <option key={stage.stage} value={String(stage.stage)}>
                Stage {stage.stage}: {stage.name}
              </option>
            ))}
          </select>
        </div>

        {/* Reset Filters */}
        <div className="flex items-end">
          <button
            onClick={() =>
              onFiltersChange({
                pillarId: null,
                stageId: null,
                timePeriod: '30d',
              })
            }
            disabled={loading}
            className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors disabled:opacity-50"
          >
            <RefreshCw className="h-4 w-4 inline mr-1" />
            Reset
          </button>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// Stats Card Component
// ============================================================================

interface StatsCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  icon: React.ReactNode;
  trend?: number | null;
  linkTo?: string;
  colorClass?: string;
}

const StatsCard: React.FC<StatsCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  trend,
  linkTo,
  colorClass = 'text-brand-blue',
}) => {
  const content = (
    <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-6 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg group">
      <div className="flex items-center justify-between">
        <div className="flex items-center">
          <div className={`flex-shrink-0 ${colorClass} group-hover:scale-110 transition-transform`}>
            {icon}
          </div>
          <div className="ml-4">
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
            <p className="text-2xl font-semibold text-gray-900 dark:text-white">
              {typeof value === 'number' ? value.toLocaleString() : value}
            </p>
            {subtitle && (
              <p className="text-xs text-gray-400 dark:text-gray-500">{subtitle}</p>
            )}
          </div>
        </div>
        {trend !== undefined && trend !== null && (
          <div
            className={`flex items-center gap-1 text-sm font-medium ${
              trend > 0
                ? 'text-emerald-600 dark:text-emerald-400'
                : trend < 0
                ? 'text-red-600 dark:text-red-400'
                : 'text-gray-500 dark:text-gray-400'
            }`}
          >
            {trend > 0 ? (
              <TrendingUp className="h-4 w-4" />
            ) : trend < 0 ? (
              <TrendingDown className="h-4 w-4" />
            ) : (
              <Minus className="h-4 w-4" />
            )}
            <span>{trend > 0 ? '+' : ''}{trend.toFixed(1)}%</span>
          </div>
        )}
      </div>
    </div>
  );

  if (linkTo) {
    return <Link to={linkTo}>{content}</Link>;
  }

  return content;
};

// ============================================================================
// Main Analytics Component
// ============================================================================

const Analytics: React.FC = () => {
  const { user } = useAuthContext();

  // Filter state
  const [filters, setFilters] = useState<AnalyticsFilters>({
    pillarId: null,
    stageId: null,
    timePeriod: '30d',
  });

  // Data states
  const [velocityData, setVelocityData] = useState<VelocityDataPoint[]>([]);
  const [weekOverWeekChange, setWeekOverWeekChange] = useState<number | null>(null);
  const [periodStart, setPeriodStart] = useState<string | null>(null);
  const [periodEnd, setPeriodEnd] = useState<string | null>(null);
  const [pillarCoverage, setPillarCoverage] = useState<PillarCoverageItem[]>([]);
  const [insightsData, setInsightsData] = useState<InsightsResponse | null>(null);
  const [stats, setStats] = useState<AnalyticsStats>({
    totalCards: 0,
    activeCards: 0,
    newThisWeek: 0,
    avgVelocity: 0,
  });

  // Loading states
  const [loadingVelocity, setLoadingVelocity] = useState(true);
  const [loadingCoverage, setLoadingCoverage] = useState(true);
  const [loadingInsights, setLoadingInsights] = useState(true);
  const [loadingStats, setLoadingStats] = useState(true);

  // Error states
  const [velocityError, setVelocityError] = useState<string | null>(null);
  const [coverageError, setCoverageError] = useState<string | null>(null);
  const [insightsError, setInsightsError] = useState<string | null>(null);

  // Calculate date range from filters
  const getFilterParams = useCallback(() => {
    const { start, end } = getDateRangeFromPeriod(filters.timePeriod);
    return {
      pillar_id: filters.pillarId || undefined,
      stage_id: filters.stageId || undefined,
      start_date: format(start, 'yyyy-MM-dd'),
      end_date: format(end, 'yyyy-MM-dd'),
    };
  }, [filters]);

  // Load stats from Supabase
  const loadStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      const { start } = getDateRangeFromPeriod(filters.timePeriod);
      const oneWeekAgo = subDays(new Date(), 7);

      // Build base query
      let baseQuery = supabase.from('cards').select('*', { count: 'exact', head: true });
      if (filters.pillarId) {
        baseQuery = baseQuery.eq('pillar_id', filters.pillarId);
      }
      if (filters.stageId) {
        baseQuery = baseQuery.eq('stage_id', filters.stageId);
      }

      // Total cards count
      const { count: totalCount } = await baseQuery;

      // Active cards count
      let activeQuery = supabase
        .from('cards')
        .select('*', { count: 'exact', head: true })
        .eq('status', 'active');
      if (filters.pillarId) {
        activeQuery = activeQuery.eq('pillar_id', filters.pillarId);
      }
      if (filters.stageId) {
        activeQuery = activeQuery.eq('stage_id', filters.stageId);
      }
      const { count: activeCount } = await activeQuery;

      // New this week count
      let newWeekQuery = supabase
        .from('cards')
        .select('*', { count: 'exact', head: true })
        .eq('status', 'active')
        .gte('created_at', oneWeekAgo.toISOString());
      if (filters.pillarId) {
        newWeekQuery = newWeekQuery.eq('pillar_id', filters.pillarId);
      }
      if (filters.stageId) {
        newWeekQuery = newWeekQuery.eq('stage_id', filters.stageId);
      }
      const { count: newCount } = await newWeekQuery;

      // Average velocity score
      let velocityQuery = supabase
        .from('cards')
        .select('velocity_score')
        .eq('status', 'active')
        .not('velocity_score', 'is', null);
      if (filters.pillarId) {
        velocityQuery = velocityQuery.eq('pillar_id', filters.pillarId);
      }
      if (filters.stageId) {
        velocityQuery = velocityQuery.eq('stage_id', filters.stageId);
      }
      const { data: velocityCards } = await velocityQuery;

      const avgVelocity =
        velocityCards && velocityCards.length > 0
          ? velocityCards.reduce((sum, card) => sum + (card.velocity_score || 0), 0) /
            velocityCards.length
          : 0;

      setStats({
        totalCards: totalCount || 0,
        activeCards: activeCount || 0,
        newThisWeek: newCount || 0,
        avgVelocity: Math.round(avgVelocity),
      });
    } catch (error) {
      // Silently fail for stats - non-critical
    } finally {
      setLoadingStats(false);
    }
  }, [filters]);

  // Load velocity data from API
  const loadVelocityData = useCallback(async () => {
    setLoadingVelocity(true);
    setVelocityError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error('Not authenticated');
      }

      const params = getFilterParams();
      const response = await fetchVelocityData(session.access_token, params);

      setVelocityData(response.data || []);
      setWeekOverWeekChange(response.week_over_week_change);
      setPeriodStart(response.period_start);
      setPeriodEnd(response.period_end);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load velocity data';
      setVelocityError(message);
      setVelocityData([]);
    } finally {
      setLoadingVelocity(false);
    }
  }, [getFilterParams]);

  // Load pillar coverage from API
  const loadPillarCoverage = useCallback(async () => {
    setLoadingCoverage(true);
    setCoverageError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error('Not authenticated');
      }

      const params = getFilterParams();
      // Don't pass pillar_id for coverage - we want all pillars
      const { pillar_id, ...coverageParams } = params;
      const response = await fetchPillarCoverage(session.access_token, coverageParams);

      setPillarCoverage(response.data || []);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load pillar coverage';
      setCoverageError(message);
      setPillarCoverage([]);
    } finally {
      setLoadingCoverage(false);
    }
  }, [getFilterParams]);

  // Load insights from API
  const loadInsights = useCallback(async () => {
    setLoadingInsights(true);
    setInsightsError(null);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error('Not authenticated');
      }

      const response = await fetchInsights(session.access_token, {
        pillar_id: filters.pillarId || undefined,
        limit: 5,
      });

      setInsightsData(response);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load insights';
      setInsightsError(message);
      setInsightsData(null);
    } finally {
      setLoadingInsights(false);
    }
  }, [filters.pillarId]);

  // Load all data when filters change
  useEffect(() => {
    loadStats();
    loadVelocityData();
    loadPillarCoverage();
    loadInsights();
  }, [loadStats, loadVelocityData, loadPillarCoverage, loadInsights]);

  // Handle filter changes
  const handleFiltersChange = (newFilters: AnalyticsFilters) => {
    setFilters(newFilters);
  };

  // Handle pillar click from heatmap
  const handlePillarClick = (pillarCode: string) => {
    setFilters((prev) => ({
      ...prev,
      pillarId: prev.pillarId === pillarCode ? null : pillarCode,
    }));
  };

  // Get selected pillar info
  const selectedPillar = filters.pillarId
    ? pillars.find((p) => p.code === filters.pillarId)
    : null;

  // Overall loading state
  const isLoading = loadingVelocity || loadingCoverage || loadingInsights || loadingStats;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <BarChart3 className="h-8 w-8 text-brand-blue" />
          <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">
            Analytics Dashboard
          </h1>
        </div>
        <p className="text-gray-600 dark:text-gray-400">
          Strategic intelligence insights and trend analysis
          {selectedPillar && (
            <span className="ml-2">
              <span
                className="inline-flex items-center px-2 py-0.5 rounded text-sm font-medium"
                style={{
                  backgroundColor: `${selectedPillar.color}20`,
                  color: selectedPillar.color,
                }}
              >
                {selectedPillar.code}: {selectedPillar.name}
              </span>
            </span>
          )}
        </p>
      </div>

      {/* Filters */}
      <AnalyticsFiltersComponent
        filters={filters}
        onFiltersChange={handleFiltersChange}
        loading={isLoading}
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatsCard
          title="Total Cards"
          value={stats.totalCards}
          icon={<Layers className="h-8 w-8" />}
          linkTo="/discover"
          colorClass="text-brand-blue"
        />
        <StatsCard
          title="Active Cards"
          value={stats.activeCards}
          icon={<Target className="h-8 w-8" />}
          linkTo="/discover?status=active"
          colorClass="text-emerald-500"
        />
        <StatsCard
          title="New This Week"
          value={stats.newThisWeek}
          icon={<Calendar className="h-8 w-8" />}
          trend={weekOverWeekChange}
          linkTo="/discover?filter=new"
          colorClass="text-extended-purple"
        />
        <StatsCard
          title="Avg. Velocity"
          value={stats.avgVelocity}
          subtitle="out of 100"
          icon={<Activity className="h-8 w-8" />}
          colorClass="text-extended-orange"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Velocity Chart - Full Width on Mobile, 2/3 on Desktop */}
        <div className="lg:col-span-2">
          <div className="bg-white dark:bg-[#2d3166] rounded-lg shadow">
            <TrendVelocityChart
              data={velocityData}
              isLoading={loadingVelocity}
              weekOverWeekChange={weekOverWeekChange}
              totalCardsAnalyzed={stats.activeCards}
              periodStart={periodStart}
              periodEnd={periodEnd}
              height={400}
            />
            {velocityError && !loadingVelocity && (
              <div className="p-4 text-center text-red-600 dark:text-red-400">
                {velocityError}
              </div>
            )}
          </div>
        </div>

        {/* Pillar Heatmap - 1/3 on Desktop */}
        <div className="lg:col-span-1">
          <PillarHeatmap
            data={pillarCoverage}
            loading={loadingCoverage}
            title="Pillar Coverage"
            height={400}
            onPillarClick={handlePillarClick}
          />
          {coverageError && !loadingCoverage && (
            <div className="mt-2 p-4 text-center text-red-600 dark:text-red-400">
              {coverageError}
            </div>
          )}
        </div>
      </div>

      {/* Insights Panel - Full Width */}
      <div className="mt-6">
        <InsightsPanel
          data={insightsData}
          loading={loadingInsights}
          error={insightsError}
          title="AI-Generated Strategic Insights"
          maxInsights={5}
        />
      </div>

      {/* Quick Links */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Link
          to="/discover"
          className="flex items-center justify-between p-4 bg-white dark:bg-[#2d3166] rounded-lg shadow hover:shadow-md transition-shadow group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand-blue/10 rounded-lg">
              <Target className="h-5 w-5 text-brand-blue" />
            </div>
            <div>
              <h3 className="font-medium text-gray-900 dark:text-white">Discover Cards</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Browse all intelligence cards
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
              <h3 className="font-medium text-gray-900 dark:text-white">Workstreams</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Manage your focused collections
              </p>
            </div>
          </div>
          <ArrowRight className="h-5 w-5 text-gray-400 group-hover:text-extended-purple group-hover:translate-x-1 transition-all" />
        </Link>

        <Link
          to="/"
          className="flex items-center justify-between p-4 bg-white dark:bg-[#2d3166] rounded-lg shadow hover:shadow-md transition-shadow group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-extended-orange/10 rounded-lg">
              <BarChart3 className="h-5 w-5 text-extended-orange" />
            </div>
            <div>
              <h3 className="font-medium text-gray-900 dark:text-white">Dashboard</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Return to main dashboard
              </p>
            </div>
          </div>
          <ArrowRight className="h-5 w-5 text-gray-400 group-hover:text-extended-orange group-hover:translate-x-1 transition-all" />
        </Link>
      </div>
    </div>
  );
};

export default Analytics;
