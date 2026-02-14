import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Search,
  Grid,
  List,
  Plus,
  Radio,
  Loader2,
  Filter,
  Star,
  AlertTriangle,
  RefreshCw,
  X,
  Eye,
  PenTool,
  Layers,
  Bell,
  Microscope,
  ChevronDown,
  Compass,
  BookOpen,
} from "lucide-react";
import { supabase } from "../App";
import { useAuthContext } from "../hooks/useAuthContext";
import { useDebouncedValue } from "../hooks/useDebounce";
import { PillarBadge } from "../components/PillarBadge";
import { HorizonBadge } from "../components/HorizonBadge";
import { StageBadge } from "../components/StageBadge";
import { QualityScoreBadge } from "../components/QualityScoreBadge";
import { Top25Badge } from "../components/Top25Badge";
import { VelocityBadge, type VelocityTrend } from "../components/VelocityBadge";
import { TrendBadge, type TrendDirection } from "../components/TrendBadge";
import { parseStageNumber } from "../lib/stage-utils";
import { CreateSignalModal } from "../components/CreateSignal";
import { VirtualizedGrid } from "../components/VirtualizedGrid";
import { VirtualizedList } from "../components/VirtualizedList";
import { API_BASE_URL } from "../lib/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

import type { FullCard } from "../types/card";

interface Signal extends FullCard {
  /** Required on the Signals page (API always returns it). */
  updated_at: string;
}

interface PersonalSignal extends Signal {
  is_followed: boolean;
  is_created: boolean;
  is_pinned: boolean;
  personal_notes: string | null;
  follow_priority: string | null;
  followed_at: string | null;
  workstream_names: string[];
}

interface SignalStats {
  total: number;
  followed_count: number;
  created_count: number;
  workstream_count: number;
  updates_this_week: number;
  needs_research: number;
}

interface WorkstreamRef {
  id: string;
  name: string;
}

interface MySignalsResponse {
  signals: PersonalSignal[];
  stats: SignalStats;
  workstreams: WorkstreamRef[];
}

type SourceFilter = "" | "followed" | "created" | "workstream";
type SortOption =
  | "recently_updated"
  | "date_followed"
  | "quality_desc"
  | "name_asc";
type GroupBy = "none" | "pillar" | "horizon" | "workstream";

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------

async function fetchMySignals(
  params: Record<string, string>,
): Promise<MySignalsResponse> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) {
    throw new Error("You must be signed in to view your signals.");
  }
  const qs = new URLSearchParams(params).toString();
  const response = await fetch(`${API_BASE_URL}/api/v1/me/signals?${qs}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Failed to load signals (${response.status}): ${body}`);
  }
  return response.json();
}

async function togglePin(cardId: string, pin: boolean): Promise<void> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) throw new Error("Not authenticated");
  const response = await fetch(
    `${API_BASE_URL}/api/v1/me/signals/${cardId}/pin`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ pinned: pin }),
    },
  );
  if (!response.ok) {
    throw new Error("Failed to update pin status");
  }
}

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------

