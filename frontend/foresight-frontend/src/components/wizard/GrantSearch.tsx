/**
 * GrantSearch — Step 1b of the Grant Application Wizard
 *
 * A simplified grant browser for users who don't have a specific grant in mind.
 * Queries the cards table directly via the Supabase client, filtering for
 * grant-type cards, and lets the user select one to proceed with.
 */

import React, { useState, useEffect, useCallback } from "react";
import { Search, ArrowLeft, Clock, DollarSign } from "lucide-react";
import { supabase } from "../../App";
import { useDebounce } from "../../hooks/useDebounce";
import { getDeadlineUrgency } from "../../data/taxonomy";
import type { GrantContext } from "../../lib/wizard-api";

// ============================================================================
// Types
// ============================================================================

interface GrantSearchProps {
  sessionId: string;
  onGrantSelected: (
    cardId: string,
    grantContext: Partial<GrantContext>,
  ) => void;
  onBack: () => void;
}

interface GrantCard {
  id: string;
  name: string;
  summary: string | null;
  grantor: string | null;
  deadline: string | null;
  funding_amount_min: number | null;
  funding_amount_max: number | null;
  grant_type: string | null;
  source_url: string | null;
  alignment_score: number | null;
}

type GrantTypeFilter = "All" | "Federal" | "State" | "Foundation";
type DeadlineFilter = "All" | "30" | "60" | "90";
type FundingFilter = "All" | "under50k" | "50k-500k" | "over500k";

// ============================================================================
// Helpers
// ============================================================================

function formatCurrency(amount: number): string {
  if (amount >= 1_000_000) {
    return `$${(amount / 1_000_000).toFixed(1)}M`;
  }
  if (amount >= 1_000) {
    return `$${(amount / 1_000).toFixed(0)}K`;
  }
  return `$${amount.toLocaleString()}`;
}

function formatFundingRange(min: number | null, max: number | null): string {
  if (min != null && max != null) {
    return `${formatCurrency(min)} - ${formatCurrency(max)}`;
  }
  if (min != null) {
    return `From ${formatCurrency(min)}`;
  }
  if (max != null) {
    return `Up to ${formatCurrency(max)}`;
  }
  return "Not specified";
}

function getDaysRemaining(deadline: string): number {
  return Math.ceil(
    (new Date(deadline).getTime() - new Date().getTime()) /
      (1000 * 60 * 60 * 24),
  );
}

// ============================================================================
// Filter Chip Component
// ============================================================================

interface FilterChipProps<T extends string> {
  label: string;
  value: T;
  selected: boolean;
  onClick: (value: T) => void;
}

