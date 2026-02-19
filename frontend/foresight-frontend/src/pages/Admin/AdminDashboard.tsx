/**
 * AdminDashboard Page
 *
 * Admin landing page -- system overview with:
 * - System health cards: DB status, worker status, scheduler status
 * - Key metrics: total cards, total sources, total users, embedding coverage %
 * - Description quality bar (5 buckets: missing/thin/short/adequate/comprehensive)
 * - Recent activity feed: last 10 research tasks, last 3 discovery runs
 * - Quick actions: "Enrich Descriptions", "Run Discovery", "Recalculate Quality"
 *
 * @module pages/Admin/AdminDashboard
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Database,
  Users,
  FileText,
  Globe,
  Clock,
  Loader2,
  AlertCircle,
  CheckCircle2,
  X,
  Sparkles,
  Compass,
  RefreshCw,
  Zap,
  Cog,
} from "lucide-react";
import {
  fetchSystemHealth,
  fetchDbStats,
  fetchDescriptionQuality,
  fetchJobStats,
  fetchJobs,
  fetchDiscoveryRuns,
  enrichDescriptions,
  triggerDiscovery,
  recalculateAllQuality,
} from "../../lib/admin-api";
import type {
  SystemHealth,
  DbStats,
  DescriptionQuality,
  JobStats,
  AdminJob,
  DiscoveryRun,
} from "../../lib/admin-api";

// ============================================================================
// Types
// ============================================================================

interface ToastState {
  message: string;
  type: "success" | "error";
}

// ============================================================================
// Sub-Components
// ============================================================================

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

function HealthBadge({
  status,
}: {
  status: "healthy" | "degraded" | "unhealthy" | "unknown";
}) {
  const styles: Record<string, string> = {
    healthy:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    degraded:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
    unhealthy: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    unknown: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",
  };
  const dots: Record<string, string> = {
    healthy: "bg-green-500",
    degraded: "bg-yellow-500",
    unhealthy: "bg-red-500",
    unknown: "bg-gray-400",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full ${styles[status] || styles.unknown}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${dots[status] || dots.unknown}`}
      />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function RunStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    running: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    queued:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  };
  return (
    <span
      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${styles[status] || "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400"}`}
    >
      {status}
    </span>
  );
}

// ============================================================================
// Quality Bar
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
      <div className="grid grid-cols-5 gap-3">
        {QUALITY_TIERS.map((tier) => (
          <div key={tier.key} className="text-center">
            <div className="animate-pulse h-16 bg-gray-200 dark:bg-gray-700 rounded-lg mb-1" />
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
    <div className="grid grid-cols-5 gap-3">
      {QUALITY_TIERS.map((tier) => {
        const count = quality[tier.key];
        const barHeight = Math.max((count / maxCount) * 100, 4);
        return (
          <div key={tier.key} className="text-center">
            <div className="flex items-end justify-center h-20 mb-1">
              <div
                className={`w-full max-w-[2.5rem] ${tier.color} rounded-t-md transition-all duration-300`}
                style={{ height: `${barHeight}%` }}
              />
            </div>
            <p className={`text-base font-semibold ${tier.textColor}`}>
              {count}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {tier.label}
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              {total > 0 ? `${Math.round((count / total) * 100)}%` : "0%"}
            </p>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "--";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ============================================================================
// Main Component
// ============================================================================

export default function AdminDashboard() {
  const token = localStorage.getItem("gs2_token") || "";
  const navigate = useNavigate();

  // Data state
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [dbStats, setDbStats] = useState<DbStats | null>(null);
  const [descQuality, setDescQuality] = useState<DescriptionQuality | null>(
    null,
  );
  const [jobStats, setJobStats] = useState<JobStats | null>(null);
  const [recentJobs, setRecentJobs] = useState<AdminJob[]>([]);
  const [recentRuns, setRecentRuns] = useState<DiscoveryRun[]>([]);

  // Loading
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [loadingDb, setLoadingDb] = useState(true);
  const [loadingQuality, setLoadingQuality] = useState(true);
  const [loadingJobStats, setLoadingJobStats] = useState(true);
  const [loadingRecentJobs, setLoadingRecentJobs] = useState(true);
  const [loadingRecentRuns, setLoadingRecentRuns] = useState(true);

  // Quick action loading
  const [enriching, setEnriching] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [recalculating, setRecalculating] = useState(false);

  // Toast
  const [toast, setToast] = useState<ToastState | null>(null);

  // --------------------------------------------------------------------------
  // Load data
  // --------------------------------------------------------------------------

  const loadHealth = useCallback(async () => {
    setLoadingHealth(true);
    try {
      const data = await fetchSystemHealth(token);
      setHealth(data);
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to load system health",
        type: "error",
      });
    } finally {
      setLoadingHealth(false);
    }
  }, [token]);

  const loadDbStats = useCallback(async () => {
    setLoadingDb(true);
    try {
      const data = await fetchDbStats(token);
      setDbStats(data);
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to load DB stats",
        type: "error",
      });
    } finally {
      setLoadingDb(false);
    }
  }, [token]);

  const loadQuality = useCallback(async () => {
    setLoadingQuality(true);
    try {
      const data = await fetchDescriptionQuality(token);
      setDescQuality(data);
    } catch {
      // Non-critical, don't toast — UI shows "--" for missing data
    } finally {
      setLoadingQuality(false);
    }
  }, [token]);

  const loadJobStats = useCallback(async () => {
    setLoadingJobStats(true);
    try {
      const data = await fetchJobStats(token);
      setJobStats(data);
    } catch {
      // Non-critical — UI shows "--" for missing data
    } finally {
      setLoadingJobStats(false);
    }
  }, [token]);

  const loadRecentJobs = useCallback(async () => {
    setLoadingRecentJobs(true);
    try {
      const data = await fetchJobs(token, { limit: 10 });
      setRecentJobs(data);
    } catch {
      // Non-critical — UI shows empty state for missing data
    } finally {
      setLoadingRecentJobs(false);
    }
  }, [token]);

  const loadRecentRuns = useCallback(async () => {
    setLoadingRecentRuns(true);
    try {
      const data = await fetchDiscoveryRuns(token);
      setRecentRuns(data.slice(0, 3));
    } catch {
      // Non-critical — UI shows empty state for missing data
    } finally {
      setLoadingRecentRuns(false);
    }
  }, [token]);

  useEffect(() => {
    loadHealth();
    loadDbStats();
    loadQuality();
    loadJobStats();
    loadRecentJobs();
    loadRecentRuns();
  }, [
    loadHealth,
    loadDbStats,
    loadQuality,
    loadJobStats,
    loadRecentJobs,
    loadRecentRuns,
  ]);

  // --------------------------------------------------------------------------
  // Quick actions
  // --------------------------------------------------------------------------

  const handleEnrich = async () => {
    setEnriching(true);
    try {
      const result = await enrichDescriptions(token, 10);
      setToast({
        message: `Enrichment complete: ${result.enriched} enriched, ${result.skipped} skipped.`,
        type: "success",
      });
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

  const handleTriggerDiscovery = async () => {
    setTriggering(true);
    try {
      const result = await triggerDiscovery(token);
      setToast({
        message: `Discovery run started (ID: ${result.id}).`,
        type: "success",
      });
      setTimeout(() => loadRecentRuns(), 3000);
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to trigger discovery.",
        type: "error",
      });
    } finally {
      setTriggering(false);
    }
  };

  const handleRecalculateQuality = async () => {
    if (
      !window.confirm(
        "Recalculate quality scores for all cards? This may take several minutes.",
      )
    )
      return;
    setRecalculating(true);
    try {
      await recalculateAllQuality(token);
      setToast({
        message: "Quality recalculation started.",
        type: "success",
      });
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to start recalculation.",
        type: "error",
      });
    } finally {
      setRecalculating(false);
    }
  };

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Admin Dashboard
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          System overview, health metrics, and operational status.
        </p>
      </div>

      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}

      {/* System Health Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Database Health */}
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-brand-blue/10 dark:bg-brand-blue/20">
                <Database className="w-5 h-5 text-brand-blue" />
              </div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                Database
              </h3>
            </div>
            {loadingHealth ? (
              <div className="animate-pulse h-5 w-16 bg-gray-200 dark:bg-gray-700 rounded-full" />
            ) : (
              <HealthBadge
                status={
                  health?.database.status === "ok" ? "healthy" : "unhealthy"
                }
              />
            )}
          </div>
          {loadingHealth ? (
            <div className="animate-pulse h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded" />
          ) : health ? (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Latency: {Math.round(health.database.latency_ms)}ms
            </p>
          ) : null}
        </div>

        {/* Worker Health */}
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-brand-blue/10 dark:bg-brand-blue/20">
                <Cog className="w-5 h-5 text-brand-blue" />
              </div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                Worker
              </h3>
            </div>
            {loadingHealth ? (
              <div className="animate-pulse h-5 w-16 bg-gray-200 dark:bg-gray-700 rounded-full" />
            ) : (
              <HealthBadge
                status={health?.worker.last_completed ? "healthy" : "degraded"}
              />
            )}
          </div>
          {loadingHealth ? (
            <div className="animate-pulse h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded" />
          ) : health ? (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Queued: {health.worker.queue_depth.queued} | Processing:{" "}
              {health.worker.queue_depth.processing}
            </p>
          ) : null}
        </div>

        {/* Embeddings Health */}
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-brand-blue/10 dark:bg-brand-blue/20">
                <Clock className="w-5 h-5 text-brand-blue" />
              </div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                Embeddings
              </h3>
            </div>
            {loadingHealth ? (
              <div className="animate-pulse h-5 w-16 bg-gray-200 dark:bg-gray-700 rounded-full" />
            ) : (
              <HealthBadge
                status={
                  health?.embeddings.coverage_pct != null &&
                  health.embeddings.coverage_pct > 80
                    ? "healthy"
                    : "degraded"
                }
              />
            )}
          </div>
          {loadingHealth ? (
            <div className="animate-pulse h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded" />
          ) : health ? (
            <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
              <span>{health.embeddings.coverage_pct}% coverage</span>
              <span>{health.embeddings.cards_without_embedding} missing</span>
            </div>
          ) : null}
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2 mb-2">
            <FileText className="w-4 h-4 text-gray-400" />
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Total Cards
            </span>
          </div>
          {loadingHealth ? (
            <div className="animate-pulse h-7 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
          ) : (
            <p className="text-2xl font-semibold text-gray-900 dark:text-white">
              {(health?.counts.cards ?? 0).toLocaleString()}
            </p>
          )}
        </div>
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Globe className="w-4 h-4 text-gray-400" />
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Total Sources
            </span>
          </div>
          {loadingHealth ? (
            <div className="animate-pulse h-7 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
          ) : (
            <p className="text-2xl font-semibold text-brand-blue">
              {(health?.counts.sources ?? 0).toLocaleString()}
            </p>
          )}
        </div>
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Users className="w-4 h-4 text-gray-400" />
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Total Users
            </span>
          </div>
          {loadingHealth ? (
            <div className="animate-pulse h-7 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
          ) : (
            <p className="text-2xl font-semibold text-brand-green">
              {(health?.counts.users ?? 0).toLocaleString()}
            </p>
          )}
        </div>
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Cog className="w-4 h-4 text-gray-400" />
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Jobs Queue
            </span>
          </div>
          {loadingJobStats ? (
            <div className="animate-pulse h-7 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
          ) : (
            <p className="text-2xl font-semibold text-yellow-600 dark:text-yellow-400">
              {(jobStats?.by_status.queued ?? 0) +
                (jobStats?.by_status.processing ?? 0)}
            </p>
          )}
        </div>
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Database className="w-4 h-4 text-gray-400" />
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              DB Size
            </span>
          </div>
          {loadingDb ? (
            <div className="animate-pulse h-7 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
          ) : (
            <p className="text-2xl font-semibold text-gray-900 dark:text-white">
              {dbStats?.total_size ?? "--"}
            </p>
          )}
        </div>
      </div>

      {/* Description Quality Bar */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-brand-blue" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Description Quality
            </h2>
          </div>
          <button
            onClick={() => navigate("/admin/content")}
            className="text-xs text-brand-blue hover:underline font-medium"
          >
            View Details
          </button>
        </div>
        <QualityBar quality={descQuality} loading={loadingQuality} />
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Jobs */}
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2">
              <Cog className="w-5 h-5 text-brand-blue" />
              <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                Recent Jobs
              </h2>
            </div>
            <button
              onClick={() => navigate("/admin/jobs")}
              className="text-xs text-brand-blue hover:underline font-medium"
            >
              View All
            </button>
          </div>
          {loadingRecentJobs ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="animate-pulse flex items-center gap-3 p-2"
                >
                  <div className="h-2 w-2 rounded-full bg-gray-200 dark:bg-gray-700" />
                  <div className="h-4 flex-1 bg-gray-200 dark:bg-gray-700 rounded" />
                  <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
                </div>
              ))}
            </div>
          ) : recentJobs.length === 0 ? (
            <div className="px-6 py-8 text-center">
              <Cog className="w-6 h-6 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No recent jobs.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {recentJobs.map((job) => (
                <div
                  key={job.id}
                  className="flex items-center gap-3 px-6 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
                >
                  <RunStatusBadge status={job.status} />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-gray-900 dark:text-white truncate block">
                      {job.task_type}
                    </span>
                    {job.card_name && (
                      <span className="text-xs text-gray-500 dark:text-gray-400 truncate block">
                        {job.card_name}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
                    {formatDate(job.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Discovery Runs */}
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2">
              <Compass className="w-5 h-5 text-brand-blue" />
              <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                Recent Discovery Runs
              </h2>
            </div>
            <button
              onClick={() => navigate("/admin/discovery")}
              className="text-xs text-brand-blue hover:underline font-medium"
            >
              View All
            </button>
          </div>
          {loadingRecentRuns ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="animate-pulse flex items-center gap-3 p-2"
                >
                  <div className="h-5 w-16 bg-gray-200 dark:bg-gray-700 rounded-full" />
                  <div className="h-4 flex-1 bg-gray-200 dark:bg-gray-700 rounded" />
                  <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
                </div>
              ))}
            </div>
          ) : recentRuns.length === 0 ? (
            <div className="px-6 py-8 text-center">
              <Compass className="w-6 h-6 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No discovery runs recorded yet.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-800">
              {recentRuns.map((run) => (
                <div
                  key={run.id}
                  className="flex items-center gap-3 px-6 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
                >
                  <RunStatusBadge status={run.status} />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-gray-900 dark:text-white">
                      {run.stats.cards_created ?? 0} created,{" "}
                      {run.stats.cards_deduplicated ?? 0} deduped
                    </span>
                    {run.error_message && (
                      <span
                        className="text-xs text-red-500 dark:text-red-400 truncate block"
                        title={run.error_message}
                      >
                        {run.error_message}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
                    {formatDate(run.started_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Zap className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Quick Actions
          </h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Enrich Descriptions */}
          <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
            <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-1">
              Enrich Descriptions
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
              AI-enrich up to 10 cards with missing or thin descriptions.
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
              Enrich Now
            </button>
          </div>

          {/* Run Discovery */}
          <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
            <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-1">
              Run Discovery
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
              Trigger an immediate content discovery scan across all sources.
            </p>
            <button
              onClick={handleTriggerDiscovery}
              disabled={triggering}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-brand-green border border-brand-green/30 rounded-lg hover:bg-brand-green/5 transition-colors disabled:opacity-50"
            >
              {triggering ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Compass className="w-3.5 h-3.5" />
              )}
              Discover Now
            </button>
          </div>

          {/* Recalculate Quality */}
          <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
            <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-1">
              Recalculate Quality
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
              Recalculate quality scores for all signal cards in the database.
            </p>
            <button
              onClick={handleRecalculateQuality}
              disabled={recalculating}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-600 dark:text-gray-400 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
            >
              {recalculating ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5" />
              )}
              Recalculate
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
