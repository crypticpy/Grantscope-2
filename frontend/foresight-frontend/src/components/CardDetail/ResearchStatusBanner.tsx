/**
 * ResearchStatusBanner Component
 *
 * A banner component that displays the current status of research tasks.
 * Shows different states: in-progress (with spinner), completed (with report),
 * or error (with dismiss option).
 *
 * Features:
 * - In-progress state with animated spinner
 * - Completed state with expandable research report
 * - Error state with dismiss functionality
 * - Copy report to clipboard functionality
 * - Markdown rendering for research reports
 * - Dark mode support
 * - Responsive design
 *
 * @example
 * ```tsx
 * <ResearchStatusBanner
 *   isResearching={isResearching}
 *   researchError={researchError}
 *   researchTask={researchTask}
 *   showReport={showReport}
 *   reportCopied={reportCopied}
 *   onToggleReport={() => setShowReport(!showReport)}
 *   onCopyReport={handleCopyReport}
 *   onDismissError={() => setResearchError(null)}
 *   onDismissTask={() => setResearchTask(null)}
 * />
 * ```
 *
 * @module CardDetail/ResearchStatusBanner
 */

import React from 'react';
import {
  Loader2,
  Check,
  Copy,
  ChevronDown,
  ChevronUp,
  FileText,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { cn } from '../../lib/utils';
import type { ResearchTask } from './types';

/**
 * Props for the ResearchStatusBanner component
 */
export interface ResearchStatusBannerProps {
  /** Whether research is currently in progress */
  isResearching: boolean;
  /** Error message if research failed, null otherwise */
  researchError: string | null;
  /** The current research task object, null if no task */
  researchTask: ResearchTask | null;
  /** Whether the report panel is expanded */
  showReport: boolean;
  /** Whether the report was recently copied to clipboard */
  reportCopied: boolean;
  /** Callback to toggle report panel visibility */
  onToggleReport: () => void;
  /** Callback to copy report to clipboard */
  onCopyReport: () => void;
  /** Callback to dismiss error state */
  onDismissError: () => void;
  /** Callback to dismiss completed task */
  onDismissTask: () => void;
  /** Optional additional class names */
  className?: string;
}

/**
 * ResearchStatusBanner - Displays research task status with visual feedback
 *
 * This component provides visual feedback for research operations:
 * - **In Progress**: Blue banner with animated spinner and task type info
 * - **Completed**: Green banner with source stats and expandable report
 * - **Error**: Red banner with error message and dismiss option
 *
 * The completed state includes an expandable research report rendered
 * from markdown with copy-to-clipboard functionality.
 */
export const ResearchStatusBanner: React.FC<ResearchStatusBannerProps> = ({
  isResearching,
  researchError,
  researchTask,
  showReport,
  reportCopied,
  onToggleReport,
  onCopyReport,
  onDismissError,
  onDismissTask,
  className,
}) => {
  // Determine the current state for styling
  const isCompleted = researchTask?.status === 'completed' && !isResearching && !researchError;
  const hasReport = researchTask?.result_summary?.report_preview;

  return (
    <div
      className={cn(
        'mb-6 rounded-lg border overflow-hidden',
        isResearching && 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800',
        researchError && 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800',
        isCompleted && 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800',
        className
      )}
    >
      {/* Status Header */}
      <div className="p-4">
        <div className="flex items-center gap-3">
          {/* In-Progress State */}
          {isResearching && (
            <>
              <Loader2
                className="h-5 w-5 text-blue-600 animate-spin"
                aria-hidden="true"
              />
              <div>
                <p className="font-medium text-blue-800 dark:text-blue-200">
                  {researchTask?.task_type === 'deep_research'
                    ? 'Deep research in progress...'
                    : 'Updating sources...'}
                </p>
                <p className="text-sm text-blue-600 dark:text-blue-300">
                  This may take a minute. You can continue browsing.
                </p>
              </div>
            </>
          )}

          {/* Error State */}
          {researchError && (
            <>
              <div
                className="h-5 w-5 rounded-full bg-red-500 text-white flex items-center justify-center text-xs font-bold flex-shrink-0"
                aria-hidden="true"
              >
                !
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-red-800 dark:text-red-200">
                  Research failed
                </p>
                <p className="text-sm text-red-600 dark:text-red-300 break-words">
                  {researchError}
                </p>
              </div>
              <button
                onClick={onDismissError}
                className="ml-auto text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-200 text-sm font-medium transition-colors flex-shrink-0"
                aria-label="Dismiss error"
              >
                Dismiss
              </button>
            </>
          )}

          {/* Completed State */}
          {isCompleted && (
            <>
              <div
                className="h-5 w-5 rounded-full bg-green-500 text-white flex items-center justify-center text-xs flex-shrink-0"
                aria-hidden="true"
              >
                &#10003;
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-green-800 dark:text-green-200">
                  Research completed!
                </p>
                <p className="text-sm text-green-600 dark:text-green-300">
                  Discovered {researchTask.result_summary?.sources_found || 0} sources
                  {researchTask.result_summary?.sources_relevant &&
                    ` → ${researchTask.result_summary.sources_relevant} relevant`}
                  {' → '}added {researchTask.result_summary?.sources_added || 0} new
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {hasReport && (
                  <button
                    onClick={onToggleReport}
                    className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-green-700 dark:text-green-200 bg-green-100 dark:bg-green-800/50 hover:bg-green-200 dark:hover:bg-green-700/50 rounded-md transition-colors"
                    aria-expanded={showReport}
                    aria-controls="research-report-panel"
                  >
                    <FileText className="h-4 w-4 mr-1.5" aria-hidden="true" />
                    {showReport ? 'Hide' : 'View'} Report
                    {showReport ? (
                      <ChevronUp className="h-4 w-4 ml-1" aria-hidden="true" />
                    ) : (
                      <ChevronDown className="h-4 w-4 ml-1" aria-hidden="true" />
                    )}
                  </button>
                )}
                <button
                  onClick={onDismissTask}
                  className="text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-200 text-sm font-medium transition-colors"
                  aria-label="Dismiss notification"
                >
                  Dismiss
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Collapsible Research Report Panel */}
      {isCompleted && showReport && hasReport && (
        <div
          id="research-report-panel"
          className="border-t border-green-200 dark:border-green-800 bg-white dark:bg-gray-900"
        >
          <div className="p-4">
            {/* Report Header */}
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                <FileText className="h-4 w-4" aria-hidden="true" />
                Research Report
              </h4>
              <button
                onClick={onCopyReport}
                className="inline-flex items-center px-2 py-1 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 dark:text-gray-300 dark:bg-gray-800 dark:hover:bg-gray-700 rounded transition-colors"
                aria-label={reportCopied ? 'Report copied' : 'Copy report to clipboard'}
              >
                {reportCopied ? (
                  <>
                    <Check className="h-3 w-3 mr-1 text-green-600" aria-hidden="true" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3 mr-1" aria-hidden="true" />
                    Copy Report
                  </>
                )}
              </button>
            </div>

            {/* Report Content */}
            <div className="prose prose-sm dark:prose-invert max-w-none max-h-[70vh] sm:max-h-[500px] overflow-y-auto p-3 sm:p-4 bg-gray-50 dark:bg-gray-800 rounded-lg break-words">
              <ReactMarkdown>{researchTask.result_summary!.report_preview!}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ResearchStatusBanner;
