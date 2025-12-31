/**
 * ExportProgressModal Component
 *
 * A modal that displays progress during AI-powered export generation
 * (particularly for Gamma.app PowerPoint exports). Shows status updates,
 * estimated time, and provides download functionality when complete.
 *
 * Features:
 * - Real-time status updates during generation
 * - City of Austin branded progress animation
 * - Download button when export is ready
 * - Error state with retry option
 * - Keyboard accessible (Escape to close when allowed)
 */

import React, { useEffect, useRef, useCallback, useState } from 'react';
import {
  X,
  Download,
  Loader2,
  CheckCircle,
  AlertCircle,
  Presentation,
  FileText,
  Sparkles,
  Clock,
  RefreshCw,
} from 'lucide-react';
import { cn } from '../lib/utils';

// =============================================================================
// Types
// =============================================================================

export type ExportStatus =
  | 'preparing'
  | 'generating'
  | 'processing'
  | 'completed'
  | 'error';

export type ExportFormat = 'pdf' | 'pptx';

export interface ExportProgressModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Current export status */
  status: ExportStatus;
  /** Export format being generated */
  format: ExportFormat;
  /** Progress percentage (0-100), if available */
  progress?: number;
  /** Status message to display */
  statusMessage?: string;
  /** Error message if status is 'error' */
  errorMessage?: string;
  /** Download URL when export is ready */
  downloadUrl?: string;
  /** Filename for the download */
  filename?: string;
  /** Callback to trigger download */
  onDownload?: () => void;
  /** Callback to retry on error */
  onRetry?: () => void;
  /** Card/brief name for display */
  itemName?: string;
  /** Whether this is a Gamma-powered export */
  isGammaPowered?: boolean;
  /** Estimated time remaining in seconds */
  estimatedTimeSeconds?: number;
}

// =============================================================================
// Constants
// =============================================================================

// City of Austin brand colors
const COA_COLORS = {
  logoBlue: '#44499C',
  logoGreen: '#009F4D',
  fadedWhite: '#f7f6f5',
  darkBlue: '#22254E',
  lightBlue: '#dcf2fd',
  lightGreen: '#dff0e3',
  red: '#F83125',
  darkGray: '#636262',
};

const STATUS_CONFIG: Record<
  ExportStatus,
  {
    icon: React.ComponentType<{ className?: string }>;
    title: string;
    description: string;
    color: string;
  }
> = {
  preparing: {
    icon: Clock,
    title: 'Preparing Export',
    description: 'Setting up your export request...',
    color: COA_COLORS.logoBlue,
  },
  generating: {
    icon: Sparkles,
    title: 'Generating Content',
    description: 'AI is creating your presentation with images and charts...',
    color: COA_COLORS.logoBlue,
  },
  processing: {
    icon: Loader2,
    title: 'Processing',
    description: 'Finalizing your export...',
    color: COA_COLORS.logoBlue,
  },
  completed: {
    icon: CheckCircle,
    title: 'Export Ready',
    description: 'Your export is ready to download.',
    color: COA_COLORS.logoGreen,
  },
  error: {
    icon: AlertCircle,
    title: 'Export Failed',
    description: 'There was a problem generating your export.',
    color: COA_COLORS.red,
  },
};

// =============================================================================
// Component
// =============================================================================

