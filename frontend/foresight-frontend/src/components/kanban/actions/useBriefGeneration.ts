/**
 * useBriefGeneration Hook
 *
 * Manages executive brief generation for workstream cards.
 * Handles the async generation workflow with polling for completion status.
 *
 * The brief generation flow:
 * 1. User triggers generateBrief() for a card
 * 2. POST request initiates generation (returns immediately with pending status)
 * 3. Hook polls status endpoint at configured interval
 * 4. On completion, fetches full brief and calls onSuccess callback
 * 5. On failure, stops polling and calls onError callback
 *
 * Features:
 * - Automatic polling with configurable interval
 * - Cleanup on unmount to prevent memory leaks
 * - Per-card loading state tracking
 * - Error handling with clear messages
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  generateBrief as generateBriefApi,
  getBrief as getBriefApi,
  getBriefStatus as getBriefStatusApi,
  getBriefVersions as getBriefVersionsApi,
} from '@/lib/workstream-api';
import type { ExecutiveBrief, BriefStatus, BriefVersionListItem } from '@/lib/workstream-api';
import { logger } from '@/lib/logger';

// ============================================================================
// Types
// ============================================================================

interface UseBriefGenerationOptions {
  /** Callback when brief generation completes successfully */
  onSuccess?: (cardId: string, brief: ExecutiveBrief) => void;
  /** Callback when brief generation fails */
  onError?: (cardId: string, error: Error) => void;
  /** Callback when brief generation starts */
  onGenerating?: (cardId: string) => void;
  /** Polling interval in milliseconds (default: 2000) */
  pollInterval?: number;
  /** Maximum polling attempts before timeout (default: 60 = 2 minutes at 2s interval) */
  maxPollAttempts?: number;
}

interface UseBriefGenerationReturn {
  /** Triggers brief generation for a card */
  triggerBriefGeneration: (cardId: string) => Promise<void>;
  /** Whether a specific card is currently generating */
  isCardGenerating: (cardId: string) => boolean;
  /** Get the current brief for a card (if loaded) */
  getCardBrief: (cardId: string) => ExecutiveBrief | null;
  /** Get the error for a card (if any) */
  getCardError: (cardId: string) => Error | null;
  /** Clear error for a card */
  clearError: (cardId: string) => void;
  /** Map of all generating states */
  isGenerating: Record<string, boolean>;
  /** Map of all loaded briefs */
  briefs: Record<string, ExecutiveBrief>;
  /** Map of all errors */
  errors: Record<string, Error | null>;
  /** Load version history for a card */
  loadVersionHistory: (cardId: string) => Promise<void>;
  /** Get version history for a card */
  getCardVersions: (cardId: string) => BriefVersionListItem[];
  /** Load a specific version of a brief */
  loadBriefVersion: (cardId: string, briefId: string) => Promise<void>;
  /** Whether versions are loading for a card */
  isLoadingVersions: (cardId: string) => boolean;
  /** Map of version lists per card */
  versions: Record<string, BriefVersionListItem[]>;
  /** Map of version loading states */
  versionsLoading: Record<string, boolean>;
}

// ============================================================================
// Constants
// ============================================================================

/** Default polling interval in milliseconds */
const DEFAULT_POLL_INTERVAL = 2000;

/** Default maximum polling attempts (2 minutes at 2s interval) */
const DEFAULT_MAX_POLL_ATTEMPTS = 60;

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for managing executive brief generation with polling.
 *
 * @param getToken - Async function to get bearer auth token
 * @param workstreamId - The workstream ID
 * @param options - Optional configuration and callbacks
 *
 * @example
 * ```typescript
 * const {
 *   triggerBriefGeneration,
 *   isCardGenerating,
 *   getCardBrief,
 *   getCardError,
 * } = useBriefGeneration(getToken, workstreamId, {
 *   onSuccess: (cardId, brief) => {
 *     console.log(`Brief generated for ${cardId}:`, brief.summary);
 *   },
 *   onError: (cardId, error) => {
 *     console.error(`Brief generation failed for ${cardId}:`, error);
 *   },
 * });
 *
 * // Trigger generation
 * await triggerBriefGeneration(cardId);
 *
 * // Check status
 * if (isCardGenerating(cardId)) {
 *   console.log('Generating...');
 * }
 *
 * // Get result
 * const brief = getCardBrief(cardId);
 * ```
 */
