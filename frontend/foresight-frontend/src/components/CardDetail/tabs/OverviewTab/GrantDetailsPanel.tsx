/**
 * GrantDetailsPanel Component
 *
 * Displays grant-specific details for a card including grantor, funding range,
 * deadline urgency, eligibility, grant type, and external identifiers.
 *
 * Only renders when at least one grant field is populated on the card.
 *
 * @module CardDetail/tabs/OverviewTab/GrantDetailsPanel
 */

import React, { useState } from "react";
import {
  Building2,
  DollarSign,
  Clock,
  FileCheck,
  Tag,
  ExternalLink,
  Hash,
  BarChart3,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { cn } from "../../../../lib/utils";
import { getDeadlineUrgency } from "../../../../data/taxonomy";
import type { Card } from "../../types";

/**
 * Check if a URL is safe to render in an href attribute.
 * Only allows http: and https: protocols to prevent XSS via javascript: or data: URLs.
 */
function isSafeUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

/**
 * Props for the GrantDetailsPanel component
 */
export interface GrantDetailsPanelProps {
  /** The card data containing grant fields */
  card: Card;
  /** Optional custom CSS class name for the container */
  className?: string;
}

/**
 * Format a number as US currency
 */
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/**
 * Check if the card has at least one grant field populated
 */
function hasGrantData(card: Card): boolean {
  return !!(
    card.grantor ||
    card.deadline ||
    card.funding_amount_min ||
    card.funding_amount_max ||
    card.eligibility_text ||
    card.grant_type ||
    card.source_url ||
    card.cfda_number ||
    card.alignment_score != null ||
    card.grants_gov_id ||
    card.sam_opportunity_id
  );
}

/**
 * GrantDetailsPanel displays grant-specific information for a card.
 *
 * Features:
 * - Grantor name with building icon
 * - Funding range formatted as currency
 * - Deadline with urgency color coding
 * - Collapsible eligibility text
 * - Grant type badge
 * - External source URL link
 * - CFDA number display
 * - Alignment score progress bar (0-100)
 * - Grants.gov and SAM.gov identifiers
 * - Dark mode support
 *
 * Only renders if at least one grant field is populated.
 *
 * @example
 * ```tsx
 * <GrantDetailsPanel card={card} />
 * ```
 */
export const GrantDetailsPanel: React.FC<GrantDetailsPanelProps> = ({
  card,
  className = "",
}) => {
  const [eligibilityExpanded, setEligibilityExpanded] = useState(false);

  // Only render if at least one grant field is populated
  if (!hasGrantData(card)) {
    return null;
  }

  const urgency = card.deadline ? getDeadlineUrgency(card.deadline) : undefined;
  const daysUntil = card.deadline
    ? Math.ceil(
        (new Date(card.deadline).getTime() - new Date().getTime()) /
          (1000 * 60 * 60 * 24),
      )
    : null;

  const hasFundingRange =
    card.funding_amount_min != null || card.funding_amount_max != null;
  const eligibilityIsLong = (card.eligibility_text?.length ?? 0) > 150;

  return (
    <div
      className={cn(
        "bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6",
        className,
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Grant Details
        </h3>
        {card.grant_type && (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-brand-blue/10 text-brand-blue border border-brand-blue/30">
            {card.grant_type}
          </span>
        )}
      </div>

      {/* Details List */}
      <div className="space-y-3">
        {/* Grantor */}
        {card.grantor && (
          <div className="flex items-start gap-3">
            <Building2 className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Grantor
              </p>
              <p className="text-sm font-medium text-gray-900 dark:text-white break-words">
                {card.grantor}
              </p>
            </div>
          </div>
        )}

        {/* Funding Range */}
        {hasFundingRange && (
          <div className="flex items-start gap-3">
            <DollarSign className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Funding Range
              </p>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                {card.funding_amount_min != null &&
                card.funding_amount_max != null
                  ? `${formatCurrency(card.funding_amount_min)} - ${formatCurrency(card.funding_amount_max)}`
                  : card.funding_amount_min != null
                    ? `From ${formatCurrency(card.funding_amount_min)}`
                    : card.funding_amount_max != null
                      ? `Up to ${formatCurrency(card.funding_amount_max)}`
                      : ""}
              </p>
            </div>
          </div>
        )}

        {/* Deadline with Urgency */}
        {card.deadline && (
          <div className="flex items-start gap-3">
            <Clock className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Deadline
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-medium text-gray-900 dark:text-white">
                  {new Date(card.deadline).toLocaleDateString("en-US", {
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

        {/* Eligibility Text */}
        {card.eligibility_text && (
          <div className="flex items-start gap-3">
            <FileCheck className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
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
                {card.eligibility_text}
              </p>
              {eligibilityIsLong && (
                <button
                  type="button"
                  onClick={() => setEligibilityExpanded(!eligibilityExpanded)}
                  className="inline-flex items-center gap-1 mt-1 text-xs text-brand-blue hover:text-brand-dark-blue transition-colors"
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

        {/* Source URL */}
        {card.source_url && isSafeUrl(card.source_url) && (
          <div className="flex items-start gap-3">
            <ExternalLink className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-gray-500 dark:text-gray-400">Source</p>
              <a
                href={card.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-brand-blue hover:text-brand-dark-blue underline underline-offset-2 break-all transition-colors"
              >
                View Original Listing
              </a>
            </div>
          </div>
        )}

        {/* CFDA Number */}
        {card.cfda_number && (
          <div className="flex items-start gap-3">
            <Tag className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                CFDA Number
              </p>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                {card.cfda_number}
              </p>
            </div>
          </div>
        )}

        {/* Alignment Score */}
        {card.alignment_score != null && (
          <div className="flex items-start gap-3">
            <BarChart3 className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Alignment Score
                </p>
                <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                  {card.alignment_score}/100
                </span>
              </div>
              <div
                className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2"
                role="progressbar"
                aria-valuenow={card.alignment_score}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Alignment score: ${card.alignment_score}%`}
              >
                <div
                  className={cn(
                    "h-2 rounded-full transition-all",
                    card.alignment_score >= 80
                      ? "bg-green-500"
                      : card.alignment_score >= 60
                        ? "bg-amber-500"
                        : card.alignment_score >= 40
                          ? "bg-orange-500"
                          : "bg-red-500",
                  )}
                  style={{
                    width: `${Math.min(100, Math.max(0, card.alignment_score))}%`,
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {/* External Identifiers */}
        {(card.grants_gov_id || card.sam_opportunity_id) && (
          <div className="flex items-start gap-3">
            <Hash className="h-4 w-4 text-gray-400 dark:text-gray-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0 space-y-1">
              {card.grants_gov_id && (
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Grants.gov ID
                  </p>
                  <p className="text-sm font-mono text-gray-900 dark:text-white">
                    {card.grants_gov_id}
                  </p>
                </div>
              )}
              {card.sam_opportunity_id && (
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    SAM.gov Opportunity ID
                  </p>
                  <p className="text-sm font-mono text-gray-900 dark:text-white">
                    {card.sam_opportunity_id}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GrantDetailsPanel;
