/**
 * SourcesTab Component
 *
 * Displays the list of source documents associated with a card.
 * Shows source metadata including title, summary, key excerpts,
 * publisher, and relevance scores with color-coded badges.
 *
 * Features:
 * - Responsive card layout with hover effects
 * - Color-coded relevance score badges (WCAG 2.1 AA compliant)
 * - External links open in new tabs
 * - Support for AI summaries and key excerpts
 * - Publisher and API source badges
 * - Empty state for cards with no sources
 *
 * @module CardDetail/tabs/SourcesTab
 */

import React from 'react';
import { FileText, ExternalLink } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { getScoreColorClasses } from '../utils';
import type { Source } from '../types';

/**
 * Props for the SourcesTab component
 */
export interface SourcesTabProps {
  /**
   * Array of sources to display
   * Can be empty, which will show the empty state
   */
  sources: Source[];

  /**
   * Optional additional CSS classes for the container
   */
  className?: string;
}

/**
 * Formats the API source name for display
 * Converts internal identifiers to user-friendly names
 *
 * @param apiSource - The raw API source identifier
 * @returns Formatted display name
 */
const formatApiSource = (apiSource: string): string => {
  switch (apiSource) {
    case 'gpt_researcher':
      return 'GPT Researcher';
    default:
      return apiSource;
  }
};

/**
 * SourcesTab displays a list of source documents with relevance scores.
 *
 * Each source card shows:
 * - Title (as a link if URL is available)
 * - AI summary or legacy summary
 * - Key excerpts (first excerpt only, truncated)
 * - Metadata: publisher, API source, date
 * - Relevance score badge with color coding
 *
 * @example
 * ```tsx
 * <SourcesTab
 *   sources={cardSources}
 *   className="mt-6"
 * />
 * ```
 */
export const SourcesTab: React.FC<SourcesTabProps> = ({
  sources,
  className,
}) => {
  // Empty state
  if (sources.length === 0) {
    return (
      <div
        className={cn(
          'text-center py-12 bg-white dark:bg-[#2d3166] rounded-lg shadow',
          className
        )}
      >
        <FileText className="mx-auto h-12 w-12 text-gray-400" />
        <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">
          No sources yet
        </h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Sources will appear here as they are discovered and analyzed.
        </p>
      </div>
    );
  }

  return (
    <div className={cn('space-y-6', className)}>
      {sources.map((source) => {
        // Use relevance_to_card (1-5 scale) scaled to 100, or legacy relevance_score
        const relevanceScore = source.relevance_to_card
          ? Math.round(source.relevance_to_card * 20) // 1-5 scale → 0-100
          : source.relevance_score || 50;
        const sourceColors = getScoreColorClasses(relevanceScore);

        // Use ai_summary as primary, fallback to legacy summary
        const displaySummary = source.ai_summary || source.summary;

        // Use publication as publisher, fallback to legacy
        const displayPublisher = source.publication || source.publisher;

        // Format date - use ingested_at or published_date, handle nulls
        const displayDate = source.ingested_at || source.published_date;
        const formattedDate =
          displayDate && new Date(displayDate).getFullYear() > 1970
            ? new Date(displayDate).toLocaleDateString()
            : null;

        return (
          <div
            key={source.id}
            className="bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue"
          >
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4">
              <div className="flex-1 min-w-0">
                {/* Title as link */}
                {source.url ? (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-base sm:text-lg font-medium text-brand-blue hover:text-brand-dark-blue hover:underline mb-2 block break-words"
                  >
                    {source.title}
                    <ExternalLink className="h-4 w-4 inline ml-2 opacity-50" />
                  </a>
                ) : (
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                    {source.title}
                  </h3>
                )}

                {/* Summary/Synopsis */}
                {displaySummary && (
                  <p className="text-gray-600 dark:text-gray-300 mb-3 line-clamp-3">
                    {displaySummary}
                  </p>
                )}

                {/* Key Excerpts */}
                {source.key_excerpts && source.key_excerpts.length > 0 && (
                  <div className="mb-3 pl-3 border-l-2 border-gray-200 dark:border-gray-600">
                    <p className="text-sm text-gray-500 dark:text-gray-400 italic line-clamp-2">
                      "{source.key_excerpts[0]}"
                    </p>
                  </div>
                )}

                {/* Metadata row */}
                <div className="flex items-center flex-wrap gap-2 text-sm text-gray-500 dark:text-gray-400">
                  {displayPublisher && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs">
                      {displayPublisher}
                    </span>
                  )}
                  {source.api_source && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 text-xs">
                      via {formatApiSource(source.api_source)}
                    </span>
                  )}
                  {formattedDate && (
                    <span className="text-gray-400 text-xs">
                      {formattedDate}
                    </span>
                  )}
                </div>
              </div>

              {/* Relevance score badge */}
              <div className="sm:ml-4 flex-shrink-0 self-start sm:self-auto">
                <div className="flex flex-row sm:flex-col items-center sm:items-end gap-2 sm:gap-1">
                  <span
                    className={cn(
                      'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border',
                      sourceColors.bg,
                      sourceColors.text,
                      sourceColors.border
                    )}
                  >
                    {relevanceScore}%
                  </span>
                  <span className="text-[10px] text-gray-400">relevance</span>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default SourcesTab;
