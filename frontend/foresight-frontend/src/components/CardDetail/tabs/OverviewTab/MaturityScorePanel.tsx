/**
 * MaturityScorePanel Component
 *
 * Displays the maturity score panel with a circular score display and stage badge.
 * The maturity score indicates how developed and established a technology or trend is,
 * with higher scores meaning more mature, proven solutions.
 *
 * @module CardDetail/tabs/OverviewTab/MaturityScorePanel
 */

import React from 'react';
import { Info } from 'lucide-react';

// UI Components
import { Tooltip } from '../../../ui/Tooltip';

// Badge Components
import { StageBadge } from '../../../StageBadge';

// Utilities
import { parseStageNumber } from '../../utils';

/**
 * Props for the MaturityScorePanel component
 */
export interface MaturityScorePanelProps {
  /**
   * The maturity score value (0-100).
   * Higher scores indicate more mature, established solutions.
   */
  maturityScore: number;

  /**
   * Stage identifier (e.g., "1_concept", "3_prototype").
   * Used to display the stage badge below the maturity score.
   */
  stageId?: string;

  /**
   * Optional custom CSS class name for the container
   */
  className?: string;
}

/**
 * Get the maturity interpretation based on score value
 */
const getMaturityInterpretation = (score: number): string => {
  if (score >= 81) {
    return 'Mature & Mainstream - Well-established with proven track record';
  }
  if (score >= 61) {
    return 'Established - Gaining broad adoption and validation';
  }
  if (score >= 31) {
    return 'Emerging - Actively developing with growing interest';
  }
  return 'Early Stage - Experimental or recently introduced';
};

/**
 * MaturityScorePanel displays the maturity score in a circular display
 * with an optional stage badge below.
 *
 * Features:
 * - Circular score display with visual styling
 * - Tooltip with detailed score interpretation
 * - Info icon with score range explanations
 * - Optional stage badge display
 * - Dark mode support
 * - Responsive design
 *
 * @example
 * ```tsx
 * <MaturityScorePanel
 *   maturityScore={75}
 *   stageId="3_prototype"
 * />
 * ```
 *
 * @example
 * ```tsx
 * // Without stage badge
 * <MaturityScorePanel
 *   maturityScore={45}
 *   className="mt-4"
 * />
 * ```
 */
export const MaturityScorePanel: React.FC<MaturityScorePanelProps> = ({
  maturityScore,
  stageId,
  className = '',
}) => {
  // Parse stage number from stage_id string (e.g., "1_concept" -> 1)
  const stageNumber = stageId ? parseStageNumber(stageId) : null;

  return (
    <div className={`bg-white dark:bg-[#2d3166] rounded-lg shadow p-4 sm:p-6 ${className}`}>
      {/* Header with info tooltip */}
      <div className="flex items-center gap-2 mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Maturity</h3>
        <Tooltip
          content={
            <div className="space-y-2 max-w-full sm:max-w-xs">
              <div className="font-semibold text-gray-900 dark:text-white">Maturity Score</div>
              <p className="text-sm text-gray-600 dark:text-gray-300">
                Indicates how developed and established this technology or trend is. Higher scores mean more mature,
                proven solutions with established best practices and widespread adoption.
              </p>
              <div className="text-xs text-gray-500 dark:text-gray-400 pt-1 border-t border-gray-200 dark:border-gray-600">
                <div className="flex justify-between"><span>0-30:</span><span>Early/Experimental</span></div>
                <div className="flex justify-between"><span>31-60:</span><span>Emerging/Developing</span></div>
                <div className="flex justify-between"><span>61-80:</span><span>Established</span></div>
                <div className="flex justify-between"><span>81-100:</span><span>Mature/Mainstream</span></div>
              </div>
            </div>
          }
          side="top"
          contentClassName="p-3"
        >
          <Info className="h-4 w-4 text-gray-400 hover:text-brand-blue cursor-help transition-colors" />
        </Tooltip>
      </div>

      {/* Circular score display */}
      <div className="text-center">
        <Tooltip
          content={<span>{getMaturityInterpretation(maturityScore)}</span>}
          side="bottom"
        >
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-brand-light-blue dark:bg-slate-700 border-4 border-brand-blue/30 dark:border-brand-blue/50 mb-2 cursor-help">
            <span className="text-2xl font-bold text-brand-dark-blue dark:text-white">
              {maturityScore}
            </span>
          </div>
        </Tooltip>
        <p className="text-sm text-gray-500 dark:text-gray-400">Maturity Score</p>
      </div>

      {/* Stage badge */}
      {stageNumber && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="text-center">
            <StageBadge
              stage={stageNumber}
              variant="progress"
              size="md"
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default MaturityScorePanel;
