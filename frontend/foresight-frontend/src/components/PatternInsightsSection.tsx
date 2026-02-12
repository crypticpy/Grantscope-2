import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Sparkles, ArrowRight } from "lucide-react";
import { PillarBadge } from "./PillarBadge";
import { supabase } from "../App";
import { cn } from "../lib/utils";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PatternInsight {
  id: string;
  pattern_title: string;
  pattern_summary: string;
  opportunity?: string;
  confidence: number;
  affected_pillars: string[];
  urgency: "high" | "medium" | "low";
  related_card_ids: string[];
  status: string;
  created_at: string;
}

interface PatternInsightsProps {
  className?: string;
}

// ---------------------------------------------------------------------------
// Urgency badge config
// ---------------------------------------------------------------------------

const urgencyConfig: Record<
  PatternInsight["urgency"],
  { label: string; classes: string }
> = {
  high: {
    label: "Urgent",
    classes: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  },
  medium: {
    label: "Notable",
    classes:
      "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  },
  low: {
    label: "Emerging",
    classes:
      "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PatternInsightsSection({ className }: PatternInsightsProps) {
  const [insights, setInsights] = useState<PatternInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function fetchInsights() {
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session?.access_token) {
          setError(true);
          return;
        }

        const res = await fetch(
          `${API_BASE_URL}/api/v1/pattern-insights?status=active&limit=3`,
          {
            headers: {
              Authorization: `Bearer ${session.access_token}`,
              "Content-Type": "application/json",
            },
          },
        );

        if (!res.ok) {
          setError(true);
          return;
        }

        const data: PatternInsight[] = await res.json();
        if (!cancelled) {
          setInsights(data);
        }
      } catch {
        if (!cancelled) {
          setError(true);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchInsights();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return null;

  if (loading) {
    return (
      <section className={cn(className)}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-brand-blue" />
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              AI-Detected Patterns
            </h2>
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-gray-700 p-4 animate-pulse"
            >
              <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-3" />
              <div className="space-y-2">
                <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-full" />
                <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-5/6" />
                <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-2/3" />
              </div>
              <div className="flex gap-1 mt-3">
                <div className="h-5 w-10 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-5 w-10 bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
              <div className="mt-3">
                <div className="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full w-full" />
              </div>
              <div className="flex items-center justify-between mt-3">
                <div className="h-5 w-16 bg-gray-200 dark:bg-gray-700 rounded-full" />
                <div className="h-4 w-14 bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (insights.length === 0) {
    return (
      <section className={cn(className)}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-brand-blue" />
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              AI-Detected Patterns
            </h2>
          </div>
        </div>
        <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl p-8 flex flex-col items-center justify-center text-center">
          <Sparkles className="h-8 w-8 text-gray-400 mb-3" />
          <p className="text-sm font-medium text-gray-600 dark:text-gray-300">
            No patterns detected yet
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Cross-signal patterns emerge as your intelligence library grows.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className={cn(className)}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-brand-blue" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            AI-Detected Patterns
          </h2>
        </div>
        <Link
          to="/ask"
          className="text-sm text-brand-blue hover:underline flex items-center gap-1"
        >
          View All
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {insights.map((insight) => {
          const urgency = urgencyConfig[insight.urgency] ?? urgencyConfig.low;
          return (
            <div
              key={insight.id}
              className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-gray-700 p-4 hover:shadow-md transition-shadow"
            >
              <h3 className="font-semibold text-sm text-gray-900 dark:text-white">
                {insight.pattern_title}
              </h3>
              <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-3 mt-1.5">
                {insight.pattern_summary}
              </p>
              {insight.affected_pillars.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1">
                  {insight.affected_pillars.map((pillar) => (
                    <PillarBadge
                      key={pillar}
                      pillarId={pillar}
                      size="sm"
                      showIcon={false}
                    />
                  ))}
                </div>
              )}
              <div className="mt-3">
                <span className="text-[10px] text-gray-500 dark:text-gray-400 font-medium">
                  Confidence
                </span>
                <div className="h-1.5 rounded-full bg-gray-200 dark:bg-gray-700 mt-0.5">
                  <div
                    className="h-1.5 rounded-full bg-brand-blue"
                    style={{ width: `${insight.confidence * 100}%` }}
                  />
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <span
                  className={cn(
                    "text-[10px] font-medium px-2 py-0.5 rounded-full",
                    urgency.classes,
                  )}
                >
                  {urgency.label}
                </span>
                <Link
                  to={`/ask?q=${encodeURIComponent(insight.pattern_title)}`}
                  className="text-xs text-brand-blue hover:underline flex items-center gap-0.5"
                >
                  Explore
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default PatternInsightsSection;
