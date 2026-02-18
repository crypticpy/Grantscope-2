/**
 * myApplicationsUtils
 *
 * Pure helper functions and constants shared by the MyApplications
 * dashboard section and its presentational sub-components.
 *
 * @module components/dashboard/myApplicationsUtils
 */

import type { WizardSession } from "../../lib/wizard-api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const STEP_LABELS = [
  "Welcome",
  "Grant Details",
  "Interview",
  "Plan Review",
  "Proposal",
  "Export",
];

export const TOTAL_STEPS = STEP_LABELS.length;

/** Maximum number of application cards shown before truncation. */
export const MAX_VISIBLE = 6;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Returns a human-readable phase label and corresponding Tailwind classes
 * based on the session's current step and status.
 */
export function getPhaseInfo(session: WizardSession): {
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

/**
 * Derives a display title for a wizard session from its grant context
 * or entry path.
 */
export function getSessionTitle(session: WizardSession): string {
  if (session.grant_context?.grant_name) {
    return session.grant_context.grant_name;
  }
  if (session.entry_path === "build_program") {
    return "Program Draft";
  }
  return "Grant Application";
}

/**
 * Returns a display label and Tailwind classes for the session's entry path.
 */
export function getEntryPathLabel(entryPath: string): {
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

/**
 * Converts an ISO date string into a short relative-time label
 * (e.g. "Just now", "5m ago", "2d ago").
 */
export function relativeTime(dateStr: string | null): string {
  if (!dateStr) return "";
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  if (isNaN(then)) return "";
  const diffMs = now - then;
  if (diffMs < 0) return "Just now";
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

/**
 * Returns a deadline proximity warning (label + classes) when the deadline
 * is within 30 days, or `null` if no warning is needed.
 */
export function deadlineWarning(
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
