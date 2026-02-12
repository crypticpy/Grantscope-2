/**
 * useExportWithProgress Hook
 *
 * Manages export operations with real-time progress tracking.
 * Supports both regular exports and Gamma-powered AI exports
 * with status polling and download handling.
 *
 * Includes proper cleanup to prevent state updates after unmount
 * and handles race conditions during async operations.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import type {
  ExportStatus,
  ExportFormat,
} from "../components/ExportProgressModal";
import { API_BASE_URL } from "../lib/config";

// Gamma exports typically take 30-90 seconds
const GAMMA_ESTIMATED_TIME = 60;
const POLL_INTERVAL = 2000; // 2 seconds

export interface ExportState {
  isExporting: boolean;
  showModal: boolean;
  status: ExportStatus;
  format: ExportFormat | null;
  progress: number;
  statusMessage: string;
  errorMessage: string | null;
  downloadUrl: string | null;
  filename: string | null;
  itemName: string | null;
  isGammaPowered: boolean;
  estimatedTimeSeconds: number;
}

export interface UseExportWithProgressReturn {
  state: ExportState;
  exportBrief: (
    workstreamId: string,
    cardId: string,
    format: ExportFormat,
    itemName?: string,
    version?: number,
  ) => Promise<void>;
  exportCard: (
    cardId: string,
    format: ExportFormat,
    itemName?: string,
  ) => Promise<void>;
  closeModal: () => void;
  retryExport: () => void;
  downloadExport: () => void;
}

const initialState: ExportState = {
  isExporting: false,
  showModal: false,
  status: "preparing",
  format: null,
  progress: 0,
  statusMessage: "",
  errorMessage: null,
  downloadUrl: null,
  filename: null,
  itemName: null,
  isGammaPowered: false,
  estimatedTimeSeconds: GAMMA_ESTIMATED_TIME,
};

/**
 * Hook for managing exports with progress modal
 */
