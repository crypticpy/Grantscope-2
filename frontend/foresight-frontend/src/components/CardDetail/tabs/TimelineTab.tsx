/**
 * TimelineTab Component
 *
 * Displays the Timeline tab content showing card events with expandable reports.
 * Shows a chronological list of events including deep research with special styling
 * and detailed markdown reports that can be expanded.
 *
 * @module CardDetail/tabs/TimelineTab
 */

import React, { useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { Calendar, Search, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '../../../lib/utils';
import type { TimelineEvent } from '../types';

/**
 * Props for the TimelineTab component
 */
export interface TimelineTabProps {
  /**
   * Array of timeline events to display.
   * Events are displayed in the order provided (typically most recent first).
   */
  timeline: TimelineEvent[];

  /**
   * Optional custom CSS class name for the container
   */
  className?: string;
}

/**
 * TimelineTab displays the timeline of events for a card.
 *
 * Features:
 * - Chronological display of card events
 * - Special styling for deep research events with gradient backgrounds
 * - Expandable detailed reports with ReactMarkdown rendering
 * - Strategic Intelligence Report branding for deep research
 * - Metadata stats display (sources found, added, entities extracted)
 * - Responsive design with proper touch targets
 * - Dark mode support
 * - Empty state handling
 *
 * @example
 * ```tsx
 * <TimelineTab
 *   timeline={[
 *     {
 *       id: 'event-1',
 *       event_type: 'deep_research',
 *       title: 'Deep Research Completed',
 *       description: 'Comprehensive analysis with 15 sources analyzed',
 *       created_at: '2024-01-15T10:30:00Z',
 *       metadata: {
 *         sources_found: 15,
 *         sources_added: 8,
 *         entities_extracted: 5,
 *         detailed_report: '## Research Summary\n\n...'
 *       }
 *     }
 *   ]}
 * />
 * ```
 */
export const TimelineTab: React.FC<TimelineTabProps> = ({
  timeline,
  className = '',
}) => {
  // State for tracking which detailed report is expanded
  const [expandedTimelineId, setExpandedTimelineId] = useState<string | null>(null);

  /**
   * Toggle expansion of a detailed report
   */
  const handleToggleExpand = useCallback((eventId: string) => {
    setExpandedTimelineId((current) => (current === eventId ? null : eventId));
  }, []);

  /**
   * Format date for display
   */
  const formatDate = useCallback((dateString: string): string => {
    return new Date(dateString).toLocaleString();
  }, []);

  /**
   * Format short date for report header
   */
  const formatShortDate = useCallback((dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  }, []);

  // Empty state
  if (timeline.length === 0) {
    return (
      <div
        className={cn(
          'bg-white dark:bg-[#2d3166] rounded-lg shadow',
          className
        )}
      >
        <div className="text-center py-12">
          <Calendar className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">
            No timeline events yet
          </h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Timeline events will appear here as the card evolves.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'bg-white dark:bg-[#2d3166] rounded-lg shadow',
        className
      )}
    >
      <div className="divide-y divide-gray-200 dark:divide-gray-700">
        {timeline.map((event) => {
          const isDeepResearch = event.event_type === 'deep_research';
          const hasDetailedReport = isDeepResearch && event.metadata?.detailed_report;
          const isExpanded = expandedTimelineId === event.id;

          return (
            <div
              key={event.id}
              className={cn(
                'p-4 sm:p-6',
                isDeepResearch && 'bg-gradient-to-r from-brand-light-blue/10 to-transparent'
              )}
            >
              <div className="flex items-start">
                {/* Event icon */}
                <div className="flex-shrink-0">
                  {isDeepResearch ? (
                    <div className="p-2 rounded-full bg-brand-blue/10">
                      <Search className="h-5 w-5 text-brand-blue" />
                    </div>
                  ) : (
                    <Calendar className="h-5 w-5 text-gray-400" />
                  )}
                </div>

                {/* Event content */}
                <div className="ml-3 flex-1 min-w-0">
                  {/* Title and badge row */}
                  <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2">
                    <h3
                      className={cn(
                        'font-medium text-gray-900 dark:text-white break-words',
                        isDeepResearch ? 'text-base' : 'text-sm'
                      )}
                    >
                      {event.title}
                    </h3>
                    {isDeepResearch && (
                      <span className="inline-flex items-center px-2 sm:px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gradient-to-r from-brand-blue to-extended-purple text-white shadow-sm w-fit">
                        Strategic Intelligence Report
                      </span>
                    )}
                  </div>

                  {/* Description */}
                  <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                    {event.description}
                  </p>

                  {/* Metadata stats for deep research - enhanced display */}
                  {isDeepResearch && event.metadata && (
                    <div className="flex flex-wrap items-center gap-4 mt-3">
                      {event.metadata.sources_found !== undefined && (
                        <div className="flex items-center gap-1.5 text-xs">
                          <div className="w-2 h-2 rounded-full bg-brand-green" />
                          <span className="text-gray-600 dark:text-gray-300">
                            <span className="font-semibold text-gray-900 dark:text-white">
                              {event.metadata.sources_found}
                            </span>{' '}
                            sources found
                          </span>
                        </div>
                      )}
                      {event.metadata.sources_added !== undefined && (
                        <div className="flex items-center gap-1.5 text-xs">
                          <div className="w-2 h-2 rounded-full bg-brand-blue" />
                          <span className="text-gray-600 dark:text-gray-300">
                            <span className="font-semibold text-gray-900 dark:text-white">
                              {event.metadata.sources_added}
                            </span>{' '}
                            added
                          </span>
                        </div>
                      )}
                      {event.metadata.entities_extracted !== undefined && (
                        <div className="flex items-center gap-1.5 text-xs">
                          <div className="w-2 h-2 rounded-full bg-extended-purple" />
                          <span className="text-gray-600 dark:text-gray-300">
                            <span className="font-semibold text-gray-900 dark:text-white">
                              {event.metadata.entities_extracted}
                            </span>{' '}
                            entities
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Detailed Report Toggle - enhanced */}
                  {hasDetailedReport && (
                    <div className="mt-4">
                      <button
                        onClick={() => handleToggleExpand(event.id)}
                        className={cn(
                          'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200',
                          isExpanded
                            ? 'bg-brand-blue text-white shadow-md hover:bg-brand-dark-blue'
                            : 'bg-brand-light-blue text-brand-blue hover:bg-brand-blue hover:text-white'
                        )}
                        aria-expanded={isExpanded}
                        aria-controls={`timeline-report-${event.id}`}
                      >
                        <FileText className="h-4 w-4" />
                        {isExpanded
                          ? 'Collapse Strategic Report'
                          : 'View Strategic Intelligence Report'}
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </button>

                      {/* Expanded Report Content - enhanced styling */}
                      {isExpanded && (
                        <div
                          id={`timeline-report-${event.id}`}
                          className="mt-4 rounded-xl border-2 border-brand-blue/20 overflow-hidden"
                        >
                          {/* Report Header */}
                          <div className="bg-gradient-to-r from-brand-blue to-extended-purple p-3 sm:p-4">
                            <div className="flex items-center gap-2 sm:gap-3 text-white">
                              <FileText className="h-5 w-5 sm:h-6 sm:w-6 flex-shrink-0" />
                              <div className="min-w-0">
                                <h4 className="font-bold text-base sm:text-lg">
                                  Strategic Intelligence Report
                                </h4>
                                <p className="text-white/80 text-xs sm:text-sm">
                                  Generated {formatShortDate(event.created_at)}
                                </p>
                              </div>
                            </div>
                          </div>

                          {/* Report Content */}
                          <div className="p-4 sm:p-6 bg-white dark:bg-[#1d2156] max-h-[70vh] sm:max-h-[80vh] overflow-y-auto overflow-x-hidden">
                            <div
                              className="prose prose-sm dark:prose-invert max-w-none break-words
                                prose-headings:text-brand-dark-blue dark:prose-headings:text-white
                                prose-h2:text-base prose-h2:sm:text-lg prose-h2:font-bold prose-h2:border-b prose-h2:border-gray-200 dark:prose-h2:border-gray-700 prose-h2:pb-2 prose-h2:mb-4 prose-h2:mt-6
                                prose-h3:text-sm prose-h3:sm:text-base prose-h3:font-semibold
                                prose-strong:text-brand-dark-blue dark:prose-strong:text-brand-light-blue
                                prose-ul:my-2 prose-li:my-0.5
                                prose-p:text-gray-700 dark:prose-p:text-gray-300
                                prose-a:text-brand-blue hover:prose-a:text-brand-dark-blue"
                            >
                              <ReactMarkdown>
                                {event.metadata!.detailed_report!}
                              </ReactMarkdown>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Timestamp */}
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
                    {formatDate(event.created_at)}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TimelineTab;