export const ExportProgressModal: React.FC<ExportProgressModalProps> = ({
  isOpen,
  onClose,
  status,
  format,
  progress,
  statusMessage,
  errorMessage,
  downloadUrl,
  filename,
  onDownload,
  onRetry,
  itemName,
  isGammaPowered = false,
  estimatedTimeSeconds,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [elapsedTime, setElapsedTime] = useState(0);

  // Track elapsed time during generation
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;

    if (isOpen && (status === 'generating' || status === 'processing')) {
      interval = setInterval(() => {
        setElapsedTime((prev) => prev + 1);
      }, 1000);
    } else if (status === 'completed' || status === 'error') {
      // Reset on completion
    } else {
      setElapsedTime(0);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isOpen, status]);

  // Reset elapsed time when modal opens
  useEffect(() => {
    if (isOpen) {
      setElapsedTime(0);
    }
  }, [isOpen]);

  // Handle escape key - only allow close when completed or error
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && (status === 'completed' || status === 'error')) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, onClose, status]);

  // Focus management
  useEffect(() => {
    if (isOpen && closeButtonRef.current) {
      closeButtonRef.current.focus();
    }
  }, [isOpen]);

  // Handle download
  const handleDownload = useCallback(() => {
    if (onDownload) {
      onDownload();
    } else if (downloadUrl) {
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename || `export.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  }, [onDownload, downloadUrl, filename, format]);

  if (!isOpen) return null;

  const config = STATUS_CONFIG[status];
  const StatusIcon = config.icon;
  const FormatIcon = format === 'pptx' ? Presentation : FileText;
  const canClose = status === 'completed' || status === 'error';
  const isInProgress = status === 'preparing' || status === 'generating' || status === 'processing';

  // Format elapsed time
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={canClose ? onClose : undefined}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        ref={modalRef}
        className={cn(
          'relative w-full max-w-md mx-4 bg-white dark:bg-gray-800 rounded-xl shadow-2xl',
          'transform transition-all duration-300',
          'border border-gray-200 dark:border-gray-700'
        )}
      >
        {/* Header */}
        <div
          className="px-6 py-4 border-b border-gray-200 dark:border-gray-700"
          style={{ backgroundColor: COA_COLORS.fadedWhite }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="p-2 rounded-lg"
                style={{ backgroundColor: `${COA_COLORS.logoBlue}15` }}
              >
                <FormatIcon
                  className="h-5 w-5"
                  style={{ color: COA_COLORS.logoBlue }}
                />
              </div>
              <div>
                <h2
                  id="export-modal-title"
                  className="text-lg font-semibold"
                  style={{ color: COA_COLORS.darkBlue }}
                >
                  {format === 'pptx' ? 'PowerPoint Export' : 'PDF Export'}
                </h2>
                {itemName && (
                  <p className="text-sm text-gray-600 dark:text-gray-400 truncate max-w-[200px]">
                    {itemName}
                  </p>
                )}
              </div>
            </div>
            {canClose && (
              <button
                ref={closeButtonRef}
                onClick={onClose}
                className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                aria-label="Close modal"
              >
                <X className="h-5 w-5 text-gray-500" />
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-8">
          {/* Status Icon & Animation */}
          <div className="flex flex-col items-center text-center">
            <div
              className={cn(
                'relative w-20 h-20 rounded-full flex items-center justify-center mb-4',
                isInProgress && 'animate-pulse'
              )}
              style={{
                backgroundColor:
                  status === 'completed'
                    ? COA_COLORS.lightGreen
                    : status === 'error'
                      ? '#FEE2E2'
                      : COA_COLORS.lightBlue,
              }}
            >
              <StatusIcon
                className={cn(
                  'h-10 w-10',
                  isInProgress && status !== 'preparing' && 'animate-spin'
                )}
                style={{ color: config.color }}
              />

              {/* Progress ring for generation */}
              {isInProgress && progress !== undefined && (
                <svg
                  className="absolute inset-0 w-full h-full -rotate-90"
                  viewBox="0 0 100 100"
                >
                  <circle
                    cx="50"
                    cy="50"
                    r="45"
                    fill="none"
                    stroke={COA_COLORS.lightBlue}
                    strokeWidth="6"
                  />
                  <circle
                    cx="50"
                    cy="50"
                    r="45"
                    fill="none"
                    stroke={COA_COLORS.logoBlue}
                    strokeWidth="6"
                    strokeLinecap="round"
                    strokeDasharray={`${progress * 2.83} 283`}
                    className="transition-all duration-500"
                  />
                </svg>
              )}
            </div>

            {/* Status Text */}
            <h3
              className="text-xl font-semibold mb-2"
              style={{ color: config.color }}
            >
              {config.title}
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              {statusMessage || config.description}
            </p>

            {/* Gamma Badge */}
            {isGammaPowered && isInProgress && (
              <div
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium mb-4"
                style={{
                  backgroundColor: COA_COLORS.lightBlue,
                  color: COA_COLORS.logoBlue,
                }}
              >
                <Sparkles className="h-4 w-4" />
                Powered by Gamma AI
              </div>
            )}

            {/* Time Elapsed */}
            {isInProgress && elapsedTime > 0 && (
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                <Clock className="h-4 w-4" />
                <span>Elapsed: {formatTime(elapsedTime)}</span>
                {estimatedTimeSeconds && estimatedTimeSeconds > elapsedTime && (
                  <span className="text-gray-400">
                    • ~{formatTime(estimatedTimeSeconds - elapsedTime)} remaining
                  </span>
                )}
              </div>
            )}

            {/* Error Message */}
            {status === 'error' && errorMessage && (
              <div
                className="mt-4 p-3 rounded-lg text-sm text-left w-full"
                style={{ backgroundColor: '#FEE2E2', color: COA_COLORS.red }}
              >
                {errorMessage}
              </div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 rounded-b-xl">
          <div className="flex items-center justify-end gap-3">
            {status === 'completed' && (
              <>
                <button
                  onClick={onClose}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  Close
                </button>
                <button
                  onClick={handleDownload}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors"
                  style={{ backgroundColor: COA_COLORS.logoGreen }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.backgroundColor = COA_COLORS.darkBlue)
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.backgroundColor = COA_COLORS.logoGreen)
                  }
                >
                  <Download className="h-4 w-4" />
                  Download {format.toUpperCase()}
                </button>
              </>
            )}

            {status === 'error' && (
              <>
                <button
                  onClick={onClose}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                {onRetry && (
                  <button
                    onClick={onRetry}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors"
                    style={{ backgroundColor: COA_COLORS.logoBlue }}
                  >
                    <RefreshCw className="h-4 w-4" />
                    Try Again
                  </button>
                )}
              </>
            )}

            {isInProgress && (
              <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                Please wait while we generate your export...
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExportProgressModal;
