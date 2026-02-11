import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Search,
  Grid,
  List,
  Plus,
  Radio,
  Loader2,
  Filter,
  Calendar,
  TrendingUp,
  Sparkles,
  BarChart3,
  AlertTriangle,
  RefreshCw,
  X,
} from "lucide-react";
import { supabase } from "../App";
import { useAuthContext } from "../hooks/useAuthContext";
import { useDebouncedValue } from "../hooks/useDebounce";
import { PillarBadge } from "../components/PillarBadge";
import { HorizonBadge } from "../components/HorizonBadge";
import { StageBadge } from "../components/StageBadge";
import { QualityScoreBadge } from "../components/QualityScoreBadge";
import { Top25Badge } from "../components/Top25Badge";
import { parseStageNumber } from "../lib/stage-utils";
import { CreateSignalModal } from "../components/CreateSignal";

interface Signal {
  id: string;
  name: string;
  slug: string;
  summary: string;
  pillar_id: string;
  stage_id: string;
  horizon: "H1" | "H2" | "H3";
  impact_score: number;
  relevance_score: number;
  novelty_score: number;
  velocity_score: number;
  risk_score: number;
  opportunity_score: number;
  signal_quality_score: number | null;
  top25_relevance?: string[];
  created_at: string;
  updated_at: string;
  source_count?: number;
}

interface Pillar {
  id: string;
  name: string;
  code: string;
}

interface Stage {
  id: string;
  name: string;
  sort_order: number;
}

type SortOption =
  | "quality_desc"
  | "quality_asc"
  | "newest"
  | "recently_updated"
  | "impact"
  | "relevance";