function FilterChip<T extends string>({
  label,
  value,
  selected,
  onClick,
}: FilterChipProps<T>) {
  return (
    <button
      type="button"
      onClick={() => onClick(value)}
      className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors min-h-[44px] min-w-[44px] ${
        selected
          ? "bg-brand-blue text-white"
          : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
      }`}
    >
      {label}
    </button>
  );
}

// ============================================================================
// Skeleton Card
// ============================================================================

const SkeletonCard: React.FC = () => (
  <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm p-5 animate-pulse">
    <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-3" />
    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-4" />
    <div className="flex gap-3 mb-3">
      <div className="h-6 w-20 bg-gray-200 dark:bg-gray-700 rounded-full" />
      <div className="h-6 w-24 bg-gray-200 dark:bg-gray-700 rounded-full" />
    </div>
    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full mb-2" />
    <div className="h-9 bg-gray-200 dark:bg-gray-700 rounded w-32 mt-4" />
  </div>
);

// ============================================================================
// Main Component
// ============================================================================

export const GrantSearch: React.FC<GrantSearchProps> = ({
  sessionId: _sessionId,
  onGrantSelected,
  onBack,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [grantType, setGrantType] = useState<GrantTypeFilter>("All");
  const [deadlineFilter, setDeadlineFilter] = useState<DeadlineFilter>("All");
  const [fundingFilter, setFundingFilter] = useState<FundingFilter>("All");

  const [results, setResults] = useState<GrantCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const debouncedSearch = useDebounce(searchTerm, 300);

  // --------------------------------------------------------------------------
  // Data fetching
  // --------------------------------------------------------------------------

  const fetchGrants = useCallback(async () => {
    setLoading(true);
    try {
      let query = supabase
        .from("cards")
        .select(
          "id, name, summary, grantor, deadline, funding_amount_min, funding_amount_max, grant_type, source_url, alignment_score",
        )
        .or("grant_type.not.is.null,grantor.not.is.null")
        .order("deadline", { ascending: true, nullsFirst: false })
        .limit(20);

      // Text search
      if (debouncedSearch.trim()) {
        query = query.ilike("name", `%${debouncedSearch.trim()}%`);
      }

      // Grant type filter
      if (grantType !== "All") {
        query = query.ilike("grant_type", `%${grantType}%`);
      }

      // Deadline filter
      if (deadlineFilter !== "All") {
        const days = parseInt(deadlineFilter, 10);
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() + days);
        query = query
          .gte("deadline", new Date().toISOString())
          .lte("deadline", cutoff.toISOString());
      }

      // Funding filter
      if (fundingFilter === "under50k") {
        query = query.lte("funding_amount_max", 50000);
      } else if (fundingFilter === "50k-500k") {
        query = query
          .gte("funding_amount_min", 50000)
          .lte("funding_amount_max", 500000);
      } else if (fundingFilter === "over500k") {
        query = query.gte("funding_amount_min", 500000);
      }

      const { data, error } = await query;

      if (error) {
        console.error("Grant search error:", error);
        setResults([]);
      } else {
        setResults((data as GrantCard[]) || []);
      }
    } catch (err) {
      console.error("Grant search failed:", err);
      setResults([]);
    } finally {
      setLoading(false);
      setHasSearched(true);
    }
  }, [debouncedSearch, grantType, deadlineFilter, fundingFilter]);

  // Trigger fetch when filters/search change
  useEffect(() => {
    fetchGrants();
  }, [fetchGrants]);

  // --------------------------------------------------------------------------
  // Selection handler
  // --------------------------------------------------------------------------

  const handleSelect = (card: GrantCard) => {
    const grantContext: Partial<GrantContext> = {
      grant_name: card.name,
      grantor: card.grantor,
      deadline: card.deadline,
      funding_amount_min: card.funding_amount_min,
      funding_amount_max: card.funding_amount_max,
      grant_type: card.grant_type,
      summary: card.summary,
    };
    onGrantSelected(card.id, grantContext);
  };

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-6">
      {/* Back link */}
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-brand-blue dark:hover:text-brand-blue transition-colors mb-6 min-h-[44px]"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to welcome
      </button>

      {/* Search input */}
      <div className="relative mb-5">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input
          type="text"
          placeholder="Search for grants..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-11 pr-4 py-3 border border-gray-300 dark:border-gray-600 bg-white dark:bg-dark-surface-elevated text-gray-900 dark:text-gray-100 rounded-lg shadow-sm focus:ring-2 focus:ring-brand-blue focus:border-brand-blue sm:text-sm min-h-[44px]"
        />
      </div>

      {/* Filter chips */}
      <div className="space-y-3 mb-6">
        {/* Grant Type */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 w-20 shrink-0">
            Type
          </span>
          {(["All", "Federal", "State", "Foundation"] as GrantTypeFilter[]).map(
            (v) => (
              <FilterChip
                key={v}
                label={v}
                value={v}
                selected={grantType === v}
                onClick={setGrantType}
              />
            ),
          )}
        </div>

        {/* Deadline */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 w-20 shrink-0">
            Deadline
          </span>
          {[
            { value: "All" as DeadlineFilter, label: "All" },
            { value: "30" as DeadlineFilter, label: "30 days" },
            { value: "60" as DeadlineFilter, label: "60 days" },
            { value: "90" as DeadlineFilter, label: "90 days" },
          ].map((item) => (
            <FilterChip
              key={item.value}
              label={item.label}
              value={item.value}
              selected={deadlineFilter === item.value}
              onClick={setDeadlineFilter}
            />
          ))}
        </div>

        {/* Funding */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 w-20 shrink-0">
            Funding
          </span>
          {[
            { value: "All" as FundingFilter, label: "All" },
            { value: "under50k" as FundingFilter, label: "Under $50K" },
            { value: "50k-500k" as FundingFilter, label: "$50K-$500K" },
            { value: "over500k" as FundingFilter, label: "Over $500K" },
          ].map((item) => (
            <FilterChip
              key={item.value}
              label={item.label}
              value={item.value}
              selected={fundingFilter === item.value}
              onClick={setFundingFilter}
            />
          ))}
        </div>
      </div>

      {/* Results area */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : !hasSearched ? (
        <div className="text-center py-12">
          <Search className="mx-auto h-10 w-10 text-gray-300 dark:text-gray-600 mb-3" />
          <p className="text-gray-500 dark:text-gray-400 text-sm max-w-md mx-auto">
            Search for grants by keyword, or browse by type and deadline.
          </p>
        </div>
      ) : results.length === 0 ? (
        <div className="text-center py-12">
          <Search className="mx-auto h-10 w-10 text-gray-300 dark:text-gray-600 mb-3" />
          <p className="text-gray-500 dark:text-gray-400 text-sm max-w-md mx-auto">
            No grants match your search. Try broader terms or paste a URL for a
            specific grant.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {results.map((card) => {
            const daysLeft = card.deadline
              ? getDaysRemaining(card.deadline)
              : null;
            const urgency = card.deadline
              ? getDeadlineUrgency(card.deadline)
              : undefined;

            return (
              <div
                key={card.id}
                className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm hover:shadow-md transition-shadow p-5"
              >
                {/* Title */}
                <h3 className="font-semibold text-gray-900 dark:text-white line-clamp-2 mb-1">
                  {card.name}
                </h3>

                {/* Grantor */}
                {card.grantor && (
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
                    {card.grantor}
                  </p>
                )}

                {/* Funding + Deadline row */}
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  {/* Funding */}
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded-full">
                    <DollarSign className="w-3 h-3" />
                    {formatFundingRange(
                      card.funding_amount_min,
                      card.funding_amount_max,
                    )}
                  </span>

                  {/* Deadline badge */}
                  {daysLeft != null && daysLeft >= 0 && urgency && (
                    <span
                      className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full"
                      style={{
                        backgroundColor: urgency.colorLight,
                        color: urgency.color,
                      }}
                    >
                      <Clock className="w-3 h-3" />
                      {daysLeft}d left
                    </span>
                  )}
                </div>

                {/* Summary */}
                {card.summary && (
                  <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-1 mb-4">
                    {card.summary}
                  </p>
                )}

                {/* Select button */}
                <button
                  type="button"
                  onClick={() => handleSelect(card)}
                  className="inline-flex items-center px-4 py-2 bg-brand-blue hover:bg-brand-blue/90 text-white text-sm font-medium rounded-lg transition-colors min-h-[44px]"
                >
                  Select this grant
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default GrantSearch;
