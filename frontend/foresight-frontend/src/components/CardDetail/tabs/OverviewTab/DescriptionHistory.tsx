/**
 * DescriptionHistory Component
 *
 * Shows version history for a card's description field with the ability
 * to preview and restore previous versions.
 *
 * @module CardDetail/tabs/OverviewTab/DescriptionHistory
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  fetchCardSnapshots,
  fetchCardSnapshot,
  restoreCardSnapshot,
  type CardSnapshot,
} from "../../../../lib/discovery-api";
import { MarkdownReport } from "../../MarkdownReport";

interface DescriptionHistoryProps {
  cardId: string;
  isOpen: boolean;
  onClose: () => void;
  onRestore?: () => void;
}

const TRIGGER_LABELS: Record<string, { label: string; color: string }> = {
  deep_research: {
    label: "Deep Research",
    color: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  },
  profile_refresh: {
    label: "Profile Refresh",
    color:
      "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  },
  enhance_research: {
    label: "Research Update",
    color:
      "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
  },
  manual_edit: {
    label: "Manual Edit",
    color: "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300",
  },
  restore: {
    label: "Restored",
    color:
      "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  },
  initial: {
    label: "Original",
    color: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  },
};

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatWordCount(charLength: number): string {
  const words = Math.round(charLength / 5.5);
  if (words < 100) return `~${words} words`;
  return `~${Math.round(words / 10) * 10} words`;
}

export const DescriptionHistory: React.FC<DescriptionHistoryProps> = ({
  cardId,
  isOpen,
  onClose,
  onRestore,
}) => {
  const [snapshots, setSnapshots] = useState<CardSnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewSnapshot, setPreviewSnapshot] = useState<CardSnapshot | null>(
    null,
  );
  const [previewLoading, setPreviewLoading] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);

  const getToken = useCallback(async () => {
    const token = localStorage.getItem("gs2_token");
    return token || "";
  }, []);

  const loadSnapshots = useCallback(async () => {
    setLoading(true);
    try {
      const token = await getToken();
      if (token) {
        const result = await fetchCardSnapshots(token, cardId, "description");
        setSnapshots(result.snapshots);
      }
    } catch {
      // Silently handle - empty state is fine
    } finally {
      setLoading(false);
    }
  }, [cardId, getToken]);

  useEffect(() => {
    if (isOpen) {
      loadSnapshots();
    }
  }, [isOpen, loadSnapshots]);

  const handlePreview = async (snapshotId: string) => {
    setPreviewLoading(true);
    try {
      const token = await getToken();
      if (token) {
        const snapshot = await fetchCardSnapshot(token, cardId, snapshotId);
        setPreviewSnapshot(snapshot);
      }
    } catch {
      // Silently handle
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleRestore = async (snapshotId: string) => {
    if (
      !confirm(
        "Restore this version? The current description will be saved as a snapshot first.",
      )
    ) {
      return;
    }
    setRestoring(snapshotId);
    try {
      const token = await getToken();
      if (token) {
        await restoreCardSnapshot(token, cardId, snapshotId);
        onRestore?.();
        onClose();
      }
    } catch {
      // Silently handle
    } finally {
      setRestoring(null);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
        onKeyDown={(e) => e.key === "Escape" && onClose()}
        role="button"
        tabIndex={0}
        aria-label="Close history panel"
      />

      {/* Panel */}
      <div className="fixed inset-y-0 right-0 w-full max-w-lg bg-white dark:bg-dark-surface shadow-xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Description History
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {snapshots.length} saved version
              {snapshots.length !== 1 ? "s" : ""}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            aria-label="Close"
          >
            <svg
              className="w-5 h-5 text-gray-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Snapshot List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            </div>
          ) : snapshots.length === 0 ? (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400">
              <svg
                className="w-12 h-12 mx-auto mb-3 opacity-40"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="text-sm">
                No version history yet. Snapshots are saved automatically before
                description updates.
              </p>
            </div>
          ) : (
            snapshots.map((snap, index) => {
              const triggerInfo =
                TRIGGER_LABELS[snap.trigger] ?? TRIGGER_LABELS.manual_edit!;
              return (
                <div
                  key={snap.id}
                  className={`border rounded-lg p-3 transition-colors ${
                    index === 0
                      ? "border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/10"
                      : "border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${triggerInfo!.color}`}
                        >
                          {triggerInfo!.label}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {formatWordCount(snap.content_length)}
                        </span>
                        {index === 0 && (
                          <span className="text-xs text-blue-600 dark:text-blue-400 font-medium">
                            Most recent
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {formatDate(snap.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handlePreview(snap.id)}
                        className="px-2.5 py-1 text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                        disabled={previewLoading}
                      >
                        View
                      </button>
                      <button
                        onClick={() => handleRestore(snap.id)}
                        className="px-2.5 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                        disabled={restoring === snap.id}
                      >
                        {restoring === snap.id ? "Restoring..." : "Restore"}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Preview Modal */}
      {previewSnapshot && (
        <>
          <div
            className="fixed inset-0 bg-black/60 z-[60]"
            onClick={() => setPreviewSnapshot(null)}
            onKeyDown={(e) => e.key === "Escape" && setPreviewSnapshot(null)}
            role="button"
            tabIndex={0}
            aria-label="Close preview"
          />
          <div className="fixed inset-4 sm:inset-8 lg:inset-16 bg-white dark:bg-dark-surface rounded-xl shadow-2xl z-[70] flex flex-col overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b dark:border-gray-700 shrink-0">
              <div className="flex items-center gap-3">
                <h4 className="font-semibold text-gray-900 dark:text-white">
                  Version Preview
                </h4>
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                    (TRIGGER_LABELS[previewSnapshot.trigger] ??
                      TRIGGER_LABELS.manual_edit!)!.color
                  }`}
                >
                  {
                    (TRIGGER_LABELS[previewSnapshot.trigger] ??
                      TRIGGER_LABELS.manual_edit!)!.label
                  }
                </span>
                <span className="text-xs text-gray-500">
                  {formatDate(previewSnapshot.created_at)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    handleRestore(previewSnapshot.id);
                    setPreviewSnapshot(null);
                  }}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                >
                  Restore This Version
                </button>
                <button
                  onClick={() => setPreviewSnapshot(null)}
                  className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  aria-label="Close preview"
                >
                  <svg
                    className="w-5 h-5 text-gray-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-6">
              {previewSnapshot.content ? (
                <MarkdownReport content={previewSnapshot.content} />
              ) : (
                <p className="text-gray-500 italic">No content available</p>
              )}
            </div>
          </div>
        </>
      )}
    </>
  );
};

export default DescriptionHistory;
