/**
 * ProposalEditor Page
 *
 * A section-based editor for grant proposals with AI-assisted drafting.
 * Displays 6 proposal sections that can be individually or bulk-generated
 * using AI, then manually edited and saved.
 *
 * Features:
 * - Editable proposal title
 * - 6 tabbed sections with textarea editors
 * - Per-section AI generation with draft acceptance flow
 * - Bulk "Generate All" functionality
 * - Auto-save and manual save
 * - Status badge display
 * - Dark mode support
 */

import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Save,
  Sparkles,
  Loader2,
  CheckCircle2,
  XCircle,
  FileText,
} from "lucide-react";
import { cn } from "../lib/utils";
import {
  getProposal,
  updateProposal,
  generateSection,
  generateAllSections,
  type Proposal,
  type SectionName,
  type ProposalStatus,
} from "../lib/proposal-api";

// =============================================================================
// Constants
// =============================================================================

/** Section definitions with display labels */
const SECTIONS: { key: SectionName; label: string }[] = [
  { key: "executive_summary", label: "Executive Summary" },
  { key: "needs_statement", label: "Needs Statement" },
  { key: "project_description", label: "Project Description" },
  { key: "budget_narrative", label: "Budget Narrative" },
  { key: "timeline", label: "Timeline" },
  { key: "evaluation_plan", label: "Evaluation Plan" },
];

/** Status badge colors */
const STATUS_STYLES: Record<ProposalStatus, string> = {
  draft: "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300",
  in_review:
    "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  final: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  submitted:
    "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  archived: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500",
};

/** Status display labels */
const STATUS_LABELS: Record<ProposalStatus, string> = {
  draft: "Draft",
  in_review: "In Review",
  final: "Final",
  submitted: "Submitted",
  archived: "Archived",
};

// =============================================================================
// Helper
// =============================================================================

/**
 * Retrieves the current session access token.
 */
async function getToken(): Promise<string | null> {
  const token = localStorage.getItem("gs2_token");
  return token || null;
}

// =============================================================================
// Component
// =============================================================================

