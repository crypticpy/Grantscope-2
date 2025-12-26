/**
 * useResearch Hook
 *
 * Custom hook for managing research task operations in the CardDetail component.
 * Handles triggering research tasks (update/deep research), polling for status,
 * and managing the research UI state.
 *
 * @module useResearch
 *
 * @example
 * ```tsx
 * const {
 *   researchTask,
 *   isResearching,
 *   researchError,
 *   showReport,
 *   reportCopied,
 *   triggerResearch,
 *   toggleReport,
 *   copyReport,
 *   dismissError,
 *   dismissTask,
 * } = useResearch(card, getAuthToken, onResearchComplete);
 * ```
 */

import { useState, useCallback, useRef } from 'react';
import type { Card, ResearchTask } from '../types';
import { API_BASE_URL } from '../utils';

/**
 * Type of research task to trigger
 */
export type ResearchTaskType = 'update' | 'deep_research';

/**
 * Return type for the useResearch hook
 */
export interface UseResearchReturn {
  /** Current research task, null if none active or completed */
  researchTask: ResearchTask | null;
  /** Whether a research task is currently in progress */
  isResearching: boolean;
  /** Error message if research failed, null otherwise */
  researchError: string | null;
  /** Whether the research report is expanded/visible */
  showReport: boolean;
  /** Whether the report was recently copied to clipboard */
  reportCopied: boolean;
  /** Whether deep research is available (rate limit check) */
  canDeepResearch: boolean;
  /** Trigger a new research task */
  triggerResearch: (taskType: ResearchTaskType) => Promise<void>;
  /** Toggle the report visibility */
  toggleReport: () => void;
  /** Copy the research report to clipboard */
  copyReport: () => void;
  /** Dismiss the error message */
  dismissError: () => void;
  /** Dismiss the completed task notification */
  dismissTask: () => void;
  /** Reset all research state */
  reset: () => void;
}

/**
 * Custom hook for managing research task operations
 *
 * This hook encapsulates all the logic for:
 * - Triggering research tasks (update or deep research)
 * - Polling for task completion status
 * - Managing UI state (showing report, copied state)
 * - Error handling and dismissal
 *
 * The hook uses polling with a 2-second interval to check task status
 * and automatically stops polling when the task completes or fails.
 *
 * @param card - The current card, or null if not loaded
 * @param getAuthToken - Function to get the current auth token
 * @param onResearchComplete - Optional callback when research completes successfully
 * @returns Object containing research state and control functions
 */
export function useResearch(
  card: Card | null,
  getAuthToken: () => Promise<string | undefined>,
  onResearchComplete?: () => void
): UseResearchReturn {
  // Research task state
  const [researchTask, setResearchTask] = useState<ResearchTask | null>(null);
  const [isResearching, setIsResearching] = useState(false);
  const [researchError, setResearchError] = useState<string | null>(null);

  // UI state
  const [showReport, setShowReport] = useState(false);
  const [reportCopied, setReportCopied] = useState(false);

  // Ref to track polling timeout for cleanup
  const pollingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * Check if deep research is available (rate limit: 2 per day)
   */
  const canDeepResearch = Boolean(
    card && (card.deep_research_count_today ?? 0) < 2
  );

  /**
   * Clean up any active polling
   */
  const cleanupPolling = useCallback(() => {
    if (pollingTimeoutRef.current) {
      clearTimeout(pollingTimeoutRef.current);
      pollingTimeoutRef.current = null;
    }
  }, []);

  /**
   * Poll for research task status
   *
   * Recursively polls the API every 2 seconds until the task
   * completes, fails, or encounters an error.
   */
  const pollTaskStatus = useCallback(
    async (taskId: string) => {
      const token = await getAuthToken();
      if (!token) {
        setIsResearching(false);
        setResearchError('Authentication lost');
        return;
      }

      const poll = async () => {
        try {
          const response = await fetch(`${API_BASE_URL}/api/v1/research/${taskId}`, {
            headers: { Authorization: `Bearer ${token}` },
          });

          if (!response.ok) {
            throw new Error('Failed to get task status');
          }

          const task: ResearchTask = await response.json();
          setResearchTask(task);

          if (task.status === 'completed') {
            setIsResearching(false);
            cleanupPolling();
            onResearchComplete?.();
          } else if (task.status === 'failed') {
            setIsResearching(false);
            setResearchError(task.error_message || 'Research failed');
            cleanupPolling();
          } else {
            // Continue polling
            pollingTimeoutRef.current = setTimeout(poll, 2000);
          }
        } catch {
          setIsResearching(false);
          setResearchError('Failed to check research status');
          cleanupPolling();
        }
      };

      poll();
    },
    [getAuthToken, onResearchComplete, cleanupPolling]
  );

  /**
   * Trigger a research task
   *
   * Starts either an update or deep research task for the current card.
   * Automatically begins polling for status updates.
   *
   * @param taskType - The type of research task to trigger
   */
  const triggerResearch = useCallback(
    async (taskType: ResearchTaskType) => {
      if (!card || isResearching) return;

      // Validate deep research rate limit
      if (taskType === 'deep_research' && !canDeepResearch) {
        setResearchError('Daily deep research limit reached (2 per day)');
        return;
      }

      setIsResearching(true);
      setResearchError(null);
      setResearchTask(null);
      setShowReport(false);

      try {
        const token = await getAuthToken();
        if (!token) {
          throw new Error('Not authenticated');
        }

        const response = await fetch(`${API_BASE_URL}/api/v1/research`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            card_id: card.id,
            task_type: taskType,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to start research');
        }

        const task: ResearchTask = await response.json();
        setResearchTask(task);
        pollTaskStatus(task.id);
      } catch (error: unknown) {
        setResearchError(
          error instanceof Error ? error.message : 'Failed to start research'
        );
        setIsResearching(false);
      }
    },
    [card, isResearching, canDeepResearch, getAuthToken, pollTaskStatus]
  );

  /**
   * Toggle the report visibility
   */
  const toggleReport = useCallback(() => {
    setShowReport((prev) => !prev);
  }, []);

  /**
   * Copy the research report to clipboard
   */
  const copyReport = useCallback(() => {
    if (researchTask?.result_summary?.report_preview) {
      navigator.clipboard.writeText(researchTask.result_summary.report_preview);
      setReportCopied(true);
      setTimeout(() => setReportCopied(false), 2000);
    }
  }, [researchTask]);

  /**
   * Dismiss the error message
   */
  const dismissError = useCallback(() => {
    setResearchError(null);
  }, []);

  /**
   * Dismiss the completed task notification
   */
  const dismissTask = useCallback(() => {
    setResearchTask(null);
    setShowReport(false);
  }, []);

  /**
   * Reset all research state
   */
  const reset = useCallback(() => {
    cleanupPolling();
    setResearchTask(null);
    setIsResearching(false);
    setResearchError(null);
    setShowReport(false);
    setReportCopied(false);
  }, [cleanupPolling]);

  return {
    researchTask,
    isResearching,
    researchError,
    showReport,
    reportCopied,
    canDeepResearch,
    triggerResearch,
    toggleReport,
    copyReport,
    dismissError,
    dismissTask,
    reset,
  };
}

export default useResearch;