const Signals: React.FC = () => {
  useAuthContext();

  const [signals, setSignals] = useState<PersonalSignal[]>([]);
  const [stats, setStats] = useState<SignalStats>({
    total: 0,
    followed_count: 0,
    created_count: 0,
    workstream_count: 0,
    updates_this_week: 0,
    needs_research: 0,
  });
  // Stored for potential filter enhancements; currently workstream grouping
  // reads workstream_names from each signal directly.
  const [_workstreams, setWorkstreams] = useState<WorkstreamRef[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateSignal, setShowCreateSignal] = useState(false);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  // Filters
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedPillar, setSelectedPillar] = useState("");
  const [selectedHorizon, setSelectedHorizon] = useState("");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("");
  const [qualityMin, setQualityMin] = useState(0);
  const [sortOption, setSortOption] = useState<SortOption>("recently_updated");
  const [groupBy, setGroupBy] = useState<GroupBy>("none");

  const { debouncedValue: debouncedSearch } = useDebouncedValue(
    searchTerm,
    300,
  );

  // Derived pillar list from the signals themselves
  const uniquePillars = React.useMemo(() => {
    const set = new Set<string>();
    signals.forEach((s) => {
      if (s.pillar_id) set.add(s.pillar_id);
    });
    return Array.from(set).sort();
  }, [signals]);

  // -------------------------------------------
  // Data loading
  // -------------------------------------------

  const loadSignals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (debouncedSearch) params.search = debouncedSearch;
      if (selectedPillar) params.pillar = selectedPillar;
      if (selectedHorizon) params.horizon = selectedHorizon;
      if (sourceFilter) params.source = sourceFilter;
      if (qualityMin > 0) params.quality_min = String(qualityMin);
      // Map frontend sort values to backend sort_by parameter
      const sortMap: Record<string, string> = {
        recently_updated: "updated",
        date_followed: "followed",
        quality_desc: "quality",
        name_asc: "name",
      };
      if (sortOption) params.sort_by = sortMap[sortOption] || sortOption;

      const data = await fetchMySignals(params);
      setSignals(data.signals);
      setStats(data.stats);
      setWorkstreams(data.workstreams);
    } catch (err) {
      console.error("Error loading signals:", err);
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load signals. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }, [
    debouncedSearch,
    selectedPillar,
    selectedHorizon,
    sourceFilter,
    qualityMin,
    sortOption,
  ]);

  useEffect(() => {
    loadSignals();
  }, [loadSignals]);

  // -------------------------------------------
  // Pin handler
  // -------------------------------------------

  const handleTogglePin = useCallback(
    async (cardId: string, currentlyPinned: boolean) => {
      // Optimistic update
      setSignals((prev) =>
        prev.map((s) =>
          s.id === cardId ? { ...s, is_pinned: !currentlyPinned } : s,
        ),
      );
      try {
        await togglePin(cardId, !currentlyPinned);
      } catch {
        // Revert on failure
        setSignals((prev) =>
          prev.map((s) =>
            s.id === cardId ? { ...s, is_pinned: currentlyPinned } : s,
          ),
        );
      }
    },
    [],
  );

  // -------------------------------------------
  // Client-side sorting for pinned-first + grouping
  // -------------------------------------------

  const sortedSignals = React.useMemo(() => {
    const copy = [...signals];
    // Pinned signals always come first within their group
    copy.sort((a, b) => {
      if (a.is_pinned && !b.is_pinned) return -1;
      if (!a.is_pinned && b.is_pinned) return 1;
      return 0;
    });
    return copy;
  }, [signals]);

  // -------------------------------------------
  // Grouping logic
  // -------------------------------------------

  const groupedSignals = React.useMemo<
    { key: string; label: string; signals: PersonalSignal[] }[]
  >(() => {
    if (groupBy === "none") {
      return [{ key: "all", label: "", signals: sortedSignals }];
    }

    const groups = new Map<string, PersonalSignal[]>();

    sortedSignals.forEach((signal) => {
      let keys: string[] = [];
      if (groupBy === "pillar") {
        keys = [signal.pillar_id || "Unknown"];
      } else if (groupBy === "horizon") {
        keys = [signal.horizon || "Unknown"];
      } else if (groupBy === "workstream") {
        keys =
          signal.workstream_names.length > 0
            ? signal.workstream_names
            : ["No Workstream"];
      }
      keys.forEach((k) => {
        if (!groups.has(k)) groups.set(k, []);
        groups.get(k)!.push(signal);
      });
    });

    return Array.from(groups.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, sigs]) => ({
        key,
        label: key,
        signals: sigs,
      }));
  }, [sortedSignals, groupBy]);

  // -------------------------------------------
  // Active-filter check
  // -------------------------------------------

  const hasActiveFilters =
    searchTerm !== "" ||
    selectedPillar !== "" ||
    selectedHorizon !== "" ||
    sourceFilter !== "" ||
    qualityMin > 0;

  const clearFilters = () => {
    setSearchTerm("");
    setSelectedPillar("");
    setSelectedHorizon("");
    setSourceFilter("");
    setQualityMin(0);
  };

  // -------------------------------------------
  // Render
  // -------------------------------------------

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* ── Hero Header ────────────────────────────────────── */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-brand-blue via-brand-blue/90 to-brand-green mb-8 p-8 md:p-10">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PGNpcmNsZSBjeD0iMzAiIGN5PSIzMCIgcj0iMiIvPjwvZz48L2c+PC9zdmc+')] opacity-50" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Radio className="w-7 h-7 text-white/90" />
              <h1 className="text-3xl md:text-4xl font-bold text-white">
                My Signals
              </h1>
            </div>
            <p className="text-white/80 text-lg max-w-2xl">
              Your personal intelligence hub &mdash; followed, created, and
              workstream signals in one place.
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <Link
              to="/guide/signals"
              className="inline-flex items-center gap-2 px-4 py-2.5 text-white/80 hover:text-white hover:bg-white/10 font-medium rounded-xl border border-white/10 transition-colors text-sm"
            >
              <BookOpen className="w-4 h-4" />
              How to use
            </Link>
            <button
              onClick={() => setShowCreateSignal(true)}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-white/20 hover:bg-white/30 text-white font-medium rounded-xl backdrop-blur-sm border border-white/20 transition-colors"
            >
              <Plus className="w-5 h-5" />
              New Signal
            </button>
          </div>
        </div>
      </div>

      {/* ── Stats Row ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {/* Tracking */}
        <div className="bg-white dark:bg-dark-surface rounded-xl shadow-sm p-5 flex items-center gap-4">
          <div className="p-3 bg-brand-blue/10 rounded-xl">
            <Radio className="w-6 h-6 text-brand-blue" />
          </div>
          <div>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {stats.total}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Signals across{" "}
              <span className="font-medium text-gray-700 dark:text-gray-300">
                {stats.workstream_count}
              </span>{" "}
              workstreams
            </p>
          </div>
        </div>

        {/* Followed / Created breakdown */}
        <div className="bg-white dark:bg-dark-surface rounded-xl shadow-sm p-5 flex items-center gap-4">
          <div className="p-3 bg-brand-green/10 rounded-xl">
            <Eye className="w-6 h-6 text-brand-green" />
          </div>
          <div>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {stats.followed_count}
              <span className="text-base font-normal text-gray-400 dark:text-gray-500">
                {" "}
                / {stats.created_count}
              </span>
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Followed / Created
            </p>
          </div>
        </div>

        {/* Updates this week */}
        <div className="bg-white dark:bg-dark-surface rounded-xl shadow-sm p-5 flex items-center gap-4">
          <div className="p-3 bg-extended-purple/10 rounded-xl">
            <Bell className="w-6 h-6 text-extended-purple" />
          </div>
          <div>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {stats.updates_this_week}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Updated this week
            </p>
          </div>
        </div>

        {/* Needs research */}
        <div className="bg-white dark:bg-dark-surface rounded-xl shadow-sm p-5 flex items-center gap-4">
          <div className="p-3 bg-amber-500/10 rounded-xl">
            <Microscope className="w-6 h-6 text-amber-500" />
          </div>
          <div>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {stats.needs_research}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Need deeper research
            </p>
          </div>
        </div>
      </div>

      {/* ── Filter / Sort Bar ──────────────────────────────── */}
      <div className="bg-white dark:bg-dark-surface rounded-xl shadow-sm p-6 mb-6">
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
                className="pl-10 block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                placeholder="Search your signals..."
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
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={selectedPillar}
              onChange={(e) => setSelectedPillar(e.target.value)}
            >
              <option value="">All Pillars</option>
              {uniquePillars.map((p) => (
                <option key={p} value={p}>
                  {p}
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
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={selectedHorizon}
              onChange={(e) => setSelectedHorizon(e.target.value)}
            >
              <option value="">All Horizons</option>
              <option value="H1">H1 (0-2 years)</option>
              <option value="H2">H2 (2-5 years)</option>
              <option value="H3">H3 (5+ years)</option>
            </select>
          </div>

          {/* Source (followed / created / workstream) */}
          <div>
            <label
              htmlFor="signal-source"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Source
            </label>
            <select
              id="signal-source"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value as SourceFilter)}
            >
              <option value="">All Sources</option>
              <option value="followed">Followed</option>
              <option value="created">Created by Me</option>
              <option value="workstream">In Workstreams</option>
            </select>
          </div>

          {/* Sort */}
          <div>
            <label
              htmlFor="signal-sort"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Sort By
            </label>
            <select
              id="signal-sort"
              className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
              value={sortOption}
              onChange={(e) => setSortOption(e.target.value as SortOption)}
            >
              <option value="recently_updated">Last Updated</option>
              <option value="date_followed">Date Followed</option>
              <option value="quality_desc">Quality Score</option>
              <option value="name_asc">Name (A-Z)</option>
            </select>
          </div>
        </div>

        {/* Second row: Quality min, Group by, View toggle */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
          {/* Quality Score Range */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label
                htmlFor="quality-min"
                className="text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Min Quality
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

          {/* Group by */}
          <div>
            <label
              htmlFor="signal-group"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Group By
            </label>
            <div className="relative">
              <Layers className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <select
                id="signal-group"
                className="pl-10 block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                value={groupBy}
                onChange={(e) => setGroupBy(e.target.value as GroupBy)}
              >
                <option value="none">No Grouping</option>
                <option value="pillar">Pillar</option>
                <option value="horizon">Horizon</option>
                <option value="workstream">Workstream</option>
              </select>
            </div>
          </div>

          {/* View toggle */}
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

        {/* Filter summary */}
        <div className="mt-3 flex items-center justify-between">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Showing {sortedSignals.length} signal
            {sortedSignals.length !== 1 ? "s" : ""}
          </p>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-sm text-brand-blue hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* ── Error Banner ───────────────────────────────────── */}
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

      {/* ── Content ────────────────────────────────────────── */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 className="h-8 w-8 text-brand-blue animate-spin" />
          <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
            Loading your signals...
          </p>
        </div>
      ) : sortedSignals.length === 0 ? (
        <EmptyState hasFilters={hasActiveFilters} />
      ) : (
        <div className="space-y-8">
          {groupedSignals.map((group) => (
            <SignalGroup
              key={group.key}
              label={group.label}
              groupBy={groupBy}
              signals={group.signals}
              viewMode={viewMode}
              onTogglePin={handleTogglePin}
            />
          ))}
        </div>
      )}

      {/* ── Create Signal Modal ────────────────────────────── */}
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

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

const EmptyState: React.FC<{ hasFilters: boolean }> = ({ hasFilters }) => (
  <div className="text-center py-16 bg-white dark:bg-dark-surface rounded-xl shadow-sm">
    {hasFilters ? (
      <>
        <Filter className="mx-auto h-12 w-12 text-gray-400" />
        <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
          No Matching Signals
        </h3>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
          Try adjusting your filters to see more results.
        </p>
      </>
    ) : (
      <>
        <Compass className="mx-auto h-12 w-12 text-gray-400" />
        <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
          No Signals Yet
        </h3>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
          You haven&apos;t followed any signals yet. Discover signals to start
          building your intelligence hub.
        </p>
        <Link
          to="/discover"
          className="mt-6 inline-flex items-center gap-2 px-5 py-2.5 bg-brand-blue hover:bg-brand-blue/90 text-white font-medium rounded-xl transition-colors"
        >
          <Compass className="w-5 h-5" />
          Discover Signals
        </Link>
      </>
    )}
  </div>
);

// ---------------------------------------------------------------------------
// Signal group wrapper (for grouped view)
// ---------------------------------------------------------------------------

interface SignalGroupProps {
  label: string;
  groupBy: GroupBy;
  signals: PersonalSignal[];
  viewMode: "grid" | "list";
  onTogglePin: (cardId: string, currentlyPinned: boolean) => void;
}

const SignalGroup: React.FC<SignalGroupProps> = ({
  label,
  groupBy,
  signals,
  viewMode,
  onTogglePin,
}) => {
  const [collapsed, setCollapsed] = useState(false);

  // Stable render callbacks to avoid re-creating on every render
  const renderGridItem = useCallback(
    (signal: PersonalSignal, _index: number) => (
      <div className="h-full">
        <SignalCard signal={signal} onTogglePin={onTogglePin} />
      </div>
    ),
    [onTogglePin],
  );

  const renderListItem = useCallback(
    (signal: PersonalSignal) => (
      <SignalListItem signal={signal} onTogglePin={onTogglePin} />
    ),
    [onTogglePin],
  );

  const getItemKey = useCallback((signal: PersonalSignal) => signal.id, []);

  // Compute a dynamic height for the virtualized container based on item count.
  // For grids, each row holds 3 items (lg) and is ~304px (280 + 24 gap).
  // For lists, each item is ~100px (80 + gap).
  // Cap at a viewport-relative height so the page doesn't grow unbounded.
  const containerHeight = useMemo(() => {
    if (viewMode === "grid") {
      const rowCount = Math.ceil(signals.length / 3);
      const totalHeight = rowCount * (280 + 24);
      // Cap so there is always a scroll context for large sets
      return Math.min(totalHeight, window.innerHeight - 300);
    } else {
      const totalHeight = signals.length * (100 + 12);
      return Math.min(totalHeight, window.innerHeight - 300);
    }
  }, [signals.length, viewMode]);

  return (
    <div>
      {/* Group header (only when groupBy is active) */}
      {groupBy !== "none" && (
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-2 mb-3 group w-full text-left"
        >
          <ChevronDown
            className={`h-4 w-4 text-gray-400 transition-transform ${
              collapsed ? "-rotate-90" : ""
            }`}
          />
          {groupBy === "pillar" ? (
            <PillarBadge pillarId={label} size="sm" disableTooltip />
          ) : groupBy === "horizon" &&
            (label === "H1" || label === "H2" || label === "H3") ? (
            <HorizonBadge horizon={label} size="sm" disableTooltip />
          ) : (
            <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              {label}
            </span>
          )}
          <span className="text-xs text-gray-400 dark:text-gray-500">
            ({signals.length})
          </span>
        </button>
      )}

      {/* Cards */}
      {!collapsed &&
        (viewMode === "grid" ? (
          <div style={{ height: `${Math.max(containerHeight, 400)}px` }}>
            <VirtualizedGrid<PersonalSignal>
              items={signals}
              getItemKey={getItemKey}
              estimatedRowHeight={280}
              gap={24}
              columns={{ sm: 1, md: 2, lg: 3 }}
              overscan={3}
              renderItem={renderGridItem}
            />
          </div>
        ) : (
          <div style={{ height: `${Math.max(containerHeight, 400)}px` }}>
            <VirtualizedList<PersonalSignal>
              items={signals}
              renderItem={renderListItem}
              getItemKey={getItemKey}
              estimatedSize={100}
              gap={12}
              overscan={5}
              scrollContainerClassName="h-full"
              ariaLabel="Signals list"
            />
          </div>
        ))}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Personal tag badges (followed / created / workstream)
// ---------------------------------------------------------------------------

const SourceBadge: React.FC<{
  type: "followed" | "created" | "workstream";
  label?: string;
}> = ({ type, label }) => {
  const configs = {
    followed: {
      icon: Eye,
      text: "Followed",
      className:
        "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800",
    },
    created: {
      icon: PenTool,
      text: "Created",
      className:
        "bg-green-50 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800",
    },
    workstream: {
      icon: Layers,
      text: label || "Workstream",
      className:
        "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-800",
    },
  };

  const config = configs[type];
  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded border ${config.className}`}
    >
      <Icon className="w-3 h-3" />
      {config.text}
    </span>
  );
};

// ---------------------------------------------------------------------------
// Signal Card (grid view)
// ---------------------------------------------------------------------------

interface SignalCardProps {
  signal: PersonalSignal;
  onTogglePin: (cardId: string, currentlyPinned: boolean) => void;
}

const SignalCard: React.FC<SignalCardProps> = React.memo(
  ({ signal, onTogglePin }) => {
    const stageNumber = parseStageNumber(signal.stage_id);

    return (
      <div className="relative bg-white dark:bg-dark-surface rounded-xl shadow-sm hover:-translate-y-1 hover:shadow-lg transition-all duration-200 overflow-hidden group">
        {/* Gradient accent bar */}
        <div className="h-1 bg-gradient-to-r from-brand-blue to-brand-green" />

        {/* Pin button */}
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onTogglePin(signal.id, signal.is_pinned);
          }}
          className={`absolute top-3 right-3 z-10 p-1.5 rounded-lg transition-all duration-200 active:scale-75 ${
            signal.is_pinned
              ? "text-amber-500 bg-amber-50 dark:bg-amber-900/30"
              : "text-gray-300 hover:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20 opacity-0 group-hover:opacity-100"
          }`}
          aria-label={signal.is_pinned ? "Unpin signal" : "Pin signal"}
          title={signal.is_pinned ? "Unpin" : "Pin"}
        >
          <Star
            className={`w-4 h-4 ${signal.is_pinned ? "fill-amber-400" : ""}`}
          />
        </button>

        <Link
          to={`/signals/${signal.slug}`}
          state={{ from: "/signals" }}
          aria-label={`View signal: ${signal.name}`}
          className="block"
        >
          <div className="p-5">
            {/* Title + Quality Score */}
            <div className="flex items-start justify-between gap-3 mb-3 pr-8">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white group-hover:text-brand-blue transition-colors line-clamp-2">
                {signal.name}
              </h3>
              <QualityScoreBadge
                score={signal.signal_quality_score}
                size="sm"
              />
            </div>

            {/* Summary */}
            <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 mb-4">
              {signal.summary}
            </p>

            {/* Taxonomy badges */}
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <PillarBadge pillarId={signal.pillar_id} size="sm" />
              <HorizonBadge horizon={signal.horizon} size="sm" />
              {stageNumber && <StageBadge stage={stageNumber} size="sm" />}
              {signal.top25_relevance && signal.top25_relevance.length > 0 && (
                <Top25Badge priorities={signal.top25_relevance} size="sm" />
              )}
              <VelocityBadge
                trend={signal.velocity_trend as VelocityTrend}
                score={signal.velocity_score}
              />
              <TrendBadge
                direction={signal.trend_direction as TrendDirection}
              />
            </div>

            {/* Personal source badges */}
            <div className="flex flex-wrap items-center gap-1.5 mb-3">
              {signal.is_followed && <SourceBadge type="followed" />}
              {signal.is_created && <SourceBadge type="created" />}
              {signal.workstream_names.map((ws) => (
                <SourceBadge key={ws} type="workstream" label={ws} />
              ))}
            </div>

            {/* Bottom meta */}
            <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
              <span>Impact {signal.impact_score}</span>
              <span>Rel. {signal.relevance_score}</span>
              <span className="ml-auto">
                {new Date(signal.updated_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        </Link>
      </div>
    );
  },
);

SignalCard.displayName = "SignalCard";

// ---------------------------------------------------------------------------
// Signal List Item (list view)
// ---------------------------------------------------------------------------

const SignalListItem: React.FC<SignalCardProps> = React.memo(
  ({ signal, onTogglePin }) => {
    const stageNumber = parseStageNumber(signal.stage_id);

    return (
      <div className="flex items-center gap-4 bg-white dark:bg-dark-surface rounded-xl shadow-sm p-4 hover:shadow-lg transition-all duration-200 group">
        {/* Pin */}
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onTogglePin(signal.id, signal.is_pinned);
          }}
          className={`shrink-0 p-1.5 rounded-lg transition-all duration-200 active:scale-75 ${
            signal.is_pinned
              ? "text-amber-500 bg-amber-50 dark:bg-amber-900/30"
              : "text-gray-300 hover:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20 opacity-0 group-hover:opacity-100"
          }`}
          aria-label={signal.is_pinned ? "Unpin signal" : "Pin signal"}
          title={signal.is_pinned ? "Unpin" : "Pin"}
        >
          <Star
            className={`w-4 h-4 ${signal.is_pinned ? "fill-amber-400" : ""}`}
          />
        </button>

        {/* Quality Score */}
        <div className="shrink-0">
          <QualityScoreBadge score={signal.signal_quality_score} size="lg" />
        </div>

        {/* Main Content */}
        <Link
          to={`/signals/${signal.slug}`}
          state={{ from: "/signals" }}
          aria-label={`View signal: ${signal.name}`}
          className="flex-1 min-w-0"
        >
          <h3 className="font-semibold text-gray-900 dark:text-white group-hover:text-brand-blue transition-colors truncate">
            {signal.name}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
            {signal.summary}
          </p>
        </Link>

        {/* Source badges */}
        <div className="hidden md:flex items-center gap-1.5 shrink-0">
          {signal.is_followed && <SourceBadge type="followed" />}
          {signal.is_created && <SourceBadge type="created" />}
          {signal.workstream_names.length > 0 && (
            <SourceBadge
              type="workstream"
              label={
                signal.workstream_names.length === 1
                  ? signal.workstream_names[0]
                  : `${signal.workstream_names.length} workstreams`
              }
            />
          )}
        </div>

        {/* Taxonomy badges */}
        <div className="hidden sm:flex items-center gap-2 shrink-0">
          <PillarBadge pillarId={signal.pillar_id} size="sm" />
          <HorizonBadge horizon={signal.horizon} size="sm" />
          {stageNumber && <StageBadge stage={stageNumber} size="sm" />}
          {signal.top25_relevance && signal.top25_relevance.length > 0 && (
            <Top25Badge priorities={signal.top25_relevance} size="sm" />
          )}
          <VelocityBadge
            trend={signal.velocity_trend as VelocityTrend}
            score={signal.velocity_score}
          />
          <TrendBadge direction={signal.trend_direction as TrendDirection} />
        </div>

        {/* Scores */}
        <div className="hidden md:flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400 shrink-0">
          <span>Impact {signal.impact_score}</span>
          <span>Rel. {signal.relevance_score}</span>
        </div>

        {/* Date */}
        <div className="text-xs text-gray-400 shrink-0 hidden lg:block">
          {new Date(signal.updated_at).toLocaleDateString()}
        </div>
      </div>
    );
  },
);

SignalListItem.displayName = "SignalListItem";

export default Signals;
