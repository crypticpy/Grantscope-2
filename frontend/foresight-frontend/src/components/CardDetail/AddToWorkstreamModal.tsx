/**
 * AddToWorkstreamModal Component
 *
 * A modal dialog for adding a card to one of the user's workstreams.
 * Shown after following a card or via the "Add to Workstream" button.
 *
 * Features:
 * - Lists all user workstreams with descriptions
 * - Shows active/inactive status
 * - Adds card to selected workstream's screening column
 * - Loading and error states
 * - Keyboard navigation (Escape to close)
 */

import React, { useState, useEffect, useCallback, memo } from "react";
import {
  X,
  Loader2,
  Briefcase,
  Plus,
  ChevronRight,
  AlertCircle,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { cn } from "../../lib/utils";
import { supabase } from "../../App";
import { addCardToWorkstream } from "../../lib/workstream-api";

// =============================================================================
// Types
// =============================================================================

interface Workstream {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface AddToWorkstreamModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** The card ID to add */
  cardId: string;
  /** The card name for display */
  cardName: string;
  /** Callback when card is successfully added */
  onSuccess?: (workstreamName: string) => void;
  /** Function to get auth token */
  getAuthToken: () => Promise<string | undefined>;
}

// =============================================================================
// Component
// =============================================================================

export const AddToWorkstreamModal = memo(function AddToWorkstreamModal({
  isOpen,
  onClose,
  cardId,
  cardName,
  onSuccess,
  getAuthToken,
}: AddToWorkstreamModalProps) {
  const navigate = useNavigate();

  // State
  const [workstreams, setWorkstreams] = useState<Workstream[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAdding, setIsAdding] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load workstreams when modal opens
  useEffect(() => {
    if (!isOpen) return;

    const loadWorkstreams = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const { data, error: fetchError } = await supabase
          .from("workstreams")
          .select("id, name, description, is_active, created_at")
          .order("is_active", { ascending: false })
          .order("name");

        if (fetchError) {
          throw new Error(fetchError.message);
        }

        setWorkstreams(data || []);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load workstreams",
        );
      } finally {
        setIsLoading(false);
      }
    };

    loadWorkstreams();
  }, [isOpen]);

  // Handle escape key to close
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isAdding) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, isAdding, onClose]);

  // Handle adding card to workstream
  const handleAddToWorkstream = useCallback(
    async (workstream: Workstream) => {
      if (isAdding) return;

      setIsAdding(workstream.id);
      setError(null);

      try {
        const token = await getAuthToken();
        if (!token) {
          throw new Error("Authentication required");
        }

        // Add to screening column by default
        await addCardToWorkstream(token, workstream.id, cardId, "screening");

        onSuccess?.(workstream.name);
        onClose();
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to add signal to workstream",
        );
        setIsAdding(null);
      }
    },
    [cardId, getAuthToken, isAdding, onClose, onSuccess],
  );

  // Handle create new workstream
  const handleCreateNew = useCallback(() => {
    // Store card info in session storage for after workstream creation
    sessionStorage.setItem(
      "pendingWorkstreamCard",
      JSON.stringify({ cardId, cardName }),
    );
    onClose();
    navigate("/workstreams?create=true");
  }, [cardId, cardName, navigate, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="add-to-workstream-title"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
        onClick={isAdding ? undefined : onClose}
        aria-hidden="true"
      />

      {/* Modal Content */}
      <div className="relative bg-white dark:bg-dark-surface rounded-xl shadow-2xl w-full max-w-md transform transition-all">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <Briefcase className="h-5 w-5 text-brand-blue" />
            <h2
              id="add-to-workstream-title"
              className="text-lg font-semibold text-gray-900 dark:text-white"
            >
              Add to Workstream
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={!!isAdding}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-md transition-colors disabled:opacity-50"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Card Reference */}
        <div className="px-6 py-3 bg-gray-50 dark:bg-dark-surface border-b border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Adding{" "}
            <span className="font-medium text-gray-900 dark:text-white">
              {cardName}
            </span>
          </p>
        </div>

        {/* Content */}
        <div className="p-4 max-h-[60vh] overflow-y-auto">
          {/* Error Banner */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-2">
              <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm text-red-800 dark:text-red-200">
                  {error}
                </p>
              </div>
              <button
                onClick={() => setError(null)}
                className="text-red-500 hover:text-red-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Loading State */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-brand-blue mb-2" />
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Loading workstreams...
              </p>
            </div>
          )}

          {/* Workstream List */}
          {!isLoading && workstreams.length > 0 && (
            <div className="space-y-2">
              {workstreams.map((ws) => (
                <button
                  key={ws.id}
                  onClick={() => handleAddToWorkstream(ws)}
                  disabled={!!isAdding}
                  className={cn(
                    "w-full flex items-center gap-3 p-3 rounded-lg border transition-colors text-left",
                    "hover:bg-gray-50 dark:hover:bg-dark-surface-elevated",
                    "border-gray-200 dark:border-gray-600",
                    "disabled:opacity-50 disabled:cursor-not-allowed",
                    isAdding === ws.id && "bg-brand-blue/5 border-brand-blue",
                  )}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 dark:text-white truncate">
                        {ws.name}
                      </span>
                      {!ws.is_active && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
                          Inactive
                        </span>
                      )}
                    </div>
                    {ws.description && (
                      <p className="text-sm text-gray-500 dark:text-gray-400 truncate mt-0.5">
                        {ws.description}
                      </p>
                    )}
                  </div>
                  {isAdding === ws.id ? (
                    <Loader2 className="h-5 w-5 text-brand-blue animate-spin flex-shrink-0" />
                  ) : (
                    <ChevronRight className="h-5 w-5 text-gray-400 flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Empty State */}
          {!isLoading && workstreams.length === 0 && (
            <div className="text-center py-8">
              <Briefcase className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
              <p className="text-gray-900 dark:text-white font-medium mb-1">
                No workstreams yet
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                Create your first workstream to organize research signals
              </p>
            </div>
          )}
        </div>

        {/* Footer - Create New Workstream */}
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={handleCreateNew}
            disabled={!!isAdding}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-brand-blue hover:text-brand-dark-blue bg-brand-blue/5 hover:bg-brand-blue/10 border border-brand-blue/30 rounded-lg transition-colors disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            Create New Workstream
          </button>
        </div>
      </div>
    </div>
  );
});

export default AddToWorkstreamModal;
