/**
 * Discover Page
 *
 * The main intelligence library browser. Features:
 * - Virtualized grid/list views for large card counts
 * - Semantic (AI) and text-based search
 * - Multi-dimensional filtering (pillar, stage, horizon, scores, dates)
 * - Card comparison mode
 * - Follow functionality
 * - Saved searches and search history
 *
 * @module Discover
 *
 * Directory Structure:
 * - index.tsx - Main page component (this file)
 * - types.ts - TypeScript interfaces
 * - utils.ts - Utility functions
 * - components/DiscoverCard.tsx - Card rendering component
 * - hooks/useSearchHistory.ts - Search history management
 */

import React, {
  useState,
  useEffect,
  useMemo,
  useCallback,
  useRef,
} from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import {
  Search,
  Filter,
  Grid,
  List,
  Eye,
  Clock,
  Star,
  Inbox,
  History,
  Calendar,
  Sparkles,
  Bookmark,
  ChevronDown,
  ChevronUp,
  Loader2,
  X,
  AlertTriangle,
  RefreshCw,
  ArrowLeftRight,
  ShieldCheck,
  BookOpen,
  DollarSign,
  Tag,
} from "lucide-react";
import { supabase } from "../../App";
import { useAuthContext } from "../../hooks/useAuthContext";
import { useDebouncedValue } from "../../hooks/useDebounce";
import { useScrollRestoration } from "../../hooks/useScrollRestoration";
import { SaveSearchModal } from "../../components/SaveSearchModal";
import { SearchSidebar } from "../../components/SearchSidebar";
import {
  VirtualizedGrid,
  VirtualizedGridHandle,
} from "../../components/VirtualizedGrid";
import {
  VirtualizedList,
  VirtualizedListHandle,
} from "../../components/VirtualizedList";
import {
  advancedSearch,
  type AdvancedSearchRequest,
  type SavedSearchQueryConfig,
} from "../../lib/discovery-api";
import { grantCategories } from "../../data/taxonomy";
import { cn } from "../../lib/utils";
import { InfoTooltip } from "../../components/onboarding/InfoTooltip";
import {
  getFilterMode,
  setFilterMode as persistFilterMode,
} from "../../lib/onboarding-state";
import { FILTER_EXPLANATIONS } from "../../lib/onboarding-content";
import { FeatureIntroBanner } from "../../components/onboarding/FeatureIntroBanner";

// Local imports from modular structure
import type { Card, Pillar, Stage, SortOption, FilterState } from "./types";
import {
  getSortConfig,
  getScoreColorClasses,
  formatHistoryTime,
} from "./utils";
import { DiscoverCard } from "./components";
import { useSearchHistory } from "./hooks";

/**
 * Build a short description of a query config for display
 */
function getHistoryDescription(config: SavedSearchQueryConfig): string {
  const parts: string[] = [];

  if (config.query) {
    parts.push(`"${config.query}"`);
  }

  if (config.filters) {
    const { pillar_ids, stage_ids, horizon, date_range, score_thresholds } =
      config.filters;

    if (pillar_ids && pillar_ids.length > 0) {
      parts.push(`${pillar_ids.length} pillar(s)`);
    }
    if (stage_ids && stage_ids.length > 0) {
      parts.push(`${stage_ids.length} stage(s)`);
    }
    if (horizon && horizon !== "ALL") {
      parts.push(`${horizon}`);
    }
    if (date_range && (date_range.start || date_range.end)) {
      parts.push("date filter");
    }
    if (score_thresholds && Object.keys(score_thresholds).length > 0) {
      parts.push("score filters");
    }
  }

  if (parts.length === 0 && !config.use_vector_search) {
    return "All opportunities";
  }

  return (
    parts.join(" • ") ||
    (config.use_vector_search ? "Semantic search" : "All opportunities")
  );
}

/**
 * Discover Page Component
 */
