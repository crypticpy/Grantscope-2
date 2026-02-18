/**
 * ExportComplete - Step 6 (final) of the Grant Application Wizard
 *
 * Celebration / success screen after the proposal or plan has been generated.
 * Provides PDF and DOCX download, summary of the grant, and next-step guidance.
 * Adapts content based on whether the user has a proposal, plan, or just a
 * program summary (build_program path without a grant).
 *
 * Features:
 * - PDF + DOCX download via wizard export endpoints
 * - Conditional hero text based on entry path and available artifacts
 * - Grant context summary card (name, deadline, funding)
 * - Next steps guidance
 * - Navigation links to Proposal Editor and new wizard session
 * - Dark mode support
 */

import React, { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Download,
  FileText,
  CheckCircle2,
  ExternalLink,
  Loader2,
  ArrowRight,
  Search,
} from "lucide-react";
import { cn } from "../../lib/utils";
import {
  exportWizardPdf,
  exportWizardSummary,
  exportWizardPlan,
  exportWizardProposal,
  type GrantContext,
  type ExportFormat,
} from "../../lib/wizard-api";

// =============================================================================
// Types
// =============================================================================

interface ExportCompleteProps {
  sessionId: string;
  proposalId: string | null;
  grantContext?: GrantContext | null;
  /** Which wizard entry path the user took */
  entryPath?: string;
  /** Whether the session has a synthesized plan */
  hasPlan?: boolean;
}

// =============================================================================
// Helper
// =============================================================================

async function getToken(): Promise<string | null> {
  const token = localStorage.getItem("gs2_token");
  return token || null;
}

/**
 * Formats a number as USD currency (e.g. 50000 -> "$50,000").
 */
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
}

// =============================================================================
// Component
// =============================================================================

