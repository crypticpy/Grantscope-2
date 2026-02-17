/**
 * ProposalPreview - Step 5 of the Grant Application Wizard
 *
 * Generates a full 6-section grant proposal from the wizard session data,
 * then displays a tab-based section editor for review and editing.
 *
 * Sections: Executive Summary, Needs Statement, Project Description,
 *           Budget Narrative, Timeline, Evaluation Plan
 *
 * Features:
 * - Auto-generates proposal on mount if proposalId is null
 * - Per-section loading progress indicators
 * - Tab-based section navigation (scrollable on mobile)
 * - Inline section editing with save
 * - AI draft accept/dismiss workflow
 * - Editable proposal title
 * - Dark mode support
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Loader2,
  Sparkles,
  Save,
  Edit3,
  CheckCircle2,
  ArrowLeft,
  ArrowRight,
  FileText,
  X,
} from "lucide-react";
import { cn } from "../../lib/utils";
import {
  generateWizardProposal,
  type GrantContext,
} from "../../lib/wizard-api";
import {
  getProposal,
  updateProposal,
  type Proposal,
  type SectionName,
} from "../../lib/proposal-api";

// =============================================================================
// Types
// =============================================================================

interface ProposalPreviewProps {
  sessionId: string;
  proposalId: string | null;
  grantContext?: GrantContext | null;
  onComplete: () => void;
  onBack: () => void;
}

// =============================================================================
// Constants
// =============================================================================

const SECTIONS: { key: SectionName; label: string }[] = [
  { key: "executive_summary", label: "Executive Summary" },
  { key: "needs_statement", label: "Needs Statement" },
  { key: "project_description", label: "Project Description" },
  { key: "budget_narrative", label: "Budget Narrative" },
  { key: "timeline", label: "Timeline" },
  { key: "evaluation_plan", label: "Evaluation Plan" },
];

// =============================================================================
// Helper
// =============================================================================

async function getToken(): Promise<string | null> {
  const token = localStorage.getItem("gs2_token");
  return token || null;
}

// =============================================================================
// Component
// =============================================================================

export const ProposalPreview: React.FC<ProposalPreviewProps> = ({
  sessionId,
  proposalId: initialProposalId,
  grantContext,
  onComplete,
  onBack,
}) => {
  // ---- State ----
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [proposalId, setProposalId] = useState<string | null>(
    initialProposalId,
  );
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<SectionName>("executive_summary");
  const [editingSection, setEditingSection] = useState<SectionName | null>(
    null,
  );
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [generationProgress, setGenerationProgress] = useState(0);

  const tabsRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // ---- Generate proposal if needed ----
  const generateAndLoad = useCallback(async () => {
    const token = await getToken();
    if (!token) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    try {
      setGenerating(true);
      setGenerationProgress(0);

      // Simulate progress while generation runs
      const progressInterval = setInterval(() => {
        setGenerationProgress((prev) => {
          if (prev >= 90) return prev;
          return prev + Math.random() * 15;
        });
      }, 800);

      // Generate proposal via wizard API
      const updatedSession = await generateWizardProposal(token, sessionId);
      clearInterval(progressInterval);
      setGenerationProgress(100);

      const newProposalId = updatedSession.proposal_id;
      if (!newProposalId) {
        throw new Error(
          "Proposal generation completed but no proposal ID was returned",
        );
      }

      setProposalId(newProposalId);

      // Fetch the full proposal
      const proposalData = await getProposal(token, newProposalId);
      setProposal(proposalData);
      setGenerating(false);
      setLoading(false);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to generate proposal",
      );
      setGenerating(false);
      setLoading(false);
    }
  }, [sessionId]);

  const loadExistingProposal = useCallback(async (id: string) => {
    const token = await getToken();
    if (!token) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    try {
      const proposalData = await getProposal(token, id);
      setProposal(proposalData);
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load proposal");
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (proposalId) {
      loadExistingProposal(proposalId);
    } else {
      generateAndLoad();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- Focus textarea when editing starts ----
  useEffect(() => {
    if (editingSection && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [editingSection]);

  // ---- Section helpers ----
  const getSectionContent = (key: SectionName): string => {
    if (!proposal?.sections) return "";
    const section = proposal.sections[key];
    if (!section) return "";
    return section.content || section.ai_draft || "";
  };

  const getSectionAiDraft = (key: SectionName): string | null => {
    if (!proposal?.sections) return null;
    const section = proposal.sections[key];
    if (!section) return null;
    return section.ai_draft || null;
  };

  const hasUnsavedAiDraft = (key: SectionName): boolean => {
    if (!proposal?.sections) return false;
    const section = proposal.sections[key];
    if (!section) return false;
    return !!(section.ai_draft && section.ai_draft !== section.content);
  };

  // ---- Edit handlers ----
  const startEditing = (key: SectionName) => {
    setEditingSection(key);
    setEditContent(getSectionContent(key));
  };

  const cancelEditing = () => {
    setEditingSection(null);
    setEditContent("");
  };

  const saveSection = async (key: SectionName, content: string) => {
    if (!proposalId) return;

    const token = await getToken();
    if (!token) return;

    setSaving(true);
    try {
      const updated = await updateProposal(token, proposalId, {
        sections: {
          [key]: {
            content,
            ai_draft: null,
            last_edited: new Date().toISOString(),
          },
        },
      });
      setProposal(updated);
      setEditingSection(null);
      setEditContent("");
    } catch (err) {
      console.error("Failed to save section:", err);
    } finally {
      setSaving(false);
    }
  };

  const acceptAiDraft = async (key: SectionName) => {
    const draft = getSectionAiDraft(key);
    if (!draft) return;
    await saveSection(key, draft);
  };

  const dismissAiDraft = async (key: SectionName) => {
    if (!proposalId) return;

    const token = await getToken();
    if (!token) return;

    setSaving(true);
    try {
      const currentContent = proposal?.sections?.[key]?.content || "";
      const updated = await updateProposal(token, proposalId, {
        sections: {
          [key]: {
            content: currentContent,
            ai_draft: null,
            last_edited: new Date().toISOString(),
          },
        },
      });
      setProposal(updated);
    } catch (err) {
      console.error("Failed to dismiss AI draft:", err);
    } finally {
      setSaving(false);
    }
  };

  // ---- Title editing ----
  const startEditingTitle = () => {
    setEditingTitle(true);
    setTitleDraft(proposal?.title || "");
  };

  const saveTitle = async () => {
    if (!proposalId || !titleDraft.trim()) return;

    const token = await getToken();
    if (!token) return;

    setSaving(true);
    try {
      const updated = await updateProposal(token, proposalId, {
        title: titleDraft.trim(),
      });
      setProposal(updated);
      setEditingTitle(false);
    } catch (err) {
      console.error("Failed to save title:", err);
    } finally {
      setSaving(false);
    }
  };

  // ===========================================================================
  // Render: Loading / Generating
  // ===========================================================================

  if (loading || generating) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-8 sm:p-12">
        <div className="text-center max-w-md mx-auto">
          <div className="relative mb-6">
            <Sparkles className="h-12 w-12 text-brand-blue mx-auto animate-pulse" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
            Generating your proposal...
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
            Our AI is crafting each section of your grant application based on
            your interview responses and plan.
          </p>

          {/* Progress bar */}
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 mb-4">
            <div
              className="bg-brand-blue h-2 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(generationProgress, 100)}%` }}
            />
          </div>

          {/* Per-section progress indicators */}
          <div className="space-y-2 text-left">
            {SECTIONS.map((section, index) => {
              const sectionThreshold = ((index + 1) / SECTIONS.length) * 100;
              const isComplete = generationProgress >= sectionThreshold;
              const isActive =
                !isComplete &&
                generationProgress >= (index / SECTIONS.length) * 100;

              return (
                <div
                  key={section.key}
                  className="flex items-center gap-2 text-sm"
                >
                  {isComplete ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                  ) : isActive ? (
                    <Loader2 className="h-4 w-4 text-brand-blue animate-spin flex-shrink-0" />
                  ) : (
                    <div className="h-4 w-4 rounded-full border-2 border-gray-300 dark:border-gray-600 flex-shrink-0" />
                  )}
                  <span
                    className={cn(
                      "transition-colors",
                      isComplete
                        ? "text-green-700 dark:text-green-400"
                        : isActive
                          ? "text-brand-blue dark:text-brand-light-blue font-medium"
                          : "text-gray-400 dark:text-gray-500",
                    )}
                  >
                    {section.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // ===========================================================================
  // Render: Error
  // ===========================================================================

  if (error) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
        <div className="text-red-500 mb-4">
          <FileText className="h-10 w-10 mx-auto" />
        </div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          Proposal Generation Failed
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">{error}</p>
        <button
          onClick={onBack}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Go Back
        </button>
      </div>
    );
  }

  // ===========================================================================
  // Render: Proposal Preview
  // ===========================================================================

  return (
    <div className="space-y-4">
      {/* Header area */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          {/* Title (editable) */}
          <div className="flex-1 min-w-0">
            {editingTitle ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveTitle();
                    if (e.key === "Escape") setEditingTitle(false);
                  }}
                  className="flex-1 text-lg font-semibold text-gray-900 dark:text-white bg-transparent border-b-2 border-brand-blue focus:outline-none"
                  autoFocus
                />
                <button
                  onClick={saveTitle}
                  disabled={saving}
                  className="p-1 text-brand-blue hover:text-brand-dark-blue transition-colors"
                  aria-label="Save title"
                >
                  {saving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                </button>
                <button
                  onClick={() => setEditingTitle(false)}
                  className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                  aria-label="Cancel editing title"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <button
                onClick={startEditingTitle}
                className="group flex items-center gap-2 text-left"
              >
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white truncate">
                  {proposal?.title || "Untitled Proposal"}
                </h2>
                <Edit3 className="h-4 w-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
              </button>
            )}
            {grantContext?.grant_name && (
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 truncate">
                {grantContext.grant_name}
              </p>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={onBack}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition-colors",
                "text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface",
                "border border-gray-300 dark:border-gray-600",
                "hover:bg-gray-50 dark:hover:bg-gray-800",
              )}
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </button>
            <button
              onClick={onComplete}
              className={cn(
                "inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors",
                "bg-brand-blue hover:bg-brand-dark-blue",
              )}
            >
              Continue to Export
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700">
        <div
          ref={tabsRef}
          className="flex overflow-x-auto border-b border-gray-200 dark:border-gray-700 scrollbar-hide"
          role="tablist"
        >
          {SECTIONS.map((section) => {
            const isActive = activeTab === section.key;
            const hasDraft = hasUnsavedAiDraft(section.key);

            return (
              <button
                key={section.key}
                role="tab"
                aria-selected={isActive}
                onClick={() => {
                  setActiveTab(section.key);
                  if (editingSection && editingSection !== section.key) {
                    cancelEditing();
                  }
                }}
                className={cn(
                  "relative px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors flex-shrink-0",
                  isActive
                    ? "text-brand-blue dark:text-brand-light-blue border-b-2 border-brand-blue"
                    : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300",
                )}
              >
                {section.label}
                {hasDraft && (
                  <span className="absolute top-2 right-1 h-2 w-2 bg-amber-400 rounded-full" />
                )}
              </button>
            );
          })}
        </div>

        {/* Section content */}
        <div className="p-4 sm:p-6">
          {/* AI draft banner */}
          {hasUnsavedAiDraft(activeTab) && editingSection !== activeTab && (
            <div className="mb-4 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-300">
                <Sparkles className="h-4 w-4 flex-shrink-0" />
                <span>A new AI draft is available for this section.</span>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={() => acceptAiDraft(activeTab)}
                  disabled={saving}
                  className="px-3 py-1.5 text-xs font-medium text-white bg-brand-blue hover:bg-brand-dark-blue rounded-md transition-colors disabled:opacity-50"
                >
                  Accept AI Draft
                </button>
                <button
                  onClick={() => dismissAiDraft(activeTab)}
                  disabled={saving}
                  className="px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors disabled:opacity-50"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {editingSection === activeTab ? (
            /* Editing mode */
            <div className="space-y-3">
              <textarea
                ref={textareaRef}
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                rows={16}
                className={cn(
                  "w-full px-4 py-3 text-sm text-gray-900 dark:text-white rounded-lg border transition-colors resize-y",
                  "bg-white dark:bg-dark-surface-deep",
                  "border-gray-300 dark:border-gray-600 focus:border-brand-blue focus:ring-1 focus:ring-brand-blue",
                  "focus:outline-none",
                )}
              />
              <div className="flex items-center justify-end gap-2">
                <button
                  onClick={cancelEditing}
                  className="px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => saveSection(activeTab, editContent)}
                  disabled={saving}
                  className={cn(
                    "inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors",
                    "bg-brand-blue hover:bg-brand-dark-blue disabled:opacity-50",
                  )}
                >
                  {saving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  Save
                </button>
              </div>
            </div>
          ) : (
            /* View mode */
            <div>
              <div className="prose prose-sm dark:prose-invert max-w-none mb-4">
                {getSectionContent(activeTab) ? (
                  <div className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 leading-relaxed">
                    {getSectionContent(activeTab)}
                  </div>
                ) : (
                  <p className="text-gray-400 dark:text-gray-500 italic">
                    No content for this section yet. Click "Edit" to add
                    content.
                  </p>
                )}
              </div>
              <button
                onClick={() => startEditing(activeTab)}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition-colors",
                  "text-gray-600 dark:text-gray-400 border border-gray-300 dark:border-gray-600",
                  "hover:bg-gray-50 dark:hover:bg-gray-800",
                )}
              >
                <Edit3 className="h-4 w-4" />
                Edit
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProposalPreview;
