/**
 * useExportWithProgress Hook
 *
 * Manages export operations with real-time progress tracking.
 * Supports both regular exports and Gamma-powered AI exports
 * with status polling and download handling.
 */

import { useState, useCallback, useRef } from 'react';
import type { ExportStatus, ExportFormat } from '../components/ExportProgressModal';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
    version?: number
  ) => Promise<void>;
  exportCard: (
    cardId: string,
    format: ExportFormat,
    itemName?: string
  ) => Promise<void>;
  closeModal: () => void;
  retryExport: () => void;
  downloadExport: () => void;
}

const initialState: ExportState = {
  isExporting: false,
  showModal: false,
  status: 'preparing',
  format: null,
  progress: 0,
  statusMessage: '',
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
  getToken: () => Promise<string | null>
): UseExportWithProgressReturn {
  const [state, setState] = useState<ExportState>(initialState);
  const lastExportRef = useRef<{
    type: 'brief' | 'card';
    workstreamId?: string;
    cardId: string;
    format: ExportFormat;
    itemName?: string;
    version?: number;
  } | null>(null);

  /**
   * Update state partially
   */
  const updateState = useCallback((updates: Partial<ExportState>) => {
    setState((prev) => ({ ...prev, ...updates }));
  }, []);

  /**
   * Reset state
   */
  const resetState = useCallback(() => {
    setState(initialState);
  }, []);

  /**
   * Close the modal
   */
  const closeModal = useCallback(() => {
    updateState({ showModal: false });
    // Reset after animation
    setTimeout(resetState, 300);
  }, [updateState, resetState]);

  /**
   * Handle successful export - trigger download
   */
  const downloadExport = useCallback(() => {
    if (state.downloadUrl) {
      const link = document.createElement('a');
      link.href = state.downloadUrl;
      link.download = state.filename || `export.${state.format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      // Revoke URL after download
      setTimeout(() => {
        if (state.downloadUrl) {
          URL.revokeObjectURL(state.downloadUrl);
        }
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
      version?: number
    ) => {
      // Store for retry
      lastExportRef.current = {
        type: 'brief',
        workstreamId,
        cardId,
        format,
        itemName,
        version,
      };

      // PPTX exports use Gamma (AI-powered)
      const isGamma = format === 'pptx';

      updateState({
        isExporting: true,
        showModal: true,
        status: 'preparing',
        format,
        progress: 0,
        statusMessage: 'Preparing your export...',
        errorMessage: null,
        downloadUrl: null,
        filename: null,
        itemName: itemName || 'Executive Brief',
        isGammaPowered: isGamma,
        estimatedTimeSeconds: isGamma ? GAMMA_ESTIMATED_TIME : 15,
      });

      try {
        const token = await getToken();
        if (!token) {
          throw new Error('Authentication required');
        }

        // Update status to generating
        updateState({
          status: 'generating',
          progress: 10,
          statusMessage: isGamma
            ? 'AI is designing your presentation...'
            : 'Generating PDF document...',
        });

        // Build URL
        const url = version
          ? `${API_BASE_URL}/api/v1/me/workstreams/${workstreamId}/cards/${cardId}/brief/export/${format}?version=${version}`
          : `${API_BASE_URL}/api/v1/me/workstreams/${workstreamId}/cards/${cardId}/brief/export/${format}`;

        // Simulate progress while waiting
        let progressInterval: NodeJS.Timeout | null = null;
        if (isGamma) {
          let currentProgress = 10;
          progressInterval = setInterval(() => {
            currentProgress = Math.min(currentProgress + 5, 85);
            updateState({
              progress: currentProgress,
              statusMessage:
                currentProgress < 30
                  ? 'AI is analyzing your brief content...'
                  : currentProgress < 50
                    ? 'Generating slides and images...'
                    : currentProgress < 70
                      ? 'Creating data visualizations...'
                      : 'Finalizing presentation...',
            });
          }, POLL_INTERVAL);
        }

        // Make the request
        const response = await fetch(url, {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        // Clear progress interval
        if (progressInterval) {
          clearInterval(progressInterval);
        }

        if (!response.ok) {
          const contentType = response.headers.get('content-type');
          let errorMsg = `Export failed: ${response.status}`;
          if (contentType?.includes('application/json')) {
            const errorData = await response.json().catch(() => ({}));
            errorMsg = errorData.detail || errorData.message || errorMsg;
          }
          throw new Error(errorMsg);
        }

        // Update to processing
        updateState({
          status: 'processing',
          progress: 90,
          statusMessage: 'Processing download...',
        });

        // Get the blob
        const blob = await response.blob();

        // Extract filename from Content-Disposition header
        const contentDisposition = response.headers.get('content-disposition');
        let filename = `brief-export.${format}`;
        if (contentDisposition) {
          const match = contentDisposition.match(
            /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/
          );
          if (match && match[1]) {
            filename = match[1].replace(/['"]/g, '');
          }
        }

        // Create blob URL
        const downloadUrl = URL.createObjectURL(blob);

        // Update to completed
        updateState({
          isExporting: false,
          status: 'completed',
          progress: 100,
          statusMessage: 'Your export is ready!',
          downloadUrl,
          filename,
        });
      } catch (error) {
        updateState({
          isExporting: false,
          status: 'error',
          progress: 0,
          statusMessage: 'Export failed',
          errorMessage:
            error instanceof Error ? error.message : 'An unexpected error occurred',
        });
      }
    },
    [getToken, updateState]
  );

  /**
   * Export a card with progress tracking
   */
  const exportCard = useCallback(
    async (cardId: string, format: ExportFormat, itemName?: string) => {
      // Store for retry
      lastExportRef.current = {
        type: 'card',
        cardId,
        format,
        itemName,
      };

      updateState({
        isExporting: true,
        showModal: true,
        status: 'preparing',
        format,
        progress: 0,
        statusMessage: 'Preparing your export...',
        errorMessage: null,
        downloadUrl: null,
        filename: null,
        itemName: itemName || 'Card Export',
        isGammaPowered: false,
        estimatedTimeSeconds: 15,
      });

      try {
        const token = await getToken();
        if (!token) {
          throw new Error('Authentication required');
        }

        updateState({
          status: 'generating',
          progress: 30,
          statusMessage: 'Generating export...',
        });

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
          const contentType = response.headers.get('content-type');
          let errorMsg = `Export failed: ${response.status}`;
          if (contentType?.includes('application/json')) {
            const errorData = await response.json().catch(() => ({}));
            errorMsg = errorData.detail || errorData.message || errorMsg;
          }
          throw new Error(errorMsg);
        }

        updateState({
          status: 'processing',
          progress: 80,
          statusMessage: 'Processing download...',
        });

        const blob = await response.blob();

        const contentDisposition = response.headers.get('content-disposition');
        let filename = `card-export.${format}`;
        if (contentDisposition) {
          const match = contentDisposition.match(
            /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/
          );
          if (match && match[1]) {
            filename = match[1].replace(/['"]/g, '');
          }
        }

        const downloadUrl = URL.createObjectURL(blob);

        updateState({
          isExporting: false,
          status: 'completed',
          progress: 100,
          statusMessage: 'Your export is ready!',
          downloadUrl,
          filename,
        });
      } catch (error) {
        updateState({
          isExporting: false,
          status: 'error',
          progress: 0,
          statusMessage: 'Export failed',
          errorMessage:
            error instanceof Error ? error.message : 'An unexpected error occurred',
        });
      }
    },
    [getToken, updateState]
  );

  /**
   * Retry the last export
   */
  const retryExport = useCallback(() => {
    const last = lastExportRef.current;
    if (!last) return;

    if (last.type === 'brief' && last.workstreamId) {
      exportBrief(
        last.workstreamId,
        last.cardId,
        last.format,
        last.itemName,
        last.version
      );
    } else if (last.type === 'card') {
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
