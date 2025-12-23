import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
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
} from 'lucide-react';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import {
  fetchDiscoveryRuns,
  triggerDiscoveryRun,
  cancelDiscoveryRun,
  type DiscoveryRun,
} from '../lib/discovery-api';

/**
 * Format duration between two dates
 */
const formatDuration = (startedAt: string, completedAt: string | null): string => {
  if (!completedAt) return 'In progress...';

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
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
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

  if (diffHours < 1) return 'Just now';
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return formatDate(dateString);
};

/**
 * Status badge component
 */
const StatusBadge: React.FC<{ status: DiscoveryRun['status'] }> = ({ status }) => {
  const config = {
    running: {
      icon: Loader2,
      text: 'Running',
      className: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
      iconClass: 'animate-spin',
    },
    completed: {
      icon: CheckCircle,
      text: 'Completed',
      className: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
      iconClass: '',
    },
    failed: {
      icon: XCircle,
      text: 'Failed',
      className: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
      iconClass: '',
    },
    cancelled: {
      icon: StopCircle,
      text: 'Cancelled',
      className: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
      iconClass: '',
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
      <div className="p-2 rounded-lg bg-white dark:bg-gray-800">{icon}</div>
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

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
      >
        <div className="flex items-center gap-4">
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
              <span>{run.cards_created} created</span>
            </div>
            <div className="flex items-center gap-1.5 text-blue-600 dark:text-blue-400">
              <RefreshCw className="w-4 h-4" />
              <span>{run.cards_updated} updated</span>
            </div>
            <div className="flex items-center gap-1.5 text-gray-500">
              <Clock className="w-4 h-4" />
              <span>{formatDuration(run.started_at, run.completed_at)}</span>
            </div>
          </div>

          {run.status === 'running' && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onCancel(run.id);
              }}
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

          <ChevronRight
            className={`w-5 h-5 text-gray-400 transition-transform ${
              expanded ? 'rotate-90' : ''
            }`}
          />
        </div>
      </button>

      {expanded && (
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-850 border-t border-gray-200 dark:border-gray-700">
          {/* Mobile stats */}
          <div className="sm:hidden grid grid-cols-2 gap-3 mb-4">
            <div className="text-sm">
              <span className="text-gray-500">Sources:</span>{' '}
              <span className="font-medium">{run.sources_found}</span>
            </div>
            <div className="text-sm">
              <span className="text-gray-500">Created:</span>{' '}
              <span className="font-medium text-green-600">{run.cards_created}</span>
            </div>
            <div className="text-sm">
              <span className="text-gray-500">Updated:</span>{' '}
              <span className="font-medium text-blue-600">{run.cards_updated}</span>
            </div>
            <div className="text-sm">
              <span className="text-gray-500">Duration:</span>{' '}
              <span className="font-medium">
                {formatDuration(run.started_at, run.completed_at)}
              </span>
            </div>
          </div>

          {/* Configuration */}
          {run.config && (
            <div className="mb-3">
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                Configuration
              </div>
              <div className="flex flex-wrap gap-2">
                {run.config.source_types?.map((type) => (
                  <span
                    key={type}
                    className="px-2 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs"
                  >
                    {type}
                  </span>
                ))}
                {run.config.pillar_focus?.map((pillar) => (
                  <span
                    key={pillar}
                    className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 rounded text-xs"
                  >
                    {pillar}
                  </span>
                ))}
                {run.config.max_cards && (
                  <span className="px-2 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300 rounded text-xs">
                    Max {run.config.max_cards} cards
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Errors */}
          {run.errors && run.errors.length > 0 && (
            <div>
              <div className="text-xs font-medium text-red-600 dark:text-red-400 uppercase tracking-wide mb-2">
                Errors ({run.errors.length})
              </div>
              <div className="space-y-1">
                {run.errors.slice(0, 5).map((error, idx) => (
                  <div
                    key={idx}
                    className="text-sm text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 rounded px-2 py-1"
                  >
                    {error}
                  </div>
                ))}
                {run.errors.length > 5 && (
                  <div className="text-sm text-red-500 italic">
                    +{run.errors.length - 5} more errors
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Timestamps */}
          <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400">
            <div>Started: {new Date(run.started_at).toLocaleString()}</div>
            {run.completed_at && (
              <div>Completed: {new Date(run.completed_at).toLocaleString()}</div>
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggerLoading, setTriggerLoading] = useState(false);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    if (!user) return;

    try {
      setLoading(true);
      setError(null);

      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error('Not authenticated');
      }

      const data = await fetchDiscoveryRuns(session.access_token, 20);
      setRuns(data);
    } catch (err) {
      console.error('Failed to load discovery runs:', err);
      setError(err instanceof Error ? err.message : 'Failed to load runs');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  // Poll for updates if there's a running job
  useEffect(() => {
    const hasRunning = runs.some((r) => r.status === 'running');
    if (!hasRunning) return;

    const interval = setInterval(loadRuns, 10000); // Poll every 10 seconds
    return () => clearInterval(interval);
  }, [runs, loadRuns]);

  const handleTriggerRun = async () => {
    if (!user) return;

    try {
      setTriggerLoading(true);
      setError(null);

      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error('Not authenticated');
      }

      await triggerDiscoveryRun(session.access_token);
      await loadRuns();
    } catch (err) {
      console.error('Failed to trigger discovery run:', err);
      setError(err instanceof Error ? err.message : 'Failed to trigger run');
    } finally {
      setTriggerLoading(false);
    }
  };

  const handleCancelRun = async (runId: string) => {
    if (!user) return;

    try {
      setCancellingId(runId);

      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        throw new Error('Not authenticated');
      }

      await cancelDiscoveryRun(session.access_token, runId);
      await loadRuns();
    } catch (err) {
      console.error('Failed to cancel run:', err);
      setError(err instanceof Error ? err.message : 'Failed to cancel run');
    } finally {
      setCancellingId(null);
    }
  };

  // Calculate aggregate stats
  const stats = {
    totalRuns: runs.length,
    successfulRuns: runs.filter((r) => r.status === 'completed').length,
    totalCardsCreated: runs.reduce((sum, r) => sum + r.cards_created, 0),
    totalCardsUpdated: runs.reduce((sum, r) => sum + r.cards_updated, 0),
    totalSources: runs.reduce((sum, r) => sum + r.sources_found, 0),
  };

  const hasRunningJob = runs.some((r) => r.status === 'running');

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
                onClick={loadRuns}
                disabled={loading}
                className="p-2 text-gray-600 dark:text-gray-400 hover:text-brand-blue hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors disabled:opacity-50"
                title="Refresh"
              >
                <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
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
        {!loading && runs.length > 0 && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard
              label="Total Runs"
              value={stats.totalRuns}
              icon={<Calendar className="w-5 h-5 text-gray-600" />}
              color="bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700"
            />
            <StatCard
              label="Cards Created"
              value={stats.totalCardsCreated}
              icon={<Zap className="w-5 h-5 text-green-600" />}
              color="bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
            />
            <StatCard
              label="Cards Updated"
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

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
          </div>
        )}

        {/* Empty State */}
        {!loading && runs.length === 0 && (
          <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
            <Clock className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
              No Discovery Runs Yet
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6 max-w-md mx-auto">
              Discovery runs automatically every Sunday at 2 AM UTC, or you can trigger one manually.
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
        {!loading && runs.length > 0 && (
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
                Discovery runs automatically every Sunday at 2:00 AM UTC. The system searches for
                emerging trends aligned with Austin's strategic priorities and creates new cards
                for review.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DiscoveryHistory;