const Signals: React.FC = () => {
  useAuthContext(); // ensure authenticated
  const [signals, setSignals] = useState<Signal[]>([]);
  const [pillars, setPillars] = useState<Pillar[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateSignal, setShowCreateSignal] = useState(false);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  // Filters
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedPillar, setSelectedPillar] = useState("");
  const [selectedStage, setSelectedStage] = useState("");
  const [selectedHorizon, setSelectedHorizon] = useState("");
  const [qualityMin, setQualityMin] = useState(0);
  const [sortOption, setSortOption] = useState<SortOption>("quality_desc");

  const { debouncedValue: debouncedSearch } = useDebouncedValue(
    searchTerm,
    300,
  );

  // Stats
  const [stats, setStats] = useState({
    total: 0,
    avgQuality: 0,
    newThisWeek: 0,
  });

  useEffect(() => {
    loadFilters();
  }, []);

  useEffect(() => {
    loadSignals();
  }, [
    debouncedSearch,
    selectedPillar,
    selectedStage,
    selectedHorizon,
    qualityMin,
    sortOption,
  ]);

  const loadFilters = async () => {
    try {
      const [pillarsRes, stagesRes] = await Promise.all([
        supabase.from("pillars").select("*").order("name"),
        supabase.from("stages").select("*").order("sort_order"),
      ]);
      setPillars(pillarsRes.data || []);
      setStages(stagesRes.data || []);
    } catch (err) {
      console.error("Error loading filters:", err);
    }
  };

  const loadSignals = async () => {
    setLoading(true);
    setError(null);
    try {
      let query = supabase.from("cards").select("*").eq("status", "active");

      if (debouncedSearch) {
        query = query.or(
          `name.ilike.%${debouncedSearch}%,summary.ilike.%${debouncedSearch}%`,
        );
      }
      if (selectedPillar) query = query.eq("pillar_id", selectedPillar);
      if (selectedStage) query = query.eq("stage_id", selectedStage);
      if (selectedHorizon) query = query.eq("horizon", selectedHorizon);
      if (qualityMin > 0) query = query.gte("signal_quality_score", qualityMin);

      // Sort
      switch (sortOption) {
        case "quality_desc":
          query = query.order("signal_quality_score", {
            ascending: false,
            nullsFirst: false,
          });
          break;
        case "quality_asc":
          query = query.order("signal_quality_score", {
            ascending: true,
            nullsFirst: false,
          });
          break;
        case "newest":
          query = query.order("created_at", { ascending: false });
          break;
        case "recently_updated":
          query = query.order("updated_at", { ascending: false });
          break;
        case "impact":
          query = query.order("impact_score", { ascending: false });
          break;
        case "relevance":
          query = query.order("relevance_score", { ascending: false });
          break;
      }

      const { data, error: queryError } = await query.limit(200);

      if (queryError) {
        setError(`Failed to load signals: ${queryError.message}`);
        return;
      }

      const signalData = (data || []) as Signal[];
      setSignals(signalData);

      // Compute stats
      const oneWeekAgo = new Date();
      oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
      const scored = signalData.filter((s) => s.signal_quality_score != null);
      const avgQ =
        scored.length > 0
          ? Math.round(
              scored.reduce(
                (sum, s) => sum + (s.signal_quality_score || 0),
                0,
              ) / scored.length,
            )
          : 0;
      const newCount = signalData.filter(
        (s) => new Date(s.created_at) >= oneWeekAgo,
      ).length;

      setStats({
        total: signalData.length,
        avgQuality: avgQ,
        newThisWeek: newCount,
      });
    } catch (err) {
      console.error("Error loading signals:", err);
      setError(
        err instanceof Error
          ? `Failed to load signals: ${err.message}`
          : "Failed to load signals. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-brand-blue via-brand-blue/90 to-brand-green mb-8 p-8 md:p-10">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PGNpcmNsZSBjeD0iMzAiIGN5PSIzMCIgcj0iMiIvPjwvZz48L2c+PC9zdmc+')] opacity-50" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Radio className="w-7 h-7 text-white/90" />
              <h1 className="text-3xl md:text-4xl font-bold text-white">
                Signals
              </h1>
            </div>
            <p className="text-white/80 text-lg max-w-2xl">
              Strategic intelligence signals tracked by Foresight. Each signal
              represents a trend, technology, or issue that could impact
              Austin&apos;s municipal operations.
            </p>
          </div>
          <button
            onClick={() => setShowCreateSignal(true)}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-white/20 hover:bg-white/30 text-white font-medium rounded-xl backdrop-blur-sm border border-white/20 transition-colors shrink-0"
          >
            <Plus className="w-5 h-5" />
            New Signal
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="bg-white dark:bg-[#2d3166] rounded-xl shadow-sm p-5 flex items-center gap-4">
          <div className="p-3 bg-brand-blue/10 rounded-xl">
            <Radio className="w-6 h-6 text-brand-blue" />
          </div>
          <div>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {stats.total}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Total Signals
            </p>
          </div>
        </div>
        <div className="bg-white dark:bg-[#2d3166] rounded-xl shadow-sm p-5 flex items-center gap-4">
          <div className="p-3 bg-brand-green/10 rounded-xl">
            <BarChart3 className="w-6 h-6 text-brand-green" />
          </div>
          <div>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {stats.avgQuality > 0 ? stats.avgQuality : "—"}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Avg Quality Score
            </p>
          </div>
        </div>
        <div className="bg-white dark:bg-[#2d3166] rounded-xl shadow-sm p-5 flex items-center gap-4">
          <div className="p-3 bg-extended-purple/10 rounded-xl">
            <Sparkles className="w-6 h-6 text-extended-purple" />
          </div>
          <div>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {stats.newThisWeek}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              New This Week
            </p>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white dark:bg-[#2d3166] rounded-xl shadow-sm p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
          {/* Search */}
          <div className="lg:col-span-2">
            <label
              htmlFor="signal-search"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <input
                type="text"
                id="signal-search"
                className="pl-10 block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                placeholder="Search signals..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>

          {/* Pillar */}
          <div>
            <label
              htmlFor="signal-pillar"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Pillar
            </label>
            <select
              id="signal-pillar"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={selectedPillar}
              onChange={(e) => setSelectedPillar(e.target.value)}
            >
              <option value="">All Pillars</option>
              {pillars.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* Stage */}
          <div>
            <label
              htmlFor="signal-stage"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Stage
            </label>
            <select
              id="signal-stage"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={selectedStage}
              onChange={(e) => setSelectedStage(e.target.value)}
            >
              <option value="">All Stages</option>
              {stages.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          {/* Horizon */}
          <div>
            <label
              htmlFor="signal-horizon"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Horizon
            </label>
            <select
              id="signal-horizon"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={selectedHorizon}
              onChange={(e) => setSelectedHorizon(e.target.value)}
            >
              <option value="">All Horizons</option>
              <option value="H1">H1 (0-2 years)</option>
              <option value="H2">H2 (2-5 years)</option>
              <option value="H3">H3 (5+ years)</option>
            </select>
          </div>

          {/* Sort */}
          <div className="lg:col-span-2">
            <label
              htmlFor="signal-sort"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Sort By
            </label>
            <select
              id="signal-sort"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-[#3d4176] dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={sortOption}
              onChange={(e) => setSortOption(e.target.value as SortOption)}
            >
              <option value="quality_desc">Highest Quality</option>
              <option value="quality_asc">Lowest Quality</option>
              <option value="newest">Newest</option>
              <option value="recently_updated">Recently Updated</option>
              <option value="impact">Highest Impact</option>
              <option value="relevance">Highest Relevance</option>
            </select>
          </div>

          {/* Quality Score Range */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-1">
              <label
                htmlFor="quality-min"
                className="text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Min Quality Score
              </label>
              <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
                {qualityMin > 0 ? `>= ${qualityMin}` : "Any"}
              </span>
            </div>
            <input
              type="range"
              id="quality-min"
              min="0"
              max="100"
              step="5"
              value={qualityMin}
              onChange={(e) => setQualityMin(Number(e.target.value))}
              className="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer accent-brand-blue"
            />
          </div>

          {/* View Toggle */}
          <div className="flex items-end gap-2">
            <button
              onClick={() => setViewMode("grid")}
              className={`p-2 rounded-md transition-colors ${
                viewMode === "grid"
                  ? "bg-brand-light-blue text-brand-blue dark:bg-brand-blue/20"
                  : "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              }`}
              aria-label="Grid view"
              aria-pressed={viewMode === "grid"}
            >
              <Grid className="h-5 w-5" />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`p-2 rounded-md transition-colors ${
                viewMode === "list"
                  ? "bg-brand-light-blue text-brand-blue dark:bg-brand-blue/20"
                  : "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              }`}
              aria-label="List view"
              aria-pressed={viewMode === "list"}
            >
              <List className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="mt-3 flex items-center justify-between">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Showing {signals.length} signals
          </p>
          {(searchTerm ||
            selectedPillar ||
            selectedStage ||
            selectedHorizon ||
            qualityMin > 0) && (
            <button
              onClick={() => {
                setSearchTerm("");
                setSelectedPillar("");
                setSelectedStage("");
                setSelectedHorizon("");
                setQualityMin(0);
              }}
              className="text-sm text-brand-blue hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium text-red-700 dark:text-red-300">
                {error}
              </p>
              <button
                onClick={() => {
                  setError(null);
                  loadSignals();
                }}
                className="mt-2 inline-flex items-center gap-1.5 text-sm text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 transition-colors"
              >
                <RefreshCw className="h-4 w-4" />
                Try again
              </button>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 className="h-8 w-8 text-brand-blue animate-spin" />
          <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
            Loading signals...
          </p>
        </div>
      ) : signals.length === 0 ? (
        <div className="text-center py-16 bg-white dark:bg-[#2d3166] rounded-xl shadow-sm">
          <Filter className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
            No Signals Found
          </h3>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
            {searchTerm ||
            selectedPillar ||
            selectedStage ||
            selectedHorizon ||
            qualityMin > 0
              ? "Try adjusting your filters to see more results."
              : "No signals have been created yet. Run a discovery scan to populate signals."}
          </p>
        </div>
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {signals.map((signal) => (
            <SignalCard key={signal.id} signal={signal} />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {signals.map((signal) => (
            <SignalListItem key={signal.id} signal={signal} />
          ))}
        </div>
      )}

      <CreateSignalModal
        isOpen={showCreateSignal}
        onClose={() => setShowCreateSignal(false)}
        onSuccess={() => {
          loadSignals();
          setShowCreateSignal(false);
        }}
      />
    </div>
  );
};

const SignalCard: React.FC<{ signal: Signal }> = React.memo(({ signal }) => {
  const stageNumber = parseStageNumber(signal.stage_id);

  return (
    <Link
      to={`/signals/${signal.slug}`}
      state={{ from: "/signals" }}
      aria-label={`View signal: ${signal.name}`}
      className="block bg-white dark:bg-[#2d3166] rounded-lg shadow-sm border border-gray-100 dark:border-gray-700/50 hover:-translate-y-1 hover:shadow-lg transition-all duration-200 overflow-hidden group"
    >
      {/* Gradient accent bar */}
      <div className="h-1 bg-gradient-to-r from-brand-blue to-brand-green" />

      <div className="p-5">
        {/* Title + Quality Score */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white group-hover:text-brand-blue transition-colors line-clamp-2">
            {signal.name}
          </h3>
          <QualityScoreBadge score={signal.signal_quality_score} size="sm" />
        </div>

        {/* Summary */}
        <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 mb-4">
          {signal.summary}
        </p>

        {/* Badges */}
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <PillarBadge pillarId={signal.pillar_id} size="sm" />
          <HorizonBadge horizon={signal.horizon} size="sm" />
          {stageNumber && <StageBadge stage={stageNumber} size="sm" />}
          {signal.top25_relevance && signal.top25_relevance.length > 0 && (
            <Top25Badge priorities={signal.top25_relevance} size="sm" />
          )}
        </div>

        {/* Scores Row */}
        <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1">
            <TrendingUp className="w-3.5 h-3.5" />
            Impact {signal.impact_score}
          </span>
          <span className="flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5" />
            Relevance {signal.relevance_score}
          </span>
          <span className="flex items-center gap-1">
            <Calendar className="w-3.5 h-3.5" />
            {new Date(signal.created_at).toLocaleDateString()}
          </span>
        </div>
      </div>
    </Link>
  );
});

SignalCard.displayName = "SignalCard";

const SignalListItem: React.FC<{ signal: Signal }> = React.memo(
  ({ signal }) => {
    const stageNumber = parseStageNumber(signal.stage_id);

    return (
      <Link
        to={`/signals/${signal.slug}`}
        state={{ from: "/signals" }}
        aria-label={`View signal: ${signal.name}`}
        className="flex items-center gap-4 bg-white dark:bg-[#2d3166] rounded-lg shadow-sm border border-gray-100 dark:border-gray-700/50 p-4 hover:shadow-md hover:border-brand-blue/30 transition-all group"
      >
        {/* Quality Score */}
        <div className="shrink-0">
          <QualityScoreBadge score={signal.signal_quality_score} size="lg" />
        </div>

        {/* Main Content */}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 dark:text-white group-hover:text-brand-blue transition-colors truncate">
            {signal.name}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
            {signal.summary}
          </p>
        </div>

        {/* Badges */}
        <div className="hidden sm:flex items-center gap-2 shrink-0">
          <PillarBadge pillarId={signal.pillar_id} size="sm" />
          <HorizonBadge horizon={signal.horizon} size="sm" />
          {stageNumber && <StageBadge stage={stageNumber} size="sm" />}
          {signal.top25_relevance && signal.top25_relevance.length > 0 && (
            <Top25Badge priorities={signal.top25_relevance} size="sm" />
          )}
        </div>

        {/* Scores */}
        <div className="hidden md:flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400 shrink-0">
          <span>Impact {signal.impact_score}</span>
          <span>Rel. {signal.relevance_score}</span>
        </div>

        {/* Date */}
        <div className="text-xs text-gray-400 shrink-0 hidden lg:block">
          {new Date(signal.created_at).toLocaleDateString()}
        </div>
      </Link>
    );
  },
);

SignalListItem.displayName = "SignalListItem";

export default Signals;
