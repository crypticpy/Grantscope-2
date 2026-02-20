/**
 * useCardData Hook
 *
 * Custom hook for loading and managing card-related data in the CardDetail component.
 * Handles loading card details, sources, timeline, notes, research history,
 * score/stage history, and related cards from the backend API.
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
import { API_BASE_URL } from "../../../lib/config";
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
 * - Card details from the backend API
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
   * Load card detail and related data from backend API
   */
  const loadCardDetail = useCallback(async () => {
    if (!slug) return;

    try {
      const token = await getAuthToken();
      if (!token) return;

      const params = new URLSearchParams({ slug, status: "active" });
      const cardResponse = await fetch(
        `${API_BASE_URL}/api/v1/cards?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!cardResponse.ok) return;
      const cardResult = await cardResponse.json();
      const cardData = Array.isArray(cardResult)
        ? cardResult[0]
        : cardResult.cards?.[0] || cardResult;
      if (!cardData?.id) return;

      setCard(cardData);

      // Load related data in parallel
      const [sourcesRes, timelineRes, notesRes, researchRes] =
        await Promise.all([
          fetch(`${API_BASE_URL}/api/v1/cards/${cardData.id}/sources`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch(`${API_BASE_URL}/api/v1/cards/${cardData.id}/timeline`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch(`${API_BASE_URL}/api/v1/cards/${cardData.id}/notes`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch(`${API_BASE_URL}/api/v1/me/research-tasks?limit=50`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);

      const sourcesData = sourcesRes.ok ? await sourcesRes.json() : [];
      const timelineData = timelineRes.ok ? await timelineRes.json() : [];
      const notesData = notesRes.ok ? await notesRes.json() : [];
      const allResearchTasks = researchRes.ok ? await researchRes.json() : [];
      const researchData = Array.isArray(allResearchTasks)
        ? allResearchTasks.filter(
            (t: { card_id?: string; status?: string }) =>
              t.card_id === cardData.id && t.status === "completed",
          )
        : [];

      setSources(
        Array.isArray(sourcesData) ? sourcesData : sourcesData.sources || [],
      );
      setTimeline(
        Array.isArray(timelineData)
          ? timelineData
          : timelineData.timeline || [],
      );
      setNotes(Array.isArray(notesData) ? notesData : notesData.notes || []);
      setResearchHistory(researchData);
    } finally {
      setLoading(false);
    }
  }, [slug, user?.id, getAuthToken]);

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
      const token = await getAuthToken();
      if (!token) return;
      const response = await fetch(`${API_BASE_URL}/api/v1/me/following`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const followedCards = await response.json();
        const ids = Array.isArray(followedCards)
          ? followedCards.map(
              (c: { card_id?: string; id?: string }) => c.card_id || c.id,
            )
          : [];
        setIsFollowing(ids.includes(card.id));
      } else {
        setIsFollowing(false);
      }
    } catch {
      setIsFollowing(false);
    }
  }, [user, card?.id, getAuthToken]);

  /**
   * Toggle follow status for the current user
   */
  const toggleFollow = useCallback(async () => {
    if (!user || !card) return;

    try {
      const token = await getAuthToken();
      if (!token) return;
      if (isFollowing) {
        const response = await fetch(`${API_BASE_URL}/api/v1/cards/${card.id}/follow`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          throw new Error(`Unfollow failed: ${response.status}`);
        }
        setIsFollowing(false);
      } else {
        const response = await fetch(`${API_BASE_URL}/api/v1/cards/${card.id}/follow`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          throw new Error(`Follow failed: ${response.status}`);
        }
        setIsFollowing(true);
      }
    } catch (_err) {
      // Silently fail - the UI will remain in sync with actual state on next load
    }
  }, [user, card, isFollowing, getAuthToken]);

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
        const token = await getAuthToken();
        if (!token) return false;
        const response = await fetch(
          `${API_BASE_URL}/api/v1/cards/${card.id}/notes`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ content, is_private: false }),
          },
        );

        if (response.ok) {
          const data = await response.json();
          setNotes((prev) => [data, ...prev]);
          return true;
        }
        return false;
      } catch (_err) {
        return false;
      }
    },
    [user, card, getAuthToken],
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
