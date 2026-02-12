/**
 * DeepResearchPanel Component
 *
 * Displays a prominent panel for Strategic Intelligence Reports from deep research.
 * Shows the latest report with expandable content and links to previous reports.
 *
 * @module CardDetail/tabs/OverviewTab/DeepResearchPanel
 */

import React, { useState, useCallback } from "react";
import {
  Search,
  FileText,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  Sparkles,
} from "lucide-react";
import { cn } from "../../../../lib/utils";
import { MarkdownReport } from "../../MarkdownReport";
import type { ResearchTask } from "../../types";

/**
 * Extract a clean text preview from markdown content.
 * Removes markdown syntax and returns plain text suitable for preview.
 */
function extractMarkdownPreview(
  markdown: string,
  maxLength: number = 300,
): string {
  if (!markdown) return "";

  // Remove markdown headers (# ## ### etc)
  let text = markdown.replace(/^#{1,6}\s+/gm, "");

  // Remove bold/italic markers
  text = text.replace(/\*\*(.+?)\*\*/g, "$1");
  text = text.replace(/\*(.+?)\*/g, "$1");
  text = text.replace(/__(.+?)__/g, "$1");
  text = text.replace(/_(.+?)_/g, "$1");

  // Remove links but keep text
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");

  // Remove horizontal rules
  text = text.replace(/^[-*_]{3,}$/gm, "");

  // Remove bullet points and list markers
  text = text.replace(/^[\s]*[-*+]\s+/gm, "");
  text = text.replace(/^[\s]*\d+\.\s+/gm, "");

  // Remove code blocks
  text = text.replace(/```[\s\S]*?```/g, "");
  text = text.replace(/`([^`]+)`/g, "$1");

  // Remove blockquotes
  text = text.replace(/^>\s+/gm, "");

  // Collapse multiple newlines and spaces
  text = text.replace(/\n{2,}/g, " ");
  text = text.replace(/\s{2,}/g, " ");

  // Trim and limit length
  text = text.trim();

  if (text.length > maxLength) {
    // Cut at word boundary
    text = text.slice(0, maxLength);
    const lastSpace = text.lastIndexOf(" ");
    if (lastSpace > maxLength * 0.8) {
      text = text.slice(0, lastSpace);
    }
    text += "...";
  }

  return text;
}

/**
 * Props for the DeepResearchPanel component
 */
export interface DeepResearchPanelProps {
  /**
   * Array of completed deep research tasks, ordered by completion date (newest first)
   */
  researchTasks: ResearchTask[];

  /**
   * Optional custom CSS class name for the container
   */
  className?: string;

  /**
   * Callback when user wants to trigger new deep research
   */
  onRequestResearch?: () => void;

  /**
   * Whether new research can be requested (rate limit check)
   */
  canRequestResearch?: boolean;
}

/**
 * DeepResearchPanel displays Strategic Intelligence Reports prominently.
 *
 * Features:
 * - Prominent gradient header for visibility
 * - Latest report shown with expandable full content
 * - Previous reports listed with quick access
 * - Copy report functionality
 * - Timestamp display with relative time
 * - Request new research button when available
 *
 * @example
 * ```tsx
 * <DeepResearchPanel
 *   researchTasks={completedDeepResearchTasks}
 *   onRequestResearch={handleDeepResearch}
 *   canRequestResearch={canDeepResearch}
 * />
 * ```
 */
export const DeepResearchPanel: React.FC<DeepResearchPanelProps> = ({
  researchTasks,
  className = "",
  onRequestResearch,
  canRequestResearch = false,
}) => {
  const [expandedReportId, setExpandedReportId] = useState<string | null>(null);
  const [showAllReports, setShowAllReports] = useState(false);

  // Filter to only deep research tasks with reports
  const deepResearchTasks = researchTasks.filter(
    (task) =>
      task.task_type === "deep_research" &&
      task.status === "completed" &&
      task.result_summary?.report_preview,
  );

  // Get the latest report
  const latestReport = deepResearchTasks[0];
  const previousReports = deepResearchTasks.slice(1);

  /**
   * Toggle expansion of a report
   */
  const handleToggleExpand = useCallback((taskId: string) => {
    setExpandedReportId((current) => (current === taskId ? null : taskId));
  }, []);

  /**
   * Format date for display
   */
  const formatDate = useCallback((dateString: string | undefined): string => {
    if (!dateString) return "Unknown date";
    const date = new Date(dateString);
    const now = new Date();
    const diffDays = Math.floor(
      (now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24),
    );

    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;

    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }, []);

  // Don't render if no deep research reports
  if (deepResearchTasks.length === 0) {
    return (
      <div
        className={cn(
          "bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-600 p-6",
          className,
        )}
      >
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-gray-200 dark:bg-gray-700 mb-3">
            <Search className="h-6 w-6 text-gray-400 dark:text-gray-500" />
          </div>
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">
            No Strategic Intelligence Reports Yet
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
            Run deep research to generate comprehensive analysis
          </p>
          {onRequestResearch && canRequestResearch && (
            <button
              onClick={onRequestResearch}
              className="inline-flex items-center gap-2 px-4 py-2 bg-brand-blue text-white rounded-lg text-sm font-medium hover:bg-brand-dark-blue transition-colors"
            >
              <Sparkles className="h-4 w-4" />
              Generate Report
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "bg-white dark:bg-dark-surface rounded-xl shadow-lg overflow-hidden border border-brand-blue/20",
        className,
      )}
    >
      {/* Header with gradient - Austin brand colors */}
      <div className="bg-gradient-to-r from-brand-blue to-brand-green p-4 sm:p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-white/20">
              <FileText className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">
                Strategic Intelligence Report
              </h2>
              <p className="text-white/80 text-sm">
                {deepResearchTasks.length} report
                {deepResearchTasks.length !== 1 ? "s" : ""} available
              </p>
            </div>
          </div>
          {onRequestResearch && canRequestResearch && (
            <button
              onClick={onRequestResearch}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white/20 hover:bg-white/30 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Sparkles className="h-4 w-4" />
              New Research
            </button>
          )}
        </div>
      </div>

      {/* Latest Report */}
      <div className="p-4 sm:p-5">
        {/* Latest report header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-brand-light-blue text-brand-blue">
              Latest
            </span>
            <span className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400">
              <Clock className="h-3.5 w-3.5" />
              {formatDate(latestReport.completed_at)}
            </span>
          </div>
          <button
            onClick={() => handleToggleExpand(latestReport.id)}
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200",
              expandedReportId === latestReport.id
                ? "bg-brand-blue text-white"
                : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600",
            )}
            aria-expanded={expandedReportId === latestReport.id}
          >
            {expandedReportId === latestReport.id ? (
              <>
                Collapse
                <ChevronUp className="h-4 w-4" />
              </>
            ) : (
              <>
                View Full Report
                <ChevronDown className="h-4 w-4" />
              </>
            )}
          </button>
        </div>

        {/* Report preview or full content */}
        {expandedReportId === latestReport.id ? (
          <div className="mt-4 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="max-h-[70vh] overflow-y-auto p-4 sm:p-6 bg-gray-50 dark:bg-dark-surface">
              <MarkdownReport
                content={latestReport.result_summary!.report_preview!}
              />
            </div>
          </div>
        ) : (
          <div className="bg-gray-50 dark:bg-dark-surface rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
              {extractMarkdownPreview(
                latestReport.result_summary?.report_preview || "",
                350,
              )}
            </p>
            <div className="mt-3 flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
              {latestReport.result_summary?.sources_found && (
                <span>
                  {latestReport.result_summary.sources_found} sources analyzed
                </span>
              )}
              {latestReport.result_summary?.sources_added && (
                <span>
                  {latestReport.result_summary.sources_added} sources added
                </span>
              )}
            </div>
          </div>
        )}

        {/* Previous Reports Section */}
        {previousReports.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
            <button
              onClick={() => setShowAllReports(!showAllReports)}
              className="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-brand-blue dark:hover:text-brand-light-blue transition-colors"
            >
              {showAllReports ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
              {previousReports.length} Previous Report
              {previousReports.length !== 1 ? "s" : ""}
            </button>

            {showAllReports && (
              <div className="mt-3 space-y-2">
                {previousReports.map((task) => (
                  <div
                    key={task.id}
                    className="flex items-center justify-between p-3 bg-gray-50 dark:bg-dark-surface rounded-lg"
                  >
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-gray-400" />
                      <span className="text-sm text-gray-600 dark:text-gray-300">
                        {formatDate(task.completed_at)}
                      </span>
                      {task.result_summary?.sources_found && (
                        <span className="text-xs text-gray-400">
                          ({task.result_summary.sources_found} sources)
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => handleToggleExpand(task.id)}
                      className="inline-flex items-center gap-1 text-sm text-brand-blue hover:text-brand-dark-blue dark:text-brand-light-blue transition-colors"
                    >
                      {expandedReportId === task.id ? "Hide" : "View"}
                      <ExternalLink className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}

                {/* Expanded previous report */}
                {previousReports.some((t) => expandedReportId === t.id) && (
                  <div className="mt-3 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                    <div className="max-h-[50vh] overflow-y-auto p-4 bg-gray-50 dark:bg-dark-surface">
                      <MarkdownReport
                        content={
                          previousReports.find((t) => t.id === expandedReportId)
                            ?.result_summary?.report_preview || ""
                        }
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DeepResearchPanel;
