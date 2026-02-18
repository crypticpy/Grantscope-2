/**
 * GrantMatching - Grant matching step for the "build_program" wizard path
 *
 * After the interview, shows matching grants from the cards database
 * that align with the user's program. User can select one to continue
 * to proposal generation, or skip to export their plan.
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  Search,
  Loader2,
  Calendar,
  DollarSign,
  ArrowRight,
  ExternalLink,
  AlertCircle,
} from "lucide-react";
import { cn } from "../../lib/utils";
import {
  matchGrants,
  attachGrant,
  type MatchedGrant,
} from "../../lib/wizard-api";

interface GrantMatchingProps {
  sessionId: string;
  onGrantAttached: () => void;
  onSkip: () => void;
  onBack: () => void;
}

async function getToken(): Promise<string | null> {
  return localStorage.getItem("gs2_token") || null;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
}

const GrantMatching: React.FC<GrantMatchingProps> = ({
  sessionId,
  onGrantAttached,
  onSkip,
  onBack,
}) => {
  const [grants, setGrants] = useState<MatchedGrant[]>([]);
  const [loading, setLoading] = useState(true);
  const [attaching, setAttaching] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load matching grants on mount
  useEffect(() => {
    const load = async () => {
      const token = await getToken();
      if (!token) {
        setError("Not authenticated");
        setLoading(false);
        return;
      }

      try {
        const result = await matchGrants(token, sessionId);
        setGrants(result.grants);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to find matching grants",
        );
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [sessionId]);

  const handleSelectGrant = useCallback(
    async (cardId: string) => {
      const token = await getToken();
      if (!token) return;

      setAttaching(cardId);
      try {
        await attachGrant(token, sessionId, cardId);
        onGrantAttached();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to attach grant");
      } finally {
        setAttaching(null);
      }
    },
    [sessionId, onGrantAttached],
  );

  // Loading state
  if (loading) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-12 text-center">
        <Search className="h-10 w-10 text-brand-blue mx-auto mb-4 animate-pulse" />
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          Searching for matching grants...
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          We're analyzing your program against available grant opportunities.
        </p>
        <Loader2 className="h-5 w-5 animate-spin mx-auto mt-4 text-brand-blue" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
          Matching Grant Opportunities
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Based on your program details, here are grants that may be a good fit.
          Select one to start building a proposal, or skip to download your
          project plan.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
          <span className="text-sm text-red-700 dark:text-red-300">
            {error}
          </span>
        </div>
      )}

      {/* Grant cards */}
      {grants.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {grants.map((grant) => (
            <div
              key={grant.card_id}
              className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-5 hover:border-brand-blue/50 dark:hover:border-brand-blue/50 transition-colors"
            >
              <h3 className="font-semibold text-gray-900 dark:text-white mb-1 line-clamp-2">
                {grant.grant_name || "Untitled Grant"}
              </h3>
              {grant.grantor && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                  {grant.grantor}
                </p>
              )}
              {grant.summary && (
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-3 line-clamp-3">
                  {grant.summary}
                </p>
              )}
              <div className="flex flex-wrap gap-3 text-xs text-gray-500 dark:text-gray-400 mb-4">
                {grant.deadline && (
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5" />
                    {grant.deadline}
                  </span>
                )}
                {(grant.funding_amount_min || grant.funding_amount_max) && (
                  <span className="flex items-center gap-1">
                    <DollarSign className="h-3.5 w-3.5" />
                    {grant.funding_amount_min && grant.funding_amount_max
                      ? `${formatCurrency(grant.funding_amount_min)} - ${formatCurrency(grant.funding_amount_max)}`
                      : grant.funding_amount_max
                        ? `Up to ${formatCurrency(grant.funding_amount_max)}`
                        : `From ${formatCurrency(grant.funding_amount_min!)}`}
                  </span>
                )}
                {grant.grant_type && (
                  <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-xs capitalize">
                    {grant.grant_type}
                  </span>
                )}
              </div>
              <button
                onClick={() => handleSelectGrant(grant.card_id)}
                disabled={attaching !== null}
                className={cn(
                  "w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors",
                  attaching === grant.card_id
                    ? "bg-gray-100 dark:bg-gray-800 text-gray-400"
                    : "bg-brand-blue text-white hover:bg-brand-dark-blue",
                )}
              >
                {attaching === grant.card_id ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Attaching...
                  </>
                ) : (
                  <>
                    Select this grant
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
          <Search className="h-8 w-8 text-gray-400 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-1">
            No matching grants found
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            We couldn't find grants matching your program right now. You can
            still download your project plan and search for grants manually.
          </p>
          <a
            href="/signals"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-brand-blue hover:underline"
          >
            Browse all grants
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      )}

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        >
          Back to Plan
        </button>
        <button
          onClick={onSkip}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
        >
          Skip — download plan instead
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

export default GrantMatching;