const ProposalEditor: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Proposal data
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit state
  const [title, setTitle] = useState("");
  const [sections, setSections] = useState<
    Record<
      string,
      { content: string; ai_draft: string | null; last_edited: string | null }
    >
  >({});
  const [activeSection, setActiveSection] =
    useState<SectionName>("executive_summary");
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Action states
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const [generatingSection, setGeneratingSection] = useState<string | null>(
    null,
  );
  const [isGeneratingAll, setIsGeneratingAll] = useState(false);

  // ---------------------------------------------------------------------------
  // Data Fetching
  // ---------------------------------------------------------------------------

  const loadProposal = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);

    try {
      const token = await getToken();
      if (!token) {
        setError("Not authenticated");
        return;
      }

      const data = await getProposal(token, id);
      setProposal(data);
      setTitle(data.title);

      // Initialize sections with defaults for any missing sections
      const initialSections: Record<
        string,
        { content: string; ai_draft: string | null; last_edited: string | null }
      > = {};
      for (const { key } of SECTIONS) {
        const existing = data.sections[key];
        initialSections[key] = {
          content: existing?.content || "",
          ai_draft: existing?.ai_draft || null,
          last_edited: existing?.last_edited || null,
        };
      }
      setSections(initialSections);
      setHasUnsavedChanges(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load proposal");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadProposal();
  }, [loadProposal]);

  // ---------------------------------------------------------------------------
  // Save
  // ---------------------------------------------------------------------------

  const handleSave = useCallback(async () => {
    if (!id || !proposal) return;
    setIsSaving(true);
    setSaveMessage(null);

    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");

      const updated = await updateProposal(token, id, {
        title,
        sections,
      });
      setProposal(updated);
      setHasUnsavedChanges(false);
      setSaveMessage({ type: "success", text: "Saved successfully" });
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (err) {
      setSaveMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Save failed",
      });
    } finally {
      setIsSaving(false);
    }
  }, [id, proposal, title, sections]);

  // ---------------------------------------------------------------------------
  // Section Content Updates
  // ---------------------------------------------------------------------------

  const handleContentChange = useCallback(
    (sectionKey: string, content: string) => {
      setSections((prev) => {
        const existing = prev[sectionKey] || {
          content: "",
          ai_draft: null,
          last_edited: null,
        };
        return {
          ...prev,
          [sectionKey]: {
            content,
            ai_draft: existing.ai_draft,
            last_edited: new Date().toISOString(),
          },
        };
      });
      setHasUnsavedChanges(true);
    },
    [],
  );

  // ---------------------------------------------------------------------------
  // AI Generation - Single Section
  // ---------------------------------------------------------------------------

  const handleGenerateSection = useCallback(
    async (sectionKey: string) => {
      if (!id) return;
      setGeneratingSection(sectionKey);

      try {
        const token = await getToken();
        if (!token) throw new Error("Not authenticated");

        const result = await generateSection(token, id, sectionKey);

        setSections((prev) => {
          const existing = prev[sectionKey] || {
            content: "",
            ai_draft: null,
            last_edited: null,
          };
          return {
            ...prev,
            [sectionKey]: {
              content: existing.content,
              last_edited: existing.last_edited,
              ai_draft: result.ai_draft,
            },
          };
        });
      } catch (err) {
        setSaveMessage({
          type: "error",
          text: err instanceof Error ? err.message : "Generation failed",
        });
      } finally {
        setGeneratingSection(null);
      }
    },
    [id],
  );

  // ---------------------------------------------------------------------------
  // AI Generation - All Sections
  // ---------------------------------------------------------------------------

  const handleGenerateAll = useCallback(async () => {
    if (!id) return;
    setIsGeneratingAll(true);

    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");

      const updated = await generateAllSections(token, id);
      setProposal(updated);

      // Update local sections with AI drafts from response
      const newSections: typeof sections = {};
      for (const { key } of SECTIONS) {
        const sec = updated.sections[key];
        newSections[key] = {
          content: sections[key]?.content || sec?.content || "",
          ai_draft: sec?.ai_draft || null,
          last_edited: sections[key]?.last_edited || sec?.last_edited || null,
        };
      }
      setSections(newSections);
      setSaveMessage({ type: "success", text: "All sections generated" });
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (err) {
      setSaveMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Bulk generation failed",
      });
    } finally {
      setIsGeneratingAll(false);
    }
  }, [id, sections]);

  // ---------------------------------------------------------------------------
  // Accept / Dismiss AI Draft
  // ---------------------------------------------------------------------------

  const handleAcceptDraft = useCallback((sectionKey: string) => {
    setSections((prev) => {
      const sec = prev[sectionKey];
      if (!sec?.ai_draft) return prev;
      return {
        ...prev,
        [sectionKey]: {
          content: sec.ai_draft,
          ai_draft: null,
          last_edited: new Date().toISOString(),
        },
      };
    });
    setHasUnsavedChanges(true);
  }, []);

  const handleDismissDraft = useCallback((sectionKey: string) => {
    setSections((prev) => {
      const existing = prev[sectionKey] || {
        content: "",
        ai_draft: null,
        last_edited: null,
      };
      return {
        ...prev,
        [sectionKey]: {
          content: existing.content,
          last_edited: existing.last_edited,
          ai_draft: null,
        },
      };
    });
  }, []);

  // ---------------------------------------------------------------------------
  // Render: Loading / Error
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-brand-faded-white dark:bg-brand-dark-blue">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-brand-blue mx-auto" />
          <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
            Loading proposal...
          </p>
        </div>
      </div>
    );
  }

  if (error || !proposal) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-brand-faded-white dark:bg-brand-dark-blue">
        <div className="text-center max-w-md">
          <XCircle className="h-10 w-10 text-red-400 mx-auto" />
          <h2 className="mt-3 text-lg font-semibold text-gray-900 dark:text-white">
            Failed to Load Proposal
          </h2>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            {error || "Proposal not found"}
          </p>
          <button
            onClick={() => navigate(-1)}
            className="mt-4 px-4 py-2 text-sm font-medium text-white bg-brand-blue rounded-md hover:bg-brand-dark-blue transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Main Editor
  // ---------------------------------------------------------------------------

  const currentSection = sections[activeSection];
  const status = (proposal.status || "draft") as ProposalStatus;

  return (
    <div className="min-h-screen bg-brand-faded-white dark:bg-brand-dark-blue">
      {/* Header */}
      <div className="sticky top-16 z-30 bg-white dark:bg-dark-surface border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            {/* Left: Back + Title */}
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <button
                onClick={() => navigate(-1)}
                className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors shrink-0"
                aria-label="Go back"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
              <FileText className="h-5 w-5 text-indigo-500 shrink-0" />
              <input
                type="text"
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                  setHasUnsavedChanges(true);
                }}
                className="text-lg font-semibold text-gray-900 dark:text-white bg-transparent border-none outline-none focus:ring-0 min-w-0 flex-1 truncate"
                placeholder="Proposal Title"
              />
              <span
                className={cn(
                  "px-2 py-0.5 text-xs font-medium rounded-full shrink-0",
                  STATUS_STYLES[status],
                )}
              >
                {STATUS_LABELS[status]}
              </span>
            </div>

            {/* Right: Actions */}
            <div className="flex items-center gap-2 ml-4 shrink-0">
              {/* Save message */}
              {saveMessage && (
                <span
                  className={cn(
                    "text-xs font-medium flex items-center gap-1",
                    saveMessage.type === "success"
                      ? "text-green-600 dark:text-green-400"
                      : "text-red-600 dark:text-red-400",
                  )}
                >
                  {saveMessage.type === "success" ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5" />
                  )}
                  {saveMessage.text}
                </span>
              )}

              {/* Generate All */}
              <button
                onClick={handleGenerateAll}
                disabled={isGeneratingAll || !!generatingSection}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
                  "text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-900/20",
                  "hover:bg-indigo-100 dark:hover:bg-indigo-900/30",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                )}
              >
                {isGeneratingAll ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                {isGeneratingAll ? "Generating..." : "Generate All"}
              </button>

              {/* Save */}
              <button
                onClick={handleSave}
                disabled={isSaving || !hasUnsavedChanges}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white rounded-md transition-colors",
                  "bg-brand-blue hover:bg-brand-dark-blue",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                )}
              >
                {isSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                {isSaving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex gap-6">
          {/* Section Tabs (sidebar) */}
          <nav className="w-56 shrink-0">
            <ul className="space-y-1">
              {SECTIONS.map(({ key, label }) => {
                const isActive = activeSection === key;
                const sec = sections[key];
                const hasContent =
                  sec?.content && sec.content.trim().length > 0;
                const hasDraft = !!sec?.ai_draft;

                return (
                  <li key={key}>
                    <button
                      onClick={() => setActiveSection(key)}
                      className={cn(
                        "w-full flex items-center gap-2 px-3 py-2 text-sm rounded-md transition-colors text-left",
                        isActive
                          ? "bg-brand-blue/10 text-brand-blue dark:bg-brand-blue/20 dark:text-brand-light-blue font-medium"
                          : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800",
                      )}
                    >
                      <span className="flex-1 truncate">{label}</span>
                      {hasDraft && (
                        <span
                          className="w-2 h-2 rounded-full bg-indigo-400 shrink-0"
                          title="AI draft available"
                        />
                      )}
                      {hasContent && !hasDraft && (
                        <span
                          className="w-2 h-2 rounded-full bg-green-400 shrink-0"
                          title="Has content"
                        />
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>

          {/* Editor Area */}
          <div className="flex-1 min-w-0">
            <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
              {/* Section Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {SECTIONS.find((s) => s.key === activeSection)?.label}
                  </h2>
                  {currentSection?.last_edited && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      Last edited:{" "}
                      {new Date(currentSection.last_edited).toLocaleString()}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => handleGenerateSection(activeSection)}
                  disabled={
                    generatingSection === activeSection || isGeneratingAll
                  }
                  className={cn(
                    "inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
                    "text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-900/20",
                    "hover:bg-indigo-100 dark:hover:bg-indigo-900/30",
                    "disabled:opacity-50 disabled:cursor-not-allowed",
                  )}
                >
                  {generatingSection === activeSection ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  {generatingSection === activeSection
                    ? "Generating..."
                    : "Generate with AI"}
                </button>
              </div>

              {/* AI Draft Banner (if available) */}
              {currentSection?.ai_draft && (
                <div className="mx-6 mt-4 rounded-lg border border-indigo-200 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-900/20 overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-2 border-b border-indigo-200 dark:border-indigo-700">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-indigo-500" />
                      <span className="text-sm font-medium text-indigo-700 dark:text-indigo-300">
                        AI-Generated Draft
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleAcceptDraft(activeSection)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-white bg-indigo-600 rounded hover:bg-indigo-700 transition-colors"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Accept
                      </button>
                      <button
                        onClick={() => handleDismissDraft(activeSection)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        Dismiss
                      </button>
                    </div>
                  </div>
                  <div className="px-4 py-3 max-h-60 overflow-y-auto">
                    <pre className="text-sm text-indigo-900 dark:text-indigo-200 whitespace-pre-wrap font-sans">
                      {currentSection.ai_draft}
                    </pre>
                  </div>
                </div>
              )}

              {/* Editor Textarea */}
              <div className="p-6">
                <textarea
                  value={currentSection?.content || ""}
                  onChange={(e) =>
                    handleContentChange(activeSection, e.target.value)
                  }
                  placeholder={`Write your ${SECTIONS.find((s) => s.key === activeSection)?.label.toLowerCase()} here...`}
                  rows={16}
                  className={cn(
                    "w-full px-4 py-3 text-sm rounded-md border resize-y",
                    "bg-white dark:bg-dark-surface-elevated",
                    "text-gray-900 dark:text-white",
                    "placeholder-gray-400 dark:placeholder-gray-500",
                    "border-gray-300 dark:border-gray-600",
                    "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue",
                    "transition-colors",
                  )}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProposalEditor;
