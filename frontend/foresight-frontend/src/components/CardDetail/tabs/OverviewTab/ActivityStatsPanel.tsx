/**
 * ActivityStatsPanel Component
 *
 * Displays the activity stats panel for a card in the Overview tab.
 * Shows sources count, timeline events, notes count, velocity trend sparkline,
 * and key timestamps (created, updated, deep research).
 *
 * @module CardDetail/tabs/OverviewTab/ActivityStatsPanel
 */

import React from 'react';
import { Search } from 'lucide-react';
import { Tooltip } from '../../../../components/ui/Tooltip';
import {
  TrendVelocitySparkline,
  TrendVelocitySparklineSkeleton,
} from '../../../../components/visualizations/TrendVelocitySparkline';
import { formatRelativeTime } from '../../utils';
import { cn } from '../../../../lib/utils';
import type { ScoreHistory } from '../../../../lib/discovery-api';

/**
 * Props for the ActivityStatsPanel component
 */
export interface ActivityStatsPanelProps {
  /**
   * Number of sources associated with the card
   */
  sourcesCount: number;

  /**
   * Number of timeline events for the card
   */
  timelineCount: number;

  /**
   * Number of notes attached to the card
   */
  notesCount: number;

  /**
   * Score history data for velocity sparkline visualization.
   * Used to show trend direction over time.
   */
  scoreHistory: ScoreHistory[];

  /**
   * Whether score history is currently loading
   */
  scoreHistoryLoading: boolean;

  /**
   * ISO timestamp when the card was created
   */
  createdAt: string;

  /**
   * ISO timestamp when the card was last updated
   */
  updatedAt: string;

  /**
   * ISO timestamp of last deep research execution (optional)
   */
  deepResearchAt?: string;

  /**
   * Optional custom CSS class name for the container
   */
  className?: string;
}

/**
 * ActivityStatsPanel displays activity statistics and key timestamps for a card.
 *
 * Features:
 * - Sources, timeline events, and notes counts
 * - Velocity trend sparkline showing score changes over time
 * - Created, updated, and deep research timestamps with relative time
 * - Tooltips showing full timestamps on hover
 * - Dark mode support with appropriate color scheme
 * - Responsive design
 *
 * @example
 * ```tsx
 * <ActivityStatsPanel
 *   sourcesCount={sources.length}
 *   timelineCount={timeline.length}
 *   notesCount={notes.length}
 *   scoreHistory={scoreHistory}
 *   scoreHistoryLoading={scoreHistoryLoading}
 *   createdAt={card.created_at}
 *   updatedAt={card.updated_at}
 *   deepResearchAt={card.deep_research_at}
 * />
 * ```
 */
export const ActivityStatsPanel: React.FC<ActivityStatsPanelProps> = ({
  sourcesCount,
  timelineCount,
  notesCount,
  scoreHistory,
  scoreHistoryLoading,
  createdAt,
  updatedAt,
  deepResearchAt,
  className = '',
}) => {
  return (
    <div
      className={`bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6 ${className}`}
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Activity
      </h3>

      <div className="space-y-3 text-sm">
        {/* Basic Stats */}
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Sources</span>
          <span className="font-medium text-gray-900 dark:text-white">
            {sourcesCount}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Timeline Events</span>
          <span className="font-medium text-gray-900 dark:text-white">
            {timelineCount}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Notes</span>
          <span className="font-medium text-gray-900 dark:text-white">
            {notesCount}
          </span>
        </div>

        {/* Velocity Trend Sparkline */}
        <div className="pt-3 mt-3 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <Tooltip
              content={
                <div className="max-w-[200px]">
                  <p className="font-medium">Velocity Trend</p>
                  <p className="text-xs text-gray-500">
                    Shows how quickly this trend is developing over the last 30 days
                  </p>
                </div>
              }
              side="left"
            >
              <span className="text-gray-500 dark:text-gray-400 cursor-help border-b border-dotted border-gray-400 dark:border-gray-500">
                Velocity Trend
              </span>
            </Tooltip>
            {scoreHistoryLoading ? (
              <TrendVelocitySparklineSkeleton />
            ) : (
              <TrendVelocitySparkline
                data={scoreHistory}
                width={80}
                height={24}
              />
            )}
          </div>
        </div>

        {/* Timestamps Section */}
        <div className="pt-3 mt-3 border-t border-gray-200 dark:border-gray-700 space-y-2">
          {/* Created Timestamp */}
          <Tooltip
            content={<span>Created: {new Date(createdAt).toLocaleString()}</span>}
            side="left"
          >
            <div className="flex justify-between cursor-help">
              <span className="text-gray-500 dark:text-gray-400">Created</span>
              <span className="font-medium text-gray-900 dark:text-white">
                {formatRelativeTime(createdAt)}
              </span>
            </div>
          </Tooltip>

          {/* Updated Timestamp */}
          <Tooltip
            content={<span>Updated: {new Date(updatedAt).toLocaleString()}</span>}
            side="left"
          >
            <div className="flex justify-between cursor-help">
              <span className="text-gray-500 dark:text-gray-400">Last Updated</span>
              <span className="font-medium text-gray-900 dark:text-white">
                {formatRelativeTime(updatedAt)}
              </span>
            </div>
          </Tooltip>

          {/* Deep Research Timestamp */}
          <Tooltip
            content={
              deepResearchAt
                ? <span>Deep Research: {new Date(deepResearchAt).toLocaleString()}</span>
                : <span>No deep research performed yet</span>
            }
            side="left"
          >
            <div className="flex justify-between cursor-help">
              <span className="text-gray-500 dark:text-gray-400 flex items-center gap-1">
                <Search className="h-3 w-3" />
                Deep Research
              </span>
              <span
                className={cn(
                  'font-medium',
                  deepResearchAt
                    ? 'text-gray-900 dark:text-white'
                    : 'text-gray-400 dark:text-gray-500 italic'
                )}
              >
                {formatRelativeTime(deepResearchAt)}
              </span>
            </div>
          </Tooltip>
        </div>
      </div>
    </div>
  );
};

export default ActivityStatsPanel;
