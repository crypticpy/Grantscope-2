/**
 * AdminSources Page
 *
 * Search and source configuration dashboard with:
 * - Search provider selection (auto/searxng/serper/tavily)
 * - Source category toggles (grants_gov, sam_gov, rss, news, academic)
 * - RSS feed management (CRUD table)
 * - Source health indicators per provider
 *
 * @module pages/Admin/AdminSources
 */

import { useState, useEffect, useCallback } from "react";
import {
  Globe,
  Activity,
  Settings,
  Rss,
  Plus,
  Trash2,
  Pencil,
  Check,
  X,
  Loader2,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";
import {
  fetchSourceConfig,
  updateSourceConfig,
  fetchSourceHealth,
  fetchRssFeeds,
  addRssFeed,
  updateRssFeed,
  deleteRssFeed,
  checkRssFeed,
} from "../../lib/admin-api";
import type {
  SourceConfig,
  SourceHealthStatus,
  RssFeed,
  RssFeedCreate,
} from "../../lib/admin-api";

// ============================================================================
// Types
// ============================================================================

interface ToastState {
  message: string;
  type: "success" | "error";
}

interface RssEditRow {
  id: string | null; // null = new feed
  name: string;
  url: string;
  category: string;
  check_interval_hours: number;
}

// ============================================================================
// Constants
// ============================================================================

const SEARCH_PROVIDERS = [
  { value: "auto", label: "Auto (best available)" },
  { value: "searxng", label: "SearXNG (self-hosted)" },
  { value: "serper", label: "Serper" },
  { value: "tavily", label: "Tavily" },
];

const SOURCE_CONFIG_FIELDS: Array<{
  key: string;
  label: string;
  description: string;
  type: "text" | "number" | "boolean";
}> = [
  {
    key: "online_search_enabled",
    label: "Online Search",
    description: "Enable online search for content discovery",
    type: "boolean",
  },
  {
    key: "max_results",
    label: "Max Results",
    description: "Maximum search results per query",
    type: "number",
  },
  {
    key: "timeout_seconds",
    label: "Timeout (seconds)",
    description: "Search request timeout",
    type: "number",
  },
];

const RSS_CATEGORIES = [
  "grants",
  "news",
  "government",
  "academic",
  "technology",
  "policy",
  "other",
];

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

function ToggleSwitch({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-brand-blue/50 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${
        checked ? "bg-brand-blue" : "bg-gray-300 dark:bg-gray-600"
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          checked ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

function HealthBadge({
  status,
}: {
  status: "healthy" | "degraded" | "offline";
}) {
  const styles: Record<string, string> = {
    healthy:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    degraded:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
    offline: "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400",
  };
  const dots: Record<string, string> = {
    healthy: "bg-green-500",
    degraded: "bg-yellow-500",
    offline: "bg-gray-400",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full ${styles[status] || styles.offline}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${dots[status] || dots.offline}`}
      />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function RssStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    active:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    error: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    paused:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
    new: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  };
  return (
    <span
      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${map[status] || "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400"}`}
    >
      {status}
    </span>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function AdminSources() {
  const token = localStorage.getItem("gs2_token") || "";

  // Data state
  const [config, setConfig] = useState<SourceConfig | null>(null);
  const [health, setHealth] = useState<SourceHealthStatus | null>(null);
  const [feeds, setFeeds] = useState<RssFeed[]>([]);

  // Loading
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [loadingFeeds, setLoadingFeeds] = useState(true);
  const [savingConfig, setSavingConfig] = useState(false);

  // RSS edit
  const [rssEditing, setRssEditing] = useState<RssEditRow | null>(null);
  const [rssSaving, setRssSaving] = useState(false);
  const [deletingFeedId, setDeletingFeedId] = useState<string | null>(null);
  const [checkingFeedId, setCheckingFeedId] = useState<string | null>(null);

  // Toast
  const [toast, setToast] = useState<ToastState | null>(null);

  // --------------------------------------------------------------------------
  // Load data
  // --------------------------------------------------------------------------

  const loadConfig = useCallback(async () => {
    setLoadingConfig(true);
    try {
      const data = await fetchSourceConfig(token);
      setConfig(data);
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to load source config",
        type: "error",
      });
    } finally {
      setLoadingConfig(false);
    }
  }, [token]);

  const loadHealth = useCallback(async () => {
    setLoadingHealth(true);
    try {
      const data = await fetchSourceHealth(token);
      setHealth(data);
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to load source health",
        type: "error",
      });
    } finally {
      setLoadingHealth(false);
    }
  }, [token]);

  const loadFeeds = useCallback(async () => {
    setLoadingFeeds(true);
    try {
      const data = await fetchRssFeeds(token);
      setFeeds(data);
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to load RSS feeds",
        type: "error",
      });
    } finally {
      setLoadingFeeds(false);
    }
  }, [token]);

  useEffect(() => {
    loadConfig();
    loadHealth();
    loadFeeds();
  }, [loadConfig, loadHealth, loadFeeds]);

  // --------------------------------------------------------------------------
  // Config updates
  // --------------------------------------------------------------------------

  const handleConfigChange = async (patch: Partial<SourceConfig>) => {
    if (!config) return;
    setSavingConfig(true);
    try {
      await updateSourceConfig(token, patch);
      setConfig({ ...config, ...patch });
      setToast({ message: "Source configuration updated.", type: "success" });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to update config",
        type: "error",
      });
    } finally {
      setSavingConfig(false);
    }
  };

  // --------------------------------------------------------------------------
  // RSS CRUD
  // --------------------------------------------------------------------------

  const startAddFeed = () => {
    setRssEditing({
      id: null,
      name: "",
      url: "",
      category: "grants",
      check_interval_hours: 6,
    });
  };

  const startEditFeed = (feed: RssFeed) => {
    setRssEditing({
      id: feed.id,
      name: feed.name,
      url: feed.url,
      category: feed.category,
      check_interval_hours: feed.check_interval_hours,
    });
  };

  const handleSaveFeed = async () => {
    if (!rssEditing) return;
    if (!rssEditing.name.trim() || !rssEditing.url.trim()) return;

    setRssSaving(true);
    try {
      if (rssEditing.id) {
        await updateRssFeed(token, rssEditing.id, {
          name: rssEditing.name,
          url: rssEditing.url,
          category: rssEditing.category,
          check_interval_hours: rssEditing.check_interval_hours,
        } as Partial<RssFeed>);
        setToast({ message: "RSS feed updated.", type: "success" });
      } else {
        const payload: RssFeedCreate = {
          name: rssEditing.name,
          url: rssEditing.url,
          category: rssEditing.category,
          check_interval_hours: rssEditing.check_interval_hours,
        };
        await addRssFeed(token, payload);
        setToast({ message: "RSS feed added.", type: "success" });
      }
      setRssEditing(null);
      await loadFeeds();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to save RSS feed",
        type: "error",
      });
    } finally {
      setRssSaving(false);
    }
  };

  const handleDeleteFeed = async (feedId: string) => {
    if (!window.confirm("Are you sure you want to delete this RSS feed?"))
      return;
    setDeletingFeedId(feedId);
    try {
      await deleteRssFeed(token, feedId);
      setToast({ message: "RSS feed deleted.", type: "success" });
      await loadFeeds();
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to delete RSS feed",
        type: "error",
      });
    } finally {
      setDeletingFeedId(null);
    }
  };

  const handleCheckFeed = async (feedId: string) => {
    setCheckingFeedId(feedId);
    try {
      await checkRssFeed(token, feedId);
      setToast({ message: "Feed check triggered.", type: "success" });
      await loadFeeds();
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to check RSS feed",
        type: "error",
      });
    } finally {
      setCheckingFeedId(null);
    }
  };

  // --------------------------------------------------------------------------
  // Helpers
  // --------------------------------------------------------------------------

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return "--";
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Source Configuration
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Manage data sources, search providers, and source health monitoring.
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

      {/* Section 1: Search Provider Config */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Settings className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Search Provider
          </h2>
        </div>

        {loadingConfig ? (
          <div className="space-y-4">
            <div className="animate-pulse h-10 w-64 bg-gray-200 dark:bg-gray-700 rounded" />
          </div>
        ) : config ? (
          <div className="space-y-4">
            <div>
              <label
                htmlFor="search-provider"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Active Provider
              </label>
              <select
                id="search-provider"
                value={String(config.search_provider ?? "")}
                onChange={(e) =>
                  handleConfigChange({ search_provider: e.target.value })
                }
                disabled={savingConfig}
                className="w-full max-w-xs px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors disabled:opacity-50"
              >
                {SEARCH_PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                Select the search provider for online content discovery.
              </p>
            </div>

            {/* Additional source settings are managed via the Source Settings section */}
          </div>
        ) : null}
      </div>

      {/* Section 2: Source Settings */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Globe className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Source Settings
          </h2>
        </div>

        {loadingConfig ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse p-4 border border-gray-100 dark:border-gray-800 rounded-lg"
              >
                <div className="h-5 w-24 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
                <div className="h-3 w-36 bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            ))}
          </div>
        ) : config ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {SOURCE_CONFIG_FIELDS.map((field) => (
              <div
                key={field.key}
                className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">
                    {field.label}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {field.description}
                  </p>
                </div>
                {field.type === "boolean" ? (
                  <ToggleSwitch
                    checked={
                      (config as unknown as Record<string, unknown>)[
                        field.key
                      ] === true
                    }
                    onChange={(v) =>
                      handleConfigChange({
                        [field.key]: v,
                      } as Partial<SourceConfig>)
                    }
                    disabled={savingConfig}
                  />
                ) : (
                  <span className="text-sm font-mono text-gray-700 dark:text-gray-300">
                    {String(
                      (config as unknown as Record<string, unknown>)[
                        field.key
                      ] ?? "--",
                    )}
                  </span>
                )}
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {/* Section 3: Source Health */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-brand-blue" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Source Health
            </h2>
          </div>
          <button
            onClick={loadHealth}
            disabled={loadingHealth}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
          >
            {loadingHealth ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5" />
            )}
            Refresh
          </button>
        </div>

        {loadingHealth ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse p-4 border border-gray-100 dark:border-gray-800 rounded-lg"
              >
                <div className="h-5 w-24 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
                <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded-full mb-3" />
                <div className="h-3 w-full bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            ))}
          </div>
        ) : health && health.providers.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {health.providers.map((provider) => (
              <div
                key={provider.name}
                className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {provider.name}
                  </span>
                  <HealthBadge status={provider.status} />
                </div>
                <div className="space-y-1 text-xs text-gray-500 dark:text-gray-400">
                  <p>{provider.message}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <Activity className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No source health data available.
            </p>
          </div>
        )}
      </div>

      {/* Section 4: RSS Feed Manager */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <Rss className="w-5 h-5 text-brand-blue" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              RSS Feeds
            </h2>
            {!loadingFeeds && (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                ({feeds.length} feed{feeds.length !== 1 ? "s" : ""})
              </span>
            )}
          </div>
          <button
            onClick={startAddFeed}
            disabled={!!rssEditing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-brand-blue hover:bg-brand-blue/90 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus className="w-4 h-4" />
            Add Feed
          </button>
        </div>

        {loadingFeeds ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse flex items-center gap-4 p-3 rounded-lg border border-gray-100 dark:border-gray-800"
              >
                <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="flex-1 h-4 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Name
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    URL
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Category
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Interval
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Status
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Last Checked
                  </th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {/* New feed editing row */}
                {rssEditing && rssEditing.id === null && (
                  <tr className="bg-brand-blue/5 dark:bg-brand-blue/10 border-b border-gray-100 dark:border-gray-800">
                    <td className="px-4 py-2">
                      <input
                        type="text"
                        value={rssEditing.name}
                        onChange={(e) =>
                          setRssEditing({
                            ...rssEditing,
                            name: e.target.value,
                          })
                        }
                        placeholder="Feed name"
                        className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
                        autoFocus
                      />
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="url"
                        value={rssEditing.url}
                        onChange={(e) =>
                          setRssEditing({
                            ...rssEditing,
                            url: e.target.value,
                          })
                        }
                        placeholder="https://example.com/feed.xml"
                        className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
                      />
                    </td>
                    <td className="px-4 py-2">
                      <select
                        value={rssEditing.category}
                        onChange={(e) =>
                          setRssEditing({
                            ...rssEditing,
                            category: e.target.value,
                          })
                        }
                        className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
                      >
                        {RSS_CATEGORIES.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="number"
                        value={rssEditing.check_interval_hours}
                        onChange={(e) =>
                          setRssEditing({
                            ...rssEditing,
                            check_interval_hours:
                              parseInt(e.target.value, 10) || 1,
                          })
                        }
                        min={1}
                        max={168}
                        className="w-20 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
                      />
                    </td>
                    <td className="px-4 py-2">
                      <span className="text-xs text-gray-400">new</span>
                    </td>
                    <td className="px-4 py-2">
                      <span className="text-xs text-gray-400">--</span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={handleSaveFeed}
                          disabled={
                            rssSaving ||
                            !rssEditing.name.trim() ||
                            !rssEditing.url.trim()
                          }
                          className="p-1.5 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors disabled:opacity-50"
                          title="Save"
                        >
                          {rssSaving ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Check className="w-4 h-4" />
                          )}
                        </button>
                        <button
                          onClick={() => setRssEditing(null)}
                          disabled={rssSaving}
                          className="p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
                          title="Cancel"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                )}

                {/* Existing feeds */}
                {feeds.map((feed) =>
                  rssEditing && rssEditing.id === feed.id ? (
                    <tr
                      key={feed.id}
                      className="bg-brand-blue/5 dark:bg-brand-blue/10 border-b border-gray-100 dark:border-gray-800"
                    >
                      <td className="px-4 py-2">
                        <input
                          type="text"
                          value={rssEditing.name}
                          onChange={(e) =>
                            setRssEditing({
                              ...rssEditing,
                              name: e.target.value,
                            })
                          }
                          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
                          autoFocus
                        />
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="url"
                          value={rssEditing.url}
                          onChange={(e) =>
                            setRssEditing({
                              ...rssEditing,
                              url: e.target.value,
                            })
                          }
                          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <select
                          value={rssEditing.category}
                          onChange={(e) =>
                            setRssEditing({
                              ...rssEditing,
                              category: e.target.value,
                            })
                          }
                          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
                        >
                          {RSS_CATEGORIES.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-2">
                        <input
                          type="number"
                          value={rssEditing.check_interval_hours}
                          onChange={(e) =>
                            setRssEditing({
                              ...rssEditing,
                              check_interval_hours:
                                parseInt(e.target.value, 10) || 1,
                            })
                          }
                          min={1}
                          max={168}
                          className="w-20 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <RssStatusBadge status={feed.status} />
                      </td>
                      <td className="px-4 py-2 text-xs text-gray-500 dark:text-gray-400">
                        {formatDate(feed.last_checked_at)}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={handleSaveFeed}
                            disabled={
                              rssSaving ||
                              !rssEditing.name.trim() ||
                              !rssEditing.url.trim()
                            }
                            className="p-1.5 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors disabled:opacity-50"
                            title="Save"
                          >
                            {rssSaving ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Check className="w-4 h-4" />
                            )}
                          </button>
                          <button
                            onClick={() => setRssEditing(null)}
                            disabled={rssSaving}
                            className="p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
                            title="Cancel"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    <tr
                      key={feed.id}
                      className="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
                    >
                      <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                        {feed.name}
                      </td>
                      <td className="px-4 py-3 max-w-xs">
                        <span
                          className="text-xs font-mono text-gray-600 dark:text-gray-400 truncate block"
                          title={feed.url}
                        >
                          {feed.url}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                          {feed.category}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                        {feed.check_interval_hours}h
                      </td>
                      <td className="px-4 py-3">
                        <RssStatusBadge status={feed.status} />
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {formatDate(feed.last_checked_at)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => handleCheckFeed(feed.id)}
                            disabled={checkingFeedId === feed.id}
                            className="p-1.5 text-gray-400 hover:text-brand-blue hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
                            title="Check now"
                          >
                            {checkingFeedId === feed.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <RefreshCw className="w-4 h-4" />
                            )}
                          </button>
                          <button
                            onClick={() => startEditFeed(feed)}
                            disabled={!!rssEditing}
                            className="p-1.5 text-gray-400 hover:text-brand-blue hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
                            title="Edit"
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteFeed(feed.id)}
                            disabled={deletingFeedId === feed.id}
                            className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors disabled:opacity-50"
                            title="Delete"
                          >
                            {deletingFeedId === feed.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ),
                )}

                {feeds.length === 0 && !rssEditing && (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
                    >
                      <Rss className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
                      <p className="text-sm">
                        No RSS feeds configured. Click "Add Feed" to add one.
                      </p>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
