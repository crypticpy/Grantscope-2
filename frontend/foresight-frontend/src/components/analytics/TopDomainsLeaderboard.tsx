/**
 * TopDomainsLeaderboard Component
 *
 * Displays a ranked leaderboard of the top source domains by composite reputation
 * score. Fetches data from the domain reputation API and presents it in a
 * professional table layout with tier badges, quality stars, and pass rates.
 *
 * Features:
 * - Top 20 domains ranked by composite score
 * - Search/filter input for finding specific domains
 * - Tier badges (Authoritative, Credible, General)
 * - Star-based user quality rating display
 * - Triage pass rate with visual indicator
 * - Loading skeleton and empty states
 * - Dark mode support
 */

import React, { useState, useEffect, useCallback } from "react";
import { Globe, Search, Shield, Star, Trophy, AlertCircle } from "lucide-react";
import { API_BASE_URL } from "../../lib/config";

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * A single domain entry from the top domains API response.
 */
interface DomainEntry {
  /** Unique identifier for the domain reputation record */
  id: string;
  /** The domain pattern (e.g. "nytimes.com") */
  domain_pattern: string;
  /** Display name of the organization behind the domain */
  organization_name: string;
  /** Content category of the domain */
  category: string;
  /** Curated tier: 1 = Authoritative, 2 = Credible, 3 = General, null = Unrated */
  curated_tier: number | null;
  /** Average user-submitted quality rating (0-5 scale) */
  user_quality_avg: number;
  /** Average user-submitted relevance rating (0-5 scale) */
  user_relevance_avg: number;
  /** Total number of user ratings for this domain */
  user_rating_count: number;
  /** Proportion of cards from this domain that pass triage (0-1) */
  triage_pass_rate: number;
  /** Overall composite reputation score (0-100) */
  composite_score: number;
  /** Bonus applied for Texas-relevant sources */
  texas_relevance_bonus: number;
}

/**
 * The backend GET /api/v1/analytics/top-domains returns a bare JSON array
 * of domain entries. The total is derived from the array length.
 */
type TopDomainsResponse = DomainEntry[];

// ============================================================================
// API Helper
// ============================================================================

/**
 * Fetch the top domains ranked by composite score.
 *
 * @param token - Bearer auth token (gs2_token)
 * @param limit - Maximum number of domains to return (default 20)
 * @returns The top domains response with ranked domain entries
 * @throws {Error} If the request fails or returns a non-OK status
 */
async function fetchTopDomains(
  token: string,
  limit: number = 20,
): Promise<TopDomainsResponse> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/analytics/top-domains?limit=${limit}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!res.ok) throw new Error("Failed to fetch top domains");
  return res.json();
}

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Tier badge with color coding by authority level.
 * Tier 1 = Authoritative (gold/green), Tier 2 = Credible (blue), Tier 3 = General (gray).
 */
const TierBadge: React.FC<{ tier: number | null }> = ({ tier }) => {
  if (tier === 1) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
        <Shield className="h-3 w-3" />
        Authoritative
      </span>
    );
  }
  if (tier === 2) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
        <Shield className="h-3 w-3" />
        Credible
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400">
      General
    </span>
  );
};

/**
 * Renders a row of filled and empty stars to represent a quality rating.
 * Displays up to 5 stars based on the provided rating value.
 */
const QualityStars: React.FC<{ rating: number; count: number }> = ({
  rating,
  count,
}) => {
  const fullStars = Math.round(rating);
  return (
    <div className="flex items-center gap-1">
      <div className="flex">
        {[1, 2, 3, 4, 5].map((i) => (
          <Star
            key={i}
            className={`h-3.5 w-3.5 ${
              i <= fullStars
                ? "text-amber-400 fill-amber-400"
                : "text-gray-300 dark:text-gray-600"
            }`}
          />
        ))}
      </div>
      {count > 0 && (
        <span className="text-xs text-gray-400 dark:text-gray-500 ml-0.5">
          ({count})
        </span>
      )}
    </div>
  );
};

/**
 * Visual bar indicator for triage pass rate percentage.
 */
