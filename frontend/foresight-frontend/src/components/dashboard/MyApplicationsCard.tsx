/**
 * MyApplicationsCard
 *
 * Presentational card component for a single wizard session in the
 * My Applications dashboard section. Displays title, phase badge,
 * progress bar, deadline warning, entry path label, and relative time.
 *
 * @module components/dashboard/MyApplicationsCard
 */

import { Link } from "react-router-dom";
import { ArrowRight, Clock, AlertTriangle } from "lucide-react";
import type { WizardSession } from "../../lib/wizard-api";
import {
  TOTAL_STEPS,
  getPhaseInfo,
  getSessionTitle,
  getEntryPathLabel,
  relativeTime,
  deadlineWarning,
} from "./myApplicationsUtils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MyApplicationsCardProps {
  session: WizardSession;
  index: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MyApplicationsCard({
  session,
  index,
}: MyApplicationsCardProps) {
  const phase = getPhaseInfo(session);
  const title = getSessionTitle(session);
  const entryPath = getEntryPathLabel(session.entry_path);
  const deadline = deadlineWarning(session.grant_context?.deadline ?? null);
  const updated = relativeTime(session.updated_at);

  return (
    <Link
      key={session.id}
      to={`/apply/${session.id}`}
      className="flex-shrink-0 w-72 bg-white dark:bg-dark-surface rounded-xl shadow p-5 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg group"
      style={{
        animationDelay: `${Math.min(index, 5) * 50}ms`,
        animationFillMode: "both",
      }}
    >
      {/* Top row: entry path + deadline warning */}
      <div className="flex items-center justify-between mb-3">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${entryPath.classes}`}
        >
          {entryPath.label}
        </span>
        {deadline && (
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${deadline.classes}`}
          >
            <AlertTriangle className="h-3 w-3" />
            {deadline.label}
          </span>
        )}
      </div>

      {/* Title */}
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2 line-clamp-2 group-hover:text-brand-blue transition-colors">
        {title}
      </h3>

      {/* Phase badge + step progress */}
      <div className="flex items-center gap-2 mb-3">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${phase.classes}`}
        >
          {phase.label}
        </span>
        <span className="text-[11px] text-gray-500 dark:text-gray-400">
          Step {Math.min(session.current_step + 1, TOTAL_STEPS)} of{" "}
          {TOTAL_STEPS}
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full mb-3">
        <div
          className="h-full bg-brand-blue rounded-full transition-all duration-300"
          style={{
            width: `${Math.min(((session.current_step + 1) / TOTAL_STEPS) * 100, 100)}%`,
          }}
        />
      </div>

      {/* Footer: updated time + arrow */}
      <div className="flex items-center justify-between">
        {updated && (
          <span className="flex items-center gap-1 text-[11px] text-gray-400 dark:text-gray-500">
            <Clock className="h-3 w-3" />
            {updated}
          </span>
        )}
        <ArrowRight className="h-4 w-4 text-gray-300 dark:text-gray-600 group-hover:text-brand-blue group-hover:translate-x-0.5 transition-all" />
      </div>
    </Link>
  );
}

export default MyApplicationsCard;
