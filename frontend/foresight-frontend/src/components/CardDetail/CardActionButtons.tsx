/**
 * CardActionButtons Component
 *
 * A row of action buttons for card interactions including:
 * - Compare: Navigate to compare mode with another card
 * - Update: Trigger a quick source update
 * - Deep Research: Trigger comprehensive research
 * - Export: Download card in various formats (PDF, PPTX, CSV)
 * - Follow: Toggle following status for the card
 */

import React, { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Heart,
  RefreshCw,
  Search,
  Loader2,
  ChevronDown,
  Download,
  FileText,
  FileSpreadsheet,
  Presentation,
  ArrowLeftRight,
  Briefcase,
  PlusCircle,
} from "lucide-react";
import { Tooltip } from "../ui/Tooltip";
import { AddToWorkstreamModal } from "./AddToWorkstreamModal";
import type { Card, ResearchTask } from "./types";
import { API_BASE_URL } from "./utils";

/**
 * Props for the CardActionButtons component
 */
export interface CardActionButtonsProps {
  /** The card to display actions for */
  card: Card;
  /** Whether the user is following this card */
  isFollowing: boolean;
  /** Whether a research task is currently running */
  isResearching: boolean;
  /** The current research task (if any) */
  researchTask: ResearchTask | null;
  /** Whether deep research is available (rate limit not exceeded) */
  canDeepResearch: boolean;
  /** Callback to trigger research (update or deep_research) */
  onTriggerResearch: (taskType: "update" | "deep_research") => void;
  /** Callback to toggle follow status */
  onToggleFollow: () => void;
  /** Function to get auth token for API requests */
  getAuthToken: () => Promise<string | undefined>;
  /** Optional additional className */
  className?: string;
}

/**
 * Export format type
 */
type ExportFormat = "pdf" | "pptx" | "csv";

/**
 * CardActionButtons component
 *
 * Renders a horizontal row of action buttons with tooltips.
 * Handles horizontal scrolling on mobile and wrapping on larger screens.
 */
