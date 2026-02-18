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
import { FileText, Plus, ClipboardList } from "lucide-react";
import { listWizardSessions } from "../../lib/wizard-api";
import type { WizardSession } from "../../lib/wizard-api";
import { MAX_VISIBLE } from "./myApplicationsUtils";
import { MyApplicationsCard } from "./MyApplicationsCard";

type FilterTab = "in_progress" | "completed" | "all";

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
      setLoading(true);
      setError(null);
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
            <span className="text-xs text-gray-500 dark:text-gray-400">
              (showing {MAX_VISIBLE} of {filtered.length})
            </span>
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
          {visible.map((session, index) => (
            <MyApplicationsCard
              key={session.id}
              session={session}
              index={index}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default MyApplications;
