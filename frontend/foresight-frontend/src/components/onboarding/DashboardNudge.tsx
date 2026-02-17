/**
 * DashboardNudge
 *
 * A smart contextual nudge component that suggests next actions based on user
 * state. Shows at most one nudge at a time, in priority order. Each nudge type
 * is independently dismissible via localStorage.
 *
 * @module components/onboarding/DashboardNudge
 */

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { X, FolderOpen, Search, FileText } from "lucide-react";
import { cn } from "../../lib/utils";
import { isNudgeDismissed, dismissNudge } from "../../lib/onboarding-state";
import type { LucideIcon } from "lucide-react";

interface DashboardNudgeProps {
  stats: {
    following: number;
    workstreams: number;
  };
  className?: string;
}

interface NudgeConfig {
  type: string;
  priority: number;
  message: string;
  cta: string;
  href: string;
  icon: LucideIcon;
}

export function DashboardNudge({ stats, className }: DashboardNudgeProps) {
  const navigate = useNavigate();
  // Tracks locally-dismissed nudge types within this render lifecycle,
  // so dismissing a nudge triggers an immediate re-render.
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());

  const activeNudge = useMemo(() => {
    const nudges: NudgeConfig[] = [];

    // Priority 3 (lowest): Following grants but no programs
    if (stats.following > 0 && stats.workstreams === 0) {
      nudges.push({
        type: "create-program",
        priority: 3,
        message: `You're following ${stats.following} grant${stats.following !== 1 ? "s" : ""}! Create a program to organize them into a review workflow.`,
        cta: "Create Program",
        href: "/workstreams",
        icon: FolderOpen,
      });
    }

    // Priority 2: Has programs but few follows
    if (stats.workstreams > 0 && stats.following < 3) {
      nudges.push({
        type: "browse-grants",
        priority: 2,
        message:
          "Your programs are set up. Follow more grants in the Discover page to fill your pipeline.",
        cta: "Browse Grants",
        href: "/discover",
        icon: Search,
      });
    }

    // Priority 1 (highest): Solid pipeline
    if (stats.following > 5 && stats.workstreams > 0) {
      nudges.push({
        type: "start-application",
        priority: 1,
        message:
          "You've built a solid pipeline. Ready to apply? Our wizard walks you through every step.",
        cta: "Start Application",
        href: "/apply",
        icon: FileText,
      });
    }

    // Sort by priority ascending (1 = highest) and return the first non-dismissed
    nudges.sort((a, b) => a.priority - b.priority);

    return (
      nudges.find((n) => !isNudgeDismissed(n.type) && !dismissed.has(n.type)) ??
      null
    );
  }, [stats.following, stats.workstreams, dismissed]);

  if (!activeNudge) return null;

  const Icon = activeNudge.icon;

  const handleDismiss = () => {
    dismissNudge(activeNudge.type);
    setDismissed((prev) => new Set(prev).add(activeNudge.type));
  };

  return (
    <div
      className={cn(
        "bg-brand-blue/5 dark:bg-brand-blue/10",
        "border border-brand-blue/15 dark:border-brand-blue/20",
        "rounded-lg px-4 py-3",
        "motion-safe:animate-in motion-safe:fade-in-0",
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <Icon
          className="h-5 w-5 text-brand-blue flex-shrink-0"
          aria-hidden="true"
        />
        <p className="text-sm text-gray-700 dark:text-gray-300 flex-1 min-w-0">
          {activeNudge.message}
        </p>
        <button
          onClick={() => navigate(activeNudge.href)}
          className="text-xs text-brand-blue font-medium hover:underline flex-shrink-0 whitespace-nowrap"
        >
          {activeNudge.cta}
        </button>
        <button
          onClick={handleDismiss}
          className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded transition-colors flex-shrink-0"
          aria-label="Dismiss suggestion"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

export default DashboardNudge;
