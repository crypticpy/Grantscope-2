/**
 * useCardData Hook
 *
 * Custom hook for loading and managing card-related data in the CardDetail component.
 * Handles loading card details, sources, timeline, notes, research history,
 * score/stage history, and related cards from Supabase and the Discovery API.
 *
 * @module useCardData
 *
 * @example
 * ```tsx
 * const {
 *   card,
 *   sources,
 *   timeline,
 *   notes,
 *   loading,
 *   isFollowing,
 *   scoreHistory,
 *   stageHistory,
 *   relatedCards,
 *   toggleFollow,
 *   addNote,
 *   refetch,
 * } = useCardData(slug, user);
 * ```
 */

import { useState, useEffect, useCallback } from "react";
import { supabase } from "../../../App";
import {
  getScoreHistory,
  getStageHistory,
  getRelatedCards,
  type ScoreHistory,
  type StageHistory,
  type RelatedCard,
} from "../../../lib/discovery-api";
import type { Card, Source, TimelineEvent, Note, ResearchTask } from "../types";
import type { GS2User } from "../../../App";

/**
 * Return type for the useCardData hook
 */
export interface UseCardDataReturn {
  /** The loaded card data, null if not found or still loading */
  card: Card | null;
  /** Array of sources associated with the card */
  sources: Source[];
  /** Array of timeline events for the card */
  timeline: TimelineEvent[];
  /** Array of notes attached to the card */
  notes: Note[];
  /** Array of completed research tasks for history display */
  researchHistory: ResearchTask[];
  /** Whether the card data is still loading */
  loading: boolean;
  /** Whether the current user is following this card */
  isFollowing: boolean;
  /** Score history for trend visualization */
  scoreHistory: ScoreHistory[];
  /** Whether score history is loading */
  scoreHistoryLoading: boolean;
  /** Error message for score history loading, if any */
  scoreHistoryError: string | null;
  /** Stage history for progression timeline */
  stageHistory: StageHistory[];
  /** Whether stage history is loading */
  stageHistoryLoading: boolean;
  /** Related cards for network visualization */
  relatedCards: RelatedCard[];
  /** Whether related cards are loading */
  relatedCardsLoading: boolean;
  /** Error message for related cards loading, if any */
  relatedCardsError: string | null;
  /** Toggle the follow status for the current user */
  toggleFollow: () => Promise<void>;
  /** Add a new note to the card */
  addNote: (content: string) => Promise<boolean>;
  /** Set the notes array (useful for optimistic updates) */
  setNotes: React.Dispatch<React.SetStateAction<Note[]>>;
  /** Refetch all card data */
  refetch: () => Promise<void>;
  /** Refetch score history data */
  refetchScoreHistory: () => Promise<void>;
  /** Refetch related cards data */
  refetchRelatedCards: () => Promise<void>;
  /** Get authentication token for API requests */
  getAuthToken: () => Promise<string | undefined>;
}

/**
 * Custom hook for loading and managing card data
 *
 * This hook centralizes all data fetching logic for the CardDetail component,
 * including:
 * - Card details from Supabase
 * - Sources, timeline, notes, and research history
 * - Score and stage history from Discovery API
 * - Related cards for network visualization
 * - Follow status management
 * - Note creation
 *
 * @param slug - The card slug from the URL
 * @param user - The authenticated user object, or null if not authenticated
 * @returns Object containing all card data and management functions
 */
