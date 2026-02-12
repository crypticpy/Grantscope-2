import React, { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  Play,
  RefreshCw,
  ChevronRight,
  FileText,
  TrendingUp,
  ArrowLeft,
  Calendar,
  Zap,
  StopCircle,
  Search,
  Filter,
  Copy,
  Sparkles,
} from "lucide-react";
import { supabase } from "../App";
import { useAuthContext } from "../hooks/useAuthContext";
import {
  fetchDiscoveryRuns,
  triggerDiscoveryRun,
  cancelDiscoveryRun,
  fetchDiscoveryConfig,
  type DiscoveryRun,
  type DiscoveryConfig,
} from "../lib/discovery-api";

/**
 * Format duration between two dates
 */
const formatDuration = (
  startedAt: string,
  completedAt: string | null,
): string => {
  if (!completedAt) return "In progress...";

  const start = new Date(startedAt);
  const end = new Date(completedAt);
  const diffMs = end.getTime() - start.getTime();

  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((diffMs % (1000 * 60)) / 1000);

  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
};

/**
 * Format date for display
 */
const formatDate = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

/**
 * Get relative time description
 */
const getRelativeTime = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffHours < 1) return "Just now";
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  return formatDate(dateString);
};

/**
 * Progress stage info
 */
interface ProgressStage {
  id: string;
  label: string;
  icon: React.ElementType;
}

const DISCOVERY_STAGES: ProgressStage[] = [
  { id: "queries", label: "Generate Queries", icon: FileText },
  { id: "search", label: "Search Sources", icon: Search },
  { id: "triage", label: "Triage Results", icon: Filter },
  { id: "blocked", label: "Filter Blocked", icon: StopCircle },
  { id: "dedupe", label: "Deduplicate", icon: Copy },
  { id: "cards", label: "Create Cards", icon: Sparkles },
];

/**
 * Progress indicator for running discovery
 */
