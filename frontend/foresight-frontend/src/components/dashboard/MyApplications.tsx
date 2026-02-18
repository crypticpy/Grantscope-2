/**
 * MyApplications
 *
 * Dashboard section that displays the user's active wizard sessions
 * (grant applications and program drafts). Shows progress, deadlines,
 * and quick-resume navigation for each application.
 *
 * @module components/dashboard/MyApplications
 */

import { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  FileText,
  Plus,
  ArrowRight,
  Clock,
  AlertTriangle,
  ClipboardList,
} from "lucide-react";
import { listWizardSessions } from "../../lib/wizard-api";
import type { WizardSession } from "../../lib/wizard-api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STEP_LABELS = [
  "Welcome",
  "Grant Details",
  "Interview",
  "Plan Review",
  "Proposal",
  "Export",
];

const TOTAL_STEPS = STEP_LABELS.length;
const MAX_VISIBLE = 6;

type FilterTab = "in_progress" | "completed" | "all";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getPhaseInfo(session: WizardSession): {
  label: string;
  classes: string;
} {
  if (session.status === "completed" || session.current_step >= 5) {
    return {
      label: "Complete",
      classes:
        "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
    };
  }
  if (session.current_step === 4) {
    return {
      label: "Proposal",
      classes:
        "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
    };
  }
  if (session.current_step === 3) {
    return {
      label: "Planning",
      classes:
        "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
    };
  }
  if (session.current_step === 2) {
    return {
      label: "Interview",
      classes:
        "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    };
  }
  return {
    label: "Getting Started",
    classes: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300",
  };
}

function getSessionTitle(session: WizardSession): string {
  if (session.grant_context?.grant_name) {
    return session.grant_context.grant_name;
  }
  if (session.entry_path === "build_program") {
    return "Program Draft";
  }
  return "Grant Application";
}

function getEntryPathLabel(entryPath: string): {
  label: string;
  classes: string;
} {
  if (entryPath === "build_program") {
    return {
      label: "Program Development",
      classes:
        "bg-brand-blue/10 text-brand-blue dark:bg-brand-blue/20 dark:text-blue-300",
    };
  }
  return {
    label: "Grant Application",
    classes:
      "bg-extended-purple/10 text-extended-purple dark:bg-extended-purple/20 dark:text-purple-300",
  };
}

function relativeTime(dateStr: string | null): string {
  if (!dateStr) return "";
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 30) return `${diffDays}d ago`;
  const diffMonths = Math.floor(diffDays / 30);
  return `${diffMonths}mo ago`;
}

function deadlineWarning(
  deadline: string | null,
): { label: string; classes: string } | null {
  if (!deadline) return null;
  const now = Date.now();
  const dl = new Date(deadline).getTime();
  const daysLeft = Math.ceil((dl - now) / (1000 * 60 * 60 * 24));
  if (daysLeft < 0) {
    return {
      label: "Past due",
      classes: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    };
  }
  if (daysLeft <= 7) {
    return {
      label: `${daysLeft}d left`,
      classes: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    };
  }
  if (daysLeft <= 30) {
    return {
      label: `${daysLeft}d left`,
      classes:
        "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
    };
  }
  return null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface MyApplicationsProps {
  token: string;
}

export function MyApplications({ token }: MyApplicationsProps) {
  const [sessions, setSessions] = useState<WizardSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<FilterTab>("all");

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await listWizardSessions(token);
        if (!cancelled) {
          // Filter out abandoned sessions
          setSessions(data.filter((s) => s.status !== "abandoned"));
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load applications",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const filtered = useMemo(() => {
    if (activeTab === "all") return sessions;
    return sessions.filter((s) => s.status === activeTab);
  }, [sessions, activeTab]);

  const visible = filtered.slice(0, MAX_VISIBLE);
  const hasMore = filtered.length > MAX_VISIBLE;

  // -----------------------------------------------------------------------
  // Loading skeleton
  // -----------------------------------------------------------------------
  if (loading) {
    return (
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-4">
          <div className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded h-6 w-40" />
        </div>
        <div className="flex gap-4 overflow-x-auto pb-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="animate-pulse bg-gray-200 dark:bg-gray-700/50 rounded-xl h-40 w-72 flex-shrink-0"
              style={{ animationDelay: `${i * 80}ms` }}
            />
          ))}
        </div>
      </div>
    );
  }

  // -----------------------------------------------------------------------
  // Error state (silent — just hide section)
  // -----------------------------------------------------------------------
  if (error) {
    return null;
  }

  // -----------------------------------------------------------------------
  // Empty state
  // -----------------------------------------------------------------------
  if (sessions.length === 0) {
    return (
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-4">
          <ClipboardList className="h-5 w-5 text-brand-blue" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            My Applications
          </h2>
        </div>
        <div className="text-center py-10 bg-white dark:bg-dark-surface rounded-xl shadow">
          <FileText className="h-10 w-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            No applications yet
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-4 max-w-xs mx-auto">
            Start by applying for a grant or documenting your program.
          </p>
          <Link
            to="/apply"
            className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors"
          >
            <Plus className="h-4 w-4 mr-2" />
            Start New Application
          </Link>
        </div>
      </div>
    );
  }

  // -----------------------------------------------------------------------
  // Tabs & Cards
  // -----------------------------------------------------------------------
  const tabs: { key: FilterTab; label: string }[] = [
    { key: "all", label: "All" },
    { key: "in_progress", label: "In Progress" },
    { key: "completed", label: "Completed" },
  ];

  return (
    <div className="mb-8">
      {/* Section header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-brand-blue" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            My Applications
          </h2>
        </div>
        <div className="flex items-center gap-3">
          {hasMore && (
            <Link
              to="/apply"
              className="text-sm text-brand-blue hover:underline"
            >
              View All
            </Link>
          )}
          <Link
            to="/apply"
            className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md text-brand-blue bg-brand-blue/10 hover:bg-brand-blue/20 dark:bg-brand-blue/20 dark:hover:bg-brand-blue/30 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Start New
          </Link>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
              activeTab === tab.key
                ? "bg-brand-blue text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Cards — horizontal scroll */}
      {visible.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400 py-4">
          No {activeTab === "completed" ? "completed" : "in-progress"}{" "}
          applications.
        </p>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2 -mx-1 px-1">
          {visible.map((session, index) => {
            const phase = getPhaseInfo(session);
            const title = getSessionTitle(session);
            const entryPath = getEntryPathLabel(session.entry_path);
            const deadline = deadlineWarning(
              session.grant_context?.deadline ?? null,
            );
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
          })}
        </div>
      )}
    </div>
  );
}

export default MyApplications;
