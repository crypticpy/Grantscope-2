/**
 * WorkstreamFeed Page
 *
 * Displays filtered cards based on a workstream's criteria including:
 * - Workstream header with name, description, and status
 * - Filter display showing selected pillars, horizon, stages, and keywords
 * - Cards grid with matching intelligence cards
 * - Empty state when no cards match filters
 */

import React, { useState, useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Edit,
  Eye,
  Heart,
  Filter,
  Loader2,
  Tag,
  RefreshCw,
  FileDown,
  FileText,
  Presentation,
  ChevronDown,
  MessageSquare,
} from "lucide-react";
import { useAuthContext } from "../hooks/useAuthContext";
import { API_BASE_URL } from "../lib/config";
import { cn } from "../lib/utils";
import { PillarBadge, PillarBadgeGroup } from "../components/PillarBadge";
import { PipelineBadge } from "../components/PipelineBadge";
import { DeadlineUrgencyBadge } from "../components/DeadlineUrgencyBadge";
import { Top25Badge } from "../components/Top25Badge";
import { WorkstreamForm } from "../components/WorkstreamForm";
import { WorkstreamChatPanel } from "../components/WorkstreamChatPanel";

// ============================================================================
// Types
// ============================================================================

interface Workstream {
  id: string;
  name: string;
  description: string;
  pillar_ids: string[];
  goal_ids: string[];
  stage_ids: string[];
  horizon: string;
  pipeline_statuses?: string[];
  keywords: string[];
  is_active: boolean;
  auto_add: boolean;
  created_at: string;
  user_id: string;
}

interface Card {
  id: string;
  name: string;
  slug: string;
  summary: string;
  pillar_id: string;
  stage_id: string;
  horizon: "H1" | "H2" | "H3";
  pipeline_status?: string;
  deadline?: string;
  novelty_score: number;
  maturity_score: number;
  impact_score: number;
  relevance_score: number;
  velocity_score: number;
  risk_score: number;
  opportunity_score: number;
  top25_relevance?: string[];
  created_at: string;
}

// CardFollow interface moved to shared types or removed if unused

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Status badge for active/inactive workstream
 */
function StatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
        isActive
          ? "bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400 border border-green-300 dark:border-green-700"
          : "bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300 border border-gray-300 dark:border-gray-600",
      )}
    >
      {isActive ? "Active" : "Inactive"}
    </span>
  );
}

/**
 * Keyword tag display
 */
function KeywordTag({ keyword }: { keyword: string }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-brand-light-blue dark:bg-brand-blue/20 text-brand-dark-blue dark:text-brand-light-blue border border-brand-blue/30 dark:border-brand-blue/40">
      <Tag className="h-3 w-3" />
      {keyword}
    </span>
  );
}

/**
 * Pipeline status display for multiple statuses
 */
function PipelineStatusDisplay({ statusIds }: { statusIds: string[] }) {
  if (statusIds.length === 0) return null;

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {statusIds.map((statusId) => (
        <PipelineBadge key={statusId} status={statusId} size="sm" />
      ))}
    </div>
  );
}

/**
 * Card component for displaying a single intelligence card
 */
