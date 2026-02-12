/**
 * CardDetail Component
 *
 * A refactored, modular component that displays comprehensive card/trend details.
 * This component orchestrates top-level state management and data flow,
 * delegating rendering to focused sub-components.
 *
 * Original: 1829 lines -> Refactored: ~290 lines
 *
 * Features:
 * - Modular composition of sub-components
 * - Centralized state management for data loading
 * - Research task triggering and polling
 * - Tab-based navigation (Overview, Sources, Timeline, Notes, Related)
 * - Dark mode support
 * - Responsive design
 *
 * @module CardDetail
 */

import React, { useState, useEffect, useCallback, Suspense } from "react";
import {
  useParams,
  Link,
  useNavigate,
  useSearchParams,
  useLocation,
} from "react-router-dom";
import {
  Eye,
  FileText,
  Calendar,
  TrendingUp,
  GitBranch,
  FolderOpen,
  MessageSquare,
} from "lucide-react";
import { supabase } from "../../App";
import { useAuthContext } from "../../hooks/useAuthContext";
import { cn } from "../../lib/utils";

// CardDetail sub-components
import { CardDetailHeader } from "./CardDetailHeader";
import { CardActionButtons } from "./CardActionButtons";
import { ResearchStatusBanner } from "./ResearchStatusBanner";
import {
  CardDescription,
  CardClassification,
  DeepResearchPanel,
  ResearchHistoryPanel,
  ImpactMetricsPanel,
  MaturityScorePanel,
  ActivityStatsPanel,
} from "./tabs/OverviewTab";
import { SourcesTab } from "./tabs/SourcesTab";
import { TimelineTab } from "./tabs/TimelineTab";
import { NotesTab } from "./tabs/NotesTab";
import { AssetsTab } from "./AssetsTab";
const ChatTabContent = React.lazy(() => import("./ChatTabContent"));

// Visualization Components
import { ScoreTimelineChart } from "../visualizations/ScoreTimelineChart";
import { ConceptNetworkDiagram } from "../visualizations/ConceptNetworkDiagram";

// Types and utilities
import type {
  Card,
  ResearchTask,
  Source,
  TimelineEvent,
  Note,
  CardDetailTab,
} from "./types";
import { API_BASE_URL } from "./utils";

// API Functions
import {
  getScoreHistory,
  getStageHistory,
  getRelatedCards,
  fetchCardAssets,
  type ScoreHistory,
  type StageHistory,
  type RelatedCard,
  type CardAsset,
} from "../../lib/discovery-api";

/**
 * Props for the CardDetail component
 */
export interface CardDetailProps {
  /** Optional custom className for the container */
  className?: string;
}

/**
 * CardDetail displays comprehensive information about a card/trend.
 *
 * This is the main orchestrator component that:
 * - Loads and manages all card-related data
 * - Handles research task triggering and status polling
 * - Manages user interactions (following, notes)
 * - Renders sub-components in a tabbed layout
 */
