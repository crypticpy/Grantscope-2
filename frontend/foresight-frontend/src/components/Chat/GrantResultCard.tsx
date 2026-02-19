/**
 * GrantResultCard Component
 *
 * Compact grant result card for inline display in chat messages.
 * Shows grant name, funder, funding range, deadline, fit level, and quick actions.
 * Used by the AI's markdown output for enhanced rendering of grant search results.
 *
 * @module components/Chat/GrantResultCard
 */

import { cn } from "../../lib/utils";

// ============================================================================
// Types
// ============================================================================

interface GrantResultCardProps {
  /** Name/title of the grant opportunity */
  grantName: string;
  /** Granting organization or funder */
  grantor?: string;
  /** Minimum funding amount in dollars */
  fundingMin?: number | null;
  /** Maximum funding amount in dollars */
  fundingMax?: number | null;
  /** Application deadline as ISO date string */
  deadline?: string | null;
  /** Grant type (e.g. "Federal", "State", "Foundation") */
  grantType?: string | null;
  /** Fit assessment level (e.g. "Strong Fit", "Moderate Fit") */
  fitLevel?: string | null;
  /** Slug for internal signal/card navigation */
  cardSlug?: string | null;
  /** External URL to the grant listing */
  sourceUrl?: string | null;
  /** Callback to track this opportunity */
  onTrack?: () => void;
}

// ============================================================================
// Helpers
// ============================================================================

/** Formats a dollar amount into a compact human-readable string. */
function formatCurrency(amount: number): string {
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(0)}K`;
  return `$${amount.toLocaleString()}`;
}

/** Determines deadline urgency based on days until due. */
function getDeadlineUrgency(
  deadline: string,
): "urgent" | "soon" | "normal" | "past" {
  const d = new Date(deadline);
  const now = new Date();
  const daysUntil = Math.ceil(
    (d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
  );
  if (daysUntil < 0) return "past";
  if (daysUntil <= 14) return "urgent";
  if (daysUntil <= 45) return "soon";
  return "normal";
}

const urgencyColors: Record<ReturnType<typeof getDeadlineUrgency>, string> = {
  urgent: "text-red-600 dark:text-red-400",
  soon: "text-amber-600 dark:text-amber-400",
  normal: "text-gray-600 dark:text-gray-400",
  past: "text-gray-400 dark:text-gray-500 line-through",
};

const fitColors: Record<string, string> = {
  "Strong Fit":
    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  "Moderate Fit":
    "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  "Weak Fit":
    "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  "Likely Not Eligible":
    "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
};

// ============================================================================
// Component
// ============================================================================

export default function GrantResultCard({
  grantName,
  grantor,
  fundingMin,
  fundingMax,
  deadline,
  grantType,
  fitLevel,
  cardSlug,
  sourceUrl,
  onTrack,
}: GrantResultCardProps) {
  const fundingRange = (() => {
    if (fundingMin != null && fundingMax != null) {
      return `${formatCurrency(fundingMin)} \u2013 ${formatCurrency(fundingMax)}`;
    }
    if (fundingMax != null) return `Up to ${formatCurrency(fundingMax)}`;
    if (fundingMin != null) return `From ${formatCurrency(fundingMin)}`;
    return null;
  })();

  const deadlineUrgency = deadline ? getDeadlineUrgency(deadline) : null;

  return (
    <div
      className={cn(
        "border border-gray-200 dark:border-dark-border rounded-lg p-3 my-2",
        "bg-white dark:bg-dark-card",
        "hover:shadow-sm transition-shadow",
      )}
    >
      {/* Top row: grant name + fit badge */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {cardSlug ? (
              <a
                href={`/signals/${cardSlug}`}
                className="font-medium text-brand-blue hover:underline truncate"
              >
                {grantName}
              </a>
            ) : sourceUrl ? (
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-brand-blue hover:underline truncate"
              >
                {grantName}
              </a>
            ) : (
              <span className="font-medium text-gray-900 dark:text-gray-100 truncate">
                {grantName}
              </span>
            )}
            {grantType && (
              <span
                className={cn(
                  "inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium shrink-0",
                  "bg-gray-100 text-gray-600 dark:bg-dark-border dark:text-gray-400",
                )}
              >
                {grantType}
              </span>
            )}
          </div>
          {grantor && (
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5 truncate">
              {grantor}
            </p>
          )}
        </div>
        {fitLevel && (
          <span
            className={cn(
              "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium shrink-0",
              fitColors[fitLevel] || "bg-gray-100 text-gray-600",
            )}
          >
            {fitLevel}
          </span>
        )}
      </div>

      {/* Details row: funding + deadline */}
      <div className="flex items-center gap-4 mt-2 text-sm">
        {fundingRange && (
          <span className="text-gray-700 dark:text-gray-300">
            {fundingRange}
          </span>
        )}
        {deadline && deadlineUrgency && (
          <span className={urgencyColors[deadlineUrgency]}>
            {deadlineUrgency === "past"
              ? "Expired"
              : `Due ${new Date(deadline).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`}
          </span>
        )}
      </div>

      {/* Track action */}
      {onTrack && (
        <div className="mt-2 pt-2 border-t border-gray-100 dark:border-dark-border">
          <button
            onClick={onTrack}
            className="text-xs text-brand-blue hover:text-brand-blue/80 font-medium"
          >
            + Track this opportunity
          </button>
        </div>
      )}
    </div>
  );
}
