/**
 * GrantRequirementsCard Component
 *
 * Displays extracted grant context in a clean summary card.
 * Used by GrantInput after AI extraction to present the grant details
 * for user review before proceeding.
 *
 * @module wizard/GrantRequirementsCard
 */

import React, { useState } from "react";
import {
  Building2,
  Clock,
  DollarSign,
  Tag,
  ChevronDown,
  ChevronUp,
  CheckSquare,
  Square,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { getDeadlineUrgency } from "../../data/taxonomy";
import type { GrantContext } from "../../lib/wizard-api";

// =============================================================================
// Props
// =============================================================================

export interface GrantRequirementsCardProps {
  grantContext: GrantContext;
  className?: string;
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Format a number as US currency.
 */
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

// =============================================================================
// Component
// =============================================================================

export const GrantRequirementsCard: React.FC<GrantRequirementsCardProps> = ({
  grantContext,
  className,
}) => {
  const [eligibilityExpanded, setEligibilityExpanded] = useState(false);

  const {
    grant_name,
    grantor,
    cfda_number,
    deadline,
    funding_amount_min,
    funding_amount_max,
    grant_type,
    eligibility_text,
    requirements,
    summary,
  } = grantContext;

  // Deadline calculations
  const daysUntil = deadline
    ? Math.ceil(
        (new Date(deadline).getTime() - new Date().getTime()) /
          (1000 * 60 * 60 * 24),
      )
    : null;
  const urgency = deadline ? getDeadlineUrgency(deadline) : undefined;

  const hasFundingRange =
    funding_amount_min != null || funding_amount_max != null;
  const eligibilityIsLong = (eligibility_text?.length ?? 0) > 150;

  return (
    <div
      className={cn(
        "bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm p-4 sm:p-6",
        className,
      )}
    >
      {/* Header: Grant name + type badge */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white leading-tight">
          {grant_name || "Untitled Grant"}
        </h2>
        {grant_type && (
          <span className="inline-flex items-center flex-shrink-0 px-2.5 py-0.5 rounded-full text-xs font-medium bg-brand-blue/10 text-brand-blue border border-brand-blue/30">
            {grant_type}
          </span>
        )}
      </div>

      {/* Details grid */}
      <div className="space-y-3">
        {/* Grantor */}
        {grantor && (
          <div className="flex items-start gap-3">
            <Building2 className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Grantor
              </p>
              <p className="text-sm font-medium text-gray-900 dark:text-white break-words">
                {grantor}
              </p>
            </div>
          </div>
        )}

        {/* Deadline with urgency */}
        {deadline && (
          <div className="flex items-start gap-3">
            <Clock className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Deadline
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-medium text-gray-900 dark:text-white">
                  {new Date(deadline).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </p>
                {urgency && daysUntil != null && daysUntil >= 0 && (
                  <span
                    className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                    style={{
                      backgroundColor: urgency.colorLight,
                      color: urgency.color,
                    }}
                  >
                    {urgency.name} ({daysUntil}d)
                  </span>
                )}
                {daysUntil != null && daysUntil < 0 && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
                    Expired
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Funding range */}
        {hasFundingRange && (
          <div className="flex items-start gap-3">
            <DollarSign className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Funding Range
              </p>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                {funding_amount_min != null && funding_amount_max != null
                  ? `${formatCurrency(funding_amount_min)} - ${formatCurrency(funding_amount_max)}`
                  : funding_amount_min != null
                    ? `From ${formatCurrency(funding_amount_min)}`
                    : funding_amount_max != null
                      ? `Up to ${formatCurrency(funding_amount_max)}`
                      : ""}
              </p>
            </div>
          </div>
        )}

        {/* CFDA number */}
        {cfda_number && (
          <div className="flex items-start gap-3">
            <Tag className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                CFDA Number
              </p>
              <p className="text-sm font-mono font-medium text-gray-900 dark:text-white">
                {cfda_number}
              </p>
            </div>
          </div>
        )}

        {/* Eligibility text (collapsible) */}
        {eligibility_text && (
          <div className="flex items-start gap-3">
            <Building2 className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Eligibility
              </p>
              <p
                className={cn(
                  "text-sm text-gray-700 dark:text-gray-300 break-words",
                  !eligibilityExpanded && eligibilityIsLong && "line-clamp-3",
                )}
              >
                {eligibility_text}
              </p>
              {eligibilityIsLong && (
                <button
                  type="button"
                  onClick={() => setEligibilityExpanded(!eligibilityExpanded)}
                  className="inline-flex items-center gap-1 mt-1 text-xs text-brand-blue hover:text-brand-dark-blue transition-colors"
                  aria-expanded={eligibilityExpanded}
                >
                  {eligibilityExpanded ? (
                    <>
                      Show less <ChevronUp className="h-3 w-3" />
                    </>
                  ) : (
                    <>
                      Show more <ChevronDown className="h-3 w-3" />
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Key requirements checklist */}
        {requirements && requirements.length > 0 && (
          <div className="pt-2">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
              Key Requirements
            </p>
            <ul className="space-y-1.5" role="list">
              {requirements.map((req, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  {req.is_mandatory ? (
                    <CheckSquare
                      className="h-4 w-4 text-brand-blue flex-shrink-0 mt-0.5"
                      aria-label="Mandatory"
                    />
                  ) : (
                    <Square
                      className="h-4 w-4 text-gray-400 dark:text-gray-500 flex-shrink-0 mt-0.5"
                      aria-label="Optional"
                    />
                  )}
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    <span className="font-medium text-gray-900 dark:text-white">
                      {req.category}:
                    </span>{" "}
                    {req.description}
                    {req.is_mandatory && (
                      <span className="ml-1 text-xs text-red-500 dark:text-red-400 font-medium">
                        (required)
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Summary */}
        {summary && (
          <div className="pt-2 border-t border-gray-100 dark:border-gray-700">
            <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
              {summary}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default GrantRequirementsCard;
