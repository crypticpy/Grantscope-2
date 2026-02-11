/**
 * useCardExport Hook
 *
 * Custom hook for managing card export functionality.
 * Handles exporting cards in various formats (PDF, PPTX, CSV) with
 * loading states, error handling, and automatic file downloads.
 *
 * @module useCardExport
 *
 * @example
 * ```tsx
 * const {
 *   isExporting,
 *   exportError,
 *   exportFormat,
 *   exportCard,
 *   clearError,
 * } = useCardExport(card, getAuthToken);
 *
 * // Trigger export
 * await exportCard('pdf');
 * ```
 */

import { useState, useCallback } from "react";
import { API_BASE_URL } from "../utils";
import type { Card } from "../types";

/**
 * Supported export format types
 */
export type ExportFormat = "pdf" | "pptx" | "csv";

/**
 * Return type for the useCardExport hook
 */
export interface UseCardExportReturn {
  /** Whether an export is currently in progress */
  isExporting: boolean;
  /** Error message if export failed, null otherwise */
  exportError: string | null;
  /** The format currently being exported, null if not exporting */
  exportFormat: ExportFormat | null;
  /** Export the card in the specified format */
  exportCard: (format: ExportFormat) => Promise<boolean>;
  /** Clear the export error */
  clearError: () => void;
}

/**
 * Options for the export function
 */
export interface ExportOptions {
  /** Callback when export starts */
  onExportStart?: (format: ExportFormat) => void;
  /** Callback when export completes successfully */
  onExportComplete?: (format: ExportFormat) => void;
  /** Callback when export fails */
  onExportError?: (format: ExportFormat, error: string) => void;
}

/**
 * File extension mapping for each format
 */
const FORMAT_EXTENSIONS: Record<ExportFormat, string> = {
  pdf: "pdf",
  pptx: "pptx",
  csv: "csv",
};

/**
 * Custom hook for managing card export operations
 *
 * This hook encapsulates all the logic for exporting cards to various formats.
 * It handles:
 * - Making authenticated API requests
 * - Managing loading and error states
 * - Converting response to blob and triggering download
 * - Cleanup of temporary object URLs
 *
 * The hook is designed to work with the existing ExportDropdown component
 * but can also be used independently for programmatic exports.
 *
 * @param card - The current card to export, or null if not loaded
 * @param getAuthToken - Function to get the current auth token
 * @param options - Optional callbacks for export lifecycle events
 * @returns Object containing export state and control functions
 */
export function useCardExport(
  card: Card | null,
  getAuthToken: () => Promise<string | undefined>,
  options?: ExportOptions,
): UseCardExportReturn {
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<ExportFormat | null>(null);

  /**
   * Export the card in the specified format
   *
   * Makes an authenticated request to the export API endpoint,
   * converts the response to a blob, and triggers a file download.
   *
   * @param format - The export format (pdf, pptx, or csv)
   * @returns true if export was successful, false otherwise
   */
  const exportCard = useCallback(
    async (format: ExportFormat): Promise<boolean> => {
      if (!card || isExporting) return false;

      setIsExporting(true);
      setExportFormat(format);
      setExportError(null);
      options?.onExportStart?.(format);

      try {
        const token = await getAuthToken();
        if (!token) {
          throw new Error("Not authenticated");
        }

        const response = await fetch(
          `${API_BASE_URL}/api/v1/cards/${card.id}/export/${format}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          },
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            errorData.detail || `Export failed: ${response.statusText}`,
          );
        }

        // Create blob from response and trigger download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = `${card.slug}-export.${FORMAT_EXTENSIONS[format]}`;
        document.body.appendChild(a);
        a.click();

        // Cleanup
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        options?.onExportComplete?.(format);
        return true;
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : "Failed to export signal";
        setExportError(errorMessage);
        options?.onExportError?.(format, errorMessage);
        return false;
      } finally {
        setIsExporting(false);
        setExportFormat(null);
      }
    },
    [card, isExporting, getAuthToken, options],
  );

  /**
   * Clear the export error
   */
  const clearError = useCallback(() => {
    setExportError(null);
  }, []);

  return {
    isExporting,
    exportError,
    exportFormat,
    exportCard,
    clearError,
  };
}

export default useCardExport;