export function useBriefGeneration(
  getToken: () => Promise<string | null>,
  workstreamId: string,
  options: UseBriefGenerationOptions = {}
): UseBriefGenerationReturn {
  // Destructure options to avoid stale closure issues with default {} object
  const {
    onSuccess,
    onError,
    onGenerating,
    pollInterval = DEFAULT_POLL_INTERVAL,
    maxPollAttempts = DEFAULT_MAX_POLL_ATTEMPTS,
  } = options;

  // State for tracking generation status per card
  const [isGenerating, setIsGenerating] = useState<Record<string, boolean>>({});
  const [briefs, setBriefs] = useState<Record<string, ExecutiveBrief>>({});
  const [errors, setErrors] = useState<Record<string, Error | null>>({});
  const [versions, setVersions] = useState<Record<string, BriefVersionListItem[]>>({});
  const [versionsLoading, setVersionsLoading] = useState<Record<string, boolean>>({});

  // Refs to track active polling intervals (keyed by cardId)
  // Using refs to avoid stale closures and enable cleanup
  const pollingIntervals = useRef<Record<string, ReturnType<typeof setInterval>>>({});
  const pollAttempts = useRef<Record<string, number>>({});

  // Ref to track if component is mounted (for cleanup)
  const isMounted = useRef(true);

  /**
   * Cleanup function to stop polling for a specific card.
   */
  const stopPolling = useCallback((cardId: string) => {
    if (pollingIntervals.current[cardId]) {
      clearInterval(pollingIntervals.current[cardId]);
      delete pollingIntervals.current[cardId];
    }
    delete pollAttempts.current[cardId];
  }, []);

  /**
   * Cleanup all polling on unmount.
   */
  useEffect(() => {
    isMounted.current = true;

    return () => {
      isMounted.current = false;
      // Clear all active polling intervals
      Object.values(pollingIntervals.current).forEach(clearInterval);
      pollingIntervals.current = {};
      pollAttempts.current = {};
    };
  }, []);

  /**
   * Polls the brief status until completion or failure.
   */
  const startPolling = useCallback(
    (cardId: string, token: string) => {
      // Clear any existing polling for this card
      stopPolling(cardId);
      pollAttempts.current[cardId] = 0;

      const pollStatus = async () => {
        // Increment attempt counter
        pollAttempts.current[cardId] = (pollAttempts.current[cardId] || 0) + 1;

        // Check for timeout
        if (pollAttempts.current[cardId] > maxPollAttempts) {
          stopPolling(cardId);
          if (isMounted.current) {
            const timeoutError = new Error('Brief generation timed out. Please try again.');
            setIsGenerating((prev) => ({ ...prev, [cardId]: false }));
            setErrors((prev) => ({ ...prev, [cardId]: timeoutError }));
            onError?.(cardId, timeoutError);
          }
          return;
        }

        try {
          const status: BriefStatus = await getBriefStatusApi(token, workstreamId, cardId);

          // Check if still mounted
          if (!isMounted.current) {
            stopPolling(cardId);
            return;
          }

          if (status.status === 'completed') {
            // Brief is ready - fetch the full content
            stopPolling(cardId);
            try {
              const brief = await getBriefApi(token, workstreamId, cardId);
              if (isMounted.current) {
                setBriefs((prev) => ({ ...prev, [cardId]: brief }));
                setIsGenerating((prev) => ({ ...prev, [cardId]: false }));
                onSuccess?.(cardId, brief);

                // Refresh version history in background
                try {
                  const versionResponse = await getBriefVersionsApi(token, workstreamId, cardId);
                  if (isMounted.current) {
                    setVersions((prev) => ({ ...prev, [cardId]: versionResponse.versions }));
                  }
                } catch {
                  // Non-critical - version history refresh failed silently
                }
              }
            } catch (fetchError) {
              if (isMounted.current) {
                const error =
                  fetchError instanceof Error ? fetchError : new Error('Failed to fetch brief');
                setErrors((prev) => ({ ...prev, [cardId]: error }));
                setIsGenerating((prev) => ({ ...prev, [cardId]: false }));
                onError?.(cardId, error);
              }
            }
          } else if (status.status === 'failed') {
            // Brief generation failed
            stopPolling(cardId);
            if (isMounted.current) {
              const error = new Error(status.error_message || 'Brief generation failed');
              setErrors((prev) => ({ ...prev, [cardId]: error }));
              setIsGenerating((prev) => ({ ...prev, [cardId]: false }));
              onError?.(cardId, error);
            }
          }
          // If status is 'pending' or 'generating', continue polling
        } catch (pollError) {
          // Network error during polling - continue trying unless max attempts reached
          logger.warn(`Brief status poll failed for ${cardId}:`, pollError);
          // Don't stop polling on network errors - the server might be temporarily unavailable
        }
      };

      // Start polling interval
      pollingIntervals.current[cardId] = setInterval(pollStatus, pollInterval);

      // Also poll immediately
      pollStatus();
    },
    [workstreamId, pollInterval, maxPollAttempts, stopPolling, onSuccess, onError]
  );

  /**
   * Triggers brief generation for a card.
   */
  const triggerBriefGeneration = useCallback(
    async (cardId: string): Promise<void> => {
      // Clear any previous error
      setErrors((prev) => ({ ...prev, [cardId]: null }));
      setIsGenerating((prev) => ({ ...prev, [cardId]: true }));
      onGenerating?.(cardId);

      try {
        const token = await getToken();
        if (!token) {
          throw new Error('Authentication required');
        }

        // Initiate brief generation
        await generateBriefApi(token, workstreamId, cardId);

        // Start polling for completion
        startPolling(cardId, token);
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to start brief generation');
        setErrors((prev) => ({ ...prev, [cardId]: error }));
        setIsGenerating((prev) => ({ ...prev, [cardId]: false }));
        onError?.(cardId, error);
      }
    },
    [getToken, workstreamId, startPolling, onGenerating, onError]
  );

  /**
   * Checks if a specific card is currently generating a brief.
   */
  const isCardGenerating = useCallback(
    (cardId: string): boolean => isGenerating[cardId] ?? false,
    [isGenerating]
  );

  /**
   * Gets the loaded brief for a card.
   */
  const getCardBrief = useCallback(
    (cardId: string): ExecutiveBrief | null => briefs[cardId] ?? null,
    [briefs]
  );

  /**
   * Gets the error for a card.
   */
  const getCardError = useCallback(
    (cardId: string): Error | null => errors[cardId] ?? null,
    [errors]
  );

  /**
   * Clears the error for a card.
   */
  const clearError = useCallback((cardId: string) => {
    setErrors((prev) => ({ ...prev, [cardId]: null }));
  }, []);

  /**
   * Loads version history for a card.
   */
  const loadVersionHistory = useCallback(
    async (cardId: string): Promise<void> => {
      setVersionsLoading((prev) => ({ ...prev, [cardId]: true }));

      try {
        const token = await getToken();
        if (!token) {
          throw new Error('Authentication required');
        }

        const response = await getBriefVersionsApi(token, workstreamId, cardId);
        if (isMounted.current) {
          setVersions((prev) => ({ ...prev, [cardId]: response.versions }));
        }
      } catch (err) {
        console.error('Failed to load version history:', err);
        // Don't throw - version history is non-critical
      } finally {
        if (isMounted.current) {
          setVersionsLoading((prev) => ({ ...prev, [cardId]: false }));
        }
      }
    },
    [getToken, workstreamId]
  );

  /**
   * Gets version history for a card.
   */
  const getCardVersions = useCallback(
    (cardId: string): BriefVersionListItem[] => versions[cardId] ?? [],
    [versions]
  );

  /**
   * Loads a specific version of a brief by brief ID.
   */
  const loadBriefVersion = useCallback(
    async (cardId: string, briefId: string): Promise<void> => {
      try {
        const token = await getToken();
        if (!token) {
          throw new Error('Authentication required');
        }

        // Find the version number from the versions list
        const versionItem = versions[cardId]?.find((v) => v.id === briefId);
        if (!versionItem) {
          throw new Error('Version not found');
        }

        const brief = await getBriefApi(token, workstreamId, cardId, versionItem.version);
        if (isMounted.current) {
          setBriefs((prev) => ({ ...prev, [cardId]: brief }));
        }
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to load brief version');
        setErrors((prev) => ({ ...prev, [cardId]: error }));
        onError?.(cardId, error);
      }
    },
    [getToken, workstreamId, versions, onError]
  );

  /**
   * Checks if versions are loading for a card.
   */
  const isLoadingVersions = useCallback(
    (cardId: string): boolean => versionsLoading[cardId] ?? false,
    [versionsLoading]
  );

  return {
    triggerBriefGeneration,
    isCardGenerating,
    getCardBrief,
    getCardError,
    clearError,
    isGenerating,
    briefs,
    errors,
    loadVersionHistory,
    getCardVersions,
    loadBriefVersion,
    isLoadingVersions,
    versions,
    versionsLoading,
  };
}