const ProgressIndicator: React.FC<{
  progress: {
    current_stage?: string;
    message?: string;
    stages?: Record<string, string>;
    stats?: Record<string, number>;
  } | null;
}> = ({ progress }) => {
  if (!progress) {
    return (
      <div className="text-sm text-gray-500 dark:text-gray-400 italic">
        Starting discovery run...
      </div>
    );
  }

  const { current_stage, message, stages, stats } = progress;

  return (
    <div className="space-y-3">
      {/* Current message */}
      {message && (
        <div className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>{message}</span>
        </div>
      )}

      {/* Stage progress bar */}
      <div className="flex items-center gap-1">
        {DISCOVERY_STAGES.map((stage, idx) => {
          const status = stages?.[stage.id] || "pending";
          const Icon = stage.icon;
          const _isActive = stage.id === current_stage;

          return (
            <div key={stage.id} className="flex items-center">
              <div
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${
                  status === "completed"
                    ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                    : status === "in_progress"
                      ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                      : "bg-gray-100 text-gray-400 dark:bg-gray-700 dark:text-gray-500"
                }`}
                title={stage.label}
              >
                {status === "completed" ? (
                  <CheckCircle className="w-3 h-3" />
                ) : status === "in_progress" ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Icon className="w-3 h-3" />
                )}
                <span className="hidden sm:inline">{stage.label}</span>
              </div>
              {idx < DISCOVERY_STAGES.length - 1 && (
                <ChevronRight className="w-3 h-3 text-gray-300 dark:text-gray-600 ml-1" />
              )}
            </div>
          );
        })}
      </div>

      {/* Live stats */}
      {stats && Object.keys(stats).length > 0 && (
        <div className="flex flex-wrap gap-3 text-xs text-gray-600 dark:text-gray-400">
          {stats.queries_generated !== undefined && (
            <span>Queries: {stats.queries_generated}</span>
          )}
          {stats.sources_found !== undefined && (
            <span>Sources: {stats.sources_found}</span>
          )}
          {stats.sources_relevant !== undefined && (
            <span>Relevant: {stats.sources_relevant}</span>
          )}
          {stats.duplicates !== undefined && (
            <span>Duplicates: {stats.duplicates}</span>
          )}
          {stats.new_concepts !== undefined && (
            <span>New: {stats.new_concepts}</span>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * Status badge component
 */
const StatusBadge: React.FC<{ status: DiscoveryRun["status"] }> = ({
  status,
}) => {
  const config = {
    running: {
      icon: Loader2,
      text: "Running",
      className:
        "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
      iconClass: "animate-spin",
    },
    completed: {
      icon: CheckCircle,
      text: "Completed",
      className:
        "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
      iconClass: "",
    },
    failed: {
      icon: XCircle,
      text: "Failed",
      className: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
      iconClass: "",
    },
    cancelled: {
      icon: StopCircle,
      text: "Cancelled",
      className:
        "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300",
      iconClass: "",
    },
  }[status];

  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.className}`}
    >
      <Icon className={`w-3.5 h-3.5 ${config.iconClass}`} />
      {config.text}
    </span>
  );
};

/**
 * Stats card component
 */
const StatCard: React.FC<{
  label: string;
  value: number;
  icon: React.ReactNode;
  color: string;
}> = ({ label, value, icon, color }) => (
  <div className={`p-4 rounded-lg border ${color}`}>
    <div className="flex items-center gap-3">
      <div className="p-2 rounded-lg bg-white dark:bg-dark-surface">{icon}</div>
      <div>
        <div className="text-2xl font-bold">{value}</div>
        <div className="text-sm text-gray-600 dark:text-gray-400">{label}</div>
      </div>
    </div>
  </div>
);

/**
 * Discovery run row component
 */
const RunRow: React.FC<{
  run: DiscoveryRun;
  onCancel: (runId: string) => void;
  cancelling: boolean;
}> = ({ run, onCancel, cancelling }) => {
  const [expanded, setExpanded] = useState(false);

  const summaryReport =
    run.summary_report && typeof run.summary_report === "object"
      ? (run.summary_report as Record<string, unknown>)
      : {};

  const configFromSummary = summaryReport.config;
  const markdownReport =
    typeof summaryReport.markdown === "string" ? summaryReport.markdown : null;
  const createdCardIds = Array.isArray(summaryReport.cards_created_ids)
    ? (summaryReport.cards_created_ids as string[])
    : [];

  const derivedErrors = (() => {
    const detailsErrors = (run.error_details as Record<string, unknown> | null)
      ?.errors;
    if (Array.isArray(detailsErrors)) return detailsErrors as string[];
    const reportErrors = summaryReport.errors;
    if (Array.isArray(reportErrors)) return reportErrors as string[];
    return [];
  })();

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <div className="w-full px-4 py-3 flex items-center justify-between bg-white dark:bg-dark-surface">
        <div
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-4 cursor-pointer hover:opacity-80 transition-opacity flex-1"
        >
          <StatusBadge status={run.status} />
          <div className="text-left">
            <div className="font-medium text-gray-900 dark:text-gray-100">
              {formatDate(run.started_at)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">
              {getRelativeTime(run.started_at)}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="hidden sm:flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
              <FileText className="w-4 h-4" />
              <span>{run.sources_found} sources</span>
            </div>
            <div className="flex items-center gap-1.5 text-green-600 dark:text-green-400">
              <TrendingUp className="w-4 h-4" />
              <span>{run.cards_created || 0} created</span>
            </div>
            <div className="flex items-center gap-1.5 text-blue-600 dark:text-blue-400">
              <RefreshCw className="w-4 h-4" />
              <span>{run.cards_enriched || 0} updated</span>
            </div>
            <div className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400">
              <Clock className="w-4 h-4" />
              <span>{formatDuration(run.started_at, run.completed_at)}</span>
            </div>
          </div>

          {run.status === "running" && (
            <button
              onClick={() => onCancel(run.id)}
              disabled={cancelling}
              className="p-1.5 text-red-600 hover:bg-red-100 dark:hover:bg-red-900/20 rounded transition-colors disabled:opacity-50"
              title="Cancel run"
            >
              {cancelling ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <StopCircle className="w-4 h-4" />
              )}
            </button>
          )}

          <div
            onClick={() => setExpanded(!expanded)}
            className="cursor-pointer p-1"
          >
            <ChevronRight
              className={`w-5 h-5 text-gray-400 transition-transform ${
                expanded ? "rotate-90" : ""
              }`}
            />
          </div>
        </div>
      </div>

      {/* Progress indicator for running jobs - always visible */}
      {run.status === "running" && (
        <div className="px-4 py-3 bg-blue-50 dark:bg-blue-900/10 border-t border-blue-200 dark:border-blue-800">
          <ProgressIndicator
            progress={
              (
                run.summary_report as {
                  progress?: {
                    current_stage?: string;
                    message?: string;
                    stages?: Record<string, string>;
                    stats?: Record<string, number>;
                  };
                }
              )?.progress || null
            }
          />
        </div>
      )}

      {expanded && (
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
          {/* Mobile stats */}
          <div className="sm:hidden grid grid-cols-2 gap-3 mb-4">
            <div className="text-sm">
              <span className="text-gray-500 dark:text-gray-400">Sources:</span>{" "}
              <span className="font-medium">{run.sources_found}</span>
            </div>
            <div className="text-sm">
              <span className="text-gray-500 dark:text-gray-400">Created:</span>{" "}
              <span className="font-medium text-green-600">
                {run.cards_created || 0}
              </span>
            </div>
            <div className="text-sm">
              <span className="text-gray-500 dark:text-gray-400">Updated:</span>{" "}
              <span className="font-medium text-blue-600">
                {run.cards_enriched || 0}
              </span>
            </div>
            <div className="text-sm">
              <span className="text-gray-500 dark:text-gray-400">
                Duration:
              </span>{" "}
              <span className="font-medium">
                {formatDuration(run.started_at, run.completed_at)}
              </span>
            </div>
          </div>

          {/* Configuration */}
          {configFromSummary != null &&
            typeof configFromSummary === "object" && (
              <div className="mb-3">
                <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                  Configuration
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                  {Object.entries(
                    configFromSummary as Record<string, unknown>,
                  ).map(([key, value]) => (
                    <div key={key} className="flex items-start gap-2">
                      <span className="text-gray-500 dark:text-gray-400 min-w-[140px]">
                        {key}:
                      </span>
                      <span className="text-gray-900 dark:text-gray-100 break-words">
                        {Array.isArray(value)
                          ? value.join(", ")
                          : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

          {/* Created cards */}
          {createdCardIds.length > 0 && (
            <div className="mb-3">
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                Created Signals
              </div>
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm text-gray-700 dark:text-gray-300">
                  {createdCardIds.length} card(s) created in this run.
                </div>
                <Link
                  to="/discover/queue"
                  className="text-sm text-brand-blue hover:text-brand-dark-blue dark:text-blue-400 dark:hover:text-blue-300"
                >
                  View review queue →
                </Link>
              </div>
            </div>
          )}

          {/* Summary report */}
          {markdownReport && (
            <div className="mb-3">
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                Summary Report
              </div>
              <div className="text-sm whitespace-pre-wrap bg-white dark:bg-dark-surface border border-gray-200 dark:border-gray-700 rounded p-3 max-h-64 overflow-auto">
                {markdownReport}
              </div>
            </div>
          )}

          {/* Errors */}
          {derivedErrors.length > 0 && (
            <div>
              <div className="text-xs font-medium text-red-600 dark:text-red-400 uppercase tracking-wide mb-2">
                Errors ({derivedErrors.length})
              </div>
              <div className="space-y-1">
                {derivedErrors.slice(0, 5).map((error, idx) => (
                  <div
                    key={idx}
                    className="text-sm text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 rounded px-2 py-1"
                  >
                    {error}
                  </div>
                ))}
                {derivedErrors.length > 5 && (
                  <div className="text-sm text-red-500 italic">
                    +{derivedErrors.length - 5} more errors
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Timestamps */}
          <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400">
            <div>Started: {new Date(run.started_at).toLocaleString()}</div>
            {run.completed_at && (
              <div>
                Completed: {new Date(run.completed_at).toLocaleString()}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Discovery History Page
 */
const DiscoveryHistory: React.FC = () => {
  const { user } = useAuthContext();
  const [runs, setRuns] = useState<DiscoveryRun[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [triggerLoading, setTriggerLoading] = useState(false);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [_discoveryConfig, setDiscoveryConfig] =
    useState<DiscoveryConfig | null>(null);

  // Fetch discovery config on mount
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (session?.access_token) {
          const config = await fetchDiscoveryConfig(session.access_token);
          setDiscoveryConfig(config);
        }
      } catch (err) {
        console.error("Failed to load discovery config:", err);
      }
    };
    loadConfig();
  }, []);

  const loadRuns = useCallback(
    async (isInitial = false) => {
      if (!user) return;

      try {
        // Only show full-page spinner on initial load
        if (isInitial) {
          setInitialLoading(true);
        } else {
          setRefreshing(true);
        }
        setError(null);

        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session?.access_token) {
          throw new Error("Not authenticated");
        }

        const data = await fetchDiscoveryRuns(session.access_token, 20);
        setRuns(data);
      } catch (err) {
        console.error("Failed to load discovery runs:", err);
        setError(err instanceof Error ? err.message : "Failed to load runs");
      } finally {
        setInitialLoading(false);
        setRefreshing(false);
      }
    },
    [user],
  );

  useEffect(() => {
    loadRuns(true); // Initial load with full spinner
  }, [loadRuns]);

  // Poll for updates if there's a running job
  useEffect(() => {
    const hasRunning = runs.some((r) => r.status === "running");
    if (!hasRunning) return;

    // Poll every 3 seconds for progress updates during active runs
    const interval = setInterval(() => loadRuns(false), 3000);
    return () => clearInterval(interval);
  }, [runs, loadRuns]);

  const handleTriggerRun = async () => {
    if (!user) return;

    try {
      setTriggerLoading(true);
      setError(null);

      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error("Not authenticated");
      }

      await triggerDiscoveryRun(session.access_token);
      await loadRuns(false);
    } catch (err) {
      console.error("Failed to trigger discovery run:", err);
      setError(err instanceof Error ? err.message : "Failed to trigger run");
    } finally {
      setTriggerLoading(false);
    }
  };

  const handleCancelRun = async (runId: string) => {
    if (!user) return;

    try {
      setCancellingId(runId);

      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error("Not authenticated");
      }

      await cancelDiscoveryRun(session.access_token, runId);
      await loadRuns(false);
    } catch (err) {
      console.error("Failed to cancel run:", err);
      setError(err instanceof Error ? err.message : "Failed to cancel run");
    } finally {
      setCancellingId(null);
    }
  };

  // Calculate aggregate stats
  const stats = {
    totalRuns: runs.length,
    successfulRuns: runs.filter((r) => r.status === "completed").length,
    totalCardsCreated: runs.reduce((sum, r) => sum + (r.cards_created || 0), 0),
    totalCardsUpdated: runs.reduce(
      (sum, r) => sum + (r.cards_enriched || 0),
      0,
    ),
    totalSources: runs.reduce((sum, r) => sum + (r.sources_found || 0), 0),
  };

  const hasRunningJob = runs.some((r) => r.status === "running");

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 pt-20 pb-8">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-6">
          <Link
            to="/discover"
            className="inline-flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-brand-blue mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Discover
          </Link>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                Discovery History
              </h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">
                View past discovery runs and trigger new ones
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => loadRuns(false)}
                disabled={refreshing}
                className="p-2 text-gray-600 dark:text-gray-400 hover:text-brand-blue hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors disabled:opacity-50"
                title="Refresh"
              >
                <RefreshCw
                  className={`w-5 h-5 ${refreshing ? "animate-spin" : ""}`}
                />
              </button>
              <button
                onClick={handleTriggerRun}
                disabled={triggerLoading || hasRunningJob}
                className="inline-flex items-center gap-2 px-4 py-2 bg-brand-blue text-white font-medium rounded-lg hover:bg-brand-dark-blue transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {triggerLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Starting...
                  </>
                ) : hasRunningJob ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Run in Progress
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Trigger Discovery
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Stats */}
        {!initialLoading && runs.length > 0 && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard
              label="Total Runs"
              value={stats.totalRuns}
              icon={<Calendar className="w-5 h-5 text-gray-600" />}
              color="bg-gray-50 dark:bg-dark-surface border-gray-200 dark:border-gray-700"
            />
            <StatCard
              label="Signals Created"
              value={stats.totalCardsCreated}
              icon={<Zap className="w-5 h-5 text-green-600" />}
              color="bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
            />
            <StatCard
              label="Signals Updated"
              value={stats.totalCardsUpdated}
              icon={<RefreshCw className="w-5 h-5 text-blue-600" />}
              color="bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800"
            />
            <StatCard
              label="Sources Found"
              value={stats.totalSources}
              icon={<FileText className="w-5 h-5 text-purple-600" />}
              color="bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800"
            />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0" />
            <span className="text-red-800 dark:text-red-200">{error}</span>
          </div>
        )}

        {/* Loading - only on initial page load */}
        {initialLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
          </div>
        )}

        {/* Empty State */}
        {!initialLoading && runs.length === 0 && (
          <div className="text-center py-12 bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-gray-700">
            <Clock className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
              No Discovery Runs Yet
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6 max-w-md mx-auto">
              Discovery runs automatically every Sunday at 2 AM UTC, or you can
              trigger one manually.
            </p>
            <button
              onClick={handleTriggerRun}
              disabled={triggerLoading}
              className="inline-flex items-center gap-2 px-4 py-2 bg-brand-blue text-white font-medium rounded-lg hover:bg-brand-dark-blue transition-colors disabled:opacity-50"
            >
              {triggerLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Run First Discovery
                </>
              )}
            </button>
          </div>
        )}

        {/* Runs List */}
        {!initialLoading && runs.length > 0 && (
          <div className="space-y-3">
            {runs.map((run) => (
              <RunRow
                key={run.id}
                run={run}
                onCancel={handleCancelRun}
                cancelling={cancellingId === run.id}
              />
            ))}
          </div>
        )}

        {/* Schedule Info */}
        <div className="mt-8 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <div className="flex items-start gap-3">
            <Calendar className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-medium text-blue-900 dark:text-blue-100">
                Automatic Discovery Schedule
              </div>
              <p className="text-sm text-blue-800 dark:text-blue-200 mt-1">
                Discovery runs automatically every Sunday at 2:00 AM UTC. The
                system searches for emerging trends aligned with Austin's
                strategic priorities and creates new signals for review.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DiscoveryHistory;