const Discover: React.FC = () => {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [cards, setCards] = useState<Card[]>([]);
  const [pillars, setPillars] = useState<Pillar[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedPillar, setSelectedPillar] = useState("");
  const [selectedStage, setSelectedStage] = useState("");
  const [selectedHorizon, setSelectedHorizon] = useState("");
  const [sortOption, setSortOption] = useState<SortOption>("recently_updated");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [followedCardIds, setFollowedCardIds] = useState<Set<string>>(
    new Set(),
  );

  // Comparison mode state
  const [compareMode, setCompareMode] = useState(false);
  const [selectedForCompare, setSelectedForCompare] = useState<
    Array<{ id: string; name: string }>
  >([]);

  // Score threshold filters (minimum values, 0-100)
  const [impactMin, setImpactMin] = useState<number>(0);
  const [relevanceMin, setRelevanceMin] = useState<number>(0);
  const [noveltyMin, setNoveltyMin] = useState<number>(0);

  // Date range filters (YYYY-MM-DD format)
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");

  // Semantic search toggle
  const [useSemanticSearch, setUseSemanticSearch] = useState<boolean>(false);

  // Quality tier filter: 'all' | 'high' | 'moderate' | 'low'
  const [qualityFilter, setQualityFilter] = useState<string>("all");

  // Grant-specific filters
  const [selectedGrantType, setSelectedGrantType] = useState<string>("");
  const [deadlineAfter, setDeadlineAfter] = useState<string>("");
  const [deadlineBefore, setDeadlineBefore] = useState<string>("");
  const [fundingMin, setFundingMin] = useState<number | undefined>(undefined);
  const [fundingMax, setFundingMax] = useState<number | undefined>(undefined);
  const [selectedGrantCategory, setSelectedGrantCategory] =
    useState<string>("");

  // Filter mode toggle (Essential vs Advanced)
  const [filterMode, setFilterModeState] = useState<"essential" | "advanced">(
    () => getFilterMode(),
  );
  // First-use intro banner is handled by FeatureIntroBanner component

  // Debounce filter values that change rapidly
  const filterState = useMemo<FilterState>(
    () => ({
      searchTerm,
      impactMin,
      relevanceMin,
      noveltyMin,
      grantType: selectedGrantType || undefined,
      deadlineAfter: deadlineAfter || undefined,
      deadlineBefore: deadlineBefore || undefined,
      fundingMin: fundingMin,
      fundingMax: fundingMax,
      grantCategory: selectedGrantCategory || undefined,
    }),
    [
      searchTerm,
      impactMin,
      relevanceMin,
      noveltyMin,
      selectedGrantType,
      deadlineAfter,
      deadlineBefore,
      fundingMin,
      fundingMax,
      selectedGrantCategory,
    ],
  );

  const { debouncedValue: debouncedFilters, isPending: isFilterPending } =
    useDebouncedValue(filterState, 300);

  // Save search modal state
  const [showSaveSearchModal, setShowSaveSearchModal] = useState(false);

  // Saved searches sidebar state
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [sidebarRefreshKey, setSidebarRefreshKey] = useState(0);

  // Search history hook
  const {
    searchHistory,
    historyLoading,
    isHistoryExpanded,
    toggleHistoryExpanded,
    deletingHistoryId,
    recordSearch,
    deleteHistoryEntry,
    clearHistory,
  } = useSearchHistory(user?.id);

  // Quick filter from URL params
  const quickFilter = searchParams.get("filter") || "";

  // Virtualized refs
  const virtualizedListRef = useRef<VirtualizedListHandle>(null);
  const virtualizedGridRef = useRef<VirtualizedGridHandle>(null);

  // Reset scroll when sort changes
  const hasMountedForSortReset = useRef(false);
  useEffect(() => {
    if (!hasMountedForSortReset.current) {
      hasMountedForSortReset.current = true;
      return;
    }

    if (viewMode === "list") {
      virtualizedListRef.current?.setScrollOffset(0);
    } else {
      virtualizedGridRef.current?.setScrollOffset(0);
    }
  }, [sortOption, viewMode]);

  // Stable scroll position callbacks for useScrollRestoration
  // Using useCallback to prevent infinite re-renders from unstable function references
  const getListScrollPosition = useCallback(
    () => virtualizedListRef.current?.getScrollOffset() ?? 0,
    [],
  );
  const setListScrollPosition = useCallback(
    (position: number) => virtualizedListRef.current?.setScrollOffset(position),
    [],
  );
  const getGridScrollPosition = useCallback(
    () => virtualizedGridRef.current?.getScrollOffset() ?? 0,
    [],
  );
  const setGridScrollPosition = useCallback(
    (position: number) => virtualizedGridRef.current?.setScrollOffset(position),
    [],
  );

  // Scroll restoration
  useScrollRestoration({
    storageKey: "discover-list",
    enabled: viewMode === "list",
    clearAfterRestore: true,
    saveOnBeforeUnload: false,
    getScrollPosition: getListScrollPosition,
    setScrollPosition: setListScrollPosition,
  });

  useScrollRestoration({
    storageKey: "discover-grid",
    enabled: viewMode === "grid",
    clearAfterRestore: true,
    saveOnBeforeUnload: false,
    getScrollPosition: getGridScrollPosition,
    setScrollPosition: setGridScrollPosition,
  });

  // Build current search query config for saving
  const currentQueryConfig = useMemo<SavedSearchQueryConfig>(() => {
    const config: SavedSearchQueryConfig = {
      use_vector_search: useSemanticSearch,
    };

    if (searchTerm.trim()) {
      config.query = searchTerm.trim();
    }

    const filters: SavedSearchQueryConfig["filters"] = {};

    if (selectedPillar) filters.pillar_ids = [selectedPillar];
    if (selectedStage) filters.stage_ids = [selectedStage];
    if (selectedHorizon)
      filters.horizon = selectedHorizon as "H1" | "H2" | "H3";
    if (dateFrom || dateTo) {
      filters.date_range = {
        ...(dateFrom && { start: dateFrom }),
        ...(dateTo && { end: dateTo }),
      };
    }
    if (impactMin > 0 || relevanceMin > 0 || noveltyMin > 0) {
      filters.score_thresholds = {
        ...(impactMin > 0 && { impact_score: { min: impactMin } }),
        ...(relevanceMin > 0 && { relevance_score: { min: relevanceMin } }),
        ...(noveltyMin > 0 && { novelty_score: { min: noveltyMin } }),
      };
    }

    if (Object.keys(filters).length > 0) {
      config.filters = filters;
    }

    return config;
  }, [
    searchTerm,
    selectedPillar,
    selectedStage,
    selectedHorizon,
    dateFrom,
    dateTo,
    impactMin,
    relevanceMin,
    noveltyMin,
    useSemanticSearch,
  ]);

  // Apply client-side quality tier filter
  const filteredCards = useMemo(() => {
    if (qualityFilter === "all") return cards;
    return cards.filter((card) => {
      const score = card.signal_quality_score;
      switch (qualityFilter) {
        case "high":
          return score != null && score >= 75;
        case "moderate":
          return score != null && score >= 50 && score < 75;
        case "low":
          return score == null || score < 50;
        default:
          return true;
      }
    });
  }, [cards, qualityFilter]);

  // Load initial data
  useEffect(() => {
    loadDiscoverData();
    loadFollowedCards();
  }, [user?.id]);

  // Load cards when filters change
  useEffect(() => {
    loadCards();
  }, [
    debouncedFilters,
    selectedPillar,
    selectedStage,
    selectedHorizon,
    quickFilter,
    followedCardIds,
    dateFrom,
    dateTo,
    useSemanticSearch,
    sortOption,
  ]);

  const loadDiscoverData = async () => {
    try {
      const { data: pillarsData } = await supabase
        .from("pillars")
        .select("*")
        .order("name");
      const { data: stagesData } = await supabase
        .from("stages")
        .select("*")
        .order("sort_order");

      setPillars(pillarsData || []);
      setStages(stagesData || []);
    } catch (error) {
      console.error("Error loading discover data:", error);
    }
  };

  const loadFollowedCards = async () => {
    if (!user?.id) return;
    try {
      const { data } = await supabase
        .from("card_follows")
        .select("card_id")
        .eq("user_id", user.id);
      if (data) {
        setFollowedCardIds(new Set(data.map((f) => f.card_id)));
      }
    } catch (error) {
      console.error("Error loading followed cards:", error);
    }
  };

  const loadCards = async () => {
    setLoading(true);
    setError(null);
    try {
      // Handle "following" filter
      if (quickFilter === "following") {
        if (followedCardIds.size === 0) {
          setCards([]);
          setLoading(false);
          return;
        }

        let query = supabase
          .from("cards")
          .select("*")
          .eq("status", "active")
          .in("id", Array.from(followedCardIds));

        if (debouncedFilters.searchTerm) {
          query = query.or(
            `name.ilike.%${debouncedFilters.searchTerm}%,summary.ilike.%${debouncedFilters.searchTerm}%`,
          );
        }
        if (selectedPillar) query = query.eq("pillar_id", selectedPillar);
        if (selectedStage) query = query.eq("stage_id", selectedStage);
        if (selectedHorizon) query = query.eq("horizon", selectedHorizon);
        if (debouncedFilters.impactMin > 0)
          query = query.gte("impact_score", debouncedFilters.impactMin);
        if (debouncedFilters.relevanceMin > 0)
          query = query.gte("relevance_score", debouncedFilters.relevanceMin);
        if (debouncedFilters.noveltyMin > 0)
          query = query.gte("novelty_score", debouncedFilters.noveltyMin);
        if (dateFrom) query = query.gte("created_at", dateFrom);
        if (dateTo) query = query.lte("created_at", dateTo);
        if (debouncedFilters.grantType)
          query = query.eq("grant_type", debouncedFilters.grantType);
        if (debouncedFilters.deadlineAfter)
          query = query.gte("deadline", debouncedFilters.deadlineAfter);
        if (debouncedFilters.deadlineBefore)
          query = query.lte("deadline", debouncedFilters.deadlineBefore);
        if (debouncedFilters.fundingMin != null)
          query = query.gte("funding_amount_min", debouncedFilters.fundingMin);
        if (debouncedFilters.fundingMax != null)
          query = query.lte("funding_amount_max", debouncedFilters.fundingMax);
        if (debouncedFilters.grantCategory)
          query = query.eq("category_id", debouncedFilters.grantCategory);

        const sortConfig = getSortConfig(sortOption);
        const { data } = await query.order(sortConfig.column, {
          ascending: sortConfig.ascending,
        });
        setCards(data || []);
        setLoading(false);
        return;
      }

      // Semantic search
      if (useSemanticSearch && debouncedFilters.searchTerm.trim()) {
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData?.session?.access_token;

        if (token) {
          const searchRequest: AdvancedSearchRequest = {
            query: debouncedFilters.searchTerm,
            use_vector_search: true,
            filters: {
              ...(selectedPillar && { pillar_ids: [selectedPillar] }),
              ...(selectedStage && { stage_ids: [selectedStage] }),
              ...(selectedHorizon && {
                horizon: selectedHorizon as "H1" | "H2" | "H3",
              }),
              ...((dateFrom || dateTo) && {
                date_range: {
                  ...(dateFrom && { start: dateFrom }),
                  ...(dateTo && { end: dateTo }),
                },
              }),
              ...((debouncedFilters.impactMin > 0 ||
                debouncedFilters.relevanceMin > 0 ||
                debouncedFilters.noveltyMin > 0) && {
                score_thresholds: {
                  ...(debouncedFilters.impactMin > 0 && {
                    impact_score: { min: debouncedFilters.impactMin },
                  }),
                  ...(debouncedFilters.relevanceMin > 0 && {
                    relevance_score: { min: debouncedFilters.relevanceMin },
                  }),
                  ...(debouncedFilters.noveltyMin > 0 && {
                    novelty_score: { min: debouncedFilters.noveltyMin },
                  }),
                },
              }),
            },
            limit: 100,
          };

          const response = await advancedSearch(token, searchRequest);

          let mappedCards: Card[] = response.results.map((result) => ({
            id: result.id,
            name: result.name,
            slug: result.slug,
            summary: result.summary || result.description || "",
            pillar_id: result.pillar_id || "",
            stage_id: result.stage_id || "",
            horizon: (result.horizon as "H1" | "H2" | "H3") || "H1",
            novelty_score: result.novelty_score || 0,
            maturity_score: result.maturity_score || 0,
            impact_score: result.impact_score || 0,
            relevance_score: result.relevance_score || 0,
            velocity_score: result.velocity_score || 0,
            risk_score: result.risk_score || 0,
            opportunity_score: result.opportunity_score || 0,
            created_at: result.created_at || "",
            updated_at: result.updated_at,
            anchor_id: result.anchor_id,
            search_relevance: result.search_relevance,
          }));

          // Apply quick filters client-side for semantic search results
          if (quickFilter === "new") {
            const oneWeekAgo = new Date();
            oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
            mappedCards = mappedCards.filter(
              (c) => c.created_at >= oneWeekAgo.toISOString(),
            );
          }
          if (quickFilter === "updated") {
            const oneWeekAgo = new Date();
            oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
            mappedCards = mappedCards.filter(
              (c) => (c.updated_at ?? c.created_at) >= oneWeekAgo.toISOString(),
            );
          }

          const sortConfig = getSortConfig(sortOption);
          mappedCards = mappedCards.sort((a, b) => {
            const aVal =
              sortConfig.column === "created_at"
                ? a.created_at
                : a.updated_at || a.created_at;
            const bVal =
              sortConfig.column === "created_at"
                ? b.created_at
                : b.updated_at || b.created_at;
            const comparison = aVal.localeCompare(bVal);
            return sortConfig.ascending ? comparison : -comparison;
          });

          setCards(mappedCards);
          recordSearch(currentQueryConfig, mappedCards.length);
          setLoading(false);
          return;
        }
      }

      // Standard Supabase query
      let query = supabase.from("cards").select("*").eq("status", "active");

      if (quickFilter === "new") {
        const oneWeekAgo = new Date();
        oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
        query = query.gte("created_at", oneWeekAgo.toISOString());
      }

      if (quickFilter === "updated") {
        const oneWeekAgo = new Date();
        oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
        query = query.gte("updated_at", oneWeekAgo.toISOString());
      }

      if (selectedPillar) query = query.eq("pillar_id", selectedPillar);
      if (selectedStage) query = query.eq("stage_id", selectedStage);
      if (selectedHorizon) query = query.eq("horizon", selectedHorizon);
      if (debouncedFilters.searchTerm) {
        query = query.or(
          `name.ilike.%${debouncedFilters.searchTerm}%,summary.ilike.%${debouncedFilters.searchTerm}%`,
        );
      }
      if (debouncedFilters.impactMin > 0)
        query = query.gte("impact_score", debouncedFilters.impactMin);
      if (debouncedFilters.relevanceMin > 0)
        query = query.gte("relevance_score", debouncedFilters.relevanceMin);
      if (debouncedFilters.noveltyMin > 0)
        query = query.gte("novelty_score", debouncedFilters.noveltyMin);
      if (dateFrom) query = query.gte("created_at", dateFrom);
      if (dateTo) query = query.lte("created_at", dateTo);
      if (debouncedFilters.grantType)
        query = query.eq("grant_type", debouncedFilters.grantType);
      if (debouncedFilters.deadlineAfter)
        query = query.gte("deadline", debouncedFilters.deadlineAfter);
      if (debouncedFilters.deadlineBefore)
        query = query.lte("deadline", debouncedFilters.deadlineBefore);
      if (debouncedFilters.fundingMin != null)
        query = query.gte("funding_amount_min", debouncedFilters.fundingMin);
      if (debouncedFilters.fundingMax != null)
        query = query.lte("funding_amount_max", debouncedFilters.fundingMax);
      if (debouncedFilters.grantCategory)
        query = query.eq("category_id", debouncedFilters.grantCategory);

      const sortConfig = getSortConfig(sortOption);
      const { data } = await query.order(sortConfig.column, {
        ascending: sortConfig.ascending,
      });

      setCards(data || []);

      if (!quickFilter) {
        recordSearch(currentQueryConfig, (data || []).length);
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An unexpected error occurred";

      if (err instanceof TypeError && err.message.includes("fetch")) {
        setError("Network error: Unable to connect to the server.");
      } else if (
        errorMessage.includes("401") ||
        errorMessage.includes("Unauthorized")
      ) {
        setError(
          "Authentication error: Please sign in to use advanced search features.",
        );
      } else if (errorMessage.includes("500")) {
        setError(
          "Server error: The search service is temporarily unavailable.",
        );
      } else if (errorMessage.includes("timeout")) {
        setError("Request timeout: Try narrowing your filters.");
      } else {
        setError(`Failed to load opportunities: ${errorMessage}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const toggleFollowCard = useCallback(
    async (cardId: string) => {
      if (!user?.id) return;

      const isFollowing = followedCardIds.has(cardId);

      // Optimistic update
      setFollowedCardIds((prev) => {
        const newSet = new Set(prev);
        if (isFollowing) {
          newSet.delete(cardId);
        } else {
          newSet.add(cardId);
        }
        return newSet;
      });

      try {
        if (isFollowing) {
          await supabase
            .from("card_follows")
            .delete()
            .eq("user_id", user.id)
            .eq("card_id", cardId);
        } else {
          await supabase
            .from("card_follows")
            .insert({ user_id: user.id, card_id: cardId, priority: "medium" });
        }
      } catch (error) {
        console.error("Error toggling card follow:", error);
        // Revert optimistic update
        setFollowedCardIds((prev) => {
          const newSet = new Set(prev);
          if (isFollowing) {
            newSet.add(cardId);
          } else {
            newSet.delete(cardId);
          }
          return newSet;
        });
      }
    },
    [user?.id, followedCardIds],
  );

  // Apply saved search configuration
  const handleSelectSavedSearch = useCallback(
    (config: SavedSearchQueryConfig) => {
      setSearchTerm(config.query ?? "");
      setUseSemanticSearch(config.use_vector_search ?? false);

      const filters = config.filters ?? {};
      setSelectedPillar(filters.pillar_ids?.[0] ?? "");
      setSelectedStage(filters.stage_ids?.[0] ?? "");
      setSelectedHorizon(
        filters.horizon && filters.horizon !== "ALL" ? filters.horizon : "",
      );
      setDateFrom(filters.date_range?.start ?? "");
      setDateTo(filters.date_range?.end ?? "");
      setImpactMin(filters.score_thresholds?.impact_score?.min ?? 0);
      setRelevanceMin(filters.score_thresholds?.relevance_score?.min ?? 0);
      setNoveltyMin(filters.score_thresholds?.novelty_score?.min ?? 0);

      setSearchParams({});
      setIsSidebarOpen(false);
    },
    [setSearchParams],
  );

  const handleSaveSearchSuccess = useCallback(() => {
    setShowSaveSearchModal(false);
    setSidebarRefreshKey((prev) => prev + 1);
  }, []);

  const handleFilterModeChange = useCallback(
    (mode: "essential" | "advanced") => {
      setFilterModeState(mode);
      persistFilterMode(mode);
    },
    [],
  );

  // Count advanced-only filters that are active (not visible in Essential mode)
  const advancedFilterCount = useMemo(() => {
    let count = 0;
    if (selectedPillar) count++;
    if (selectedStage) count++;
    if (selectedHorizon) count++;
    if (impactMin > 0) count++;
    if (relevanceMin > 0) count++;
    if (noveltyMin > 0) count++;
    if (dateFrom || dateTo) count++;
    if (useSemanticSearch) count++;
    if (qualityFilter !== "all") count++;
    if (selectedGrantCategory) count++;
    return count;
  }, [
    selectedPillar,
    selectedStage,
    selectedHorizon,
    impactMin,
    relevanceMin,
    noveltyMin,
    dateFrom,
    dateTo,
    useSemanticSearch,
    qualityFilter,
    selectedGrantCategory,
  ]);

  // Comparison mode handlers
  useEffect(() => {
    const isCompareMode = searchParams.get("compare") === "true";
    if (isCompareMode) {
      setCompareMode(true);
      const storedCard = sessionStorage.getItem("compareCard");
      if (storedCard) {
        try {
          const cardData = JSON.parse(storedCard);
          if (cardData.id && cardData.name) {
            setSelectedForCompare([cardData]);
          }
        } catch {
          // Invalid data
        }
        sessionStorage.removeItem("compareCard");
      }
    }
  }, [searchParams]);

  const toggleCardForCompare = useCallback(
    (card: { id: string; name: string }) => {
      setSelectedForCompare((prev): { id: string; name: string }[] => {
        const isSelected = prev.some((c) => c.id === card.id);
        if (isSelected) {
          return prev.filter((c) => c.id !== card.id);
        }
        if (prev.length >= 2) {
          const second = prev[1];
          return second ? [second, card] : [card];
        }
        return [...prev, card];
      });
    },
    [],
  );

  const navigateToCompare = useCallback(() => {
    if (selectedForCompare.length === 2) {
      const ids = selectedForCompare.map((c) => c.id).join(",");
      navigate(`/compare?card_ids=${ids}`);
    }
  }, [selectedForCompare, navigate]);

  const exitCompareMode = useCallback(() => {
    setCompareMode(false);
    setSelectedForCompare([]);
    const newParams = new URLSearchParams(searchParams);
    newParams.delete("compare");
    setSearchParams(newParams);
  }, [searchParams, setSearchParams]);

  // Render card item
  const renderCardItem = useCallback(
    (card: Card, index?: number) => {
      const isSelectedForCompare = selectedForCompare.some(
        (c) => c.id === card.id,
      );

      return (
        <div
          className="animate-in fade-in slide-in-from-bottom-2 duration-300"
          style={{
            animationDelay: `${Math.min(index ?? 0, 5) * 50}ms`,
            animationFillMode: "both",
          }}
        >
          <DiscoverCard
            card={card}
            compareMode={compareMode}
            isSelectedForCompare={isSelectedForCompare}
            isFollowed={followedCardIds.has(card.id)}
            searchTerm={searchTerm}
            onToggleCompare={toggleCardForCompare}
            onToggleFollow={toggleFollowCard}
          />
        </div>
      );
    },
    [
      compareMode,
      selectedForCompare,
      followedCardIds,
      searchTerm,
      toggleCardForCompare,
      toggleFollowCard,
    ],
  );

  return (
    <>
      {/* Saved Searches Sidebar */}
      <SearchSidebar
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        onSelectSearch={handleSelectSavedSearch}
        refreshKey={sidebarRefreshKey}
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">
                Discover Grant Opportunities
              </h1>
              <p className="mt-2 text-gray-600 dark:text-gray-400">
                Explore grant opportunities relevant to Austin&apos;s strategic
                priorities.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Link
                to="/guide/discover"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <BookOpen className="w-4 h-4" />
                How to use
              </Link>
              <button
                onClick={() =>
                  compareMode ? exitCompareMode() : setCompareMode(true)
                }
                className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                  compareMode
                    ? "text-white bg-extended-purple border border-extended-purple"
                    : "text-extended-purple bg-extended-purple/10 border border-extended-purple/30 hover:bg-extended-purple hover:text-white"
                }`}
                aria-pressed={compareMode}
              >
                <ArrowLeftRight className="w-4 h-4" />
                {compareMode ? "Exit Compare" : "Compare"}
              </button>
              <button
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                  isSidebarOpen
                    ? "text-brand-blue bg-brand-light-blue dark:bg-brand-blue/20 border border-brand-blue/30"
                    : "text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
                }`}
                aria-pressed={isSidebarOpen}
              >
                <Bookmark className="w-4 h-4" />
                Saved Searches
              </button>
              <Link
                to="/discover/queue"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <Inbox className="w-4 h-4" />
                Review Queue
              </Link>
              <Link
                to="/discover/history"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <History className="w-4 h-4" />
                Run History
              </Link>
            </div>
          </div>
        </div>

        {/* Quick Filter Chips */}
        <div className="flex items-center gap-3 mb-6">
          <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
            Quick filters:
          </span>
          <button
            onClick={() => setSearchParams({})}
            className={`inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              !quickFilter
                ? "bg-brand-blue text-white"
                : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
            }`}
          >
            <Eye className="h-4 w-4 mr-1.5" />
            All Opportunities
          </button>
          <button
            onClick={() => setSearchParams({ filter: "new" })}
            className={`inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              quickFilter === "new"
                ? "bg-brand-green text-white"
                : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
            }`}
          >
            <Clock className="h-4 w-4 mr-1.5" />
            New This Week
          </button>
          <button
            onClick={() => setSearchParams({ filter: "updated" })}
            className={`inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              quickFilter === "updated"
                ? "bg-amber-500 text-white"
                : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
            }`}
          >
            <RefreshCw className="h-4 w-4 mr-1.5" />
            Updated This Week
          </button>
          <Link
            to="/signals"
            className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium transition-colors bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-extended-purple/10 hover:text-extended-purple dark:hover:text-extended-purple"
          >
            <Star className="h-4 w-4 mr-1.5" />
            My Opportunities &rarr;
          </Link>

          {/* Quality Tier Filter */}
          <div className="ml-auto flex items-center gap-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-0.5">
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 px-2">
              <ShieldCheck className="h-3.5 w-3.5 inline mr-1" />
              Quality:
            </span>
            {[
              { value: "all", label: "All" },
              { value: "high", label: "High" },
              { value: "moderate", label: "Moderate" },
              { value: "low", label: "Needs Verification" },
            ].map((tier) => (
              <button
                key={tier.value}
                onClick={() => setQualityFilter(tier.value)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  qualityFilter === tier.value
                    ? tier.value === "high"
                      ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                      : tier.value === "moderate"
                        ? "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
                        : tier.value === "low"
                          ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                          : "bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm"
                    : "text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
                }`}
              >
                {tier.label}
              </button>
            ))}
          </div>
        </div>

        {/* First-use intro banner */}
        <FeatureIntroBanner feature="discover" className="mb-6" />

        {/* Filters */}
        <div className="bg-white dark:bg-dark-surface rounded-lg shadow p-6 mb-6">
          {/* Filter mode toggle + header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Filter className="h-4 w-4 text-gray-400" />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Filters
              </span>
              {filterMode === "essential" && advancedFilterCount > 0 && (
                <button
                  onClick={() => handleFilterModeChange("advanced")}
                  className="text-xs text-brand-blue hover:underline"
                >
                  {advancedFilterCount} advanced filter
                  {advancedFilterCount !== 1 ? "s" : ""} active
                </button>
              )}
            </div>
            <div className="inline-flex items-center rounded-lg border border-gray-200 dark:border-gray-700 p-0.5 bg-gray-50 dark:bg-dark-surface">
              <button
                onClick={() => handleFilterModeChange("essential")}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                  filterMode === "essential"
                    ? "bg-brand-blue text-white shadow-sm"
                    : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200",
                )}
              >
                Essential
              </button>
              <button
                onClick={() => handleFilterModeChange("advanced")}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                  filterMode === "advanced"
                    ? "bg-brand-blue text-white shadow-sm"
                    : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200",
                )}
              >
                All Filters
              </button>
            </div>
          </div>

          {/* Essential Mode Filters */}
          {filterMode === "essential" && (
            <div className="space-y-4">
              {/* Search bar */}
              <div>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                  <input
                    type="text"
                    className="pl-10 block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    placeholder="Search opportunities..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
              </div>

              {/* Grant Type chips */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 w-20 shrink-0">
                  Grant Type
                </span>
                {["All", "Federal", "State", "Foundation", "Local"].map(
                  (type) => {
                    const filterValue = type === "All" ? "" : type;
                    const isActive = selectedGrantType === filterValue;
                    return (
                      <button
                        key={type}
                        onClick={() => setSelectedGrantType(filterValue)}
                        className={cn(
                          "px-3 py-1.5 text-xs font-medium rounded-full border transition-colors",
                          isActive
                            ? "bg-brand-blue text-white border-brand-blue"
                            : "bg-white dark:bg-dark-surface border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:border-brand-blue hover:text-brand-blue",
                        )}
                      >
                        {type}
                      </button>
                    );
                  },
                )}
              </div>

              {/* Deadline preset chips */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 w-20 shrink-0">
                  Deadline
                </span>
                {[
                  { label: "All", days: 0 },
                  { label: "Next 30 days", days: 30 },
                  { label: "Next 90 days", days: 90 },
                  { label: "Next 6 months", days: 180 },
                ].map((preset) => {
                  let isActive: boolean;
                  if (preset.days === 0) {
                    isActive = !deadlineAfter && !deadlineBefore;
                  } else {
                    const today = new Date();
                    const future = new Date();
                    future.setDate(today.getDate() + preset.days);
                    const afterVal = today.toISOString().split("T")[0] ?? "";
                    const beforeVal = future.toISOString().split("T")[0] ?? "";
                    isActive =
                      deadlineAfter === afterVal &&
                      deadlineBefore === beforeVal;
                  }
                  return (
                    <button
                      key={preset.label}
                      onClick={() => {
                        if (preset.days === 0) {
                          setDeadlineAfter("");
                          setDeadlineBefore("");
                        } else {
                          const today = new Date();
                          const future = new Date();
                          future.setDate(today.getDate() + preset.days);
                          const afterVal =
                            today.toISOString().split("T")[0] ?? "";
                          const beforeVal =
                            future.toISOString().split("T")[0] ?? "";
                          if (isActive) {
                            setDeadlineAfter("");
                            setDeadlineBefore("");
                          } else {
                            setDeadlineAfter(afterVal);
                            setDeadlineBefore(beforeVal);
                          }
                        }
                      }}
                      className={cn(
                        "px-3 py-1.5 text-xs font-medium rounded-full border transition-colors",
                        isActive
                          ? "bg-brand-blue text-white border-brand-blue"
                          : "bg-white dark:bg-dark-surface border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:border-brand-blue hover:text-brand-blue",
                      )}
                    >
                      {preset.label}
                    </button>
                  );
                })}
              </div>

              {/* Funding preset chips */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 w-20 shrink-0">
                  Funding
                </span>
                {[
                  {
                    label: "All",
                    min: undefined as number | undefined,
                    max: undefined as number | undefined,
                  },
                  { label: "Under $50K", min: 0, max: 50000 },
                  { label: "$50K - $500K", min: 50000, max: 500000 },
                  {
                    label: "$500K+",
                    min: 500000,
                    max: undefined as number | undefined,
                  },
                ].map((preset) => {
                  const isActive =
                    fundingMin === preset.min && fundingMax === preset.max;
                  return (
                    <button
                      key={preset.label}
                      onClick={() => {
                        if (isActive) {
                          setFundingMin(undefined);
                          setFundingMax(undefined);
                        } else {
                          setFundingMin(preset.min);
                          setFundingMax(preset.max);
                        }
                      }}
                      className={cn(
                        "px-3 py-1.5 text-xs font-medium rounded-full border transition-colors",
                        isActive
                          ? "bg-brand-blue text-white border-brand-blue"
                          : "bg-white dark:bg-dark-surface border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:border-brand-blue hover:text-brand-blue",
                      )}
                    >
                      {preset.label}
                    </button>
                  );
                })}
              </div>

              {/* Sort dropdown */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 w-20 shrink-0">
                  Sort By
                </span>
                <select
                  className="border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue text-sm"
                  value={sortOption}
                  onChange={(e) => setSortOption(e.target.value as SortOption)}
                >
                  <option value="newest">Newest Created</option>
                  <option value="oldest">Oldest First</option>
                  <option value="recently_updated">Recently Updated</option>
                  <option value="least_recently_updated">
                    Least Recently Updated
                  </option>
                  <option value="signal_quality_score">Quality Score</option>
                  <option value="deadline_soonest">Deadline (Soonest)</option>
                  <option value="funding_highest">Funding (Highest)</option>
                </select>
                <InfoTooltip content={FILTER_EXPLANATIONS.sortBy} />
              </div>
            </div>
          )}

          {/* Advanced Mode Filters */}
          {filterMode === "advanced" && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
                {/* Search */}
                <div className="lg:col-span-2">
                  <label
                    htmlFor="search"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    Search
                  </label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                    <input
                      type="text"
                      id="search"
                      className="pl-10 block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                      placeholder={
                        useSemanticSearch
                          ? "Semantic search (finds related concepts)..."
                          : "Search opportunities..."
                      }
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                    />
                  </div>
                  {/* Semantic Search Toggle */}
                  <div className="mt-2 flex items-center gap-2">
                    <button
                      type="button"
                      role="switch"
                      aria-checked={useSemanticSearch}
                      onClick={() => setUseSemanticSearch(!useSemanticSearch)}
                      className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2 ${
                        useSemanticSearch
                          ? "bg-extended-purple"
                          : "bg-gray-200 dark:bg-gray-600"
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          useSemanticSearch ? "translate-x-4" : "translate-x-0"
                        }`}
                      />
                    </button>
                    <label
                      className={`flex items-center gap-1.5 text-sm cursor-pointer ${
                        useSemanticSearch
                          ? "text-extended-purple font-medium"
                          : "text-gray-600 dark:text-gray-400"
                      }`}
                      onClick={() => setUseSemanticSearch(!useSemanticSearch)}
                    >
                      <Sparkles
                        className={`h-4 w-4 ${useSemanticSearch ? "text-extended-purple" : "text-gray-400"}`}
                      />
                      Semantic Search
                    </label>
                    <InfoTooltip content={FILTER_EXPLANATIONS.semanticSearch} />
                    {useSemanticSearch && (
                      <span className="text-xs text-gray-500 dark:text-gray-400 ml-1">
                        (finds conceptually related opportunities)
                      </span>
                    )}
                  </div>
                </div>

                {/* Pillar Filter */}
                <div>
                  <label
                    htmlFor="pillar"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    Strategic Pillar{" "}
                    <InfoTooltip
                      content={FILTER_EXPLANATIONS.strategicPillar}
                    />
                  </label>
                  <select
                    id="pillar"
                    className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    value={selectedPillar}
                    onChange={(e) => setSelectedPillar(e.target.value)}
                  >
                    <option value="">All Pillars</option>
                    {pillars.map((pillar) => (
                      <option key={pillar.id} value={pillar.id}>
                        {pillar.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Stage Filter */}
                <div>
                  <label
                    htmlFor="stage"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    Maturity Stage{" "}
                    <InfoTooltip content={FILTER_EXPLANATIONS.maturityStage} />
                  </label>
                  <select
                    id="stage"
                    className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    value={selectedStage}
                    onChange={(e) => setSelectedStage(e.target.value)}
                  >
                    <option value="">All Stages</option>
                    {stages.map((stage) => (
                      <option key={stage.id} value={stage.id}>
                        {stage.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Horizon Filter */}
                <div>
                  <label
                    htmlFor="horizon"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    Horizon{" "}
                    <InfoTooltip content={FILTER_EXPLANATIONS.horizon} />
                  </label>
                  <select
                    id="horizon"
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

                {/* Sort */}
                <div>
                  <label
                    htmlFor="sort"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    Sort By <InfoTooltip content={FILTER_EXPLANATIONS.sortBy} />
                  </label>
                  <select
                    id="sort"
                    className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    value={sortOption}
                    onChange={(e) =>
                      setSortOption(e.target.value as SortOption)
                    }
                  >
                    <option value="newest">Newest Created</option>
                    <option value="oldest">Oldest First</option>
                    <option value="recently_updated">Recently Updated</option>
                    <option value="least_recently_updated">
                      Least Recently Updated
                    </option>
                    <option value="signal_quality_score">Quality Score</option>
                    <option value="deadline_soonest">Deadline (Soonest)</option>
                    <option value="funding_highest">Funding (Highest)</option>
                  </select>
                </div>
              </div>

              {/* Grant Filters */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                {/* Grant Type */}
                <div>
                  <label
                    htmlFor="grantType"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    <Tag className="h-3.5 w-3.5 inline mr-1" />
                    Grant Type{" "}
                    <InfoTooltip content={FILTER_EXPLANATIONS.grantType} />
                  </label>
                  <select
                    id="grantType"
                    className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    value={selectedGrantType}
                    onChange={(e) => setSelectedGrantType(e.target.value)}
                  >
                    <option value="">All Types</option>
                    <option value="Federal">Federal</option>
                    <option value="State">State</option>
                    <option value="Foundation">Foundation</option>
                    <option value="Local">Local</option>
                    <option value="Other">Other</option>
                  </select>
                </div>

                {/* Grant Category */}
                <div>
                  <label
                    htmlFor="grantCategory"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    Grant Category{" "}
                    <InfoTooltip content={FILTER_EXPLANATIONS.grantCategory} />
                  </label>
                  <select
                    id="grantCategory"
                    className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    value={selectedGrantCategory}
                    onChange={(e) => setSelectedGrantCategory(e.target.value)}
                  >
                    <option value="">All Categories</option>
                    {grantCategories.map((cat) => (
                      <option key={cat.code} value={cat.code}>
                        {cat.code} - {cat.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Deadline Range */}
                <div>
                  <label
                    htmlFor="deadlineAfter"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    Deadline After{" "}
                    <InfoTooltip content={FILTER_EXPLANATIONS.deadlineRange} />
                  </label>
                  <input
                    type="date"
                    id="deadlineAfter"
                    className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    value={deadlineAfter}
                    onChange={(e) => setDeadlineAfter(e.target.value)}
                  />
                </div>
                <div>
                  <label
                    htmlFor="deadlineBefore"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    Deadline Before
                  </label>
                  <input
                    type="date"
                    id="deadlineBefore"
                    className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    value={deadlineBefore}
                    onChange={(e) => setDeadlineBefore(e.target.value)}
                  />
                </div>
              </div>

              {/* Deadline Preset Chips */}
              <div className="flex items-center gap-2 mt-3">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                  Deadline presets:
                </span>
                {[
                  { label: "Next 30 days", days: 30 },
                  { label: "Next 90 days", days: 90 },
                  { label: "Next 6 months", days: 180 },
                ].map((preset) => {
                  const today = new Date();
                  const future = new Date();
                  future.setDate(today.getDate() + preset.days);
                  const afterVal = today.toISOString().split("T")[0] ?? "";
                  const beforeVal = future.toISOString().split("T")[0] ?? "";
                  const isActive =
                    deadlineAfter === afterVal && deadlineBefore === beforeVal;
                  return (
                    <button
                      key={preset.days}
                      onClick={() => {
                        if (isActive) {
                          setDeadlineAfter("");
                          setDeadlineBefore("");
                        } else {
                          setDeadlineAfter(afterVal);
                          setDeadlineBefore(beforeVal);
                        }
                      }}
                      className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                        isActive
                          ? "bg-brand-blue text-white"
                          : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                      }`}
                    >
                      {preset.label}
                    </button>
                  );
                })}
                {(deadlineAfter || deadlineBefore) && (
                  <button
                    onClick={() => {
                      setDeadlineAfter("");
                      setDeadlineBefore("");
                    }}
                    className="px-2 py-1 text-xs text-gray-500 hover:text-red-500 transition-colors"
                  >
                    <X className="h-3 w-3 inline" /> Clear
                  </button>
                )}
              </div>

              {/* Funding Amount Range */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                <div className="lg:col-span-1 flex items-center gap-2">
                  <DollarSign className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Funding Range:{" "}
                    <InfoTooltip content={FILTER_EXPLANATIONS.fundingRange} />
                  </span>
                </div>
                <div>
                  <label
                    htmlFor="fundingMin"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    Min Amount ($)
                  </label>
                  <input
                    type="number"
                    id="fundingMin"
                    min="0"
                    step="1000"
                    className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    placeholder="e.g. 50000"
                    value={fundingMin ?? ""}
                    onChange={(e) =>
                      setFundingMin(
                        e.target.value ? Number(e.target.value) : undefined,
                      )
                    }
                  />
                </div>
                <div>
                  <label
                    htmlFor="fundingMax"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    Max Amount ($)
                  </label>
                  <input
                    type="number"
                    id="fundingMax"
                    min="0"
                    step="1000"
                    className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    placeholder="e.g. 500000"
                    value={fundingMax ?? ""}
                    onChange={(e) =>
                      setFundingMax(
                        e.target.value ? Number(e.target.value) : undefined,
                      )
                    }
                  />
                </div>
                <div className="flex items-end">
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      { label: "$0-50K", min: 0, max: 50000 },
                      { label: "$50K-500K", min: 50000, max: 500000 },
                      { label: "$500K+", min: 500000, max: undefined },
                    ].map((preset) => {
                      const isActive =
                        fundingMin === preset.min && fundingMax === preset.max;
                      return (
                        <button
                          key={preset.label}
                          onClick={() => {
                            if (isActive) {
                              setFundingMin(undefined);
                              setFundingMax(undefined);
                            } else {
                              setFundingMin(preset.min);
                              setFundingMax(preset.max);
                            }
                          }}
                          className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                            isActive
                              ? "bg-brand-blue text-white"
                              : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                          }`}
                        >
                          {preset.label}
                        </button>
                      );
                    })}
                    {(fundingMin != null || fundingMax != null) && (
                      <button
                        onClick={() => {
                          setFundingMin(undefined);
                          setFundingMax(undefined);
                        }}
                        className="px-2 py-1 text-xs text-gray-500 hover:text-red-500 transition-colors"
                      >
                        <X className="h-3 w-3 inline" /> Clear
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Date Range Filters */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                <div className="lg:col-span-2 flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Date Range:
                  </span>
                </div>
                <div>
                  <label
                    htmlFor="dateFrom"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    Created After
                  </label>
                  <input
                    type="date"
                    id="dateFrom"
                    className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                  />
                </div>
                <div>
                  <label
                    htmlFor="dateTo"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
                  >
                    Created Before
                  </label>
                  <input
                    type="date"
                    id="dateTo"
                    className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-gray-100 rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                  />
                </div>
              </div>

              {/* Score Threshold Sliders */}
              <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                  Minimum Score Thresholds
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* Impact Score Slider */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label
                        htmlFor="impactMin"
                        className="text-sm text-gray-600 dark:text-gray-400"
                      >
                        Impact{" "}
                        <InfoTooltip
                          content={FILTER_EXPLANATIONS.impactScore}
                        />
                      </label>
                      <span
                        className={`text-sm font-medium ${impactMin > 0 ? getScoreColorClasses(impactMin) : "text-gray-500 dark:text-gray-400"}`}
                      >
                        {impactMin > 0 ? `≥ ${impactMin}` : "Any"}
                      </span>
                    </div>
                    <input
                      type="range"
                      id="impactMin"
                      min="0"
                      max="100"
                      step="5"
                      value={impactMin}
                      onChange={(e) => setImpactMin(Number(e.target.value))}
                      className="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer accent-brand-blue"
                    />
                    <div className="flex justify-between text-xs text-gray-400 mt-1">
                      <span>0</span>
                      <span>50</span>
                      <span>100</span>
                    </div>
                  </div>

                  {/* Relevance Score Slider */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label
                        htmlFor="relevanceMin"
                        className="text-sm text-gray-600 dark:text-gray-400"
                      >
                        Relevance{" "}
                        <InfoTooltip
                          content={FILTER_EXPLANATIONS.relevanceScore}
                        />
                      </label>
                      <span
                        className={`text-sm font-medium ${relevanceMin > 0 ? getScoreColorClasses(relevanceMin) : "text-gray-500 dark:text-gray-400"}`}
                      >
                        {relevanceMin > 0 ? `≥ ${relevanceMin}` : "Any"}
                      </span>
                    </div>
                    <input
                      type="range"
                      id="relevanceMin"
                      min="0"
                      max="100"
                      step="5"
                      value={relevanceMin}
                      onChange={(e) => setRelevanceMin(Number(e.target.value))}
                      className="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer accent-brand-blue"
                    />
                    <div className="flex justify-between text-xs text-gray-400 mt-1">
                      <span>0</span>
                      <span>50</span>
                      <span>100</span>
                    </div>
                  </div>

                  {/* Novelty Score Slider */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label
                        htmlFor="noveltyMin"
                        className="text-sm text-gray-600 dark:text-gray-400"
                      >
                        Novelty{" "}
                        <InfoTooltip
                          content={FILTER_EXPLANATIONS.noveltyScore}
                        />
                      </label>
                      <span
                        className={`text-sm font-medium ${noveltyMin > 0 ? getScoreColorClasses(noveltyMin) : "text-gray-500 dark:text-gray-400"}`}
                      >
                        {noveltyMin > 0 ? `≥ ${noveltyMin}` : "Any"}
                      </span>
                    </div>
                    <input
                      type="range"
                      id="noveltyMin"
                      min="0"
                      max="100"
                      step="5"
                      value={noveltyMin}
                      onChange={(e) => setNoveltyMin(Number(e.target.value))}
                      className="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-lg appearance-none cursor-pointer accent-brand-blue"
                    />
                    <div className="flex justify-between text-xs text-gray-400 mt-1">
                      <span>0</span>
                      <span>50</span>
                      <span>100</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recent Search History */}
              {user?.id && searchHistory.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                  <button
                    onClick={toggleHistoryExpanded}
                    className="w-full flex items-center justify-between text-left"
                  >
                    <div className="flex items-center gap-2">
                      <History className="h-4 w-4 text-gray-400" />
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        Recent Searches ({searchHistory.length})
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {historyLoading && (
                        <Loader2 className="h-4 w-4 text-gray-400 animate-spin" />
                      )}
                      {isHistoryExpanded ? (
                        <ChevronUp className="h-4 w-4 text-gray-400" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-gray-400" />
                      )}
                    </div>
                  </button>

                  {isHistoryExpanded && (
                    <div className="mt-3 space-y-2 max-h-64 overflow-y-auto">
                      <div className="flex justify-end mb-2">
                        <button
                          onClick={clearHistory}
                          className="text-xs text-gray-500 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                        >
                          Clear all
                        </button>
                      </div>

                      {searchHistory.map((entry) => (
                        <div
                          key={entry.id}
                          onClick={() =>
                            handleSelectSavedSearch(entry.query_config)
                          }
                          className="group flex items-start justify-between gap-2 p-2 rounded-md border border-gray-200 dark:border-gray-600 hover:border-brand-blue hover:bg-brand-light-blue/50 dark:hover:bg-brand-blue/10 cursor-pointer transition-all duration-200"
                          role="button"
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              handleSelectSavedSearch(entry.query_config);
                            }
                          }}
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              {entry.query_config.use_vector_search && (
                                <span className="inline-flex items-center gap-0.5 px-1 py-0.5 rounded text-[10px] font-medium bg-extended-purple/10 text-extended-purple">
                                  <Sparkles className="h-2.5 w-2.5" />
                                  AI
                                </span>
                              )}
                              <span className="text-sm text-gray-900 dark:text-white truncate">
                                {getHistoryDescription(entry.query_config)}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 mt-1">
                              <span className="text-xs text-gray-400">
                                {formatHistoryTime(entry.executed_at)}
                              </span>
                              <span className="text-xs text-gray-400">•</span>
                              <span className="text-xs text-gray-400">
                                {entry.result_count} result
                                {entry.result_count !== 1 ? "s" : ""}
                              </span>
                            </div>
                          </div>

                          <button
                            onClick={(e) => deleteHistoryEntry(entry.id, e)}
                            disabled={deletingHistoryId === entry.id}
                            className="p-1 text-gray-400 hover:text-red-500 rounded opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50 shrink-0"
                            title="Remove from history"
                          >
                            {deletingHistoryId === entry.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <X className="h-3.5 w-3.5" />
                            )}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* View Controls and Save Search */}
          <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Showing {filteredCards.length}
                {qualityFilter !== "all" ? ` of ${cards.length}` : ""}{" "}
                opportunities
              </p>
              {isFilterPending && (
                <span className="inline-flex items-center gap-1 text-xs text-brand-blue">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Updating...
                </span>
              )}
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setShowSaveSearchModal(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-brand-blue bg-brand-light-blue dark:bg-brand-blue/20 border border-brand-blue/30 rounded-md hover:bg-brand-blue hover:text-white dark:hover:bg-brand-blue transition-colors"
              >
                <Bookmark className="h-4 w-4" />
                Save Search
              </button>
              <div className="flex items-center space-x-2">
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
                  <Grid className="h-4 w-4" />
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
                  <List className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Compare Mode Banner */}
        {compareMode && (
          <div className="mb-6 p-4 bg-extended-purple/10 border border-extended-purple/30 rounded-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <ArrowLeftRight className="h-5 w-5 text-extended-purple" />
                <div>
                  <p className="font-medium text-gray-900 dark:text-white">
                    Compare Mode Active
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-300">
                    {selectedForCompare.length === 0
                      ? "Click on opportunities to select them for comparison (max 2)"
                      : selectedForCompare.length === 1
                        ? `Selected: ${selectedForCompare[0]?.name ?? "opportunity"} — Click another opportunity to compare`
                        : `Ready to compare: ${selectedForCompare[0]?.name ?? "opportunity"} vs ${selectedForCompare[1]?.name ?? "opportunity"}`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {selectedForCompare.length > 0 && (
                  <button
                    onClick={() => setSelectedForCompare([])}
                    className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900"
                  >
                    Clear Selection
                  </button>
                )}
                <button
                  onClick={navigateToCompare}
                  disabled={selectedForCompare.length !== 2}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-extended-purple text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-extended-purple/90 transition-colors"
                >
                  <ArrowLeftRight className="h-4 w-4" />
                  Compare Opportunities
                </button>
                <button
                  onClick={exitCompareMode}
                  className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {selectedForCompare.length > 0 && (
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                {selectedForCompare.map((card, index) => (
                  <span
                    key={card.id}
                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-dark-surface rounded-full text-sm border border-extended-purple/30"
                  >
                    <span className="font-medium text-extended-purple">
                      {index + 1}.
                    </span>
                    <span className="text-gray-700 dark:text-gray-200 truncate max-w-[200px]">
                      {card.name}
                    </span>
                    <button
                      onClick={() => toggleCardForCompare(card)}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

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
                    loadCards();
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

        {/* Cards Grid/List */}
        {loading || isFilterPending ? (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue"></div>
            {isFilterPending && !loading && (
              <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
                Updating search...
              </p>
            )}
          </div>
        ) : filteredCards.length === 0 && !error ? (
          <div className="text-center py-12 bg-white dark:bg-dark-surface rounded-lg shadow">
            {useSemanticSearch && searchTerm ? (
              <Sparkles className="mx-auto h-12 w-12 text-gray-400" />
            ) : searchTerm ||
              selectedPillar ||
              selectedStage ||
              selectedHorizon ||
              dateFrom ||
              dateTo ||
              impactMin > 0 ||
              relevanceMin > 0 ||
              noveltyMin > 0 ||
              selectedGrantType ||
              deadlineAfter ||
              deadlineBefore ||
              fundingMin != null ||
              fundingMax != null ||
              selectedGrantCategory ? (
              <Filter className="mx-auto h-12 w-12 text-gray-400" />
            ) : (
              <Inbox className="mx-auto h-12 w-12 text-gray-400" />
            )}

            <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
              {quickFilter === "new"
                ? "No New Opportunities This Week"
                : useSemanticSearch && searchTerm
                  ? "No Semantic Matches Found"
                  : searchTerm ||
                      selectedPillar ||
                      selectedStage ||
                      selectedHorizon ||
                      dateFrom ||
                      dateTo ||
                      impactMin > 0 ||
                      relevanceMin > 0 ||
                      noveltyMin > 0 ||
                      selectedGrantType ||
                      deadlineAfter ||
                      deadlineBefore ||
                      fundingMin != null ||
                      fundingMax != null ||
                      selectedGrantCategory
                    ? "No Opportunities Match Your Filters"
                    : "No Opportunities Available"}
            </h3>

            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
              {quickFilter === "new"
                ? "Check back soon for newly discovered grant opportunities."
                : useSemanticSearch && searchTerm
                  ? `No opportunities matched your semantic search for "${searchTerm}". Try different keywords, or switch to standard text search.`
                  : searchTerm
                    ? `No opportunities matched your search for "${searchTerm}". Try different keywords or enable semantic search for broader matches.`
                    : selectedPillar ||
                        selectedStage ||
                        selectedHorizon ||
                        dateFrom ||
                        dateTo ||
                        impactMin > 0 ||
                        relevanceMin > 0 ||
                        noveltyMin > 0 ||
                        selectedGrantType ||
                        deadlineAfter ||
                        deadlineBefore ||
                        fundingMin != null ||
                        fundingMax != null ||
                        selectedGrantCategory
                      ? "Your current filter combination returned no results. Try removing some filters or adjusting score thresholds."
                      : "The grant library is empty. Opportunities will appear here as they are discovered."}
            </p>

            <div className="mt-6 flex flex-wrap justify-center gap-3">
              {/* Link to My Signals page */}
              {(searchTerm ||
                selectedPillar ||
                selectedStage ||
                selectedHorizon ||
                dateFrom ||
                dateTo ||
                impactMin > 0 ||
                relevanceMin > 0 ||
                noveltyMin > 0 ||
                selectedGrantType ||
                deadlineAfter ||
                deadlineBefore ||
                fundingMin != null ||
                fundingMax != null ||
                selectedGrantCategory) &&
                !quickFilter && (
                  <button
                    onClick={() => {
                      setSearchTerm("");
                      setSelectedPillar("");
                      setSelectedStage("");
                      setSelectedHorizon("");
                      setDateFrom("");
                      setDateTo("");
                      setImpactMin(0);
                      setRelevanceMin(0);
                      setNoveltyMin(0);
                      setUseSemanticSearch(false);
                      setSelectedGrantType("");
                      setDeadlineAfter("");
                      setDeadlineBefore("");
                      setFundingMin(undefined);
                      setFundingMax(undefined);
                      setSelectedGrantCategory("");
                    }}
                    className="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                  >
                    <X className="h-4 w-4 mr-2" />
                    Clear All Filters
                  </button>
                )}
              {useSemanticSearch && searchTerm && (
                <button
                  onClick={() => setUseSemanticSearch(false)}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                  <Search className="h-4 w-4 mr-2" />
                  Try Standard Search
                </button>
              )}
            </div>
          </div>
        ) : filteredCards.length > 0 ? (
          viewMode === "list" ? (
            <VirtualizedList
              ref={virtualizedListRef}
              items={filteredCards}
              renderItem={renderCardItem}
              getItemKey={(card) => card.id}
              estimatedSize={180}
              gap={16}
              overscan={3}
              scrollContainerClassName="h-[calc(100vh-280px)]"
              ariaLabel="Grant opportunities list"
            />
          ) : (
            <div className="h-[calc(100vh-400px)] min-h-[500px]">
              <VirtualizedGrid
                ref={virtualizedGridRef}
                items={filteredCards}
                getItemKey={(card) => card.id}
                estimatedRowHeight={280}
                gap={24}
                columns={{ sm: 1, md: 2, lg: 3 }}
                overscan={3}
                renderItem={(card, index) => (
                  <div className="h-full">{renderCardItem(card, index)}</div>
                )}
              />
            </div>
          )
        ) : null}

        {/* Save Search Modal */}
        <SaveSearchModal
          isOpen={showSaveSearchModal}
          onClose={() => setShowSaveSearchModal(false)}
          onSuccess={handleSaveSearchSuccess}
          queryConfig={currentQueryConfig}
        />
      </div>
    </>
  );
};

export default Discover;
