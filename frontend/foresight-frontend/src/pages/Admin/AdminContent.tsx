/**
 * AdminContent Page
 *
 * Content management dashboard with:
 * - Content statistics overview
 * - Description quality distribution with enrichment trigger
 * - Embedding coverage monitoring
 * - Card purge tool with dry-run preview
 * - Bulk operations (reanalyze, scan)
 *
 * @module pages/Admin/AdminContent
 */

import { useState, useEffect, useCallback } from "react";
import {
  FileText,
  BarChart3,
  RefreshCw,
  Trash2,
  AlertCircle,
  CheckCircle2,
  X,
  Loader2,
  Sparkles,
  Database,
  ShieldAlert,
  Zap,
} from "lucide-react";
import {
  fetchContentStats,
  fetchDescriptionQuality,
  enrichDescriptions,
  purgeCards,
  triggerScan,
  fetchDbStats,
} from "../../lib/admin-api";
import type {
  ContentStats,
  DescriptionQuality,
  EnrichmentResult,
  PurgeResult,
} from "../../lib/admin-api";

// ============================================================================
// Types
// ============================================================================

interface ToastState {
  message: string;
  type: "success" | "error";
}

// ============================================================================
// Helpers
// ============================================================================

function pct(count: number, total: number): string {
  if (total === 0) return "0%";
  return `${Math.round((count / total) * 100)}%`;
}

// ============================================================================
// Sub-Components
// ============================================================================

