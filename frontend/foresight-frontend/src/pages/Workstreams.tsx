import React, { useState, useEffect, useRef, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Plus,
  FolderOpen,
  Pencil,
  Trash2,
  AlertTriangle,
  HelpCircle,
  X,
  Sparkles,
  FileText,
  Filter,
  ArrowRight,
  Inbox,
  Search,
  ClipboardList,
  Eye,
  Archive,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Radar,
  Loader2,
} from "lucide-react";
import { API_BASE_URL } from "../lib/config";
import { WorkstreamForm, type Workstream } from "../components/WorkstreamForm";
import { WorkstreamWizard } from "../components/workstream/WorkstreamWizard";
import { PillarBadgeGroup } from "../components/PillarBadge";
import { getGoalByCode } from "../data/taxonomy";
import { cn } from "../lib/utils";
import { useFocusTrap } from "../hooks/useFocusTrap";
import {
  getWorkstreamScanStatus,
  type WorkstreamScanStatusResponse,
} from "../lib/workstream-api";

// ============================================================================
// Delete Confirmation Modal
// ============================================================================

interface DeleteConfirmModalProps {
  workstream: Workstream;
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting: boolean;
}

function DeleteConfirmModal({
  workstream,
  onConfirm,
  onCancel,
  isDeleting,
}: DeleteConfirmModalProps) {
  const focusTrapRef = useFocusTrap(true);

  return (
    <div
      ref={focusTrapRef}
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50"
    >
      <div className="bg-white dark:bg-dark-surface rounded-xl shadow-2xl max-w-md w-full p-6">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0 w-10 h-10 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
            <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">
              Delete Program
            </h3>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
              Are you sure you want to delete{" "}
              <span className="font-semibold">"{workstream.name}"</span>? This
              action cannot be undone.
            </p>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isDeleting}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-dark-surface-elevated border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-dark-surface-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDeleting}
            className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 transition-colors"
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Workstream Form Modal
// ============================================================================

interface FormModalProps {
  workstream?: Workstream;
  onSuccess: (createdId?: string, scanTriggered?: boolean) => void;
  onCancel: () => void;
}