export function CardActionButtons({
  card,
  isFollowing,
  isResearching,
  researchTask,
  canDeepResearch,
  onTriggerResearch,
  onToggleFollow,
  getAuthToken,
  className = "",
}: CardActionButtonsProps): React.ReactElement {
  const navigate = useNavigate();

  // Export state
  const [showExportDropdown, setShowExportDropdown] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // Workstream modal state
  const [showWorkstreamModal, setShowWorkstreamModal] = useState(false);
  const [workstreamSuccess, setWorkstreamSuccess] = useState<string | null>(
    null,
  );

  /**
   * Handle export to different formats
   */
  const handleExport = useCallback(
    async (format: ExportFormat) => {
      if (!card || isExporting) return;

      setIsExporting(true);
      setExportError(null);
      setShowExportDropdown(false);

      try {
        const token = await getAuthToken();
        if (!token) {
          throw new Error("Not authenticated");
        }

        const response = await fetch(
          `${API_BASE_URL}/api/v1/cards/${card.id}/export/${format}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          },
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            errorData.detail || `Export failed: ${response.statusText}`,
          );
        }

        // Create blob from response and trigger download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${card.slug}-export.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : "Failed to export card";
        setExportError(errorMessage);
      } finally {
        setIsExporting(false);
      }
    },
    [card, isExporting, getAuthToken],
  );

  /**
   * Handle compare button click
   * Stores the card info and navigates to Discover in compare mode
   */
  const handleCompare = useCallback(() => {
    sessionStorage.setItem(
      "compareCard",
      JSON.stringify({ id: card.id, name: card.name }),
    );
    navigate("/discover?compare=true");
  }, [card.id, card.name, navigate]);

  /**
   * Close export dropdown when clicking outside
   */
  const handleBackdropClick = useCallback(() => {
    setShowExportDropdown(false);
  }, []);

  /**
   * Handle follow button with optional workstream prompt
   */
  const handleFollowClick = useCallback(() => {
    onToggleFollow();
    // If not already following, show the workstream modal after following
    if (!isFollowing) {
      // Small delay to let the follow action complete
      setTimeout(() => {
        setShowWorkstreamModal(true);
      }, 300);
    }
  }, [isFollowing, onToggleFollow]);

  /**
   * Handle workstream add success
   */
  const handleWorkstreamSuccess = useCallback((workstreamName: string) => {
    setWorkstreamSuccess(workstreamName);
    // Clear success message after a few seconds
    setTimeout(() => setWorkstreamSuccess(null), 4000);
  }, []);

  return (
    <>
      {/* Action buttons - horizontal scroll on mobile, wrap on larger screens */}
      <div
        className={`flex items-center gap-2 sm:gap-3 overflow-x-auto pb-2 lg:pb-0 lg:overflow-visible lg:flex-wrap lg:justify-end -mx-4 px-4 sm:mx-0 sm:px-0 ${className}`}
      >
        {/* Add to Pipeline button - prominent for grant cards */}
        {(card.grantor || card.deadline) && (
          <Tooltip
            content={
              <div className="max-w-[200px]">
                <p className="font-medium">Add to Pipeline</p>
                <p className="text-xs text-gray-500">
                  Add this grant opportunity to a workstream pipeline for
                  tracking
                </p>
              </div>
            }
            side="bottom"
          >
            <button
              onClick={() => setShowWorkstreamModal(true)}
              className="inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-4 py-2 border border-brand-green rounded-md shadow-sm text-sm font-semibold text-white bg-brand-green hover:bg-brand-green/90 transition-colors active:scale-95"
            >
              <PlusCircle className="h-4 w-4 mr-2" />
              Add to Pipeline
            </button>
          </Tooltip>
        )}

        {/* Apply for This Grant button - prominent for grant cards */}
        {(card.grantor || card.deadline) && (
          <Tooltip
            content={
              <div className="max-w-[200px]">
                <p className="font-medium">Apply for This Grant</p>
                <p className="text-xs text-gray-500">
                  Start a guided grant application with AI assistance
                </p>
              </div>
            }
            side="bottom"
          >
            <button
              onClick={() => navigate(`/apply?card_id=${card.id}`)}
              className="inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-4 py-2 border border-brand-blue rounded-md shadow-sm text-sm font-semibold text-white bg-brand-blue hover:bg-brand-dark-blue transition-colors active:scale-95"
            >
              <FileText className="h-4 w-4 mr-2" />
              Apply
            </button>
          </Tooltip>
        )}

        {/* Compare button */}
        <Tooltip
          content={
            <div className="max-w-[200px]">
              <p className="font-medium">Compare Trends</p>
              <p className="text-xs text-gray-500">
                Select another opportunity to compare trends side-by-side
              </p>
            </div>
          }
          side="bottom"
        >
          <button
            onClick={handleCompare}
            className="inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-3 py-2 border border-extended-purple/30 rounded-md shadow-sm text-sm font-medium text-extended-purple bg-extended-purple/10 hover:bg-extended-purple hover:text-white transition-colors active:scale-95"
          >
            <ArrowLeftRight className="h-4 w-4 mr-2" />
            Compare
          </button>
        </Tooltip>

        {/* Update button */}
        <Tooltip
          content={
            <div className="max-w-[200px]">
              <p className="font-medium">Quick Update</p>
              <p className="text-xs text-gray-500">
                Find 5-10 new sources and refresh card data
              </p>
            </div>
          }
          side="bottom"
        >
          <button
            onClick={() => onTriggerResearch("update")}
            disabled={isResearching}
            className="inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors active:scale-95"
          >
            {isResearching && researchTask?.task_type === "update" ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Update
          </button>
        </Tooltip>

        {/* Deep Research button */}
        <Tooltip
          content={
            <div className="max-w-[200px]">
              <p className="font-medium">Deep Research</p>
              <p className="text-xs text-gray-500">
                Comprehensive research with 15+ sources and metrics update
                {!canDeepResearch && (
                  <span className="block text-amber-500 mt-1">
                    Daily limit reached (2/day)
                  </span>
                )}
              </p>
            </div>
          }
          side="bottom"
        >
          <button
            onClick={() => onTriggerResearch("deep_research")}
            disabled={isResearching || !canDeepResearch}
            className="inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-3 py-2 border border-brand-blue rounded-md shadow-sm text-sm font-medium text-white bg-brand-blue hover:bg-brand-dark-blue disabled:opacity-50 disabled:cursor-not-allowed transition-colors active:scale-95"
          >
            {isResearching && researchTask?.task_type === "deep_research" ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Search className="h-4 w-4 mr-2" />
            )}
            Deep Research
          </button>
        </Tooltip>

        {/* Export Dropdown */}
        <div className="relative">
          <Tooltip
            content={
              <div className="max-w-[200px]">
                <p className="font-medium">Export Card</p>
                <p className="text-xs text-gray-500">
                  Download this card in various formats for sharing and analysis
                </p>
              </div>
            }
            side="bottom"
          >
            <button
              onClick={() => setShowExportDropdown(!showExportDropdown)}
              disabled={isExporting}
              className="inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors active:scale-95"
            >
              {isExporting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-2" />
              )}
              Export
              <ChevronDown className="h-4 w-4 ml-1" />
            </button>
          </Tooltip>

          {/* Dropdown Menu */}
          {showExportDropdown && (
            <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-dark-surface-elevated rounded-md shadow-lg border border-gray-200 dark:border-gray-600 py-1 z-20">
              <button
                onClick={() => handleExport("pdf")}
                className="w-full flex items-center min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors active:bg-gray-200 dark:active:bg-gray-600"
              >
                <FileText className="h-4 w-4 mr-3 text-red-500" />
                Export as PDF
              </button>
              <button
                onClick={() => handleExport("pptx")}
                className="w-full flex items-center min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors active:bg-gray-200 dark:active:bg-gray-600"
              >
                <Presentation className="h-4 w-4 mr-3 text-orange-500" />
                Export as PowerPoint
              </button>
              <button
                onClick={() => handleExport("csv")}
                className="w-full flex items-center min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors active:bg-gray-200 dark:active:bg-gray-600"
              >
                <FileSpreadsheet className="h-4 w-4 mr-3 text-green-500" />
                Export as CSV
              </button>
            </div>
          )}
        </div>

        {/* Add to Workstream button */}
        <Tooltip
          content={
            <div className="max-w-[200px]">
              <p className="font-medium">Add to Workstream</p>
              <p className="text-xs text-gray-500">
                Add this card to one of your research workstreams
              </p>
            </div>
          }
          side="bottom"
        >
          <button
            onClick={() => setShowWorkstreamModal(true)}
            className="inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-3 py-2 border border-brand-green/30 rounded-md shadow-sm text-sm font-medium text-brand-green bg-brand-green/10 hover:bg-brand-green hover:text-white transition-colors active:scale-95"
          >
            <Briefcase className="h-4 w-4 mr-2" />
            Workstream
          </button>
        </Tooltip>

        {/* Follow button */}
        <button
          onClick={handleFollowClick}
          className={`inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-4 py-2 border rounded-md shadow-sm text-sm font-medium transition-colors active:scale-95 ${
            isFollowing
              ? "border-red-300 text-red-700 bg-red-50 hover:bg-red-100"
              : "border-gray-300 text-gray-700 bg-white hover:bg-gray-50"
          }`}
        >
          <Heart
            className={`h-4 w-4 mr-2 ${isFollowing ? "fill-current" : ""}`}
          />
          {isFollowing ? "Following" : "Follow"}
        </button>
      </div>

      {/* Export Error Banner */}
      {exportError && (
        <div className="mt-4 rounded-lg border bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800 p-4">
          <div className="flex items-center gap-3">
            <div className="h-5 w-5 rounded-full bg-red-500 text-white flex items-center justify-center text-xs font-bold">
              !
            </div>
            <div>
              <p className="font-medium text-red-800 dark:text-red-200">
                Export failed
              </p>
              <p className="text-sm text-red-600 dark:text-red-300">
                {exportError}
              </p>
            </div>
            <button
              onClick={() => setExportError(null)}
              className="ml-auto text-red-600 hover:text-red-800 text-sm"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Close export dropdown when clicking outside */}
      {showExportDropdown && (
        <div className="fixed inset-0 z-10" onClick={handleBackdropClick} />
      )}

      {/* Workstream Success Message */}
      {workstreamSuccess && (
        <div className="mt-4 rounded-lg border bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800 p-4">
          <div className="flex items-center gap-3">
            <div className="h-5 w-5 rounded-full bg-green-500 text-white flex items-center justify-center text-xs font-bold">
              ✓
            </div>
            <p className="text-sm text-green-800 dark:text-green-200">
              Added to <span className="font-medium">{workstreamSuccess}</span>
            </p>
          </div>
        </div>
      )}

      {/* Add to Workstream Modal */}
      <AddToWorkstreamModal
        isOpen={showWorkstreamModal}
        onClose={() => setShowWorkstreamModal(false)}
        cardId={card.id}
        cardName={card.name}
        onSuccess={handleWorkstreamSuccess}
        getAuthToken={getAuthToken}
      />
    </>
  );
}

export default CardActionButtons;
