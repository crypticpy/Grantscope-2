/**
 * useCheckUpdates Hook
 *
 * Manages check for updates actions for cards in the watching column.
 * Searches for recent developments and news about the card topic.
 */

import { useState, useCallback } from "react";
import { API_BASE_URL } from "../../../lib/config";

interface UseCheckUpdatesOptions {
  /** Callback when check starts */
  onStart?: (cardId: string) => void;
  /** Callback when check succeeds */
  onSuccess?: (cardId: string, result: CheckUpdatesResult) => void;
  /** Callback when check fails */
  onError?: (cardId: string, error: Error) => void;
}

interface CheckUpdatesResult {
  id: string;
  status: string;
  task_type: string;
  has_updates?: boolean;
  updates_count?: number;
}

/**
 * Hook for checking for updates on watched cards.
 *
 * @param getToken - Async function to get bearer auth token
 * @param workstreamId - The workstream ID
 * @param options - Optional callbacks for lifecycle events
 */
export function useCheckUpdates(
  getToken: () => Promise<string | null>,
  workstreamId: string,
  options: UseCheckUpdatesOptions = {},
) {
  // Destructure options to avoid stale closure issues with default {} object
  const { onStart, onSuccess, onError } = options;

  const [isChecking, setIsChecking] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<Record<string, Error | null>>({});
  const [lastChecked, setLastChecked] = useState<Record<string, Date>>({});

  const checkForUpdates = useCallback(
    async (cardId: string): Promise<CheckUpdatesResult | null> => {
      setIsChecking((prev) => ({ ...prev, [cardId]: true }));
      setError((prev) => ({ ...prev, [cardId]: null }));
      onStart?.(cardId);

      try {
        const token = await getToken();
        if (!token) {
          throw new Error("Authentication required");
        }

        // Call the check updates endpoint
        // This is similar to quick update but specifically checks for new developments
        const response = await fetch(
          `${API_BASE_URL}/api/v1/me/workstreams/${workstreamId}/cards/${cardId}/check-updates`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
          },
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            errorData.message ||
              errorData.detail ||
              `Check updates failed: ${response.status}`,
          );
        }

        const result: CheckUpdatesResult = await response.json();
        setLastChecked((prev) => ({ ...prev, [cardId]: new Date() }));
        onSuccess?.(cardId, result);
        return result;
      } catch (err) {
        const error =
          err instanceof Error ? err : new Error("Check updates failed");
        setError((prev) => ({ ...prev, [cardId]: error }));
        onError?.(cardId, error);
        return null;
      } finally {
        setIsChecking((prev) => ({ ...prev, [cardId]: false }));
      }
    },
    [getToken, workstreamId, onStart, onSuccess, onError],
  );

  const isCardChecking = useCallback(
    (cardId: string): boolean => isChecking[cardId] ?? false,
    [isChecking],
  );

  const getCardError = useCallback(
    (cardId: string): Error | null => error[cardId] ?? null,
    [error],
  );

  const getLastChecked = useCallback(
    (cardId: string): Date | null => lastChecked[cardId] ?? null,
    [lastChecked],
  );

  const clearError = useCallback((cardId: string) => {
    setError((prev) => ({ ...prev, [cardId]: null }));
  }, []);

  return {
    checkForUpdates,
    isChecking,
    isCardChecking,
    error,
    getCardError,
    lastChecked,
    getLastChecked,
    clearError,
  };
}