function CardItem({
  card,
  isFollowed,
  onToggleFollow,
}: {
  card: Card;
  isFollowed: boolean;
  onToggleFollow: (cardId: string, isFollowed: boolean) => void;
}) {
  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-green-600";
    if (score >= 60) return "text-yellow-600";
    return "text-red-600";
  };

  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg shadow p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2 truncate">
            <Link
              to={`/signals/${card.slug}`}
              className="hover:text-brand-blue transition-colors"
            >
              {card.name}
            </Link>
          </h3>
          <div className="flex items-center gap-2 flex-wrap mb-3">
            <PillarBadge pillarId={card.pillar_id} size="sm" />
            <PipelineBadge
              status={card.pipeline_status || "discovered"}
              size="sm"
            />
            <DeadlineUrgencyBadge deadline={card.deadline} size="sm" />
            {card.top25_relevance && card.top25_relevance.length > 0 && (
              <Top25Badge
                priorities={card.top25_relevance}
                size="sm"
                showCount
              />
            )}
          </div>
        </div>
        <button
          onClick={() => onToggleFollow(card.id, isFollowed)}
          className={cn(
            "flex-shrink-0 p-2 transition-colors rounded-full",
            isFollowed
              ? "text-red-500 hover:text-red-600 hover:bg-red-50"
              : "text-gray-400 hover:text-red-500 hover:bg-gray-50",
          )}
          title={isFollowed ? "Unfollow opportunity" : "Follow opportunity"}
          aria-label={
            isFollowed ? "Unfollow opportunity" : "Follow opportunity"
          }
        >
          {isFollowed ? (
            <Heart className="h-5 w-5 fill-current" />
          ) : (
            <Heart className="h-5 w-5" />
          )}
        </button>
      </div>

      <p className="text-gray-600 dark:text-gray-400 mb-4 line-clamp-3">
        {card.summary}
      </p>

      {/* Scores */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Impact:</span>
          <span className={getScoreColor(card.impact_score)}>
            {card.impact_score}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Relevance:</span>
          <span className={getScoreColor(card.relevance_score)}>
            {card.relevance_score}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Velocity:</span>
          <span className={getScoreColor(card.velocity_score)}>
            {card.velocity_score}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Novelty:</span>
          <span className={getScoreColor(card.novelty_score)}>
            {card.novelty_score}
          </span>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
        <Link
          to={`/signals/${card.slug}`}
          className="inline-flex items-center text-sm text-brand-blue hover:text-brand-dark-blue dark:hover:text-brand-light-blue transition-colors"
        >
          <Eye className="h-4 w-4 mr-1" />
          View Details
        </Link>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

const WorkstreamFeed: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuthContext();

  // State
  const [workstream, setWorkstream] = useState<Workstream | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [followedCardIds, setFollowedCardIds] = useState<Set<string>>(
    new Set(),
  );
  const [loading, setLoading] = useState(true);
  const [cardsLoading, setCardsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Export state
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [exportLoading, setExportLoading] = useState<"pdf" | "pptx" | null>(
    null,
  );

  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false);

  // Chat panel state
  const [chatOpen, setChatOpen] = useState(false);

  // Load workstream data
  useEffect(() => {
    if (id) {
      loadWorkstream();
    }
  }, [id]);

  // Load cards when workstream changes
  useEffect(() => {
    if (workstream) {
      loadWorkstreamFeed();
      loadFollowedCards();
    }
  }, [workstream]);

  /**
   * Load workstream details
   */
  const loadWorkstream = async () => {
    try {
      setLoading(true);
      setError(null);

      const token = localStorage.getItem("gs2_token");
      if (!token) {
        setError("Authentication required.");
        return;
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/me/workstreams`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        console.error("Error loading workstreams:", response.status);
        setError(
          "Failed to load workstream. It may not exist or you may not have access.",
        );
        return;
      }

      const workstreams: Workstream[] = await response.json();
      const found = workstreams.find((ws) => ws.id === id);

      if (!found) {
        setError(
          "Failed to load workstream. It may not exist or you may not have access.",
        );
        return;
      }

      setWorkstream(found);
    } catch (err) {
      console.error("Error loading workstream:", err);
      setError("An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  /**
   * Load cards matching workstream filters via the backend API.
   */
  const loadWorkstreamFeed = async () => {
    if (!workstream) return;

    try {
      setCardsLoading(true);

      const token = localStorage.getItem("gs2_token");
      if (!token) return;

      // Build query parameters from workstream filters
      const params = new URLSearchParams();
      params.set("status", "active");
      params.set("sort", "-created_at");
      params.set("limit", "200");

      if (workstream.pillar_ids && workstream.pillar_ids.length > 0) {
        for (const pillar of workstream.pillar_ids) {
          params.append("pillar_id", pillar);
        }
      }

      if (
        workstream.pipeline_statuses &&
        workstream.pipeline_statuses.length > 0
      ) {
        for (const status of workstream.pipeline_statuses) {
          params.append("pipeline_status", status);
        }
      }

      const response = await fetch(
        `${API_BASE_URL}/api/v1/cards?${params.toString()}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      if (!response.ok) {
        console.error("Error loading feed:", response.status);
        return;
      }

      const rawCardData = await response.json();
      let fetchedCards: Card[] = Array.isArray(rawCardData)
        ? rawCardData
        : rawCardData.cards || [];

      // Client-side keyword filtering (if keywords exist)
      if (workstream.keywords && workstream.keywords.length > 0) {
        const lowercaseKeywords = workstream.keywords.map((k) =>
          k.toLowerCase(),
        );
        fetchedCards = fetchedCards.filter((card) => {
          const cardText = `${card.name} ${card.summary}`.toLowerCase();
          return lowercaseKeywords.some((keyword) =>
            cardText.includes(keyword),
          );
        });
      }

      setCards(fetchedCards);
    } catch (err) {
      console.error("Error loading feed:", err);
    } finally {
      setCardsLoading(false);
    }
  };

  /**
   * Load user's followed cards
   */
  const loadFollowedCards = async () => {
    if (!user) return;

    try {
      const token = localStorage.getItem("gs2_token");
      if (!token) return;

      const response = await fetch(`${API_BASE_URL}/api/v1/me/following`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data)) {
          setFollowedCardIds(
            new Set(
              data
                .map(
                  (f: { card_id?: string; id?: string }) => f.card_id || f.id,
                )
                .filter((id): id is string => !!id),
            ),
          );
        }
      }
    } catch (err) {
      console.error("Error loading followed cards:", err);
    }
  };

  /**
   * Toggle card follow status
   */
  const handleToggleFollow = async (
    cardId: string,
    isCurrentlyFollowed: boolean,
  ) => {
    if (!user) return;

    try {
      const token = localStorage.getItem("gs2_token");
      if (!token) return;

      if (isCurrentlyFollowed) {
        // Unfollow
        const response = await fetch(`${API_BASE_URL}/api/v1/cards/${cardId}/follow`, {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (!response.ok) {
          throw new Error(`Unfollow failed: ${response.status}`);
        }

        setFollowedCardIds((prev) => {
          const next = new Set(prev);
          next.delete(cardId);
          return next;
        });
      } else {
        // Follow
        const response = await fetch(`${API_BASE_URL}/api/v1/cards/${cardId}/follow`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });
        if (!response.ok) {
          throw new Error(`Follow failed: ${response.status}`);
        }

        setFollowedCardIds((prev) => new Set([...prev, cardId]));
      }
    } catch (err) {
      console.error("Error toggling follow:", err);
    }
  };

  /**
   * Refresh feed
   */
  const handleRefresh = () => {
    if (workstream) {
      loadWorkstreamFeed();
    }
  };

  /**
   * Export workstream report
   */
  const handleExport = async (format: "pdf" | "pptx") => {
    if (!workstream || !id) return;

    try {
      setExportLoading(format);
      setShowExportMenu(false);

      // Get the session token
      const token = localStorage.getItem("gs2_token");
      if (!token) {
        throw new Error("Authentication required");
      }

      // Build the export URL
      const exportUrl = `${API_BASE_URL}/api/v1/workstreams/${id}/export/${format}`;

      // Fetch the export file
      const response = await fetch(exportUrl, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `Export failed: ${response.status}`,
        );
      }

      // Get the filename from Content-Disposition header or generate one
      const contentDisposition = response.headers.get("Content-Disposition");
      let filename = `${workstream.name.replace(/[^a-zA-Z0-9-_]/g, "_")}.${format}`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
        if (filenameMatch?.[1]) {
          filename = filenameMatch[1];
        }
      }

      // Create blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed:", err);
      // Could add toast notification here
    } finally {
      setExportLoading(null);
    }
  };

  /**
   * Handle edit modal success
   */
  const handleEditSuccess = () => {
    setShowEditModal(false);
    loadWorkstream();
  };

  /**
   * Handle edit modal cancel
   */
  const handleEditCancel = () => {
    setShowEditModal(false);
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-brand-blue" />
          <p className="text-gray-600 dark:text-gray-400">
            Loading workstream...
          </p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12 bg-white dark:bg-dark-surface rounded-lg shadow">
          <div className="text-red-500 dark:text-red-400 mb-4">
            <Filter className="mx-auto h-12 w-12" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Error
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-6">{error}</p>
          <Link
            to="/workstreams"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Workstreams
          </Link>
        </div>
      </div>
    );
  }

  // No workstream found
  if (!workstream) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12 bg-white dark:bg-dark-surface rounded-lg shadow">
          <Filter className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" />
          <h3 className="mt-2 text-lg font-medium text-gray-900 dark:text-white">
            Workstream not found
          </h3>
          <p className="mt-1 text-gray-600 dark:text-gray-400">
            The workstream you're looking for doesn't exist or has been deleted.
          </p>
          <div className="mt-6">
            <Link
              to="/workstreams"
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Workstreams
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header Section */}
      <div className="mb-8">
        {/* Back button */}
        <Link
          to="/workstreams"
          className="inline-flex items-center text-sm text-gray-600 dark:text-gray-400 hover:text-brand-blue transition-colors mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Workstreams
        </Link>

        {/* Title and actions */}
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">
                {workstream.name}
              </h1>
              <StatusBadge isActive={workstream.is_active} />
            </div>
            {workstream.description && (
              <p className="text-gray-600 dark:text-gray-400 max-w-3xl">
                {workstream.description}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              className="inline-flex items-center px-3 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface-elevated hover:bg-gray-50 dark:hover:bg-dark-surface-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface transition-colors"
              title="Refresh feed"
            >
              <RefreshCw
                className={cn("h-4 w-4", cardsLoading && "animate-spin")}
              />
            </button>

            {/* Export Dropdown */}
            <div className="relative">
              <button
                onClick={() => setShowExportMenu(!showExportMenu)}
                disabled={exportLoading !== null}
                className={cn(
                  "inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface-elevated hover:bg-gray-50 dark:hover:bg-dark-surface-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface transition-colors",
                  exportLoading !== null && "opacity-75 cursor-not-allowed",
                )}
                title="Export workstream report"
              >
                {exportLoading !== null ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <FileDown className="h-4 w-4 mr-2" />
                )}
                Export
                <ChevronDown
                  className={cn(
                    "h-4 w-4 ml-1 transition-transform",
                    showExportMenu && "rotate-180",
                  )}
                />
              </button>

              {/* Dropdown Menu */}
              {showExportMenu && (
                <>
                  {/* Backdrop to close menu when clicking outside */}
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setShowExportMenu(false)}
                  />
                  <div className="absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-white dark:bg-dark-surface-elevated ring-1 ring-black ring-opacity-5 z-20">
                    <div
                      className="py-1"
                      role="menu"
                      aria-orientation="vertical"
                    >
                      <button
                        onClick={() => handleExport("pdf")}
                        className="w-full text-left px-4 py-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-dark-surface-hover flex items-center gap-3 transition-colors"
                        role="menuitem"
                      >
                        <FileText className="h-5 w-5 text-red-500" />
                        <div>
                          <div className="font-medium">PDF Report</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            Printable document format
                          </div>
                        </div>
                      </button>
                      <button
                        onClick={() => handleExport("pptx")}
                        className="w-full text-left px-4 py-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-dark-surface-hover flex items-center gap-3 transition-colors"
                        role="menuitem"
                      >
                        <Presentation className="h-5 w-5 text-orange-500" />
                        <div>
                          <div className="font-medium">PowerPoint</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            Presentation slides
                          </div>
                        </div>
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Chat Button */}
            <button
              onClick={() => setChatOpen(true)}
              className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface-elevated hover:bg-gray-50 dark:hover:bg-dark-surface-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface transition-colors"
              aria-label="Open workstream chat"
            >
              <MessageSquare className="h-4 w-4" />
              <span className="hidden sm:inline">Chat</span>
            </button>

            <button
              onClick={() => setShowEditModal(true)}
              className="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface-elevated hover:bg-gray-50 dark:hover:bg-dark-surface-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface transition-colors"
            >
              <Edit className="h-4 w-4 mr-2" />
              Edit Filters
            </button>
          </div>
        </div>
      </div>

      {/* Filter Display Section */}
      <div className="bg-white dark:bg-dark-surface rounded-lg shadow p-6 mb-6">
        <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">
          Active Filters
        </h2>

        <div className="space-y-4">
          {/* Pillars */}
          {workstream.pillar_ids && workstream.pillar_ids.length > 0 && (
            <div className="flex items-start gap-3">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-20 shrink-0 pt-0.5">
                Pillars:
              </span>
              <PillarBadgeGroup
                pillarIds={workstream.pillar_ids}
                size="sm"
                maxVisible={6}
              />
            </div>
          )}

          {/* Pipeline Statuses */}
          {workstream.pipeline_statuses &&
            workstream.pipeline_statuses.length > 0 && (
              <div className="flex items-start gap-3">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-20 shrink-0 pt-0.5">
                  Statuses:
                </span>
                <PipelineStatusDisplay
                  statusIds={workstream.pipeline_statuses}
                />
              </div>
            )}

          {/* Keywords */}
          {workstream.keywords && workstream.keywords.length > 0 && (
            <div className="flex items-start gap-3">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-20 shrink-0 pt-0.5">
                Keywords:
              </span>
              <div className="flex items-center gap-1.5 flex-wrap">
                {workstream.keywords.map((keyword) => (
                  <KeywordTag key={keyword} keyword={keyword} />
                ))}
              </div>
            </div>
          )}

          {/* No filters */}
          {(!workstream.pillar_ids || workstream.pillar_ids.length === 0) &&
            (!workstream.pipeline_statuses ||
              workstream.pipeline_statuses.length === 0) &&
            (!workstream.keywords || workstream.keywords.length === 0) && (
              <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                No filters configured. Showing all opportunities.
              </p>
            )}
        </div>
      </div>

      {/* Cards Grid */}
      {cardsLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-brand-blue" />
            <p className="text-gray-600 dark:text-gray-400">
              Loading opportunities...
            </p>
          </div>
        </div>
      ) : cards.length === 0 ? (
        /* Empty State */
        <div className="text-center py-12 bg-white dark:bg-dark-surface rounded-lg shadow">
          <Filter className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" />
          <h3 className="mt-2 text-lg font-medium text-gray-900 dark:text-white">
            No matching opportunities
          </h3>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
            This program&apos;s filters might be too narrow. Try broadening your
            search terms or removing some filters to see more results.
          </p>
          <p className="mt-3 text-xs text-gray-400 dark:text-gray-500 italic max-w-sm mx-auto">
            GrantScope scans for new grants daily. Check back soon or adjust
            your program&apos;s focus area to broaden matches.
          </p>
          <div className="mt-6">
            <button
              onClick={() => setShowEditModal(true)}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-dark-surface transition-colors"
            >
              <Edit className="h-4 w-4 mr-2" />
              Adjust Filters
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* Results count */}
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Showing {cards.length} {cards.length === 1 ? "card" : "cards"}
            </p>
          </div>

          {/* Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {cards.map((card) => (
              <CardItem
                key={card.id}
                card={card}
                isFollowed={followedCardIds.has(card.id)}
                onToggleFollow={handleToggleFollow}
              />
            ))}
          </div>
        </>
      )}

      {/* Edit Workstream Modal */}
      {showEditModal && workstream && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50 overflow-y-auto">
          <div className="bg-white dark:bg-dark-surface rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col">
            <div className="sticky top-0 bg-white dark:bg-dark-surface border-b border-gray-200 dark:border-gray-700 px-6 py-4 rounded-t-lg">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                Edit Workstream Filters
              </h3>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Adjust the filters to change which opportunities match this
                workstream.
              </p>
            </div>
            <div className="flex-1 overflow-y-auto">
              <WorkstreamForm
                workstream={workstream}
                onSuccess={handleEditSuccess}
                onCancel={handleEditCancel}
              />
            </div>
          </div>
        </div>
      )}

      {/* Workstream Chat Panel */}
      <WorkstreamChatPanel
        workstreamId={id!}
        workstreamName={workstream?.name || "Workstream"}
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
      />
    </div>
  );
};

export default WorkstreamFeed;