/** Success/error toast banner (auto-dismisses success after 3s). */
function Toast({
  message,
  type,
  onDismiss,
}: {
  message: string;
  type: "success" | "error";
  onDismiss: () => void;
}) {
  useEffect(() => {
    if (type === "success") {
      const t = setTimeout(onDismiss, 3000);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [type, onDismiss]);

  const isSuccess = type === "success";
  return (
    <div
      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm ${
        isSuccess
          ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800/50"
          : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800/50"
      }`}
    >
      {isSuccess ? (
        <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
      ) : (
        <AlertCircle className="w-4 h-4 flex-shrink-0" />
      )}
      <span className="flex-1">{message}</span>
      <button
        onClick={onDismiss}
        className="p-0.5 rounded hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

/** Stat card with label and value. */
function StatCard({
  label,
  value,
  icon: Icon,
  color = "text-gray-900 dark:text-white",
  loading,
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  color?: string;
  loading: boolean;
}) {
  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-gray-400" />
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          {label}
        </span>
      </div>
      {loading ? (
        <div className="animate-pulse h-7 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
      ) : (
        <p className={`text-2xl font-semibold ${color}`}>{value}</p>
      )}
    </div>
  );
}

// ============================================================================
// Description Quality Bar
// ============================================================================

const QUALITY_TIERS = [
  {
    key: "missing" as const,
    label: "Missing",
    color: "bg-red-500",
    textColor: "text-red-700 dark:text-red-400",
  },
  {
    key: "thin" as const,
    label: "Thin",
    color: "bg-orange-500",
    textColor: "text-orange-700 dark:text-orange-400",
  },
  {
    key: "short" as const,
    label: "Short",
    color: "bg-yellow-500",
    textColor: "text-yellow-700 dark:text-yellow-400",
  },
  {
    key: "adequate" as const,
    label: "Adequate",
    color: "bg-blue-500",
    textColor: "text-blue-700 dark:text-blue-400",
  },
  {
    key: "comprehensive" as const,
    label: "Comprehensive",
    color: "bg-green-500",
    textColor: "text-green-700 dark:text-green-400",
  },
];

function QualityBar({
  quality,
  loading,
}: {
  quality: DescriptionQuality | null;
  loading: boolean;
}) {
  if (loading || !quality) {
    return (
      <div className="grid grid-cols-5 gap-4">
        {QUALITY_TIERS.map((tier) => (
          <div key={tier.key} className="text-center">
            <div className="animate-pulse h-20 bg-gray-200 dark:bg-gray-700 rounded-lg mb-2" />
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {tier.label}
            </span>
          </div>
        ))}
      </div>
    );
  }

  const total = quality.total || 1;
  const maxCount = Math.max(
    quality.missing,
    quality.thin,
    quality.short,
    quality.adequate,
    quality.comprehensive,
    1,
  );

  return (
    <div className="grid grid-cols-5 gap-4">
      {QUALITY_TIERS.map((tier) => {
        const count = quality[tier.key];
        const barHeight = Math.max((count / maxCount) * 100, 4);
        return (
          <div key={tier.key} className="text-center">
            <div className="flex items-end justify-center h-24 mb-2">
              <div
                className={`w-full max-w-[3rem] ${tier.color} rounded-t-md transition-all duration-300`}
                style={{ height: `${barHeight}%` }}
              />
            </div>
            <p className={`text-lg font-semibold ${tier.textColor}`}>{count}</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {tier.label}
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              {pct(count, total)}
            </p>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function AdminContent() {
  const token = localStorage.getItem("gs2_token") || "";

  // Data state
  const [contentStats, setContentStats] = useState<ContentStats | null>(null);
  const [descQuality, setDescQuality] = useState<DescriptionQuality | null>(
    null,
  );
  const [dbCardCount, setDbCardCount] = useState<number | null>(null);

  // Loading states
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingQuality, setLoadingQuality] = useState(true);
  const [errorStats, setErrorStats] = useState<string | null>(null);
  const [errorQuality, setErrorQuality] = useState<string | null>(null);

  // Enrichment
  const [enriching, setEnriching] = useState(false);
  const [enrichResult, setEnrichResult] = useState<EnrichmentResult | null>(
    null,
  );

  // Purge
  const [purgeMaxAge, setPurgeMaxAge] = useState(180);
  const [purgeMinQuality, setPurgeMinQuality] = useState(20);
  const [purgeDryRun, setPurgeDryRun] = useState(true);
  const [purging, setPurging] = useState(false);
  const [purgeResult, setPurgeResult] = useState<PurgeResult | null>(null);
  const [purgePreview, setPurgePreview] = useState<PurgeResult | null>(null);

  // Bulk operations
  const [scanning, setScanning] = useState(false);

  // Toast
  const [toast, setToast] = useState<ToastState | null>(null);

  // --------------------------------------------------------------------------
  // Load data
  // --------------------------------------------------------------------------

  const loadStats = useCallback(async () => {
    setLoadingStats(true);
    setErrorStats(null);
    try {
      const [stats, dbStats] = await Promise.all([
        fetchContentStats(token),
        fetchDbStats(token),
      ]);
      setContentStats(stats);
      // Extract card count from the tables array (look for "cards" table)
      const cardsTable = dbStats.tables?.find((t) => t.name === "cards");
      setDbCardCount(cardsTable?.row_count ?? 0);
    } catch (err) {
      setErrorStats(
        err instanceof Error ? err.message : "Failed to load content stats",
      );
    } finally {
      setLoadingStats(false);
    }
  }, [token]);

  const loadQuality = useCallback(async () => {
    setLoadingQuality(true);
    setErrorQuality(null);
    try {
      const quality = await fetchDescriptionQuality(token);
      setDescQuality(quality);
    } catch (err) {
      setErrorQuality(
        err instanceof Error
          ? err.message
          : "Failed to load description quality",
      );
    } finally {
      setLoadingQuality(false);
    }
  }, [token]);

  useEffect(() => {
    loadStats();
    loadQuality();
  }, [loadStats, loadQuality]);

  // --------------------------------------------------------------------------
  // Enrichment
  // --------------------------------------------------------------------------

  const handleEnrich = async () => {
    setEnriching(true);
    setEnrichResult(null);
    try {
      const result = await enrichDescriptions(token, 10);
      setEnrichResult(result);
      setToast({
        message: `Enrichment complete: ${result.enriched} enriched, ${result.skipped} skipped, ${result.errors} errors.`,
        type: result.errors > 0 ? "error" : "success",
      });
      // Reload quality after enrichment
      loadQuality();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Enrichment failed.",
        type: "error",
      });
    } finally {
      setEnriching(false);
    }
  };

  // --------------------------------------------------------------------------
  // Purge
  // --------------------------------------------------------------------------

  const handlePurgePreview = async () => {
    setPurging(true);
    setPurgeResult(null);
    setPurgePreview(null);
    try {
      const result = await purgeCards(token, {
        max_age_days: purgeMaxAge,
        min_quality_score: purgeMinQuality,
        dry_run: true,
      });
      setPurgePreview(result);
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Purge preview failed.",
        type: "error",
      });
    } finally {
      setPurging(false);
    }
  };

  const handlePurgeConfirm = async () => {
    if (
      !window.confirm(
        `Are you sure you want to permanently archive ${purgePreview?.affected_count ?? 0} cards? This action cannot be undone.`,
      )
    )
      return;

    setPurging(true);
    try {
      const result = await purgeCards(token, {
        max_age_days: purgeMaxAge,
        min_quality_score: purgeMinQuality,
        dry_run: false,
      });
      setPurgeResult(result);
      setPurgePreview(null);
      setToast({
        message: `Purged ${result.affected_count} cards successfully.`,
        type: "success",
      });
      loadStats();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Purge failed.",
        type: "error",
      });
    } finally {
      setPurging(false);
    }
  };

  // --------------------------------------------------------------------------
  // Bulk: Trigger Scan
  // --------------------------------------------------------------------------

  const handleTriggerScan = async () => {
    setScanning(true);
    try {
      const result = await triggerScan(token);
      setToast({
        message:
          result.message ||
          `Scan triggered: ${result.cards_queued} cards queued.`,
        type: "success",
      });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to trigger scan.",
        type: "error",
      });
    } finally {
      setScanning(false);
    }
  };

  // --------------------------------------------------------------------------
  // Computed values for embedding coverage
  // --------------------------------------------------------------------------

  const activeCards = contentStats?.by_status?.["active"] ?? 0;
  const archivedCards = contentStats?.by_status?.["archived"] ?? 0;
  const reviewingCards = contentStats?.by_status?.["reviewing"] ?? 0;
  const totalCards = contentStats
    ? Object.values(contentStats.by_status).reduce((sum, n) => sum + n, 0)
    : 0;
  const avgQuality = contentStats?.average_scores?.relevance ?? 0;

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Content Management
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Manage signal cards, trigger scans, and enrich descriptions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleEnrich}
            disabled={enriching}
            className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
          >
            {enriching ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            Enrich
          </button>
          <button
            onClick={handleTriggerScan}
            disabled={scanning}
            className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-brand-blue hover:bg-brand-blue/90 rounded-lg transition-colors disabled:opacity-50"
          >
            {scanning ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4" />
            )}
            Trigger Scan
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}

      {/* Error banner for stats */}
      {errorStats && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50 rounded-lg text-sm text-red-700 dark:text-red-300">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorStats}</span>
          <button
            onClick={loadStats}
            className="ml-auto text-red-600 dark:text-red-400 hover:underline text-xs font-medium"
          >
            Retry
          </button>
        </div>
      )}

      {/* Section 1: Stats Overview */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          label="Total Cards"
          value={totalCards.toLocaleString()}
          icon={FileText}
          loading={loadingStats}
        />
        <StatCard
          label="Active"
          value={activeCards.toLocaleString()}
          icon={BarChart3}
          color="text-green-600 dark:text-green-400"
          loading={loadingStats}
        />
        <StatCard
          label="Archived"
          value={archivedCards.toLocaleString()}
          icon={FileText}
          color="text-gray-500"
          loading={loadingStats}
        />
        <StatCard
          label="Reviewing"
          value={reviewingCards.toLocaleString()}
          icon={BarChart3}
          color="text-yellow-600 dark:text-yellow-400"
          loading={loadingStats}
        />
        <StatCard
          label="Avg Quality"
          value={avgQuality > 0 ? avgQuality.toFixed(1) : "--"}
          icon={BarChart3}
          color="text-brand-blue"
          loading={loadingStats}
        />
      </div>

      {/* Section 2: Description Quality Dashboard */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-brand-blue" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Description Quality Distribution
            </h2>
          </div>
          <button
            onClick={handleEnrich}
            disabled={enriching}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-brand-blue border border-brand-blue/30 rounded-lg hover:bg-brand-blue/5 transition-colors disabled:opacity-50"
          >
            {enriching ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5" />
            )}
            Enrich Now (10 cards)
          </button>
        </div>

        {errorQuality ? (
          <div className="flex items-center gap-2 px-4 py-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50 rounded-lg text-sm text-red-700 dark:text-red-300">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{errorQuality}</span>
            <button
              onClick={loadQuality}
              className="ml-auto text-red-600 dark:text-red-400 hover:underline text-xs font-medium"
            >
              Retry
            </button>
          </div>
        ) : (
          <QualityBar quality={descQuality} loading={loadingQuality} />
        )}

        {/* Enrichment result */}
        {enrichResult && (
          <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
            <p className="text-sm text-gray-700 dark:text-gray-300">
              <span className="font-medium">Last enrichment:</span>{" "}
              <span className="text-green-600 dark:text-green-400">
                {enrichResult.enriched} enriched
              </span>
              {enrichResult.skipped > 0 && (
                <span className="text-gray-500">
                  , {enrichResult.skipped} skipped
                </span>
              )}
              {enrichResult.errors > 0 && (
                <span className="text-red-500">
                  , {enrichResult.errors} errors
                </span>
              )}
            </p>
          </div>
        )}
      </div>

      {/* Section 3: Embedding Coverage */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Database className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Database Overview
          </h2>
        </div>

        {loadingStats ? (
          <div className="grid grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse">
                <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
                <div className="h-8 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                DB Total Cards
              </p>
              <p className="text-xl font-semibold text-gray-900 dark:text-white">
                {(dbCardCount ?? 0).toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                Active Cards
              </p>
              <p className="text-xl font-semibold text-green-600 dark:text-green-400">
                {activeCards.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                Archived
              </p>
              <p className="text-xl font-semibold text-gray-500">
                {archivedCards.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                Reviewing
              </p>
              <p className="text-xl font-semibold text-yellow-600 dark:text-yellow-400">
                {reviewingCards.toLocaleString()}
              </p>
            </div>
          </div>
        )}

        {/* Coverage progress bar */}
        {!loadingStats && totalCards > 0 && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1.5">
              <span>Active card ratio</span>
              <span>
                {activeCards} / {totalCards} ({pct(activeCards, totalCards)})
              </span>
            </div>
            <div className="w-full h-2.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-green rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min((activeCards / totalCards) * 100, 100)}%`,
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Section 4: Card Purge Tool */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <ShieldAlert className="w-5 h-5 text-red-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Card Purge Tool
          </h2>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Remove old or low-quality cards from the database. Always preview
          before confirming.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
          {/* Max Age Days */}
          <div>
            <label
              htmlFor="purge-age"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Max Age (days)
            </label>
            <input
              id="purge-age"
              type="number"
              min={1}
              max={9999}
              value={purgeMaxAge}
              onChange={(e) =>
                setPurgeMaxAge(parseInt(e.target.value, 10) || 180)
              }
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors"
            />
            <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
              Cards older than this will be purged
            </p>
          </div>

          {/* Min Quality Score */}
          <div>
            <label
              htmlFor="purge-quality"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Min Quality Score (0-100)
            </label>
            <input
              id="purge-quality"
              type="number"
              min={0}
              max={100}
              value={purgeMinQuality}
              onChange={(e) =>
                setPurgeMinQuality(parseInt(e.target.value, 10) || 0)
              }
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors"
            />
            <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
              Cards below this score are eligible
            </p>
          </div>

          {/* Dry Run Toggle */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Mode
            </label>
            <div className="flex items-center gap-3 mt-2">
              <button
                onClick={() => setPurgeDryRun(true)}
                className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                  purgeDryRun
                    ? "bg-brand-blue text-white border-brand-blue"
                    : "bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
                }`}
              >
                Dry Run
              </button>
              <button
                onClick={() => setPurgeDryRun(false)}
                className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                  !purgeDryRun
                    ? "bg-red-600 text-white border-red-600"
                    : "bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
                }`}
              >
                Live
              </button>
            </div>
          </div>
        </div>

        {/* Purge actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={handlePurgePreview}
            disabled={purging}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
          >
            {purging && !purgePreview ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <FileText className="w-4 h-4" />
            )}
            Preview Purge
          </button>

          {purgePreview && purgePreview.affected_count > 0 && (
            <button
              onClick={handlePurgeConfirm}
              disabled={purging}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {purging ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
              Confirm Purge ({purgePreview.affected_count} cards)
            </button>
          )}
        </div>

        {/* Preview result */}
        {purgePreview && (
          <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/50 rounded-lg">
            <p className="text-sm text-yellow-800 dark:text-yellow-300">
              <span className="font-medium">Preview:</span>{" "}
              {purgePreview.affected_count} card
              {purgePreview.affected_count !== 1 ? "s" : ""} would be purged
              (older than {purgeMaxAge} days).
            </p>
          </div>
        )}

        {/* Confirmed purge result */}
        {purgeResult && !purgeResult.dry_run && (
          <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800/50 rounded-lg">
            <p className="text-sm text-green-800 dark:text-green-300">
              <span className="font-medium">Done:</span>{" "}
              {purgeResult.affected_count} card
              {purgeResult.affected_count !== 1 ? "s" : ""} permanently removed.
            </p>
          </div>
        )}
      </div>

      {/* Section 5: Bulk Operations */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Zap className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Bulk Operations
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Trigger Content Scan */}
          <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
            <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-1">
              Content Scan
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
              Trigger a full content discovery scan to find new signals across
              all configured sources.
            </p>
            <button
              onClick={handleTriggerScan}
              disabled={scanning}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-brand-blue border border-brand-blue/30 rounded-lg hover:bg-brand-blue/5 transition-colors disabled:opacity-50"
            >
              {scanning ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5" />
              )}
              Run Scan Now
            </button>
          </div>

          {/* Enrich Descriptions */}
          <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
            <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-1">
              Batch Enrichment
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
              Use AI to enrich descriptions for cards with missing or thin
              descriptions. Processes up to 10 cards per batch.
            </p>
            <button
              onClick={handleEnrich}
              disabled={enriching}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-brand-blue border border-brand-blue/30 rounded-lg hover:bg-brand-blue/5 transition-colors disabled:opacity-50"
            >
              {enriching ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Sparkles className="w-3.5 h-3.5" />
              )}
              Enrich Batch
            </button>
          </div>
        </div>

        {/* Card status summary */}
        {!loadingStats && contentStats && (
          <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Card Status Summary
            </h3>
            <div className="flex flex-wrap gap-3">
              {[
                {
                  label: "Active",
                  count: contentStats.by_status?.["active"] ?? 0,
                  color:
                    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
                },
                {
                  label: "Reviewing",
                  count: contentStats.by_status?.["reviewing"] ?? 0,
                  color:
                    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
                },
                {
                  label: "Archived",
                  count: contentStats.by_status?.["archived"] ?? 0,
                  color:
                    "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300",
                },
                {
                  label: "Total",
                  count: Object.values(contentStats.by_status).reduce(
                    (sum, n) => sum + n,
                    0,
                  ),
                  color:
                    "bg-brand-blue/10 text-brand-blue dark:bg-brand-blue/20 dark:text-blue-300",
                },
              ].map((item) => (
                <span
                  key={item.label}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-full ${item.color}`}
                >
                  {item.label}:{" "}
                  <span className="font-semibold">
                    {item.count.toLocaleString()}
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
