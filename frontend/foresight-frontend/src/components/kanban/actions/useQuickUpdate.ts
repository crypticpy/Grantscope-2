/**
 * useQuickUpdate Hook
 *
 * Manages quick update (5-source) research actions for cards in the screening column.
 * Triggers a lightweight research update to help with initial triage.
 */

import { useState, useCallback } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface UseQuickUpdateOptions {
  /** Callback when update starts */
  onStart?: (cardId: string) => void;
  /** Callback when update succeeds */
  onSuccess?: (cardId: string, result: QuickUpdateResult) => void;
  /** Callback when update fails */
  onError?: (cardId: string, error: Error) => void;
}

interface QuickUpdateResult {
  id: string;
  status: string;
  task_type: string;
}

/**
 * Hook for triggering quick research updates on cards.
 *
 * @param getToken - Async function to get bearer auth token
 * @param workstreamId - The workstream ID
 * @param options - Optional callbacks for lifecycle events
 */
export function useQuickUpdate(
  getToken: () => Promise<string | null>,
  workstreamId: string,
  options: UseQuickUpdateOptions = {}
) {
  // Destructure options to avoid stale closure issues with default {} object
  const { onStart, onSuccess, onError } = options;

  const [isLoading, setIsLoading] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<Record<string, Error | null>>({});

  const triggerQuickUpdate = useCallback(
    async (cardId: string): Promise<QuickUpdateResult | null> => {
      setIsLoading((prev) => ({ ...prev, [cardId]: true }));
      setError((prev) => ({ ...prev, [cardId]: null }));
      onStart?.(cardId);

      try {
        const token = await getToken();
        if (!token) {
          throw new Error('Authentication required');
        }

        // Call the research endpoint with task_type='update' for a quick 5-source update
        const response = await fetch(
          `${API_BASE_URL}/api/v1/me/workstreams/${workstreamId}/cards/${cardId}/quick-update`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            errorData.message || errorData.detail || `Quick update failed: ${response.status}`
          );
        }

        const result: QuickUpdateResult = await response.json();
        onSuccess?.(cardId, result);
        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Quick update failed');
        setError((prev) => ({ ...prev, [cardId]: error }));
        onError?.(cardId, error);
        return null;
      } finally {
        setIsLoading((prev) => ({ ...prev, [cardId]: false }));
      }
    },
    [getToken, workstreamId, onStart, onSuccess, onError]
  );

  const isCardLoading = useCallback(
    (cardId: string): boolean => isLoading[cardId] ?? false,
    [isLoading]
  );

  const getCardError = useCallback(
    (cardId: string): Error | null => error[cardId] ?? null,
    [error]
  );

  const clearError = useCallback((cardId: string) => {
    setError((prev) => ({ ...prev, [cardId]: null }));
  }, []);

  return {
    triggerQuickUpdate,
    isLoading,
    isCardLoading,
    error,
    getCardError,
    clearError,
  };
}
