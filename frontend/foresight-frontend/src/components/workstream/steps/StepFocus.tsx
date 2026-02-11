/**
 * StepFocus - Pillars + Stages + Horizon (Step 3)
 *
 * Combined step for selecting strategic pillars (with expandable goals),
 * maturity stages, and time horizon.
 */

import { cn } from "../../../lib/utils";
import { PillarBadge } from "../../PillarBadge";
import {
  pillars,
  stages,
  horizons,
  getGoalsByPillar,
} from "../../../data/taxonomy";
import type { FormData } from "../../../types/workstream";

interface StepFocusProps {
  formData: FormData;
  onPillarToggle: (pillarCode: string) => void;
  onGoalToggle: (goalCode: string) => void;
  onStageToggle: (stageNum: number) => void;
  onHorizonChange: (horizon: string) => void;
}

export function StepFocus({
  formData,
  onPillarToggle,
  onGoalToggle,
  onStageToggle,
  onHorizonChange,
}: StepFocusProps) {
  return (
    <div className="space-y-8">
      {/* Section 1: Pillars */}
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
            Strategic Pillars
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Pillars represent Austin's strategic priorities. Click to select the
            ones relevant to your research focus, or skip for a purely
            topic-driven workstream.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {pillars.map((pillar) => (
            <button
              key={pillar.code}
              type="button"
              onClick={() => onPillarToggle(pillar.code)}
              className={cn(
                "transition-all duration-200 cursor-pointer",
                formData.pillar_ids.includes(pillar.code)
                  ? "ring-2 ring-brand-blue ring-offset-1 dark:ring-offset-[#2d3166] rounded scale-105"
                  : "hover:scale-105 hover:ring-1 hover:ring-gray-300 dark:hover:ring-gray-500 rounded",
              )}
              aria-pressed={formData.pillar_ids.includes(pillar.code)}
              aria-label={`${pillar.name} pillar`}
            >
              <PillarBadge
                pillarId={pillar.code}
                size="md"
                showIcon={true}
                disableTooltip
              />
            </button>
          ))}
        </div>

        {/* Expandable Goals */}
        {formData.pillar_ids.length > 0 && (
          <div className="space-y-4 max-h-48 overflow-y-auto border border-gray-200 dark:border-gray-600 rounded-md p-3 bg-gray-50 dark:bg-dark-surface-elevated">
            {formData.pillar_ids.map((pillarCode) => {
              const pillarGoals = getGoalsByPillar(pillarCode);
              const pillar = pillars.find((p) => p.code === pillarCode);
              if (!pillar || pillarGoals.length === 0) return null;

              return (
                <div key={pillarCode}>
                  <div className="flex items-center gap-2 mb-2">
                    <PillarBadge
                      pillarId={pillarCode}
                      size="sm"
                      showIcon={false}
                      disableTooltip
                    />
                    <span className="text-xs font-medium text-gray-600 dark:text-gray-300">
                      {pillar.name}
                    </span>
                  </div>
                  <div className="space-y-1 ml-4">
                    {pillarGoals.map((goal) => (
                      <label
                        key={goal.code}
                        className="flex items-start gap-2 cursor-pointer group"
                      >
                        <input
                          type="checkbox"
                          checked={formData.goal_ids.includes(goal.code)}
                          onChange={() => onGoalToggle(goal.code)}
                          className="mt-0.5 h-4 w-4 text-brand-blue border-gray-300 dark:border-gray-500 rounded focus:ring-brand-blue"
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white">
                          <span className="font-mono text-xs text-gray-500 dark:text-gray-400 mr-1">
                            {goal.code}
                          </span>
                          {goal.name}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Section 2: Maturity Stages */}
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
            Maturity Stages
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Filter by how developed the technology or trend is. Early stages
            (1-3) catch emerging innovations. Later stages (5-8) find proven
            solutions ready for implementation.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {stages.map((stage) => (
            <button
              key={stage.stage}
              type="button"
              onClick={() => onStageToggle(stage.stage)}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-md border transition-colors",
                formData.stage_ids.includes(stage.stage.toString())
                  ? "bg-brand-light-blue dark:bg-brand-blue/20 border-brand-blue text-brand-dark-blue dark:text-brand-light-blue"
                  : "bg-white dark:bg-dark-surface-elevated border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
              )}
              aria-pressed={formData.stage_ids.includes(stage.stage.toString())}
              title={`${stage.name}: ${stage.description}`}
            >
              {stage.stage}. {stage.name}
            </button>
          ))}
        </div>
      </div>

      {/* Section 3: Time Horizon */}
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
            Time Horizon
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            How far into the future are you looking? Short-term (H1) finds
            immediately relevant signals. Long-term (H3) spots early weak
            signals.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            {
              code: "ALL",
              name: "All Horizons",
              timeframe: "All timeframes",
              description: "No time restriction",
            },
            ...horizons.map((h) => ({
              code: h.code,
              name: h.name,
              timeframe: h.timeframe,
              description: h.description,
            })),
          ].map((h) => (
            <button
              key={h.code}
              type="button"
              onClick={() => onHorizonChange(h.code)}
              className={cn(
                "flex flex-col items-start p-3 rounded-lg border transition-all text-left",
                formData.horizon === h.code
                  ? "bg-brand-light-blue dark:bg-brand-blue/20 border-brand-blue ring-2 ring-brand-blue/30"
                  : "bg-white dark:bg-dark-surface-elevated border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
              )}
              aria-pressed={formData.horizon === h.code}
            >
              <span
                className={cn(
                  "text-sm font-semibold",
                  formData.horizon === h.code
                    ? "text-brand-dark-blue dark:text-brand-light-blue"
                    : "text-gray-900 dark:text-white",
                )}
              >
                {h.code === "ALL" ? "All" : h.code}
              </span>
              <span
                className={cn(
                  "text-xs mt-0.5",
                  formData.horizon === h.code
                    ? "text-brand-blue dark:text-brand-light-blue"
                    : "text-gray-500 dark:text-gray-400",
                )}
              >
                {h.timeframe}
              </span>
              <span className="text-[11px] text-gray-400 dark:text-gray-500 mt-1">
                {h.description}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
