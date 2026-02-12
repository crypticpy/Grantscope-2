/**
 * BriefPreviewModal Component
 *
 * A modal component for displaying generated executive briefs.
 * Shows the brief content with markdown rendering and provides
 * export options for PDF and PowerPoint formats.
 *
 * Features:
 * - Markdown rendering for brief content
 * - Executive summary highlight section
 * - Version history display with collapsible list
 * - Regenerate brief button
 * - New sources indicator
 * - Creation date display
 * - Export buttons (PDF, PPTX)
 * - Loading state during brief generation
 * - Error state with retry messaging
 * - Scrollable content area for long briefs
 * - Dark mode support
 * - Keyboard navigation (Escape to close)
 * - Focus management and accessibility
 */

import React, { useEffect, useRef, useCallback, memo, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  X,
  FileText,
  Download,
  Presentation,
  Loader2,
  AlertCircle,
  Calendar,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  History,
  Sparkles,
} from "lucide-react";
import { cn } from "../../lib/utils";
import type { BriefVersionListItem } from "../../lib/workstream-api";

// =============================================================================
// Types
// =============================================================================

/**
 * Executive Brief data structure.
 * Represents the generated brief content and metadata.
 */
export interface ExecutiveBrief {
  /** Unique identifier for the brief */
  id: string;
  /** The card ID this brief is associated with */
  card_id: string;
  /** Title of the brief */
  title: string;
  /** Executive summary - key highlights */
  executive_summary: string;
  /** Full brief content in markdown format */
  content_markdown: string;
  /** When the brief was generated */
  created_at: string;
  /** Version number for tracking revisions */
  version?: number;
  /** Metadata about sources discovered since previous version */
  sources_since_previous?: {
    new_sources_count: number;
    previous_version?: number;
    since_timestamp?: string;
  } | null;
}

/**
 * Props for the BriefPreviewModal component.
 */
export interface BriefPreviewModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** The executive brief to display, null if not yet loaded */
  brief: ExecutiveBrief | null;
  /** Whether the brief is currently being generated */
  isGenerating: boolean;
  /** Error message if generation failed */
  error: string | null;
  /** Callback to export as PDF */
  onExportPdf: () => void;
  /** Callback to export as PowerPoint */
  onExportPptx: () => void;
  /** Name of the card for display in header */
  cardName: string;
  /** Optional callback to retry generation on error */
  onRetry?: () => void;
  /** List of all brief versions for this card */
  versions?: BriefVersionListItem[];
  /** Number of new sources since last brief */
  newSourcesCount?: number;
  /** Callback to regenerate brief with latest sources */
  onRegenerateBrief?: () => void;
  /** Callback to load a specific version */
  onLoadVersion?: (briefId: string) => void;
  /** Whether versions are currently loading */
  isLoadingVersions?: boolean;
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Format a date string for display.
 */
function formatDate(dateString: string): string {
  try {
    return new Date(dateString).toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "Unknown date";
  }
}

// =============================================================================
// Subcomponents
// =============================================================================

/**
 * Loading state displayed while brief is generating.
 */
const LoadingState = memo(function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6">
      <Loader2
        className="h-12 w-12 text-brand-blue animate-spin mb-4"
        aria-hidden="true"
      />
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        Generating Executive Brief
      </h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 text-center max-w-sm">
        Analyzing research data and synthesizing key insights. This may take a
        moment...
      </p>
    </div>
  );
});

/**
 * Error state displayed when brief generation fails.
 */
interface ErrorStateProps {
  error: string;
  onRetry?: () => void;
}

const ErrorState = memo(function ErrorState({
  error,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6">
      <div
        className="h-12 w-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4"
        aria-hidden="true"
      >
        <AlertCircle className="h-6 w-6 text-red-600 dark:text-red-400" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        Generation Failed
      </h3>
      <p className="text-sm text-red-600 dark:text-red-400 text-center max-w-sm mb-4">
        {error}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 text-sm font-medium text-white bg-brand-blue hover:bg-brand-dark-blue rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2 dark:focus:ring-offset-dark-surface"
        >
          Try Again
        </button>
      )}
    </div>
  );
});

/**
 * Brief content display with markdown rendering.
 */
interface BriefContentProps {
  brief: ExecutiveBrief;
}

