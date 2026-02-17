/**
 * GrantInput Component
 *
 * Step 1a of the Grant Application Wizard. Allows the user to provide a grant
 * opportunity via URL or file upload. Uses AI to extract grant context and
 * presents results for review before proceeding.
 *
 * Features:
 * - Tab toggle between URL paste and document upload
 * - Drag-and-drop file upload with validation
 * - Loading states with contextual messaging
 * - Extracted grant context display via GrantRequirementsCard
 * - Error handling with user-friendly messages
 * - Full dark mode support
 *
 * @module wizard/GrantInput
 */

import React, { useState, useRef, useCallback } from "react";
import {
  Loader2,
  Upload,
  Link as LinkIcon,
  FileText,
  X,
  ArrowLeft,
  ArrowRight,
  RefreshCw,
} from "lucide-react";
import { cn } from "../../lib/utils";
import {
  processGrantUrl,
  processGrantFile,
  type GrantContext,
} from "../../lib/wizard-api";
import { GrantRequirementsCard } from "./GrantRequirementsCard";

// =============================================================================
// Constants
// =============================================================================

const MAX_FILE_SIZE_MB = 10;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const ACCEPTED_FILE_TYPES = ".pdf,.txt";

// =============================================================================
// Props
// =============================================================================

export interface GrantInputProps {
  sessionId: string;
  onGrantProcessed: (grantContext: GrantContext, cardId?: string) => void;
  onBack: () => void;
}

// =============================================================================
// Helpers
// =============================================================================

type TabId = "url" | "upload";

/**
 * Retrieves the current Supabase session access token.
 */
async function getToken(): Promise<string | null> {
  const token = localStorage.getItem("gs2_token");
  return token || null;
}

/**
 * Format file size in human-readable form.
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Maps common error patterns to user-friendly messages.
 */
function getUserFriendlyError(error: unknown, tab: TabId): string {
  const message = error instanceof Error ? error.message : String(error);
  const lower = message.toLowerCase();

  if (tab === "url") {
    if (
      lower.includes("fetch") ||
      lower.includes("access") ||
      lower.includes("404") ||
      lower.includes("timeout")
    ) {
      return "We couldn't access that URL. Check the address and try again.";
    }
  }

  if (tab === "upload") {
    if (
      lower.includes("read") ||
      lower.includes("parse") ||
      lower.includes("corrupt")
    ) {
      return "We couldn't read this document. Try pasting the text directly.";
    }
  }

  if (
    lower.includes("extract") ||
    lower.includes("context") ||
    lower.includes("empty")
  ) {
    return "We couldn't extract grant details. Try a different document.";
  }

  // Generic fallback with original message
  return message || "Something went wrong. Please try again.";
}

// =============================================================================
// Component
// =============================================================================

