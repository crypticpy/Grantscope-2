/**
 * WizardSaveExit - Save & Exit bar for the Grant Wizard
 *
 * Shows auto-save status and provides a "Save & Come Back Later" action.
 * Renders as a slim bar between the step progress indicator and the step content.
 */

import React, { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Save, Check, Loader2, X } from "lucide-react";

interface WizardSaveExitProps {
  /** Whether data is currently being saved */
  saving?: boolean;
  /** Timestamp of last save (ISO string) */
  lastSaved?: string | null;
}

export const WizardSaveExit: React.FC<WizardSaveExitProps> = ({
  saving = false,
  lastSaved,
}) => {
  const navigate = useNavigate();
  const [showModal, setShowModal] = useState(false);

  const handleSaveAndExit = useCallback(() => {
    setShowModal(true);
  }, []);

  const handleConfirmExit = useCallback(() => {
    navigate("/");
  }, [navigate]);

  // Format relative time
  const timeAgo = lastSaved ? formatRelativeTime(lastSaved) : null;

  return (
    <>
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-dark-surface-deep border-b border-gray-200 dark:border-gray-700 text-xs">
        {/* Save status */}
        <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
          {saving ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Saving...</span>
            </>
          ) : (
            <>
              <Check className="h-3.5 w-3.5 text-green-500" />
              <span>All changes saved{timeAgo ? ` ${timeAgo}` : ""}</span>
            </>
          )}
        </div>

        {/* Save & Exit button */}
        <button
          onClick={handleSaveAndExit}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 bg-white dark:bg-dark-surface border border-gray-200 dark:border-gray-700 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          <Save className="h-3.5 w-3.5" />
          Save &amp; Come Back Later
        </button>
      </div>

      {/* Confirmation modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-dark-surface rounded-xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Your progress is saved
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              Your progress is saved automatically. You can close this tab and
              come back anytime from your dashboard to pick up where you left
              off.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowModal(false)}
                className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                Keep Working
              </button>
              <button
                onClick={handleConfirmExit}
                className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-brand-blue rounded-lg hover:bg-brand-dark-blue transition-colors"
              >
                Go to Dashboard
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.floor(diffHours / 24)}d ago`;
  } catch {
    return "";
  }
}

export default WizardSaveExit;
