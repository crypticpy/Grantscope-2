/**
 * ResearchHistoryPanel Component
 *
 * Displays the research history section with expandable reports in the Overview tab.
 * Shows a chronological list of research tasks with their results and full markdown reports.
 *
 * @module CardDetail/tabs/OverviewTab/ResearchHistoryPanel
 */

import React, { useState, useCallback } from 'react';
import { Search, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react';
import { cn } from '../../../../lib/utils';
import { MarkdownReport } from '../../MarkdownReport';
import type { ResearchTask } from '../../types';

/**
 * Props for the ResearchHistoryPanel component
 */
export interface ResearchHistoryPanelProps {
  /**
   * Array of research tasks to display.
   * Tasks are displayed in the order provided (typically most recent first).
   */
  researchHistory: ResearchTask[];

  /**
   * Optional custom CSS class name for the container
   */
  className?: string;

  /**
   * Optional title for the panel (defaults to "Research History")
   */
  title?: string;
}

/**
 * ResearchHistoryPanel displays the research history for a card.
 *
 * Features:
 * - Expandable/collapsible research reports
 * - Markdown rendering for research reports using ReactMarkdown
 * - Copy-to-clipboard functionality for reports
 * - Visual feedback on copy success
 * - Responsive design with proper touch targets
 * - Dark mode support
 * - Task type badges (Deep Research vs Update)
 * - Source count summary (found → added)
 *
 * @example
 * ```tsx
 * <ResearchHistoryPanel
 *   researchHistory={[
 *     {
 *       id: 'task-1',
 *       task_type: 'deep_research',
 *       status: 'completed',
 *       completed_at: '2024-01-15T10:30:00Z',
 *       result_summary: {
 *         sources_found: 15,
 *         sources_added: 8,
 *         report_preview: '## Research Summary\n\n...'
 *       }
 *     }
 *   ]}
 * />
 * ```
 */
export const ResearchHistoryPanel: React.FC<ResearchHistoryPanelProps> = ({
  researchHistory,
  className = '',
  title = 'Research History',
}) => {
  // State for tracking which report is expanded
  const [expandedReportId, setExpandedReportId] = useState<string | null>(null);

  // State for tracking copy success feedback
  const [copiedReportId, setCopiedReportId] = useState<string | null>(null);

  /**
   * Handle copying report content to clipboard
   * Shows visual feedback for 2 seconds after successful copy
   */
  const handleCopyReport = useCallback((taskId: string, reportContent: string) => {
    navigator.clipboard.writeText(reportContent);
    setCopiedReportId(taskId);

    // Reset copy feedback after 2 seconds
    setTimeout(() => {
      setCopiedReportId(null);
    }, 2000);
  }, []);

  /**
   * Toggle expansion of a report
   */
  const handleToggleExpand = useCallback((taskId: string) => {
    setExpandedReportId((current) => (current === taskId ? null : taskId));
  }, []);

  /**
   * Format the completion date for display
   */
  const formatDate = useCallback((dateString: string | undefined): string => {
    if (!dateString) return 'Unknown date';

    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }, []);

  // Don't render if no history
  if (researchHistory.length === 0) {
    return null;
  }

  return (
    <div
      className={cn(
        'bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6',
        className
      )}
    >
      <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-white mb-3 sm:mb-4 flex items-center gap-2">
        <Search className="h-5 w-5 text-brand-blue" />
        {title}
      </h2>

      <div className="space-y-4">
        {researchHistory.map((task) => (
          <div
            key={task.id}
            className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
          >
            {/* Task header - always visible */}
            <button
              onClick={() => handleToggleExpand(task.id)}
              className="w-full px-3 sm:px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-0 bg-gray-50 dark:bg-dark-surface hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors min-h-[48px] touch-manipulation"
              aria-expanded={expandedReportId === task.id}
              aria-controls={`report-${task.id}`}
            >
              <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
                {/* Task type badge */}
                <span
                  className={cn(
                    'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                    task.task_type === 'deep_research'
                      ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
                      : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                  )}
                >
                  {task.task_type === 'deep_research' ? 'Deep Research' : 'Update'}
                </span>

                {/* Completion date */}
                <span className="text-xs sm:text-sm text-gray-600 dark:text-gray-300">
                  {formatDate(task.completed_at)}
                </span>
              </div>

              <div className="flex items-center justify-between sm:justify-end gap-2 sm:gap-3">
                {/* Source count summary */}
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {task.result_summary?.sources_found || 0} found
                  {task.result_summary?.sources_added
                    ? ` → ${task.result_summary.sources_added} added`
                    : ''}
                </span>

                {/* Expand/collapse icon */}
                {expandedReportId === task.id ? (
                  <ChevronUp className="h-5 w-5 sm:h-4 sm:w-4 text-gray-400" aria-hidden="true" />
                ) : (
                  <ChevronDown className="h-5 w-5 sm:h-4 sm:w-4 text-gray-400" aria-hidden="true" />
                )}
              </div>
            </button>

            {/* Expanded report content */}
            {expandedReportId === task.id && task.result_summary?.report_preview && (
              <div
                id={`report-${task.id}`}
                className="p-4 border-t border-gray-200 dark:border-gray-700"
              >
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-gray-900 dark:text-white text-sm">
                    Research Report
                  </h4>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleCopyReport(task.id, task.result_summary?.report_preview || '');
                    }}
                    className="inline-flex items-center px-2 py-1 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 dark:text-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 rounded transition-colors min-h-[32px] touch-manipulation"
                    aria-label="Copy report to clipboard"
                  >
                    {copiedReportId === task.id ? (
                      <>
                        <Check className="h-3 w-3 mr-1 text-green-500" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3 mr-1" />
                        Copy
                      </>
                    )}
                  </button>
                </div>

                {/* Markdown report content */}
                <div className="max-h-[60vh] sm:max-h-[400px] overflow-y-auto overflow-x-hidden p-3 bg-gray-50 dark:bg-dark-surface rounded-lg">
                  <MarkdownReport content={task.result_summary.report_preview} />
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ResearchHistoryPanel;