export function useCardData(
  slug: string | undefined,
  user: GS2User | null,
): UseCardDataReturn {
  // Core card data state
  const [card, setCard] = useState<Card | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [researchHistory, setResearchHistory] = useState<ResearchTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [isFollowing, setIsFollowing] = useState(false);

  // Score and stage history state
  const [scoreHistory, setScoreHistory] = useState<ScoreHistory[]>([]);
  const [scoreHistoryLoading, setScoreHistoryLoading] = useState(false);
  const [scoreHistoryError, setScoreHistoryError] = useState<string | null>(
    null,
  );
  const [stageHistory, setStageHistory] = useState<StageHistory[]>([]);
  const [stageHistoryLoading, setStageHistoryLoading] = useState(false);

  // Related cards state
  const [relatedCards, setRelatedCards] = useState<RelatedCard[]>([]);
  const [relatedCardsLoading, setRelatedCardsLoading] = useState(false);
  const [relatedCardsError, setRelatedCardsError] = useState<string | null>(
    null,
  );

  /**
   * Get the current authentication token for API requests
   */
  const getAuthToken = useCallback(async (): Promise<string | undefined> => {
    const token = localStorage.getItem("gs2_token");
    return token ?? undefined;
  }, []);

  /**
   * Load card detail and related data from Supabase
   */
  const loadCardDetail = useCallback(async () => {
    if (!slug) return;

    try {
      const { data: cardData } = await supabase
        .from("cards")
        .select("*")
        .eq("slug", slug)
        .eq("status", "active")
        .single();

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
  }, [slug, user?.id]);

  /**
   * Load score history from Discovery API
   */
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
        error instanceof Error ? error.message : "Failed to load score history",
      );
    } finally {
      setScoreHistoryLoading(false);
    }
  }, [card?.id, getAuthToken]);

  /**
   * Load stage history from Discovery API
   */
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

  /**
   * Load related cards from Discovery API
   */
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
        error instanceof Error
          ? error.message
          : "Failed to load related opportunities",
      );
    } finally {
      setRelatedCardsLoading(false);
    }
  }, [card?.id, getAuthToken]);

  /**
   * Check if the current user is following this card
   */
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

  /**
   * Toggle follow status for the current user
   */
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
        await supabase.from("card_follows").insert({
          user_id: user.id,
          card_id: card.id,
          priority: "medium",
        });
        setIsFollowing(true);
      }
    } catch (_err) {
      // Silently fail - the UI will remain in sync with actual state on next load
    }
  }, [user, card, isFollowing]);

  /**
   * Add a new note to the card
   *
   * @param content - The note content
   * @returns true if the note was added successfully, false otherwise
   */
  const addNote = useCallback(
    async (content: string): Promise<boolean> => {
      if (!user || !card || !content.trim()) return false;

      try {
        const { data } = await supabase
          .from("card_notes")
          .insert({
            user_id: user.id,
            card_id: card.id,
            content,
            is_private: false,
          })
          .select()
          .single();

        if (data) {
          setNotes((prev) => [data, ...prev]);
          return true;
        }
        return false;
      } catch (_err) {
        return false;
      }
    },
    [user, card],
  );

  /**
   * Refetch all card data
   */
  const refetch = useCallback(async () => {
    setLoading(true);
    await loadCardDetail();
  }, [loadCardDetail]);

  // Load card data when slug changes
  useEffect(() => {
    if (slug) {
      loadCardDetail();
    }
  }, [slug, loadCardDetail]);

  // Check following status when card or user changes
  useEffect(() => {
    if (card?.id && user) {
      checkIfFollowing();
    }
  }, [card?.id, user, checkIfFollowing]);

  // Load history and related data when card is loaded
  useEffect(() => {
    if (card?.id) {
      loadScoreHistory();
      loadStageHistory();
      loadRelatedCards();
    }
  }, [card?.id, loadScoreHistory, loadStageHistory, loadRelatedCards]);

  return {
    card,
    sources,
    timeline,
    notes,
    researchHistory,
    loading,
    isFollowing,
    scoreHistory,
    scoreHistoryLoading,
    scoreHistoryError,
    stageHistory,
    stageHistoryLoading,
    relatedCards,
    relatedCardsLoading,
    relatedCardsError,
    toggleFollow,
    addNote,
    setNotes,
    refetch,
    refetchScoreHistory: loadScoreHistory,
    refetchRelatedCards: loadRelatedCards,
    getAuthToken,
  };
}

export default useCardData;