function FormModal({ workstream, onSuccess, onCancel }: FormModalProps) {
  const isCreateMode = !workstream;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50 overflow-y-auto">
      <div
        className={cn(
          "bg-white dark:bg-dark-surface rounded-xl shadow-2xl w-full my-8",
          isCreateMode
            ? "max-w-3xl max-h-[90vh] flex flex-col"
            : "max-w-2xl max-h-[90vh] overflow-y-auto",
        )}
      >
        {isCreateMode ? (
          /* Wizard for create mode - no sticky header, wizard manages its own layout */
          <WorkstreamWizard onSuccess={onSuccess} onCancel={onCancel} />
        ) : (
          /* Flat form for edit mode */
          <>
            <div className="sticky top-0 bg-white dark:bg-dark-surface border-b border-gray-200 dark:border-gray-700 px-6 py-4 rounded-t-lg">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                Edit Program
              </h3>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Update the filters and settings for this program.
              </p>
            </div>
            <div className="px-6 py-4">
              <WorkstreamForm
                workstream={workstream}
                onSuccess={onSuccess}
                onCancel={onCancel}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Workstream Help Banner
// ============================================================================

const BANNER_DISMISSED_KEY = "workstream-banner-dismissed";

interface WorkstreamHelpBannerProps {
  onDismiss: () => void;
}

function WorkstreamHelpBanner({ onDismiss }: WorkstreamHelpBannerProps) {
  const [expanded, setExpanded] = useState(false);

  const kanbanColumns = [
    {
      name: "Inbox",
      icon: Inbox,
      color: "bg-blue-100 dark:bg-blue-900/30",
      description: "New opportunities awaiting triage",
    },
    {
      name: "Screening",
      icon: Filter,
      color: "bg-amber-100 dark:bg-amber-900/30",
      description: "Evaluating relevance",
    },
    {
      name: "Research",
      icon: Search,
      color: "bg-purple-100 dark:bg-purple-900/30",
      description: "Active investigation",
    },
    {
      name: "Brief",
      icon: FileText,
      color: "bg-green-100 dark:bg-green-900/30",
      description: "Ready for leadership",
    },
    {
      name: "Watching",
      icon: Eye,
      color: "bg-cyan-100 dark:bg-cyan-900/30",
      description: "Monitoring developments",
    },
    {
      name: "Archived",
      icon: Archive,
      color: "bg-gray-100 dark:bg-gray-800/50",
      description: "Completed or dismissed",
    },
  ];

  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden mb-6">
      {/* Gradient accent strip */}
      <div className="bg-gradient-to-r from-brand-blue to-brand-green h-1 rounded-t-lg" />

      {/* Collapsed content: description + learn more + dismiss */}
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
              Programs are personalized grant tracking workspaces. Define filter
              criteria to automatically collect and track relevant opportunities
              through a structured review workflow.
            </p>
            <button
              onClick={() => setExpanded(!expanded)}
              className="inline-flex items-center gap-1 mt-2 text-sm font-medium text-brand-blue hover:text-brand-dark-blue dark:text-brand-light-blue dark:hover:text-white transition-colors"
            >
              {expanded ? "Show less" : "Learn more"}
              {expanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </button>
          </div>
          <button
            onClick={onDismiss}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded transition-colors flex-shrink-0"
            aria-label="Dismiss banner"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Expanded content */}
        {expanded && (
          <div className="mt-5 space-y-6 border-t border-gray-200 dark:border-gray-700 pt-5">
            {/* Introduction */}
            <div className="bg-brand-light-blue/30 dark:bg-brand-blue/10 rounded-lg p-4 border border-brand-blue/20">
              <p className="text-gray-700 dark:text-gray-300 leading-relaxed text-sm">
                A{" "}
                <strong className="text-brand-dark-blue dark:text-brand-light-blue">
                  Program
                </strong>{" "}
                is a personalized grant tracking workspace that helps you
                organize and track opportunities relevant to a specific focus
                area. Think of it as a customized feed combined with a Kanban
                board for grant categories you care about.
              </p>
            </div>

            {/* How to Create Section */}
            <div>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                <Plus className="h-4 w-4 text-brand-blue" />
                Creating a Program
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="bg-gray-50 dark:bg-dark-surface/50 rounded-lg p-3">
                  <h4 className="font-medium text-gray-900 dark:text-white text-sm mb-1">
                    1. Define Your Focus
                  </h4>
                  <p className="text-xs text-gray-600 dark:text-gray-400">
                    Give your program a name like "Infrastructure Grants" or
                    "Climate Resilience Funding"
                  </p>
                </div>
                <div className="bg-gray-50 dark:bg-dark-surface/50 rounded-lg p-3">
                  <h4 className="font-medium text-gray-900 dark:text-white text-sm mb-1">
                    2. Set Filter Criteria
                  </h4>
                  <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-brand-blue" />
                      Strategic Pillars & Goals
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-brand-blue" />
                      Maturity Stages (1-8)
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-brand-blue" />
                      Time Horizon (H1, H2, H3)
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-brand-blue" />
                      Keywords
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Kanban Workflow Section */}
            <div>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                <ClipboardList className="h-4 w-4 text-brand-blue" />
                Research Workflow
              </h3>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
                Opportunities in your program flow through a Kanban board as you
                evaluate them:
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                {kanbanColumns.map((col, idx) => (
                  <div key={col.name} className="relative">
                    <div
                      className={cn("rounded-lg p-3 text-center", col.color)}
                    >
                      <col.icon className="h-4 w-4 mx-auto mb-1 text-gray-600 dark:text-gray-300" />
                      <div className="text-xs font-medium text-gray-900 dark:text-white">
                        {col.name}
                      </div>
                      <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-1 leading-tight">
                        {col.description}
                      </div>
                    </div>
                    {idx < kanbanColumns.length - 1 && (
                      <ArrowRight className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-gray-400 z-10" />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Features Section */}
            <div>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-brand-blue" />
                What You Can Do
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="flex items-start gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700">
                  <div className="p-1.5 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                    <Sparkles className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white text-xs">
                      Auto-Populate
                    </h4>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
                      AI finds and adds matching opportunities to your inbox
                      automatically
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700">
                  <div className="p-1.5 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                    <Search className="h-3.5 w-3.5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white text-xs">
                      Deep Dive Research
                    </h4>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
                      Trigger comprehensive AI analysis on any opportunity
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700">
                  <div className="p-1.5 bg-green-100 dark:bg-green-900/30 rounded-lg">
                    <FileText className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                  </div>
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white text-xs">
                      Executive Briefs
                    </h4>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
                      Generate leadership-ready summaries with version history
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700">
                  <div className="p-1.5 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
                    <ClipboardList className="h-3.5 w-3.5 text-orange-600 dark:text-orange-400" />
                  </div>
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white text-xs">
                      Notes & Reminders
                    </h4>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
                      Add context-specific notes and set follow-up reminders
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Getting Started CTA */}
            <div className="bg-gradient-to-r from-brand-blue/10 to-brand-green/10 rounded-lg p-4 border border-brand-blue/20">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-gray-900 dark:text-white text-sm">
                    Ready to get started?
                  </h4>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                    Create your first program to begin organizing your grant
                    pipeline.
                  </p>
                </div>
                <button
                  onClick={() => setExpanded(false)}
                  className="inline-flex items-center px-3 py-1.5 bg-brand-blue text-white text-xs font-medium rounded-lg hover:bg-brand-dark-blue transition-colors"
                >
                  Got it
                  <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Workstream Card
// ============================================================================

interface WorkstreamCardProps {
  workstream: Workstream;
  onEdit: () => void;
  onDelete: () => void;
  scanStatus?: WorkstreamScanStatusResponse | null;
}

function WorkstreamCard({
  workstream,
  onEdit,
  onDelete,
  scanStatus,
}: WorkstreamCardProps) {
  // Format stage IDs for display
  const formatStages = (stageIds: string[]): string => {
    if (stageIds.length === 0) return "";
    const nums = stageIds.map(Number).sort((a, b) => a - b);
    // Check if consecutive range
    const first = nums[0];
    const last = nums[nums.length - 1];
    if (
      nums.length > 2 &&
      first !== undefined &&
      last !== undefined &&
      last - first === nums.length - 1
    ) {
      return `${first}-${last}`;
    }
    return nums.join(", ");
  };

  const handleEditClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onEdit();
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onDelete();
  };

  return (
    <Link
      to={`/workstreams/${workstream.id}/board`}
      className="block bg-white dark:bg-dark-surface overflow-hidden rounded-xl shadow transition-all duration-200 hover:-translate-y-1 hover:shadow-lg cursor-pointer"
    >
      {/* Gradient accent bar */}
      <div className="bg-gradient-to-r from-brand-blue to-brand-green h-1" />

      <div className="p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-xl font-semibold tracking-tight text-gray-900 dark:text-white truncate">
              {workstream.name}
            </h3>
            {workstream.description && (
              <p className="text-gray-600 dark:text-gray-300 text-sm mt-1 line-clamp-2">
                {workstream.description}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 ml-4 flex-wrap justify-end">
            {/* Scan running indicator */}
            {scanStatus &&
              (scanStatus.status === "queued" ||
                scanStatus.status === "running") && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Scanning...
                </span>
              )}
            {/* Auto-scan badge */}
            {workstream.auto_scan && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                <Radar className="h-3 w-3" />
                Auto-scan
              </span>
            )}
            {workstream.is_active ? (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                Active
              </span>
            ) : (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
                Inactive
              </span>
            )}
          </div>
        </div>

        {/* Filter Summary */}
        <div className="space-y-3 text-sm">
          {/* Pillars */}
          {workstream.pillar_ids.length > 0 && (
            <div>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-1.5">
                Pillars
              </span>
              <PillarBadgeGroup
                pillarIds={workstream.pillar_ids}
                size="sm"
                maxVisible={6}
              />
            </div>
          )}

          {/* Goals */}
          {workstream.goal_ids.length > 0 && (
            <div>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-1">
                Goals
              </span>
              <div className="text-gray-600 dark:text-gray-300 text-sm">
                {workstream.goal_ids.length <= 3
                  ? workstream.goal_ids
                      .map((id) => {
                        const goal = getGoalByCode(id);
                        return goal ? `${goal.code}` : id;
                      })
                      .join(", ")
                  : `${workstream.goal_ids.length} goals selected`}
              </div>
            </div>
          )}

          {/* Stages and Horizon */}
          <div className="flex flex-wrap gap-4">
            {workstream.stage_ids.length > 0 && (
              <div>
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-1">
                  Stages
                </span>
                <span className="text-gray-600 dark:text-gray-300">
                  {formatStages(workstream.stage_ids)}
                </span>
              </div>
            )}

            {workstream.horizon && workstream.horizon !== "ALL" && (
              <div>
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-1">
                  Horizon
                </span>
                <span className="text-gray-600 dark:text-gray-300">
                  {workstream.horizon}
                </span>
              </div>
            )}
          </div>

          {/* Keywords */}
          {workstream.keywords.length > 0 && (
            <div>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide block mb-1.5">
                Keywords
              </span>
              <div className="flex flex-wrap gap-1.5">
                {workstream.keywords.slice(0, 5).map((keyword) => (
                  <span
                    key={keyword}
                    className="inline-flex px-2 py-0.5 rounded-full bg-brand-light-blue text-brand-blue dark:bg-brand-blue/20 dark:text-brand-light-blue text-xs font-medium"
                  >
                    {keyword}
                  </span>
                ))}
                {workstream.keywords.length > 5 && (
                  <span className="inline-flex px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 text-xs">
                    +{workstream.keywords.length - 5} more
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500 dark:text-gray-400">
              Created {new Date(workstream.created_at).toLocaleDateString()}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={handleEditClick}
                className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-dark-surface-elevated border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-dark-surface-hover focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-brand-blue transition-colors"
                aria-label={`Edit ${workstream.name}`}
              >
                <Pencil className="h-3.5 w-3.5 mr-1" />
                Edit
              </button>
              <button
                onClick={handleDeleteClick}
                className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium text-red-700 dark:text-red-400 bg-white dark:bg-dark-surface-elevated border border-red-300 dark:border-red-500/50 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-red-500 transition-colors"
                aria-label={`Delete ${workstream.name}`}
              >
                <Trash2 className="h-3.5 w-3.5 mr-1" />
                Delete
              </button>
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}

// ============================================================================
// Main Component
// ============================================================================

const Workstreams: React.FC = () => {
  const navigate = useNavigate();
  const [workstreams, setWorkstreams] = useState<Workstream[]>([]);
  const [loading, setLoading] = useState(true);

  // Error state (replaces alert())
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modal states
  const [showForm, setShowForm] = useState(false);
  const [editingWorkstream, setEditingWorkstream] = useState<
    Workstream | undefined
  >(undefined);
  const [deletingWorkstream, setDeletingWorkstream] = useState<
    Workstream | undefined
  >(undefined);
  const [isDeleting, setIsDeleting] = useState(false);

  // Scan status for each workstream (keyed by workstream ID)
  const [scanStatuses, setScanStatuses] = useState<
    Record<string, WorkstreamScanStatusResponse>
  >({});
  const scanPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const workstreamsRef = useRef<Workstream[]>([]);

  // Banner dismissed state (persisted in localStorage)
  const [bannerDismissed, setBannerDismissed] = useState(() => {
    try {
      return localStorage.getItem(BANNER_DISMISSED_KEY) === "true";
    } catch {
      return false;
    }
  });

  const handleDismissBanner = () => {
    setBannerDismissed(true);
    try {
      localStorage.setItem(BANNER_DISMISSED_KEY, "true");
    } catch {
      // localStorage may be unavailable
    }
  };

  const handleRestoreBanner = () => {
    setBannerDismissed(false);
    try {
      localStorage.removeItem(BANNER_DISMISSED_KEY);
    } catch {
      // localStorage may be unavailable
    }
  };

  useEffect(() => {
    loadWorkstreams();
  }, []);

  const fetchScanStatuses = useCallback(async () => {
    const wsList = workstreamsRef.current;
    if (wsList.length === 0) return;

    const token = localStorage.getItem("gs2_token");
    if (!token) return;

    const statuses: Record<string, WorkstreamScanStatusResponse> = {};
    let hasActiveScans = false;

    // Fetch latest scan status for each workstream (in parallel, but with concurrency limit)
    const results = await Promise.allSettled(
      wsList.map(async (ws) => {
        try {
          const status = await getWorkstreamScanStatus(token, ws.id);
          return { id: ws.id, status };
        } catch {
          // No scan found for this workstream, that's fine
          return null;
        }
      }),
    );

    for (const result of results) {
      if (result.status === "fulfilled" && result.value) {
        const { id, status } = result.value;
        statuses[id] = status;
        if (status.status === "queued" || status.status === "running") {
          hasActiveScans = true;
        }
      }
    }

    setScanStatuses(statuses);

    // If there are active scans, poll periodically
    if (hasActiveScans) {
      if (!scanPollRef.current) {
        scanPollRef.current = setInterval(() => {
          fetchScanStatuses();
        }, 5000);
      }
    } else if (scanPollRef.current) {
      clearInterval(scanPollRef.current);
      scanPollRef.current = null;
    }
  }, []);

  const loadWorkstreams = async () => {
    try {
      const token = localStorage.getItem("gs2_token");
      if (!token) {
        setLoading(false);
        return;
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/me/workstreams`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data: Workstream[] = await response.json();
      // Sort by created_at descending (in case API doesn't guarantee order)
      const list = data.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
      setWorkstreams(list);
      workstreamsRef.current = list;

      // Fetch scan statuses for all active workstreams
      if (list.length > 0) {
        fetchScanStatuses();
      }
    } catch (error) {
      console.error("Error loading workstreams:", error);
    } finally {
      setLoading(false);
    }
  };

  // Cleanup scan polling on unmount
  useEffect(() => {
    return () => {
      if (scanPollRef.current) {
        clearInterval(scanPollRef.current);
      }
    };
  }, []);

  const handleFormSuccess = (createdId?: string, scanTriggered?: boolean) => {
    setShowForm(false);
    setEditingWorkstream(undefined);

    if (createdId && scanTriggered) {
      // Navigate to the kanban board so user can see scan progress
      navigate(`/workstreams/${createdId}/board`, {
        state: { scanJustStarted: true },
      });
    } else {
      loadWorkstreams();
    }
  };

  const handleFormCancel = () => {
    setShowForm(false);
    setEditingWorkstream(undefined);
  };

  const handleEditClick = (workstream: Workstream) => {
    setEditingWorkstream(workstream);
    setShowForm(true);
  };

  const handleDeleteClick = (workstream: Workstream) => {
    setDeletingWorkstream(workstream);
  };

  const handleDeleteConfirm = async () => {
    if (!deletingWorkstream) return;

    setIsDeleting(true);
    try {
      const token = localStorage.getItem("gs2_token");
      if (!token) throw new Error("Authentication required");

      const response = await fetch(
        `${API_BASE_URL}/api/v1/me/workstreams/${deletingWorkstream.id}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        throw new Error(errBody.detail || `Delete failed: ${response.status}`);
      }

      setDeletingWorkstream(undefined);
      loadWorkstreams();
    } catch (error) {
      console.error("Error deleting workstream:", error);
      setErrorMessage("Failed to delete program. Please try again.");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeletingWorkstream(undefined);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-brand-blue"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-3xl font-bold text-brand-dark-blue dark:text-white">
              Programs
            </h1>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              Create custom research programs based on your grant priorities.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {bannerDismissed && (
              <button
                onClick={handleRestoreBanner}
                className="p-2 text-gray-400 hover:text-brand-blue hover:bg-brand-light-blue/30 dark:hover:bg-brand-blue/20 rounded-lg transition-colors"
                aria-label="Show program help"
                title="Show program help"
              >
                <HelpCircle className="h-5 w-5" />
              </button>
            )}
            <Link
              to="/guide/workstreams"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-500 dark:text-gray-400 hover:text-brand-blue dark:hover:text-brand-light-blue hover:bg-brand-light-blue/30 dark:hover:bg-brand-blue/20 rounded-lg transition-colors"
            >
              <BookOpen className="h-4 w-4" />
              How to use
            </Link>
          </div>
        </div>
        <button
          onClick={() => {
            setEditingWorkstream(undefined);
            setShowForm(true);
          }}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue transition-colors"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Program
        </button>
      </div>

      {/* Error Banner */}
      {errorMessage && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm flex items-center justify-between">
          <span>{errorMessage}</span>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="ml-2 text-red-500 hover:text-red-700"
          >
            &#x2715;
          </button>
        </div>
      )}

      {/* Help Banner */}
      {!bannerDismissed && (
        <WorkstreamHelpBanner onDismiss={handleDismissBanner} />
      )}

      {/* Workstreams List */}
      {workstreams.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-dark-surface rounded-lg shadow">
          <FolderOpen className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-lg font-medium text-gray-900 dark:text-white">
            No programs yet
          </h3>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
            A program groups grants around a focus area, like &ldquo;Public
            Safety Grants&rdquo; or &ldquo;Youth Services Funding&rdquo;.
            GrantScope automatically finds matching opportunities and adds them
            to your review board.
          </p>
          <ol className="text-sm text-gray-500 dark:text-gray-400 space-y-2 mb-4 mt-4 text-left max-w-sm mx-auto">
            <li className="flex gap-2">
              <span className="text-brand-blue font-semibold shrink-0">1.</span>
              <span>Name your program and describe your focus area</span>
            </li>
            <li className="flex gap-2">
              <span className="text-brand-blue font-semibold shrink-0">2.</span>
              <span>Set keywords and filters to match relevant grants</span>
            </li>
            <li className="flex gap-2">
              <span className="text-brand-blue font-semibold shrink-0">3.</span>
              <span>
                GrantScope fills your board with matching opportunities
                automatically
              </span>
            </li>
          </ol>
          <div className="mt-6 flex flex-col items-center gap-3">
            <button
              onClick={() => {
                setEditingWorkstream(undefined);
                setShowForm(true);
              }}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue transition-colors"
            >
              <Plus className="h-4 w-4 mr-2" />
              Create Program
            </button>
            <Link
              to="/guide/workstreams"
              className="text-xs text-brand-blue hover:underline"
            >
              Learn more about programs
            </Link>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-4">
            Not sure where to start?{" "}
            <Link
              to="/ask?scope=grant_assistant"
              className="text-brand-blue hover:underline"
            >
              Ask GrantScope
            </Link>{" "}
            can help you identify grants and set up a program.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {workstreams.map((workstream) => (
            <WorkstreamCard
              key={workstream.id}
              workstream={workstream}
              onEdit={() => handleEditClick(workstream)}
              onDelete={() => handleDeleteClick(workstream)}
              scanStatus={scanStatuses[workstream.id] || null}
            />
          ))}
        </div>
      )}

      {/* Form Modal */}
      {showForm && (
        <FormModal
          workstream={editingWorkstream}
          onSuccess={handleFormSuccess}
          onCancel={handleFormCancel}
        />
      )}

      {/* Delete Confirmation Modal */}
      {deletingWorkstream && (
        <DeleteConfirmModal
          workstream={deletingWorkstream}
          onConfirm={handleDeleteConfirm}
          onCancel={handleDeleteCancel}
          isDeleting={isDeleting}
        />
      )}
    </div>
  );
};

export default Workstreams;
