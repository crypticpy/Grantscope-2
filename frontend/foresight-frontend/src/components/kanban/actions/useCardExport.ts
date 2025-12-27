/**
 * useCardExport Hook
 *
 * Manages card export actions for cards in the brief column.
 * Supports PDF and PPTX export formats for leadership briefings.
 */

import { useState, useCallback } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

type ExportFormat = 'pdf' | 'pptx';

interface UseCardExportOptions {
  /** Callback when export starts */
  onStart?: (cardId: string, format: ExportFormat) => void;
  /** Callback when export succeeds */
  onSuccess?: (cardId: string, format: ExportFormat) => void;
  /** Callback when export fails */
  onError?: (cardId: string, format: ExportFormat, error: Error) => void;
}

/**
 * Hook for exporting cards to PDF or PPTX format.
 *
 * @param getToken - Async function to get bearer auth token
 * @param options - Optional callbacks for lifecycle events
 */
export function useCardExport(
  getToken: () => Promise<string | null>,
  options: UseCardExportOptions = {}
) {
  // Destructure options to avoid stale closure issues with default {} object
  const { onStart, onSuccess, onError } = options;

  const [isExporting, setIsExporting] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<Record<string, Error | null>>({});

  const exportCard = useCallback(
    async (cardId: string, format: ExportFormat): Promise<boolean> => {
      const key = `${cardId}-${format}`;
      setIsExporting((prev) => ({ ...prev, [key]: true }));
      setError((prev) => ({ ...prev, [key]: null }));
      onStart?.(cardId, format);

      try {
        const token = await getToken();
        if (!token) {
          throw new Error('Authentication required');
        }

        // Call the export endpoint
        const response = await fetch(
          `${API_BASE_URL}/api/v1/cards/${cardId}/export/${format}`,
          {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          // Check for JSON error response
          const contentType = response.headers.get('content-type');
          if (contentType?.includes('application/json')) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(
              errorData.message || errorData.detail || `Export failed: ${response.status}`
            );
          }
          throw new Error(`Export failed: ${response.status}`);
        }

        // Get the blob and trigger download
        const blob = await response.blob();

        // Extract filename from Content-Disposition header or use default
        const contentDisposition = response.headers.get('content-disposition');
        let filename = `card-export.${format}`;

        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
          if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1].replace(/['"]/g, '');
          }
        }

        // Create download link and trigger click
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        onSuccess?.(cardId, format);
        return true;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Export failed');
        setError((prev) => ({ ...prev, [key]: error }));
        onError?.(cardId, format, error);
        return false;
      } finally {
        setIsExporting((prev) => ({ ...prev, [key]: false }));
      }
    },
    [getToken, onStart, onSuccess, onError]
  );

  const isCardExporting = useCallback(
    (cardId: string, format?: ExportFormat): boolean => {
      if (format) {
        return isExporting[`${cardId}-${format}`] ?? false;
      }
      // Check if any format is exporting for this card
      return (
        (isExporting[`${cardId}-pdf`] ?? false) ||
        (isExporting[`${cardId}-pptx`] ?? false)
      );
    },
    [isExporting]
  );

  const getCardError = useCallback(
    (cardId: string, format: ExportFormat): Error | null =>
      error[`${cardId}-${format}`] ?? null,
    [error]
  );

  const clearError = useCallback((cardId: string, format: ExportFormat) => {
    setError((prev) => ({ ...prev, [`${cardId}-${format}`]: null }));
  }, []);

  return {
    exportCard,
    isExporting,
    isCardExporting,
    error,
    getCardError,
    clearError,
  };
}