const PassRateBar: React.FC<{ rate: number }> = ({ rate }) => {
  const pct = Math.round(rate * 100);
  const barColor =
    pct >= 80 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500";

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden max-w-[60px]">
        <div
          className={`h-full rounded-full ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-medium text-gray-600 dark:text-gray-300 w-9 text-right">
        {pct}%
      </span>
    </div>
  );
};

/**
 * Loading skeleton displayed while domain data is being fetched.
 */
const LeaderboardSkeleton: React.FC = () => (
  <div className="animate-pulse">
    <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded mb-4" />
    <div className="space-y-3">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4">
          <div className="w-8 h-6 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="flex-1 h-6 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="w-24 h-6 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="w-20 h-6 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
      ))}
    </div>
  </div>
);

/**
 * Empty state displayed when no domain reputation data exists.
 */
const LeaderboardEmptyState: React.FC = () => (
  <div className="text-center py-12">
    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-gray-100 dark:bg-gray-700 mb-4">
      <Globe className="h-6 w-6 text-gray-400" />
    </div>
    <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-1">
      No domain reputation data
    </h3>
    <p className="text-sm text-gray-500 dark:text-gray-400">
      Domain reputation scores will appear as sources are discovered and rated.
    </p>
  </div>
);

/**
 * Error state displayed when the API request fails.
 */
const LeaderboardError: React.FC<{ message: string; onRetry: () => void }> = ({
  message,
  onRetry,
}) => (
  <div className="flex items-start gap-3 p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700">
    <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
    <div className="flex-1">
      <h4 className="text-sm font-medium text-red-800 dark:text-red-200">
        Failed to load domain leaderboard
      </h4>
      <p className="text-sm text-red-700 dark:text-red-300 mt-1">{message}</p>
    </div>
    <button
      onClick={onRetry}
      className="text-sm text-red-600 dark:text-red-400 hover:underline flex-shrink-0"
    >
      Retry
    </button>
  </div>
);

// ============================================================================
// Main Component
// ============================================================================

/**
 * TopDomainsLeaderboard displays a ranked table of source domains sorted by
 * composite reputation score. It is designed for the analytics dashboard and
 * provides at-a-glance insight into which content sources are most trusted.
 */
const TopDomainsLeaderboard: React.FC = () => {
  const [domains, setDomains] = useState<DomainEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const loadDomains = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("gs2_token");
      if (!token) {
        throw new Error("Not authenticated");
      }
      const result = await fetchTopDomains(token, 20);
      setDomains(result);
      setTotal(result.length);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load domain data",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDomains();
  }, [loadDomains]);

  const filteredDomains = searchQuery.trim()
    ? domains.filter(
        (d) =>
          d.domain_pattern.toLowerCase().includes(searchQuery.toLowerCase()) ||
          d.organization_name.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : domains;

  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg shadow p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Trophy className="h-5 w-5 text-amber-500" />
          Top Source Domains
        </h3>
        {!loading && domains.length > 0 && (
          <span className="text-xs text-gray-400 dark:text-gray-500">
            {total} domains tracked
          </span>
        )}
      </div>

      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Highest-rated content sources ranked by composite reputation score
      </p>

      {/* Loading */}
      {loading && <LeaderboardSkeleton />}

      {/* Error */}
      {!loading && error && (
        <LeaderboardError message={error} onRetry={loadDomains} />
      )}

      {/* Empty */}
      {!loading && !error && domains.length === 0 && <LeaderboardEmptyState />}

      {/* Content */}
      {!loading && !error && domains.length > 0 && (
        <>
          {/* Search input */}
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Filter domains..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm bg-gray-50 dark:bg-dark-surface border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-blue/40 focus:border-brand-blue"
            />
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-2 pr-2 text-xs font-medium text-gray-500 dark:text-gray-400 w-10">
                    #
                  </th>
                  <th className="text-left py-2 pr-2 text-xs font-medium text-gray-500 dark:text-gray-400">
                    Domain
                  </th>
                  <th className="text-left py-2 pr-2 text-xs font-medium text-gray-500 dark:text-gray-400 hidden md:table-cell">
                    Organization
                  </th>
                  <th className="text-left py-2 pr-2 text-xs font-medium text-gray-500 dark:text-gray-400 hidden sm:table-cell">
                    Tier
                  </th>
                  <th className="text-left py-2 pr-2 text-xs font-medium text-gray-500 dark:text-gray-400 hidden lg:table-cell">
                    User Quality
                  </th>
                  <th className="text-left py-2 pr-2 text-xs font-medium text-gray-500 dark:text-gray-400 hidden lg:table-cell">
                    Pass Rate
                  </th>
                  <th className="text-right py-2 text-xs font-medium text-gray-500 dark:text-gray-400">
                    Score
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
                {filteredDomains.map((domain, idx) => {
                  const scoreColor =
                    domain.composite_score >= 80
                      ? "text-emerald-600 dark:text-emerald-400"
                      : domain.composite_score >= 60
                        ? "text-blue-600 dark:text-blue-400"
                        : domain.composite_score >= 40
                          ? "text-amber-600 dark:text-amber-400"
                          : "text-gray-600 dark:text-gray-400";

                  const scoreBg =
                    domain.composite_score >= 80
                      ? "bg-emerald-50 dark:bg-emerald-900/20"
                      : domain.composite_score >= 60
                        ? "bg-blue-50 dark:bg-blue-900/20"
                        : domain.composite_score >= 40
                          ? "bg-amber-50 dark:bg-amber-900/20"
                          : "bg-gray-50 dark:bg-gray-700/30";

                  return (
                    <tr
                      key={domain.id}
                      className="hover:bg-gray-50 dark:hover:bg-dark-surface-deep transition-colors"
                    >
                      {/* Rank */}
                      <td className="py-2.5 pr-2">
                        <span
                          className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                            idx < 3
                              ? "bg-gradient-to-br from-brand-blue to-brand-green text-white"
                              : "bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400"
                          }`}
                        >
                          {idx + 1}
                        </span>
                      </td>

                      {/* Domain */}
                      <td className="py-2.5 pr-2">
                        <div className="flex items-center gap-2">
                          <Globe className="h-4 w-4 text-gray-400 flex-shrink-0" />
                          <span className="font-medium text-gray-900 dark:text-white truncate max-w-[180px]">
                            {domain.domain_pattern}
                          </span>
                        </div>
                      </td>

                      {/* Organization */}
                      <td className="py-2.5 pr-2 hidden md:table-cell">
                        <span className="text-gray-600 dark:text-gray-300 truncate max-w-[160px] inline-block">
                          {domain.organization_name || "\u2014"}
                        </span>
                      </td>

                      {/* Tier */}
                      <td className="py-2.5 pr-2 hidden sm:table-cell">
                        <TierBadge tier={domain.curated_tier} />
                      </td>

                      {/* User Quality */}
                      <td className="py-2.5 pr-2 hidden lg:table-cell">
                        <QualityStars
                          rating={domain.user_quality_avg}
                          count={domain.user_rating_count}
                        />
                      </td>

                      {/* Triage Pass Rate */}
                      <td className="py-2.5 pr-2 hidden lg:table-cell">
                        <PassRateBar rate={domain.triage_pass_rate} />
                      </td>

                      {/* Composite Score */}
                      <td className="py-2.5 text-right">
                        <span
                          className={`inline-flex items-center justify-center px-2 py-0.5 rounded-md text-xs font-semibold ${scoreColor} ${scoreBg}`}
                        >
                          {domain.composite_score.toFixed(0)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Filter no-results */}
          {searchQuery.trim() && filteredDomains.length === 0 && (
            <div className="text-center py-6 text-sm text-gray-500 dark:text-gray-400">
              No domains matching "{searchQuery}"
            </div>
          )}

          {/* Footer */}
          <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700 flex justify-between text-xs text-gray-500 dark:text-gray-400">
            <span>
              Showing {filteredDomains.length} of {domains.length} top domains
            </span>
            <span>{total} total domains in system</span>
          </div>
        </>
      )}
    </div>
  );
};

export default TopDomainsLeaderboard;