export const GrantInput: React.FC<GrantInputProps> = ({
  sessionId,
  onGrantProcessed,
  onBack,
}) => {
  // Tab state
  const [activeTab, setActiveTab] = useState<TabId>("url");

  // URL tab state
  const [url, setUrl] = useState("");

  // Upload tab state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);

  // Shared state
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [grantContext, setGrantContext] = useState<GrantContext | null>(null);
  const [cardId, setCardId] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // URL Handling
  // ---------------------------------------------------------------------------

  const handleAnalyzeUrl = useCallback(async () => {
    if (!url.trim()) return;

    setError(null);
    setLoading(true);
    setLoadingMessage("Reading grant details...");

    try {
      const token = await getToken();
      if (!token) {
        setError("Not authenticated. Please log in and try again.");
        return;
      }

      const result = await processGrantUrl(token, sessionId, url.trim());
      setGrantContext(result.grant_context);
      setCardId(result.card_id || null);
    } catch (err) {
      setError(getUserFriendlyError(err, "url"));
    } finally {
      setLoading(false);
      setLoadingMessage("");
    }
  }, [url, sessionId]);

  // ---------------------------------------------------------------------------
  // File Handling
  // ---------------------------------------------------------------------------

  const validateFile = useCallback((file: File): string | null => {
    if (file.size > MAX_FILE_SIZE_BYTES) {
      return `File is too large (${formatFileSize(file.size)}). Maximum size is ${MAX_FILE_SIZE_MB}MB.`;
    }
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !["pdf", "txt"].includes(ext)) {
      return "Unsupported file type. Please upload a PDF or TXT file.";
    }
    return null;
  }, []);

  const handleFileSelected = useCallback(
    (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }
      setError(null);
      setSelectedFile(file);
    },
    [validateFile],
  );

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFileSelected(file);
    },
    [handleFileSelected],
  );

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current += 1;
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragOver(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter.current = 0;
      setIsDragOver(false);

      const file = e.dataTransfer.files?.[0];
      if (file) handleFileSelected(file);
    },
    [handleFileSelected],
  );

  const handleAnalyzeFile = useCallback(async () => {
    if (!selectedFile) return;

    setError(null);
    setLoading(true);
    setLoadingMessage("Extracting grant details...");

    try {
      const token = await getToken();
      if (!token) {
        setError("Not authenticated. Please log in and try again.");
        return;
      }

      const result = await processGrantFile(token, sessionId, selectedFile);
      setGrantContext(result.grant_context);
      setCardId(result.card_id || null);
    } catch (err) {
      setError(getUserFriendlyError(err, "upload"));
    } finally {
      setLoading(false);
      setLoadingMessage("");
    }
  }, [selectedFile, sessionId]);

  // ---------------------------------------------------------------------------
  // Reset / Continue
  // ---------------------------------------------------------------------------

  const handleReset = useCallback(() => {
    setGrantContext(null);
    setCardId(null);
    setUrl("");
    setSelectedFile(null);
    setError(null);
  }, []);

  const handleContinue = useCallback(() => {
    if (grantContext) {
      onGrantProcessed(grantContext, cardId || undefined);
    }
  }, [grantContext, cardId, onGrantProcessed]);

  // ---------------------------------------------------------------------------
  // Render: Results View (after successful extraction)
  // ---------------------------------------------------------------------------

  if (grantContext) {
    return (
      <div className="space-y-6">
        <GrantRequirementsCard grantContext={grantContext} />

        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={handleReset}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md transition-colors min-h-[44px]",
              "text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface",
              "border border-gray-300 dark:border-gray-600",
              "hover:bg-gray-50 dark:hover:bg-gray-800",
            )}
          >
            <RefreshCw className="h-4 w-4" />
            Try a different grant
          </button>
          <button
            type="button"
            onClick={handleContinue}
            className={cn(
              "inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white rounded-md transition-colors min-h-[44px]",
              "bg-brand-blue hover:bg-brand-dark-blue",
            )}
          >
            Looks good, continue
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Input View
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-1">
          Tell us about your grant
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Paste a link to the grant listing or upload the grant document. We'll
          extract the key details automatically.
        </p>
      </div>

      {/* Tab Toggle */}
      <div
        className="flex border-b border-gray-200 dark:border-gray-700"
        role="tablist"
        aria-label="Grant input method"
      >
        <button
          type="button"
          role="tab"
          id="tab-url"
          aria-selected={activeTab === "url"}
          aria-controls="panel-url"
          onClick={() => {
            setActiveTab("url");
            setError(null);
          }}
          className={cn(
            "inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px min-h-[44px]",
            activeTab === "url"
              ? "border-brand-blue text-brand-blue"
              : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600",
          )}
        >
          <LinkIcon className="h-4 w-4" />
          Paste a URL
        </button>
        <button
          type="button"
          role="tab"
          id="tab-upload"
          aria-selected={activeTab === "upload"}
          aria-controls="panel-upload"
          onClick={() => {
            setActiveTab("upload");
            setError(null);
          }}
          className={cn(
            "inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px min-h-[44px]",
            activeTab === "upload"
              ? "border-brand-blue text-brand-blue"
              : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600",
          )}
        >
          <Upload className="h-4 w-4" />
          Upload a Document
        </button>
      </div>

      {/* Error Alert */}
      {error && (
        <div
          className="flex items-start gap-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md"
          role="alert"
        >
          <p className="flex-1 text-sm text-red-700 dark:text-red-300">
            {error}
          </p>
          <button
            type="button"
            onClick={() => setError(null)}
            className="flex-shrink-0 text-red-400 hover:text-red-600 dark:hover:text-red-200 transition-colors"
            aria-label="Dismiss error"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* URL Tab Panel */}
      {activeTab === "url" && (
        <div
          id="panel-url"
          role="tabpanel"
          aria-labelledby="tab-url"
          className="space-y-4"
        >
          <div>
            <label
              htmlFor="grant-url"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5"
            >
              Grant URL
            </label>
            <input
              id="grant-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.grants.gov/search-results-detail/..."
              disabled={loading}
              className={cn(
                "w-full px-3 py-2.5 text-sm rounded-md transition-colors min-h-[44px]",
                "bg-white dark:bg-dark-surface-deep",
                "border border-gray-300 dark:border-gray-600",
                "text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue",
                "disabled:opacity-50 disabled:cursor-not-allowed",
              )}
              onKeyDown={(e) => {
                if (e.key === "Enter" && url.trim() && !loading) {
                  handleAnalyzeUrl();
                }
              }}
            />
          </div>

          <button
            type="button"
            onClick={handleAnalyzeUrl}
            disabled={!url.trim() || loading}
            className={cn(
              "inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white rounded-md transition-colors min-h-[44px]",
              "bg-brand-blue hover:bg-brand-dark-blue",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {loadingMessage}
              </>
            ) : (
              "Analyze Grant"
            )}
          </button>
        </div>
      )}

      {/* Upload Tab Panel */}
      {activeTab === "upload" && (
        <div
          id="panel-upload"
          role="tabpanel"
          aria-labelledby="tab-upload"
          className="space-y-4"
        >
          {/* Drag-and-drop zone */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            className={cn(
              "flex flex-col items-center justify-center px-6 py-10 rounded-lg border-2 border-dashed transition-colors cursor-pointer min-h-[44px]",
              isDragOver
                ? "border-brand-blue bg-brand-blue/5 dark:bg-brand-blue/10"
                : "border-gray-300 dark:border-gray-600 hover:border-brand-blue dark:hover:border-brand-blue",
              loading && "opacity-50 pointer-events-none",
            )}
            aria-label="Upload grant document. Click or drag and drop a PDF or TXT file."
          >
            <Upload className="h-8 w-8 text-gray-400 dark:text-gray-500 mb-3" />
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {isDragOver
                ? "Drop your file here"
                : "Click to browse or drag and drop"}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              PDF or TXT up to {MAX_FILE_SIZE_MB}MB
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_FILE_TYPES}
              onChange={handleFileInputChange}
              className="sr-only"
              aria-hidden="true"
              tabIndex={-1}
            />
          </div>

          {/* Selected file display */}
          {selectedFile && (
            <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-dark-surface-deep rounded-md border border-gray-200 dark:border-gray-700">
              <FileText className="h-5 w-5 text-brand-blue flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                  {selectedFile.name}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {formatFileSize(selectedFile.size)}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelectedFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                className="flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
                aria-label="Remove selected file"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={handleAnalyzeFile}
            disabled={!selectedFile || loading}
            className={cn(
              "inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white rounded-md transition-colors min-h-[44px]",
              "bg-brand-blue hover:bg-brand-dark-blue",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {loadingMessage}
              </>
            ) : (
              "Analyze Document"
            )}
          </button>
        </div>
      )}

      {/* Back button */}
      <div className="pt-2">
        <button
          type="button"
          onClick={onBack}
          disabled={loading}
          className={cn(
            "inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md transition-colors min-h-[44px]",
            "text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-surface",
            "border border-gray-300 dark:border-gray-600",
            "hover:bg-gray-50 dark:hover:bg-gray-800",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
      </div>
    </div>
  );
};

export default GrantInput;
