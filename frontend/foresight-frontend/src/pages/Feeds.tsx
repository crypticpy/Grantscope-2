/**
 * Feeds Page
 *
 * RSS feed management interface. Features:
 * - List all configured RSS feeds with stats
 * - Add, edit, delete feeds
 * - Trigger manual feed checks
 * - View feed items with triage result filtering
 * - Status indicators and error reporting
 *
 * @module pages/Feeds
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  Rss,
  Plus,
  RefreshCw,
  Trash2,
  Edit2,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  X,
  Loader2,
  Clock,
  ChevronDown,
  ChevronUp,
  PauseCircle,
  Filter,
} from "lucide-react";
import { supabase } from "../App";
import { useAuthContext } from "../hooks/useAuthContext";
import { LoadingButton } from "../components/ui/LoadingButton";
import type {
  Feed,
  FeedItem,
  CreateFeedPayload,
  UpdateFeedPayload,
} from "../lib/feeds-api";
import {
  getFeeds,
  createFeed,
  updateFeed,
  deleteFeed,
  triggerCheck,
  getFeedItems,
} from "../lib/feeds-api";

// ============================================================================
// Constants
// ============================================================================

const FEED_CATEGORIES = [
  { value: "gov_tech", label: "Government Tech" },
  { value: "municipal", label: "Municipal" },
  { value: "academic", label: "Academic" },
  { value: "news", label: "News" },
  { value: "think_tank", label: "Think Tank" },
  { value: "tech", label: "Technology" },
  { value: "general", label: "General" },
] as const;

const PILLARS = [
  { value: "", label: "None" },
  { value: "CH", label: "CH - Community Health" },
  { value: "MC", label: "MC - Mobility" },
  { value: "HS", label: "HS - Housing" },
  { value: "EC", label: "EC - Economic" },
  { value: "ES", label: "ES - Environmental" },
  { value: "CE", label: "CE - Cultural" },
] as const;

const TRIAGE_FILTERS = [
  { value: "all", label: "All Items" },
  { value: "matched", label: "Matched" },
  { value: "pending", label: "Pending" },
  { value: "irrelevant", label: "Irrelevant" },
] as const;

// ============================================================================
// Helpers
// ============================================================================

function getCategoryColor(category: string): string {
  const colors: Record<string, string> = {
    gov_tech:
      "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    municipal:
      "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
    academic:
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    news: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
    think_tank:
      "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300",
    tech: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300",
    general: "bg-gray-100 text-gray-800 dark:bg-gray-700/50 dark:text-gray-300",
  };
  return colors[category] || colors.general;
}

function getStatusIcon(status: string) {
  switch (status) {
    case "active":
      return <CheckCircle2 className="w-4 h-4 text-green-500" />;
    case "paused":
      return <PauseCircle className="w-4 h-4 text-yellow-500" />;
    case "error":
      return <AlertCircle className="w-4 h-4 text-red-500" />;
    default:
      return <Clock className="w-4 h-4 text-gray-400" />;
  }
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "Never";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function getCategoryLabel(value: string): string {
  const cat = FEED_CATEGORIES.find((c) => c.value === value);
  return cat ? cat.label : value;
}

function getTriageColor(result: string | null): string {
  switch (result) {
    case "matched":
      return "text-green-600 dark:text-green-400";
    case "pending":
      return "text-yellow-600 dark:text-yellow-400";
    case "irrelevant":
      return "text-gray-400 dark:text-gray-500";
    default:
      return "text-gray-500 dark:text-gray-400";
  }
}

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Modal for adding or editing a feed.
 */
const FeedModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateFeedPayload | UpdateFeedPayload) => Promise<void>;
  initialData?: Feed | null;
  isSubmitting: boolean;
}> = ({ isOpen, onClose, onSubmit, initialData, isSubmitting }) => {
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("general");
  const [pillarId, setPillarId] = useState("");
  const [checkInterval, setCheckInterval] = useState(6);

  // Populate form when editing
  useEffect(() => {
    if (initialData) {
      setUrl(initialData.url);
      setName(initialData.name);
      setCategory(initialData.category || "general");
      setPillarId(initialData.pillar_id || "");
      setCheckInterval(initialData.check_interval_hours || 6);
    } else {
      setUrl("");
      setName("");
      setCategory("general");
      setPillarId("");
      setCheckInterval(6);
    }
  }, [initialData, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: CreateFeedPayload = {
      url,
      name,
      category,
      pillar_id: pillarId || null,
      check_interval_hours: checkInterval,
    };
    await onSubmit(payload);
  };

  const isEditing = !!initialData;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Modal */}
      <div className="relative w-full max-w-lg mx-4 bg-white dark:bg-dark-surface rounded-xl shadow-xl border border-gray-200 dark:border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            {isEditing ? "Edit Feed" : "Add New Feed"}
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-md transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          {/* URL */}
          <div>
            <label
              htmlFor="feed-url"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Feed URL <span className="text-red-500">*</span>
            </label>
            <input
              id="feed-url"
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/feed.xml"
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-dark-surface-elevated text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors"
            />
          </div>

          {/* Name */}
          <div>
            <label
              htmlFor="feed-name"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Feed Name <span className="text-red-500">*</span>
            </label>
            <input
              id="feed-name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., GovTech Weekly"
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-dark-surface-elevated text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors"
            />
          </div>

          {/* Category and Pillar row */}
          <div className="grid grid-cols-2 gap-4">
            {/* Category */}
            <div>
              <label
                htmlFor="feed-category"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Category
              </label>
              <select
                id="feed-category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-dark-surface-elevated text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors"
              >
                {FEED_CATEGORIES.map((cat) => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Pillar */}
            <div>
              <label
                htmlFor="feed-pillar"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Strategic Pillar
              </label>
              <select
                id="feed-pillar"
                value={pillarId}
                onChange={(e) => setPillarId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-dark-surface-elevated text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors"
              >
                {PILLARS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Check Interval */}
          <div>
            <label
              htmlFor="feed-interval"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Check Interval (hours)
            </label>
            <input
              id="feed-interval"
              type="number"
              min={1}
              max={168}
              value={checkInterval}
              onChange={(e) =>
                setCheckInterval(parseInt(e.target.value, 10) || 6)
              }
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-dark-surface-elevated text-gray-900 dark:text-white focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-colors"
            />
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              How often this feed should be checked for new articles (1-168
              hours)
            </p>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <LoadingButton
              type="button"
              variant="secondary"
              size="sm"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </LoadingButton>
            <LoadingButton
              type="submit"
              variant="primary"
              size="sm"
              loading={isSubmitting}
              loadingText={isEditing ? "Saving..." : "Adding..."}
            >
              {isEditing ? "Save Changes" : "Add Feed"}
            </LoadingButton>
          </div>
        </form>
      </div>
    </div>
  );
};

/**
 * Expandable feed items section shown when a feed card is expanded.
 */
const FeedItemsSection: React.FC<{
  feedId: string;
  token: string;
}> = ({ feedId, token }) => {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triageFilter, setTriageFilter] = useState("all");

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getFeedItems(token, feedId, {
        limit: 50,
        triage_result: triageFilter === "all" ? undefined : triageFilter,
      });
      setItems(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load items");
    } finally {
      setLoading(false);
    }
  }, [feedId, token, triageFilter]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  return (
    <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-dark-surface-elevated/50">
      {/* Filter bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-100 dark:border-gray-700/50">
        <Filter className="w-3.5 h-3.5 text-gray-400" />
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
          Filter:
        </span>
        {TRIAGE_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setTriageFilter(f.value)}
            className={`px-2 py-0.5 text-xs rounded-md transition-colors ${
              triageFilter === f.value
                ? "bg-brand-blue text-white"
                : "text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Items list */}
      <div className="max-h-80 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-brand-blue" />
            <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">
              Loading items...
            </span>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center py-8 text-sm text-red-500">
            <AlertCircle className="w-4 h-4 mr-2" />
            {error}
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">
            No items found
            {triageFilter !== "all" ? " matching this filter" : ""}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2 hidden sm:table-cell">Published</th>
                <th className="px-4 py-2 hidden md:table-cell">Triage</th>
                <th className="px-4 py-2 w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
              {items.map((item) => (
                <tr
                  key={item.id}
                  className="hover:bg-gray-100/50 dark:hover:bg-gray-700/30 transition-colors"
                >
                  <td className="px-4 py-2">
                    <span className="text-gray-900 dark:text-white line-clamp-1">
                      {item.title}
                    </span>
                  </td>
                  <td className="px-4 py-2 hidden sm:table-cell text-gray-500 dark:text-gray-400 whitespace-nowrap">
                    {item.published_at
                      ? formatRelativeTime(item.published_at)
                      : "--"}
                  </td>
                  <td
                    className={`px-4 py-2 hidden md:table-cell font-medium whitespace-nowrap ${getTriageColor(item.triage_result)}`}
                  >
                    {item.triage_result || "unprocessed"}
                  </td>
                  <td className="px-4 py-2">
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-400 hover:text-brand-blue transition-colors"
                      title="Open article"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

const Feeds: React.FC = () => {
  // Verify auth context is available (token retrieved via supabase.auth.getSession)
  useAuthContext();

  // Feed data state
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingFeed, setEditingFeed] = useState<Feed | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Action states
  const [isChecking, setIsChecking] = useState(false);
  const [checkMessage, setCheckMessage] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Expanded feed (show items)
  const [expandedFeedId, setExpandedFeedId] = useState<string | null>(null);

  // Get auth token
  const getToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) throw new Error("Not authenticated");
    return session.access_token;
  }, []);

  // Load feeds
  const loadFeeds = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const data = await getFeeds(token);
      setFeeds(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load feeds");
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    loadFeeds();
  }, [loadFeeds]);

  // Add or edit feed
  const handleSubmitFeed = async (
    payload: CreateFeedPayload | UpdateFeedPayload,
  ) => {
    setIsSubmitting(true);
    try {
      const token = await getToken();
      if (editingFeed) {
        await updateFeed(token, editingFeed.id, payload as UpdateFeedPayload);
      } else {
        await createFeed(token, payload as CreateFeedPayload);
      }
      setIsModalOpen(false);
      setEditingFeed(null);
      await loadFeeds();
    } catch (err) {
      // Keep modal open on error so user can fix
      console.error("Feed save error:", err);
      throw err;
    } finally {
      setIsSubmitting(false);
    }
  };

  // Delete feed
  const handleDeleteFeed = async (feedId: string) => {
    if (!window.confirm("Are you sure you want to delete this feed?")) return;
    setDeletingId(feedId);
    try {
      const token = await getToken();
      await deleteFeed(token, feedId);
      if (expandedFeedId === feedId) setExpandedFeedId(null);
      await loadFeeds();
    } catch (err) {
      console.error("Delete error:", err);
    } finally {
      setDeletingId(null);
    }
  };

  // Manual check
  const handleCheckNow = async () => {
    setIsChecking(true);
    setCheckMessage(null);
    try {
      const token = await getToken();
      const result = await triggerCheck(token);
      setCheckMessage(
        result.message || `Checked ${result.feeds_checked} feeds`,
      );
      // Reload feeds after check to get updated stats
      setTimeout(() => {
        loadFeeds();
        setCheckMessage(null);
      }, 3000);
    } catch (err) {
      setCheckMessage(err instanceof Error ? err.message : "Check failed");
      setTimeout(() => setCheckMessage(null), 5000);
    } finally {
      setIsChecking(false);
    }
  };

  // Open edit modal
  const handleEditFeed = (feed: Feed) => {
    setEditingFeed(feed);
    setIsModalOpen(true);
  };

  // Open add modal
  const handleAddFeed = () => {
    setEditingFeed(null);
    setIsModalOpen(true);
  };

  // Toggle expanded feed
  const toggleExpanded = (feedId: string) => {
    setExpandedFeedId((prev) => (prev === feedId ? null : feedId));
  };

  // Stats
  const activeCount = feeds.filter((f) => f.status === "active").length;
  const errorCount = feeds.filter((f) => f.status === "error").length;
  const totalArticles = feeds.reduce(
    (sum, f) => sum + f.articles_found_total,
    0,
  );
  const totalMatched = feeds.reduce(
    (sum, f) => sum + f.articles_matched_total,
    0,
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand-blue/10 rounded-lg">
              <Rss className="w-6 h-6 text-brand-blue" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                RSS Feeds
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Monitor curated RSS feeds for emerging signals
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <LoadingButton
            variant="secondary"
            size="sm"
            loading={isChecking}
            loadingText="Checking..."
            onClick={handleCheckNow}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Check Now
          </LoadingButton>
          <LoadingButton variant="primary" size="sm" onClick={handleAddFeed}>
            <Plus className="w-4 h-4 mr-2" />
            Add Feed
          </LoadingButton>
        </div>
      </div>

      {/* Check message toast */}
      {checkMessage && (
        <div className="mb-4 px-4 py-2 bg-brand-blue/10 text-brand-blue text-sm rounded-lg border border-brand-blue/20 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          {checkMessage}
        </div>
      )}

      {/* Summary Stats */}
      {!loading && feeds.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Total Feeds
            </p>
            <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">
              {feeds.length}
            </p>
          </div>
          <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Active
            </p>
            <p className="mt-1 text-2xl font-semibold text-green-600 dark:text-green-400">
              {activeCount}
            </p>
          </div>
          <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Articles Found
            </p>
            <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">
              {totalArticles.toLocaleString()}
            </p>
          </div>
          <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Matched
            </p>
            <p className="mt-1 text-2xl font-semibold text-brand-blue">
              {totalMatched.toLocaleString()}
            </p>
          </div>
        </div>
      )}

      {/* Error banner for feeds with errors */}
      {!loading && errorCount > 0 && (
        <div className="mb-4 px-4 py-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-800 dark:text-red-300">
              {errorCount} feed{errorCount > 1 ? "s" : ""} reporting errors
            </p>
            <p className="text-xs text-red-600 dark:text-red-400 mt-0.5">
              Check the error details below and verify the feed URLs are
              correct.
            </p>
          </div>
        </div>
      )}

      {/* Main Content */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
          <span className="ml-3 text-gray-500 dark:text-gray-400">
            Loading feeds...
          </span>
        </div>
      ) : error ? (
        <div className="text-center py-16">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 mb-4">{error}</p>
          <LoadingButton variant="secondary" size="sm" onClick={loadFeeds}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </LoadingButton>
        </div>
      ) : feeds.length === 0 ? (
        <div className="text-center py-16">
          <Rss className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            No feeds configured
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-6 max-w-md mx-auto">
            Add RSS feeds to automatically monitor for emerging signals and
            trends relevant to Austin's strategic priorities.
          </p>
          <LoadingButton variant="primary" size="md" onClick={handleAddFeed}>
            <Plus className="w-4 h-4 mr-2" />
            Add Your First Feed
          </LoadingButton>
        </div>
      ) : (
        /* Feed Cards Grid */
        <div className="space-y-3">
          {feeds.map((feed) => {
            const isExpanded = expandedFeedId === feed.id;
            const isDeleting = deletingId === feed.id;

            return (
              <div
                key={feed.id}
                className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden transition-shadow hover:shadow-md"
              >
                {/* Feed Card Header */}
                <div className="p-4 sm:p-5">
                  <div className="flex items-start justify-between gap-4">
                    {/* Left: Feed info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        {getStatusIcon(feed.status)}
                        <h3 className="text-base font-semibold text-gray-900 dark:text-white truncate">
                          {feed.name}
                        </h3>
                        <span
                          className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${getCategoryColor(feed.category)}`}
                        >
                          {getCategoryLabel(feed.category)}
                        </span>
                        {feed.pillar_id && (
                          <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded-full bg-brand-blue/10 text-brand-blue">
                            {feed.pillar_id}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate mb-2">
                        {feed.url}
                      </p>

                      {/* Stats row */}
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
                        <span>
                          <strong className="text-gray-700 dark:text-gray-300">
                            {feed.articles_found_total}
                          </strong>{" "}
                          found
                        </span>
                        <span>
                          <strong className="text-gray-700 dark:text-gray-300">
                            {feed.articles_matched_total}
                          </strong>{" "}
                          matched
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatRelativeTime(feed.last_checked_at)}
                        </span>
                        <span>Every {feed.check_interval_hours}h</span>
                        {feed.error_count > 0 && (
                          <span className="flex items-center gap-1 text-red-500">
                            <AlertCircle className="w-3 h-3" />
                            {feed.error_count} error
                            {feed.error_count > 1 ? "s" : ""}
                          </span>
                        )}
                      </div>

                      {/* Error message */}
                      {feed.last_error && (
                        <div className="mt-2 px-3 py-1.5 bg-red-50 dark:bg-red-900/20 rounded-md">
                          <p className="text-xs text-red-600 dark:text-red-400 line-clamp-2">
                            {feed.last_error}
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Right: Actions */}
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button
                        onClick={() => toggleExpanded(feed.id)}
                        className="p-2 text-gray-400 hover:text-brand-blue hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
                        title={isExpanded ? "Collapse" : "Show items"}
                      >
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </button>
                      <a
                        href={feed.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 text-gray-400 hover:text-brand-blue hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
                        title="Open feed URL"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                      <button
                        onClick={() => handleEditFeed(feed)}
                        className="p-2 text-gray-400 hover:text-brand-blue hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
                        title="Edit feed"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteFeed(feed.id)}
                        disabled={isDeleting}
                        className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors disabled:opacity-50"
                        title="Delete feed"
                      >
                        {isDeleting ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Expanded Items Section */}
                {isExpanded && (
                  <FeedItemsSectionWrapper
                    feedId={feed.id}
                    getToken={getToken}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Add/Edit Modal */}
      <FeedModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingFeed(null);
        }}
        onSubmit={handleSubmitFeed}
        initialData={editingFeed}
        isSubmitting={isSubmitting}
      />
    </div>
  );
};

/**
 * Wrapper component for FeedItemsSection that resolves the token.
 */
const FeedItemsSectionWrapper: React.FC<{
  feedId: string;
  getToken: () => Promise<string>;
}> = ({ feedId, getToken }) => {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    getToken().then(setToken).catch(console.error);
  }, [getToken]);

  if (!token) {
    return (
      <div className="flex items-center justify-center py-6 border-t border-gray-200 dark:border-gray-700">
        <Loader2 className="w-4 h-4 animate-spin text-brand-blue" />
      </div>
    );
  }

  return <FeedItemsSection feedId={feedId} token={token} />;
};

export default Feeds;