const BriefContent = memo(function BriefContent({ brief }: BriefContentProps) {
  const [copiedSection, setCopiedSection] = React.useState<string | null>(null);

  const handleCopy = useCallback((content: string, section: string) => {
    navigator.clipboard.writeText(content);
    setCopiedSection(section);
    setTimeout(() => setCopiedSection(null), 2000);
  }, []);

  return (
    <div className="space-y-6">
      {/* Creation Date */}
      <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
        <Calendar className="h-4 w-4" aria-hidden="true" />
        <span>Generated {formatDate(brief.created_at)}</span>
        {brief.version && brief.version > 1 && (
          <span className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 rounded-full">
            v{brief.version}
          </span>
        )}
      </div>

      {/* Executive Summary - Highlighted */}
      <div className="bg-gradient-to-br from-brand-blue/5 to-brand-blue/10 dark:from-brand-blue/10 dark:to-brand-blue/20 border border-brand-blue/20 dark:border-brand-blue/30 rounded-lg p-4">
        <div className="flex items-start justify-between gap-3 mb-3">
          <h3 className="text-sm font-semibold text-brand-blue dark:text-brand-light-blue uppercase tracking-wide">
            Executive Summary
          </h3>
          <button
            onClick={() => handleCopy(brief.executive_summary, "summary")}
            className="flex-shrink-0 p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded transition-colors"
            aria-label="Copy executive summary"
          >
            {copiedSection === "summary" ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </button>
        </div>
        <p className="text-gray-800 dark:text-gray-200 leading-relaxed">
          {brief.executive_summary}
        </p>
      </div>

      {/* Full Brief Content */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
            Full Brief
          </h3>
          <button
            onClick={() => handleCopy(brief.content_markdown, "content")}
            className="inline-flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
            aria-label="Copy full brief content"
          >
            {copiedSection === "content" ? (
              <>
                <Check className="h-3 w-3 text-green-500" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" />
                Copy
              </>
            )}
          </button>
        </div>

        {/* Markdown Content with Styled Prose */}
        <div className="prose prose-sm dark:prose-invert max-w-none bg-gray-50 dark:bg-dark-surface/50 rounded-lg p-4 overflow-hidden">
          <ReactMarkdown
            components={{
              a: ({ node: _node, ...props }) => (
                <a
                  {...props}
                  className="text-brand-blue hover:text-brand-dark-blue dark:text-brand-light-blue underline"
                  target="_blank"
                  rel="noopener noreferrer"
                />
              ),
              h1: ({ node: _node, ...props }) => (
                <h1
                  {...props}
                  className="text-xl font-bold text-gray-900 dark:text-white mt-4 mb-3 first:mt-0"
                />
              ),
              h2: ({ node: _node, ...props }) => (
                <h2
                  {...props}
                  className="text-lg font-semibold text-gray-900 dark:text-white mt-4 mb-2"
                />
              ),
              h3: ({ node: _node, ...props }) => (
                <h3
                  {...props}
                  className="text-base font-semibold text-gray-800 dark:text-gray-100 mt-3 mb-2"
                />
              ),
              h4: ({ node: _node, ...props }) => (
                <h4
                  {...props}
                  className="text-sm font-semibold text-gray-800 dark:text-gray-200 mt-3 mb-1"
                />
              ),
              p: ({ node: _node, ...props }) => (
                <p
                  {...props}
                  className="text-gray-700 dark:text-gray-300 mb-3 text-sm leading-relaxed"
                />
              ),
              ul: ({ node: _node, ...props }) => (
                <ul
                  {...props}
                  className="list-disc list-outside ml-4 mb-3 space-y-1"
                />
              ),
              ol: ({ node: _node, ...props }) => (
                <ol
                  {...props}
                  className="list-decimal list-outside ml-4 mb-3 space-y-1"
                />
              ),
              li: ({ node: _node, ...props }) => (
                <li
                  {...props}
                  className="text-gray-700 dark:text-gray-300 text-sm"
                />
              ),
              code: ({ node: _node, className, children, ...props }) => {
                const isInline = !className;
                if (isInline) {
                  return (
                    <code
                      {...props}
                      className="bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded text-xs font-mono"
                    >
                      {children}
                    </code>
                  );
                }
                return (
                  <code {...props} className={className}>
                    {children}
                  </code>
                );
              },
              pre: ({ node: _node, ...props }) => (
                <pre
                  {...props}
                  className="bg-gray-200 dark:bg-gray-700 rounded-md p-3 overflow-x-auto text-xs"
                />
              ),
              blockquote: ({ node: _node, ...props }) => (
                <blockquote
                  {...props}
                  className="border-l-4 border-brand-blue pl-4 italic text-gray-600 dark:text-gray-400 my-3 text-sm"
                />
              ),
              table: ({ node: _node, ...props }) => (
                <div className="overflow-x-auto my-3">
                  <table
                    {...props}
                    className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm"
                  />
                </div>
              ),
              th: ({ node: _node, ...props }) => (
                <th
                  {...props}
                  className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider bg-gray-100 dark:bg-gray-700"
                />
              ),
              td: ({ node: _node, ...props }) => (
                <td
                  {...props}
                  className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 border-b border-gray-200 dark:border-gray-700"
                />
              ),
              hr: ({ node: _node, ...props }) => (
                <hr
                  {...props}
                  className="my-4 border-gray-200 dark:border-gray-700"
                />
              ),
              strong: ({ node: _node, ...props }) => (
                <strong
                  {...props}
                  className="font-semibold text-gray-900 dark:text-white"
                />
              ),
              em: ({ node: _node, ...props }) => (
                <em {...props} className="italic" />
              ),
            }}
          >
            {brief.content_markdown}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
});

/**
 * Version history panel showing all versions of a brief.
 */
interface VersionHistoryPanelProps {
  versions: BriefVersionListItem[];
  currentBriefId?: string;
  onLoadVersion: (briefId: string) => void;
  isLoading?: boolean;
}

const VersionHistoryPanel = memo(function VersionHistoryPanel({
  versions,
  currentBriefId,
  onLoadVersion,
  isLoading,
}: VersionHistoryPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (versions.length <= 1) return null;

  return (
    <div className="border border-gray-200 dark:border-gray-600 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-dark-surface/50 hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-gray-500 dark:text-gray-400" />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Version History
          </span>
          <span className="px-2 py-0.5 text-xs bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300 rounded-full">
            {versions.length} versions
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-gray-500" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-500" />
        )}
      </button>

      {isExpanded && (
        <div className="divide-y divide-gray-200 dark:divide-gray-600 max-h-48 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : (
            versions.map((version) => {
              const isCurrentVersion = version.id === currentBriefId;
              const versionDate = version.generated_at
                ? new Date(version.generated_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "Pending";

              return (
                <button
                  key={version.id}
                  onClick={() => !isCurrentVersion && onLoadVersion(version.id)}
                  disabled={isCurrentVersion || version.status !== "completed"}
                  className={cn(
                    "w-full flex items-center justify-between px-4 py-3 text-left transition-colors",
                    isCurrentVersion
                      ? "bg-brand-blue/5 dark:bg-brand-blue/10"
                      : version.status === "completed"
                        ? "hover:bg-gray-50 dark:hover:bg-gray-700/30"
                        : "opacity-50 cursor-not-allowed",
                  )}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span
                      className={cn(
                        "flex-shrink-0 px-2 py-0.5 text-xs font-medium rounded",
                        isCurrentVersion
                          ? "bg-brand-blue text-white"
                          : "bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300",
                      )}
                    >
                      v{version.version}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm text-gray-900 dark:text-white truncate">
                        {versionDate}
                      </p>
                      {version.summary && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                          {version.summary.substring(0, 60)}...
                        </p>
                      )}
                    </div>
                  </div>
                  {isCurrentVersion && (
                    <span className="flex-shrink-0 text-xs text-brand-blue dark:text-brand-light-blue font-medium">
                      Current
                    </span>
                  )}
                  {version.status !== "completed" && (
                    <span className="flex-shrink-0 text-xs text-gray-500 capitalize">
                      {version.status}
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
});

// =============================================================================
// Main Component
// =============================================================================

/**
 * BriefPreviewModal - Modal for displaying and exporting executive briefs.
 *
 * Renders the generated brief content with proper markdown formatting,
 * highlights the executive summary, and provides export options for
 * PDF and PowerPoint formats.
 */
export const BriefPreviewModal = memo(function BriefPreviewModal({
  isOpen,
  onClose,
  brief,
  isGenerating,
  error,
  onExportPdf,
  onExportPptx,
  cardName,
  onRetry,
  versions = [],
  newSourcesCount = 0,
  onRegenerateBrief,
  onLoadVersion,
  isLoadingVersions = false,
}: BriefPreviewModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  // Focus close button when modal opens
  useEffect(() => {
    if (isOpen) {
      // Small delay to allow for animation
      const timer = setTimeout(() => {
        closeButtonRef.current?.focus();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Handle escape key to close
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = originalOverflow;
      };
    }
  }, [isOpen]);

  // Focus trap within modal
  useEffect(() => {
    if (!isOpen) return;

    const handleTabKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;

      const focusableElements = modalRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );

      if (!focusableElements || focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      } else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    };

    document.addEventListener("keydown", handleTabKey);
    return () => document.removeEventListener("keydown", handleTabKey);
  }, [isOpen]);

  // Handle backdrop click
  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) {
        onClose();
      }
    },
    [onClose],
  );

  if (!isOpen) return null;

  const hasBrief = brief !== null && !isGenerating && !error;
  const canExport = hasBrief;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="brief-modal-title"
      onClick={handleBackdropClick}
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
        aria-hidden="true"
      />

      {/* Modal Content */}
      <div
        ref={modalRef}
        className={cn(
          "relative bg-white dark:bg-dark-surface rounded-xl shadow-2xl",
          "w-full max-w-3xl max-h-[90vh] flex flex-col",
          "transform transition-all duration-200",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-600 flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div
              className="p-2 rounded-lg bg-brand-blue/10 dark:bg-brand-blue/20"
              aria-hidden="true"
            >
              <FileText className="h-5 w-5 text-brand-blue dark:text-brand-light-blue" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2
                  id="brief-modal-title"
                  className="text-lg font-semibold text-gray-900 dark:text-white truncate"
                >
                  Executive Brief
                </h2>
                {brief?.version && (
                  <span className="px-2 py-0.5 text-xs font-medium bg-brand-blue/10 dark:bg-brand-blue/20 text-brand-blue dark:text-brand-light-blue rounded-full">
                    v{brief.version}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                {cardName}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Regenerate Button with New Sources Indicator */}
            {hasBrief && onRegenerateBrief && (
              <button
                onClick={onRegenerateBrief}
                disabled={isGenerating}
                className={cn(
                  "inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors",
                  "text-gray-700 dark:text-gray-200",
                  "bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600",
                  "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2 dark:focus:ring-offset-dark-surface",
                  isGenerating && "opacity-50 cursor-not-allowed",
                )}
                aria-label="Regenerate brief with latest sources"
              >
                <RefreshCw
                  className={cn("h-4 w-4", isGenerating && "animate-spin")}
                />
                <span className="hidden sm:inline">Regenerate</span>
                {newSourcesCount > 0 && (
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded-full">
                    <Sparkles className="h-3 w-3" />
                    {newSourcesCount} new
                  </span>
                )}
              </button>
            )}
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}
              className={cn(
                "p-2 rounded-lg transition-colors",
                "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300",
                "hover:bg-gray-100 dark:hover:bg-gray-700",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2 dark:focus:ring-offset-dark-surface",
              )}
              aria-label="Close modal"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Content Area - Scrollable */}
        <div ref={contentRef} className="flex-1 overflow-y-auto px-6 py-4">
          {/* Loading State */}
          {isGenerating && <LoadingState />}

          {/* Error State */}
          {error && !isGenerating && (
            <ErrorState error={error} onRetry={onRetry} />
          )}

          {/* Brief Content */}
          {hasBrief && (
            <div className="space-y-6">
              <BriefContent brief={brief} />

              {/* Version History Panel */}
              {versions.length > 1 && onLoadVersion && (
                <VersionHistoryPanel
                  versions={versions}
                  currentBriefId={brief.id}
                  onLoadVersion={onLoadVersion}
                  isLoading={isLoadingVersions}
                />
              )}
            </div>
          )}

          {/* Empty State - No brief and not loading/error */}
          {!brief && !isGenerating && !error && (
            <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
              <FileText
                className="h-12 w-12 text-gray-300 dark:text-gray-600 mb-4"
                aria-hidden="true"
              />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                No Brief Available
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Generate a brief from the card actions menu.
              </p>
            </div>
          )}
        </div>

        {/* Footer - Export Actions */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-600 flex-shrink-0 bg-gray-50 dark:bg-dark-surface">
          <button
            type="button"
            onClick={onClose}
            className={cn(
              "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
              "text-gray-700 dark:text-gray-300",
              "bg-white dark:bg-dark-surface-elevated",
              "border border-gray-300 dark:border-gray-600",
              "hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
              "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2 dark:focus:ring-offset-dark-surface-deep",
            )}
          >
            Close
          </button>
          <button
            type="button"
            onClick={onExportPptx}
            disabled={!canExport}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors",
              "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2 dark:focus:ring-offset-dark-surface-deep",
              canExport
                ? "text-gray-700 dark:text-gray-200 bg-white dark:bg-dark-surface-elevated border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-dark-surface-hover"
                : "text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 cursor-not-allowed",
            )}
          >
            <Presentation className="h-4 w-4" aria-hidden="true" />
            Export PPTX
          </button>
          <button
            type="button"
            onClick={onExportPdf}
            disabled={!canExport}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors",
              "focus:outline-none focus:ring-2 focus:ring-offset-2",
              canExport
                ? "text-white bg-brand-blue hover:bg-brand-dark-blue focus:ring-brand-blue dark:focus:ring-offset-dark-surface-deep"
                : "text-gray-400 bg-brand-blue/40 cursor-not-allowed focus:ring-brand-blue/50 dark:focus:ring-offset-dark-surface-deep",
            )}
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            Export PDF
          </button>
        </div>
      </div>
    </div>
  );
});

export default BriefPreviewModal;