export const CardDetail: React.FC<CardDetailProps> = ({ className = "" }) => {
  const { slug } = useParams<{ slug: string }>();
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const location = useLocation();

  // Allow viewing non-active cards (e.g., pending review) when opened from the queue.
  const mode = searchParams.get("mode");
  const isReviewMode = mode === "review" || mode === "edit";
  const fromPath = (location.state as { from?: string })?.from;
  const backLink = isReviewMode ? "/discover/queue" : fromPath || "/discover";
  const backLinkText = isReviewMode
    ? "Back to Review Queue"
    : fromPath === "/signals"
      ? "Back to Signals"
      : fromPath === "/"
        ? "Back to Dashboard"
        : "Back to Discover";

  // Core card data
  const [card, setCard] = useState<Card | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [isFollowing, setIsFollowing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<CardDetailTab>("overview");
  const [newNote, setNewNote] = useState("");

  // Research state
  const [researchTask, setResearchTask] = useState<ResearchTask | null>(null);
  const [isResearching, setIsResearching] = useState(false);
  const [researchError, setResearchError] = useState<string | null>(null);
  const [showReport, setShowReport] = useState(false);
  const [reportCopied, setReportCopied] = useState(false);
  const [researchHistory, setResearchHistory] = useState<ResearchTask[]>([]);

  // Trend visualization state
  const [scoreHistory, setScoreHistory] = useState<ScoreHistory[]>([]);
  const [stageHistory, setStageHistory] = useState<StageHistory[]>([]);
  const [scoreHistoryLoading, setScoreHistoryLoading] = useState(false);
  const [stageHistoryLoading, setStageHistoryLoading] = useState(false);
  const [scoreHistoryError, setScoreHistoryError] = useState<string | null>(
    null,
  );

  // Related cards state
  const [relatedCards, setRelatedCards] = useState<RelatedCard[]>([]);
  const [relatedCardsLoading, setRelatedCardsLoading] = useState(false);
  const [relatedCardsError, setRelatedCardsError] = useState<string | null>(
    null,
  );

  // Assets state
  const [assets, setAssets] = useState<CardAsset[]>([]);
  const [assetsLoading, setAssetsLoading] = useState(false);
  const [assetsError, setAssetsError] = useState<string | null>(null);

  // Get auth token for API requests
  const getAuthToken = useCallback(async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token;
  }, []);

  // Load card detail from database
  const loadCardDetail = useCallback(async () => {
    if (!slug) return;
    try {
      let query = supabase.from("cards").select("*").eq("slug", slug);

      // Default: only show active cards. Review mode: allow pending/draft cards.
      if (!isReviewMode) {
        query = query.eq("status", "active");
      }

      const { data: cardData } = await query.single();

      if (cardData) {
        setCard(cardData);

        // Load related data in parallel
        const [sourcesRes, timelineRes, notesRes, researchRes] =
          await Promise.all([
            supabase
              .from("sources")
              .select("*")
              .eq("card_id", cardData.id)
              .order("relevance_score", { ascending: false }),
            supabase
              .from("card_timeline")
              .select("*")
              .eq("card_id", cardData.id)
              .order("created_at", { ascending: false }),
            supabase
              .from("card_notes")
              .select("*")
              .eq("card_id", cardData.id)
              .or(`user_id.eq.${user?.id},is_private.eq.false`)
              .order("created_at", { ascending: false }),
            supabase
              .from("research_tasks")
              .select("*")
              .eq("card_id", cardData.id)
              .eq("status", "completed")
              .order("completed_at", { ascending: false })
              .limit(10),
          ]);

        setSources(sourcesRes.data || []);
        setTimeline(timelineRes.data || []);
        setNotes(notesRes.data || []);
        setResearchHistory(researchRes.data || []);
      }
    } finally {
      setLoading(false);
    }
  }, [slug, user?.id, isReviewMode]);

  // Load score/stage history and related cards
  const loadScoreHistory = useCallback(async () => {
    if (!card?.id) return;
    setScoreHistoryLoading(true);
    setScoreHistoryError(null);
    try {
      const token = await getAuthToken();
      if (token) {
        const response = await getScoreHistory(token, card.id);
        setScoreHistory(response.history);
      }
    } catch (error: unknown) {
      setScoreHistoryError(
        error instanceof Error ? error.message : "Failed to load",
      );
    } finally {
      setScoreHistoryLoading(false);
    }
  }, [card?.id, getAuthToken]);

  const loadStageHistory = useCallback(async () => {
    if (!card?.id) return;
    setStageHistoryLoading(true);
    try {
      const token = await getAuthToken();
      if (token) {
        const response = await getStageHistory(token, card.id);
        setStageHistory(response.history);
      }
    } finally {
      setStageHistoryLoading(false);
    }
  }, [card?.id, getAuthToken]);

  const loadRelatedCards = useCallback(async () => {
    if (!card?.id) return;
    setRelatedCardsLoading(true);
    setRelatedCardsError(null);
    try {
      const token = await getAuthToken();
      if (token) {
        const response = await getRelatedCards(token, card.id);
        setRelatedCards(response.related_cards);
      }
    } catch (error: unknown) {
      setRelatedCardsError(
        error instanceof Error ? error.message : "Failed to load",
      );
    } finally {
      setRelatedCardsLoading(false);
    }
  }, [card?.id, getAuthToken]);

  // Load card assets (briefs, research reports, exports)
  const loadAssets = useCallback(async () => {
    if (!card?.id) return;
    setAssetsLoading(true);
    setAssetsError(null);
    try {
      const token = await getAuthToken();
      if (token) {
        const response = await fetchCardAssets(token, card.id);
        setAssets(response.assets);
      }
    } catch (error: unknown) {
      setAssetsError(
        error instanceof Error ? error.message : "Failed to load assets",
      );
    } finally {
      setAssetsLoading(false);
    }
  }, [card?.id, getAuthToken]);

  // Check following status
  const checkIfFollowing = useCallback(async () => {
    if (!user || !card?.id) return;
    try {
      const { data } = await supabase
        .from("card_follows")
        .select("id")
        .eq("user_id", user.id)
        .eq("card_id", card.id)
        .maybeSingle();
      setIsFollowing(!!data);
    } catch {
      setIsFollowing(false);
    }
  }, [user, card?.id]);

  // Toggle follow status
  const toggleFollow = useCallback(async () => {
    if (!user || !card) return;
    try {
      if (isFollowing) {
        await supabase
          .from("card_follows")
          .delete()
          .eq("user_id", user.id)
          .eq("card_id", card.id);
        setIsFollowing(false);
      } else {
        await supabase
          .from("card_follows")
          .insert({ user_id: user.id, card_id: card.id, priority: "medium" });
        setIsFollowing(true);
      }
    } catch (error) {
      console.error("Error toggling follow:", error);
    }
  }, [user, card, isFollowing]);

  // Add note
  const addNote = useCallback(async () => {
    if (!user || !card || !newNote.trim()) return;
    try {
      const { data } = await supabase
        .from("card_notes")
        .insert({
          user_id: user.id,
          card_id: card.id,
          content: newNote,
          is_private: false,
        })
        .select()
        .single();
      if (data) {
        setNotes([data, ...notes]);
        setNewNote("");
      }
    } catch (error) {
      console.error("Error adding note:", error);
    }
  }, [user, card, newNote, notes]);

  // Poll for research task status
  const pollTaskStatus = useCallback(
    async (taskId: string) => {
      const token = await getAuthToken();
      if (!token) return;

      const poll = async () => {
        try {
          const response = await fetch(
            `${API_BASE_URL}/api/v1/research/${taskId}`,
            { headers: { Authorization: `Bearer ${token}` } },
          );
          if (!response.ok) throw new Error("Failed to get task status");
          const task: ResearchTask = await response.json();
          setResearchTask(task);

          if (task.status === "completed") {
            setIsResearching(false);
            loadCardDetail();
          } else if (task.status === "failed") {
            setIsResearching(false);
            setResearchError(task.error_message || "Research failed");
          } else {
            setTimeout(poll, 2000);
          }
        } catch {
          setIsResearching(false);
          setResearchError("Failed to check research status");
        }
      };
      poll();
    },
    [getAuthToken, loadCardDetail],
  );

  // Trigger research
  const triggerResearch = useCallback(
    async (taskType: "update" | "deep_research") => {
      if (!card || isResearching) return;
      setIsResearching(true);
      setResearchError(null);
      setResearchTask(null);

      try {
        const token = await getAuthToken();
        if (!token) throw new Error("Not authenticated");

        const response = await fetch(`${API_BASE_URL}/api/v1/research`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ card_id: card.id, task_type: taskType }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Failed to start research");
        }

        const task = await response.json();
        setResearchTask(task);
        pollTaskStatus(task.id);
      } catch (error: unknown) {
        setResearchError(
          error instanceof Error ? error.message : "Failed to start research",
        );
        setIsResearching(false);
      }
    },
    [card, isResearching, getAuthToken, pollTaskStatus],
  );

  // Handle deep research request from DeepResearchPanel
  const handleDeepResearch = useCallback(() => {
    triggerResearch("deep_research");
  }, [triggerResearch]);

  // Handle related card click
  const handleRelatedCardClick = useCallback(
    (cardId: string, cardSlug: string) => {
      if (cardSlug) navigate(`/signals/${cardSlug}`);
    },
    [navigate],
  );

  // Effects
  useEffect(() => {
    if (slug) loadCardDetail();
  }, [slug, loadCardDetail]);
  useEffect(() => {
    if (card?.id && user) checkIfFollowing();
  }, [card?.id, user, checkIfFollowing]);
  useEffect(() => {
    if (card?.id) {
      loadScoreHistory();
      loadStageHistory();
      loadRelatedCards();
      loadAssets();
    }
  }, [
    card?.id,
    loadScoreHistory,
    loadStageHistory,
    loadRelatedCards,
    loadAssets,
  ]);

  // Computed values
  const canDeepResearch = card && (card.deep_research_count_today ?? 0) < 2;

  // Tab definitions
  const tabs = [
    { id: "overview" as const, name: "Overview", icon: Eye },
    { id: "sources" as const, name: "Sources", icon: FileText },
    { id: "timeline" as const, name: "Timeline", icon: Calendar },
    { id: "notes" as const, name: "Notes", icon: TrendingUp },
    { id: "related" as const, name: "Related", icon: GitBranch },
    { id: "chat" as const, name: "Chat", icon: MessageSquare },
    { id: "assets" as const, name: "Assets", icon: FolderOpen },
  ];

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-brand-blue" />
      </div>
    );
  }

  // Not found state
  if (!card) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Card not found
          </h1>
          <Link
            to={backLink}
            className="text-brand-blue hover:text-brand-dark-blue mt-4 inline-block transition-colors"
          >
            {backLinkText}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn("max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8", className)}
    >
      {/* Header with action buttons */}
      <CardDetailHeader
        card={card}
        backLink={backLink}
        backLinkText={backLinkText}
      >
        <CardActionButtons
          card={card}
          isFollowing={isFollowing}
          isResearching={isResearching}
          researchTask={researchTask}
          canDeepResearch={canDeepResearch ?? false}
          onTriggerResearch={triggerResearch}
          onToggleFollow={toggleFollow}
          getAuthToken={getAuthToken}
        />
      </CardDetailHeader>

      {/* Research Status Banner */}
      {(isResearching ||
        researchError ||
        researchTask?.status === "completed") && (
        <ResearchStatusBanner
          isResearching={isResearching}
          researchError={researchError}
          researchTask={researchTask}
          showReport={showReport}
          reportCopied={reportCopied}
          onToggleReport={() => setShowReport(!showReport)}
          onCopyReport={() => {
            navigator.clipboard.writeText(
              researchTask?.result_summary?.report_preview || "",
            );
            setReportCopied(true);
            setTimeout(() => setReportCopied(false), 2000);
          }}
          onDismissError={() => setResearchError(null)}
          onDismissTask={() => setResearchTask(null)}
        />
      )}

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6 sm:mb-8 -mx-4 px-4 sm:mx-0 sm:px-0">
        <nav
          className="-mb-px flex space-x-4 sm:space-x-8 overflow-x-auto scrollbar-hide"
          role="tablist"
        >
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                role="tab"
                aria-selected={activeTab === tab.id}
                className={cn(
                  "py-2 px-1 border-b-2 font-medium text-sm flex items-center whitespace-nowrap transition-colors flex-shrink-0",
                  activeTab === tab.id
                    ? "border-brand-blue text-brand-blue"
                    : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300",
                )}
              >
                <Icon className="h-4 w-4 mr-2" />
                {tab.name}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6 lg:gap-8">
          <div className="lg:col-span-2 space-y-4 sm:space-y-6">
            <CardDescription description={card.description} />
            <CardClassification
              card={card}
              stageHistory={stageHistory}
              stageHistoryLoading={stageHistoryLoading}
            />
            {/* Deep Research Panel - Prominent placement */}
            <DeepResearchPanel
              researchTasks={researchHistory}
              onRequestResearch={handleDeepResearch}
              canRequestResearch={canDeepResearch}
            />
            {/* Only show update history if there are non-deep-research tasks */}
            {researchHistory.some((t) => t.task_type !== "deep_research") && (
              <ResearchHistoryPanel
                researchHistory={researchHistory.filter(
                  (t) => t.task_type !== "deep_research",
                )}
                title="Update History"
              />
            )}
          </div>
          <div className="space-y-4 sm:space-y-6">
            <ImpactMetricsPanel
              impactScore={card.impact_score}
              relevanceScore={card.relevance_score}
              velocityScore={card.velocity_score}
              noveltyScore={card.novelty_score}
              opportunityScore={card.opportunity_score}
              riskScore={card.risk_score}
            />
            <MaturityScorePanel
              maturityScore={card.maturity_score}
              stageId={card.stage_id}
            />
            <ActivityStatsPanel
              sourcesCount={sources.length}
              timelineCount={timeline.length}
              notesCount={notes.length}
              scoreHistory={scoreHistory}
              scoreHistoryLoading={scoreHistoryLoading}
              createdAt={card.created_at}
              updatedAt={card.updated_at}
              deepResearchAt={card.deep_research_at}
            />
            {/* Score History - Compact sidebar widget */}
            <ScoreTimelineChart
              data={scoreHistory}
              title="Score History"
              height={180}
              loading={scoreHistoryLoading}
              error={scoreHistoryError}
              onRetry={loadScoreHistory}
              compact
            />
          </div>
        </div>
      )}

      {activeTab === "sources" && <SourcesTab sources={sources} />}
      {activeTab === "timeline" && <TimelineTab timeline={timeline} />}
      {activeTab === "notes" && (
        <NotesTab
          notes={notes}
          newNoteValue={newNote}
          onNewNoteChange={setNewNote}
          onAddNote={addNote}
        />
      )}
      {activeTab === "related" && (
        <ConceptNetworkDiagram
          sourceCardId={card.id}
          sourceCardName={card.name}
          sourceCardSummary={card.summary}
          sourceCardHorizon={card.horizon}
          relatedCards={relatedCards}
          height={600}
          loading={relatedCardsLoading}
          error={relatedCardsError}
          onRetry={loadRelatedCards}
          onCardClick={handleRelatedCardClick}
          showMinimap
          showBackground
          title="Related Trends Network"
        />
      )}
      {activeTab === "chat" && (
        <Suspense
          fallback={
            <div className="flex items-center justify-center p-8 text-gray-500">
              Loading chat...
            </div>
          }
        >
          <ChatTabContent
            cardId={card.id}
            cardName={card.name}
            primaryPillar={card.pillar_id}
          />
        </Suspense>
      )}
      {activeTab === "assets" && (
        <AssetsTab
          cardId={card.id}
          assets={assets}
          isLoading={assetsLoading}
          error={assetsError}
          onRefresh={loadAssets}
        />
      )}
    </div>
  );
};

export default CardDetail;