export function useExportWithProgress(
  getToken: () => Promise<string | null>,
): UseExportWithProgressReturn {
  const [state, setState] = useState<ExportState>(initialState);

  // Refs to track active operations and prevent memory leaks
  const lastExportRef = useRef<{
    type: "brief" | "card";
    workstreamId?: string;
    cardId: string;
    format: ExportFormat;
    itemName?: string;
    version?: number;
  } | null>(null);

  // Track if component is mounted to prevent state updates after unmount
  const isMountedRef = useRef(true);

  // Track active abort controller for cancellation
  const abortControllerRef = useRef<AbortController | null>(null);

  // Track active interval for cleanup
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Track blob URL revocation timeout for cleanup on unmount
  const revokeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Track current export ID to detect stale updates
  const exportIdRef = useRef<number>(0);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;

      // Cleanup any active interval
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }

      // Abort any active request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }

      // Clear any pending blob URL revocation timeout
      if (revokeTimeoutRef.current) {
        clearTimeout(revokeTimeoutRef.current);
        revokeTimeoutRef.current = null;
      }
    };
  }, []);

  /**
   * Update state partially - only if mounted
   */
  const updateState = useCallback((updates: Partial<ExportState>) => {
    if (isMountedRef.current) {
      setState((prev) => ({ ...prev, ...updates }));
    }
  }, []);

  /**
   * Reset state - only if mounted
   */
  const resetState = useCallback(() => {
    if (isMountedRef.current) {
      setState(initialState);
    }
  }, []);

  /**
   * Cleanup active export resources
   */
  const cleanupExport = useCallback(() => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  /**
   * Close the modal
   */
  const closeModal = useCallback(() => {
    cleanupExport();
    updateState({ showModal: false });
    // Reset after animation
    setTimeout(resetState, 300);
  }, [cleanupExport, updateState, resetState]);

  /**
   * Handle successful export - trigger download
   */
  const downloadExport = useCallback(() => {
    if (state.downloadUrl) {
      const link = document.createElement("a");
      link.href = state.downloadUrl;
      link.download = state.filename || `export.${state.format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // Revoke URL after download (store timeout for cleanup on unmount)
      revokeTimeoutRef.current = setTimeout(() => {
        if (state.downloadUrl) {
          URL.revokeObjectURL(state.downloadUrl);
        }
        revokeTimeoutRef.current = null;
      }, 1000);
    }
  }, [state.downloadUrl, state.filename, state.format]);

  /**
   * Export a brief with progress tracking
   */
  const exportBrief = useCallback(
    async (
      workstreamId: string,
      cardId: string,
      format: ExportFormat,
      itemName?: string,
      version?: number,
    ) => {
      // Cleanup any previous export in progress
      cleanupExport();

      // Generate a unique ID for this export to detect stale updates
      const currentExportId = ++exportIdRef.current;

      // Helper to check if this export is still current
      const isCurrentExport = () =>
        exportIdRef.current === currentExportId && isMountedRef.current;

      // Store for retry
      lastExportRef.current = {
        type: "brief",
        workstreamId,
        cardId,
        format,
        itemName,
        version,
      };

      // PPTX exports use Gamma (AI-powered)
      const isGamma = format === "pptx";

      updateState({
        isExporting: true,
        showModal: true,
        status: "preparing",
        format,
        progress: 0,
        statusMessage: "Preparing your export...",
        errorMessage: null,
        downloadUrl: null,
        filename: null,
        itemName: itemName || "Executive Brief",
        isGammaPowered: isGamma,
        estimatedTimeSeconds: isGamma ? GAMMA_ESTIMATED_TIME : 15,
      });

      try {
        const token = await getToken();
        if (!token) {
          throw new Error("Authentication required");
        }

        // Check if still current after async token fetch
        if (!isCurrentExport()) {
          console.log("[Export] Aborted: export superseded during token fetch");
          return;
        }

        // Update status to generating
        updateState({
          status: "generating",
          progress: 10,
          statusMessage: isGamma
            ? "AI is designing your presentation..."
            : "Generating PDF document...",
        });

        // Build URL
        const url = version
          ? `${API_BASE_URL}/api/v1/me/workstreams/${workstreamId}/cards/${cardId}/brief/export/${format}?version=${version}`
          : `${API_BASE_URL}/api/v1/me/workstreams/${workstreamId}/cards/${cardId}/brief/export/${format}`;

        // Create abort controller for this request
        const abortController = new AbortController();
        abortControllerRef.current = abortController;

        // Simulate progress while waiting
        if (isGamma) {
          let currentProgress = 10;
          progressIntervalRef.current = setInterval(() => {
            // Stop updating if this export is no longer current
            if (!isCurrentExport()) {
              if (progressIntervalRef.current) {
                clearInterval(progressIntervalRef.current);
                progressIntervalRef.current = null;
              }
              return;
            }
            currentProgress = Math.min(currentProgress + 5, 85);
            updateState({
              progress: currentProgress,
              statusMessage:
                currentProgress < 30
                  ? "AI is analyzing your brief content..."
                  : currentProgress < 50
                    ? "Generating slides and images..."
                    : currentProgress < 70
                      ? "Creating data visualizations..."
                      : "Finalizing presentation...",
            });
          }, POLL_INTERVAL);
        }

        // Make the request with abort signal
        const response = await fetch(url, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          signal: abortController.signal,
        });

        // Clear progress interval
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
          progressIntervalRef.current = null;
        }

        // Check if still current after fetch
        if (!isCurrentExport()) {
          console.log("[Export] Aborted: export superseded during fetch");
          return;
        }

        if (!response.ok) {
          const contentType = response.headers.get("content-type");
          let errorMsg = `Export failed: ${response.status}`;
          if (contentType?.includes("application/json")) {
            const errorData = await response.json().catch(() => ({}));
            errorMsg = errorData.detail || errorData.message || errorMsg;
          }
          throw new Error(errorMsg);
        }

        // Update to processing
        updateState({
          status: "processing",
          progress: 90,
          statusMessage: "Processing download...",
        });

        // Get the blob
        const blob = await response.blob();

        // Final check before completing
        if (!isCurrentExport()) {
          console.log(
            "[Export] Aborted: export superseded during blob processing",
          );
          return;
        }

        // Extract filename from Content-Disposition header
        const contentDisposition = response.headers.get("content-disposition");
        let filename = `brief-export.${format}`;
        if (contentDisposition) {
          const match = contentDisposition.match(
            /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/,
          );
          if (match && match[1]) {
            filename = match[1].replace(/['"]/g, "");
          }
        }

        // Create blob URL
        const downloadUrl = URL.createObjectURL(blob);

        // Update to completed
        updateState({
          isExporting: false,
          status: "completed",
          progress: 100,
          statusMessage: "Your export is ready!",
          downloadUrl,
          filename,
        });
      } catch (error) {
        // Don't show error if it was an intentional abort
        if (error instanceof Error && error.name === "AbortError") {
          console.log("[Export] Request aborted");
          return;
        }

        // Only update state if this export is still current
        if (isMountedRef.current && exportIdRef.current === currentExportId) {
          updateState({
            isExporting: false,
            status: "error",
            progress: 0,
            statusMessage: "Export failed",
            errorMessage:
              error instanceof Error
                ? error.message
                : "An unexpected error occurred",
          });
        }
      }
    },
    [getToken, updateState, cleanupExport],
  );

  /**
   * Export a card with progress tracking
   */
  const exportCard = useCallback(
    async (cardId: string, format: ExportFormat, itemName?: string) => {
      // Cleanup any previous export in progress
      cleanupExport();

      // Generate a unique ID for this export to detect stale updates
      const currentExportId = ++exportIdRef.current;

      // Helper to check if this export is still current
      const isCurrentExport = () =>
        exportIdRef.current === currentExportId && isMountedRef.current;

      // Store for retry
      lastExportRef.current = {
        type: "card",
        cardId,
        format,
        itemName,
      };

      updateState({
        isExporting: true,
        showModal: true,
        status: "preparing",
        format,
        progress: 0,
        statusMessage: "Preparing your export...",
        errorMessage: null,
        downloadUrl: null,
        filename: null,
        itemName: itemName || "Card Export",
        isGammaPowered: false,
        estimatedTimeSeconds: 15,
      });

      try {
        const token = await getToken();
        if (!token) {
          throw new Error("Authentication required");
        }

        // Check if still current after async token fetch
        if (!isCurrentExport()) {
          console.log(
            "[Export] Aborted: card export superseded during token fetch",
          );
          return;
        }

        updateState({
          status: "generating",
          progress: 30,
          statusMessage: "Generating export...",
        });

        // Create abort controller for this request
        const abortController = new AbortController();
        abortControllerRef.current = abortController;

        const response = await fetch(
          `${API_BASE_URL}/api/v1/cards/${cardId}/export/${format}`,
          {
            method: "GET",
            headers: {
              Authorization: `Bearer ${token}`,
            },
            signal: abortController.signal,
          },
        );

        // Check if still current after fetch
        if (!isCurrentExport()) {
          console.log("[Export] Aborted: card export superseded during fetch");
          return;
        }

        if (!response.ok) {
          const contentType = response.headers.get("content-type");
          let errorMsg = `Export failed: ${response.status}`;
          if (contentType?.includes("application/json")) {
            const errorData = await response.json().catch(() => ({}));
            errorMsg = errorData.detail || errorData.message || errorMsg;
          }
          throw new Error(errorMsg);
        }

        updateState({
          status: "processing",
          progress: 80,
          statusMessage: "Processing download...",
        });

        const blob = await response.blob();

        // Final check before completing
        if (!isCurrentExport()) {
          console.log(
            "[Export] Aborted: card export superseded during blob processing",
          );
          return;
        }

        const contentDisposition = response.headers.get("content-disposition");
        let filename = `card-export.${format}`;
        if (contentDisposition) {
          const match = contentDisposition.match(
            /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/,
          );
          if (match && match[1]) {
            filename = match[1].replace(/['"]/g, "");
          }
        }

        const downloadUrl = URL.createObjectURL(blob);

        updateState({
          isExporting: false,
          status: "completed",
          progress: 100,
          statusMessage: "Your export is ready!",
          downloadUrl,
          filename,
        });
      } catch (error) {
        // Don't show error if it was an intentional abort
        if (error instanceof Error && error.name === "AbortError") {
          console.log("[Export] Card request aborted");
          return;
        }

        // Only update state if this export is still current
        if (isMountedRef.current && exportIdRef.current === currentExportId) {
          updateState({
            isExporting: false,
            status: "error",
            progress: 0,
            statusMessage: "Export failed",
            errorMessage:
              error instanceof Error
                ? error.message
                : "An unexpected error occurred",
          });
        }
      }
    },
    [getToken, updateState, cleanupExport],
  );

  /**
   * Retry the last export
   */
  const retryExport = useCallback(() => {
    const last = lastExportRef.current;
    if (!last) return;

    if (last.type === "brief" && last.workstreamId) {
      exportBrief(
        last.workstreamId,
        last.cardId,
        last.format,
        last.itemName,
        last.version,
      );
    } else if (last.type === "card") {
      exportCard(last.cardId, last.format, last.itemName);
    }
  }, [exportBrief, exportCard]);

  return {
    state,
    exportBrief,
    exportCard,
    closeModal,
    retryExport,
    downloadExport,
  };
}

export default useExportWithProgress;