export const ExportComplete: React.FC<ExportCompleteProps> = ({
  sessionId,
  proposalId,
  grantContext,
  entryPath,
  hasPlan,
}) => {
  const navigate = useNavigate();
  const [downloading, setDownloading] = useState(false);
  const [downloadFormat, setDownloadFormat] = useState<"pdf" | "docx" | null>(
    null,
  );
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // ---- Determine what artifact to export ----
  const hasProposal = !!proposalId;
  const isProgramPath = entryPath === "build_program";

  // ---- Generic download handler ----
  const handleDownload = useCallback(
    async (format: ExportFormat) => {
      const token = await getToken();
      if (!token) {
        setDownloadError("Not authenticated. Please sign in and try again.");
        return;
      }

      setDownloading(true);
      setDownloadFormat(format === "pdf" ? "pdf" : "docx");
      setDownloadError(null);

      // Determine which export function and filename to use
      let exportFn: (
        token: string,
        sessionId: string,
        format: ExportFormat,
      ) => Promise<Blob>;
      let filenamePrefix: string;

      if (hasProposal) {
        exportFn = exportWizardProposal;
        filenamePrefix = "proposal";
      } else if (hasPlan) {
        exportFn = exportWizardPlan;
        filenamePrefix = "project-plan";
      } else {
        exportFn = exportWizardSummary;
        filenamePrefix = "program-summary";
      }

      try {
        const blob = await exportFn(token, sessionId, format);

        // Create a temporary download link
        const ext = format === "pdf" ? "pdf" : "docx";
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${filenamePrefix}-${sessionId.slice(0, 8)}.${ext}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (err) {
        setDownloadError(
          err instanceof Error
            ? err.message
            : `Failed to download ${format.toUpperCase()}`,
        );
      } finally {
        setDownloading(false);
        setDownloadFormat(null);
      }
    },
    [sessionId, hasProposal, hasPlan],
  );

  // ---- Legacy PDF-only download for backward compatibility ----
  const handleDownloadPdf = useCallback(async () => {
    // If the session has a proposal and was created before the new export
    // endpoints existed, fall back to the original PDF endpoint.
    if (hasProposal && !isProgramPath) {
      const token = await getToken();
      if (!token) {
        setDownloadError("Not authenticated. Please sign in and try again.");
        return;
      }

      setDownloading(true);
      setDownloadFormat("pdf");
      setDownloadError(null);

      try {
        const blob = await exportWizardPdf(token, sessionId);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `grant-application-${sessionId.slice(0, 8)}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (err) {
        setDownloadError(
          err instanceof Error ? err.message : "Failed to download PDF",
        );
      } finally {
        setDownloading(false);
        setDownloadFormat(null);
      }
      return;
    }

    handleDownload("pdf");
  }, [sessionId, hasProposal, isProgramPath, handleDownload]);

  // ---- Funding range display ----
  const fundingDisplay = (() => {
    if (!grantContext) return null;
    const { funding_amount_min, funding_amount_max } = grantContext;
    if (funding_amount_min && funding_amount_max) {
      return `${formatCurrency(funding_amount_min)} - ${formatCurrency(funding_amount_max)}`;
    }
    if (funding_amount_max)
      return `Up to ${formatCurrency(funding_amount_max)}`;
    if (funding_amount_min) return `From ${formatCurrency(funding_amount_min)}`;
    return null;
  })();

  // ---- Determine hero content ----
  let heroTitle: string;
  let heroDescription: string;

  if (hasProposal) {
    heroTitle = "Your grant application package is ready!";
    heroDescription =
      "Your proposal has been generated with all six sections. Download the PDF or Word document to review offline or share with colleagues.";
  } else if (hasPlan) {
    heroTitle = "Your project plan is ready!";
    heroDescription =
      "Your project plan has been synthesized from your interview responses. Download it to share with your team or use it for future grant applications.";
  } else {
    heroTitle = "Your program summary is ready!";
    heroDescription =
      "We've compiled a program summary from your interview. Download it and use it as a foundation for grant applications.";
  }

  // ===========================================================================
  // Render
  // ===========================================================================

  return (
    <div className="space-y-6">
      {/* Success hero */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-8 sm:p-12 text-center">
        <div className="mx-auto mb-5 w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
          <CheckCircle2 className="h-9 w-9 text-green-600 dark:text-green-400" />
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white mb-2">
          {heroTitle}
        </h2>
        <p className="text-sm sm:text-base text-gray-500 dark:text-gray-400 max-w-lg mx-auto">
          {heroDescription}
        </p>

        {/* Download buttons */}
        <div className="flex items-center justify-center gap-3 mt-8">
          <button
            onClick={handleDownloadPdf}
            disabled={downloading}
            className={cn(
              "inline-flex items-center gap-2 px-6 py-3 text-base font-medium text-white rounded-lg transition-colors",
              "bg-brand-blue hover:bg-brand-dark-blue disabled:opacity-60",
            )}
          >
            {downloading && downloadFormat === "pdf" ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Download className="h-5 w-5" />
            )}
            {downloading && downloadFormat === "pdf"
              ? "Preparing PDF..."
              : "Download PDF"}
          </button>
          <button
            onClick={() => handleDownload("docx")}
            disabled={downloading}
            className={cn(
              "inline-flex items-center gap-2 px-6 py-3 text-base font-medium rounded-lg transition-colors",
              "text-brand-blue border border-brand-blue/30 dark:border-brand-blue/40",
              "hover:bg-brand-blue/5 dark:hover:bg-brand-blue/10 disabled:opacity-60",
            )}
          >
            {downloading && downloadFormat === "docx" ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <FileText className="h-5 w-5" />
            )}
            {downloading && downloadFormat === "docx"
              ? "Preparing Word..."
              : "Download Word"}
          </button>
        </div>
        {downloadError && (
          <p className="mt-3 text-sm text-red-500">{downloadError}</p>
        )}
      </div>

      {/* Grant summary card */}
      {grantContext &&
        (grantContext.grant_name ||
          grantContext.deadline ||
          fundingDisplay) && (
          <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4 sm:p-6">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <FileText className="h-4 w-4 text-brand-blue" />
              Grant Summary
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
              {grantContext.grant_name && (
                <div>
                  <span className="text-gray-500 dark:text-gray-400 block mb-0.5">
                    Grant Name
                  </span>
                  <span className="text-gray-900 dark:text-white font-medium">
                    {grantContext.grant_name}
                  </span>
                </div>
              )}
              {grantContext.deadline && (
                <div>
                  <span className="text-gray-500 dark:text-gray-400 block mb-0.5">
                    Deadline
                  </span>
                  <span className="text-gray-900 dark:text-white font-medium">
                    {grantContext.deadline}
                  </span>
                </div>
              )}
              {fundingDisplay && (
                <div>
                  <span className="text-gray-500 dark:text-gray-400 block mb-0.5">
                    Funding Amount
                  </span>
                  <span className="text-gray-900 dark:text-white font-medium">
                    {fundingDisplay}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

      {/* Next steps */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4 sm:p-6">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
          Next Steps
        </h3>
        <ul className="space-y-3 text-sm text-gray-600 dark:text-gray-400">
          {hasProposal ? (
            <>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 h-5 w-5 bg-brand-blue/10 dark:bg-brand-blue/20 text-brand-blue rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">
                  1
                </span>
                <span>
                  <strong className="text-gray-800 dark:text-gray-200">
                    Review your proposal
                  </strong>{" "}
                  -- Read through all sections and make any final edits.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 h-5 w-5 bg-brand-blue/10 dark:bg-brand-blue/20 text-brand-blue rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">
                  2
                </span>
                <span>
                  <strong className="text-gray-800 dark:text-gray-200">
                    Submit through the grant portal
                  </strong>{" "}
                  -- Use the funder's official submission portal or method.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 h-5 w-5 bg-brand-blue/10 dark:bg-brand-blue/20 text-brand-blue rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">
                  3
                </span>
                <span>
                  <strong className="text-gray-800 dark:text-gray-200">
                    Share with your grant advisor
                  </strong>{" "}
                  -- Get a second pair of eyes before final submission.
                </span>
              </li>
            </>
          ) : (
            <>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 h-5 w-5 bg-brand-blue/10 dark:bg-brand-blue/20 text-brand-blue rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">
                  1
                </span>
                <span>
                  <strong className="text-gray-800 dark:text-gray-200">
                    Review your {hasPlan ? "project plan" : "program summary"}
                  </strong>{" "}
                  -- Make sure the details accurately reflect your program.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 h-5 w-5 bg-brand-blue/10 dark:bg-brand-blue/20 text-brand-blue rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">
                  2
                </span>
                <span>
                  <strong className="text-gray-800 dark:text-gray-200">
                    Find a matching grant
                  </strong>{" "}
                  -- Browse available grants or let us search for you.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-0.5 h-5 w-5 bg-brand-blue/10 dark:bg-brand-blue/20 text-brand-blue rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">
                  3
                </span>
                <span>
                  <strong className="text-gray-800 dark:text-gray-200">
                    Start a new application
                  </strong>{" "}
                  -- Use the wizard with a specific grant to generate a full
                  proposal.
                </span>
              </li>
            </>
          )}
        </ul>
      </div>

      {/* Navigation links */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
        {proposalId && (
          <button
            onClick={() => navigate(`/proposals/${proposalId}`)}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors",
              "text-brand-blue border border-brand-blue/30 dark:border-brand-blue/40",
              "hover:bg-brand-blue/5 dark:hover:bg-brand-blue/10",
            )}
          >
            <ExternalLink className="h-4 w-4" />
            View in Proposal Editor
          </button>
        )}
        {!hasProposal && isProgramPath && (
          <button
            onClick={() => navigate("/signals")}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors",
              "text-brand-blue border border-brand-blue/30 dark:border-brand-blue/40",
              "hover:bg-brand-blue/5 dark:hover:bg-brand-blue/10",
            )}
          >
            <Search className="h-4 w-4" />
            Find a Grant
          </button>
        )}
        <button
          onClick={() => navigate("/")}
          className={cn(
            "inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors",
            "text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600",
            "hover:bg-gray-50 dark:hover:bg-gray-800",
          )}
        >
          View Dashboard
          <ArrowRight className="h-4 w-4" />
        </button>
        <button
          onClick={() => navigate("/apply")}
          className={cn(
            "inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors",
            "text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600",
            "hover:bg-gray-50 dark:hover:bg-gray-800",
          )}
        >
          Start Another Application
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

export default ExportComplete;
