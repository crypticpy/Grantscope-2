/**
 * ExportComplete - Step 6 (final) of the Grant Application Wizard
 *
 * Celebration / success screen after the proposal has been generated.
 * Provides PDF download, summary of the grant, and next-step guidance.
 *
 * Features:
 * - PDF download via wizard export endpoint
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
} from "lucide-react";
import { cn } from "../../lib/utils";
import { exportWizardPdf, type GrantContext } from "../../lib/wizard-api";
import { supabase } from "../../App";

// =============================================================================
// Types
// =============================================================================

interface ExportCompleteProps {
  sessionId: string;
  proposalId: string | null;
  grantContext?: GrantContext | null;
}

// =============================================================================
// Helper
// =============================================================================

async function getToken(): Promise<string | null> {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token || null;
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
}) => {
  const navigate = useNavigate();
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // ---- PDF Download ----
  const handleDownloadPdf = useCallback(async () => {
    const token = await getToken();
    if (!token) {
      setDownloadError("Not authenticated. Please sign in and try again.");
      return;
    }

    setDownloading(true);
    setDownloadError(null);

    try {
      const blob = await exportWizardPdf(token, sessionId);

      // Create a temporary download link
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
    }
  }, [sessionId]);

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
          Your grant application package is ready!
        </h2>
        <p className="text-sm sm:text-base text-gray-500 dark:text-gray-400 max-w-lg mx-auto">
          Your proposal has been generated with all six sections. Download the
          PDF to review offline or share with colleagues.
        </p>

        {/* Download button */}
        <div className="mt-8">
          <button
            onClick={handleDownloadPdf}
            disabled={downloading}
            className={cn(
              "inline-flex items-center gap-2 px-6 py-3 text-base font-medium text-white rounded-lg transition-colors",
              "bg-brand-blue hover:bg-brand-dark-blue disabled:opacity-60",
            )}
          >
            {downloading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Download className="h-5 w-5" />
            )}
            {downloading ? "Preparing PDF..." : "Download PDF"}
          </button>
          {downloadError && (
            <p className="mt-3 text-sm text-red-500">{downloadError}</p>
          )}
        </div>
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
