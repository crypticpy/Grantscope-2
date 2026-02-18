/**
 * CardDocuments Component
 *
 * Provides document upload and management for a card, including:
 * - Drag-and-drop or click-to-browse file upload
 * - Document type classification (nofo, budget, narrative, etc.)
 * - Optional description field
 * - List of uploaded documents with metadata
 * - Download and delete actions
 * - Dark mode support
 *
 * @module CardDocuments
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Upload,
  FileText,
  Trash2,
  Download,
  Loader2,
  AlertCircle,
  X,
  ChevronDown,
} from "lucide-react";
import { cn } from "../../lib/utils";
import {
  uploadCardDocument,
  listCardDocuments,
  deleteCardDocument,
  getDocumentDownloadUrl,
  type CardDocumentResponse,
  type CardDocumentType,
} from "../../lib/discovery-api";

// =============================================================================
// Constants
// =============================================================================

const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB

const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".doc", ".txt", ".pptx", ".xlsx"];

const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/msword",
  "text/plain",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
];

const DOCUMENT_TYPE_OPTIONS: { value: CardDocumentType; label: string }[] = [
  { value: "nofo", label: "NOFO" },
  { value: "budget", label: "Budget" },
  { value: "narrative", label: "Narrative" },
  { value: "letter_of_support", label: "Letter of Support" },
  { value: "application_guide", label: "Application Guide" },
  { value: "other", label: "Other" },
];

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  nofo: "NOFO",
  budget: "Budget",
  narrative: "Narrative",
  letter_of_support: "Letter of Support",
  application_guide: "Application Guide",
  other: "Other",
};

const DOCUMENT_TYPE_COLORS: Record<string, { bg: string; text: string }> = {
  nofo: {
    bg: "bg-blue-100 dark:bg-blue-900/30",
    text: "text-blue-700 dark:text-blue-300",
  },
  budget: {
    bg: "bg-green-100 dark:bg-green-900/30",
    text: "text-green-700 dark:text-green-300",
  },
  narrative: {
    bg: "bg-purple-100 dark:bg-purple-900/30",
    text: "text-purple-700 dark:text-purple-300",
  },
  letter_of_support: {
    bg: "bg-amber-100 dark:bg-amber-900/30",
    text: "text-amber-700 dark:text-amber-300",
  },
  application_guide: {
    bg: "bg-cyan-100 dark:bg-cyan-900/30",
    text: "text-cyan-700 dark:text-cyan-300",
  },
  other: {
    bg: "bg-gray-100 dark:bg-gray-700/50",
    text: "text-gray-700 dark:text-gray-300",
  },
};

// =============================================================================
// Helpers
// =============================================================================

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "Unknown";
  }
}

function getFileExtension(filename: string): string {
  const parts = filename.split(".");
  return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "";
}

// =============================================================================
// Component
// =============================================================================

export const CardDocuments: React.FC<{ cardId: string }> = ({ cardId }) => {
  // -- State ------------------------------------------------------------------
  const [documents, setDocuments] = useState<CardDocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<CardDocumentType>("other");
  const [description, setDescription] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const [showTypeDropdown, setShowTypeDropdown] = useState(false);

  // Delete state
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // -- Auth -------------------------------------------------------------------
  const getToken = useCallback((): string | null => {
    return localStorage.getItem("gs2_token");
  }, []);

  // -- Data Loading -----------------------------------------------------------
  const loadDocuments = useCallback(async () => {
    const token = getToken();
    if (!token) return;

    setLoading(true);
    setError(null);
    try {
      const response = await listCardDocuments(token, cardId);
      setDocuments(response.documents);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [cardId, getToken]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setShowTypeDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // -- File Validation --------------------------------------------------------
  const validateFile = useCallback((file: File): string | null => {
    if (file.size > MAX_FILE_SIZE) {
      return `File size (${formatFileSize(file.size)}) exceeds the 25 MB limit.`;
    }

    const ext = "." + (file.name.split(".").pop()?.toLowerCase() || "");
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      return `File type '${ext}' is not supported. Accepted: ${ACCEPTED_EXTENSIONS.join(", ")}`;
    }

    // Also check MIME type if the browser provides one
    if (file.type && !ACCEPTED_MIME_TYPES.includes(file.type)) {
      // Some browsers may report slightly different MIME types, so only warn
      // if the extension is also not valid (already checked above).
    }

    return null;
  }, []);

  // -- File Selection ---------------------------------------------------------
  const handleFileSelect = useCallback(
    (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        setUploadError(validationError);
        return;
      }
      setSelectedFile(file);
      setUploadError(null);
    },
    [validateFile],
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect],
  );

  // -- Drag and Drop ----------------------------------------------------------
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      const file = e.dataTransfer.files?.[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect],
  );

  // -- Upload -----------------------------------------------------------------
  const handleUpload = useCallback(async () => {
    if (!selectedFile) return;

    const token = getToken();
    if (!token) {
      setUploadError("Not authenticated. Please log in again.");
      return;
    }

    setUploading(true);
    setUploadError(null);
    try {
      await uploadCardDocument(
        token,
        cardId,
        selectedFile,
        documentType,
        description.trim() || undefined,
      );
      // Reset form
      setSelectedFile(null);
      setDocumentType("other");
      setDescription("");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      // Reload documents
      await loadDocuments();
    } catch (err: unknown) {
      setUploadError(
        err instanceof Error ? err.message : "Upload failed. Please try again.",
      );
    } finally {
      setUploading(false);
    }
  }, [
    selectedFile,
    cardId,
    documentType,
    description,
    getToken,
    loadDocuments,
  ]);

  // -- Delete -----------------------------------------------------------------
  const handleDelete = useCallback(
    async (documentId: string) => {
      const token = getToken();
      if (!token) return;

      setDeletingId(documentId);
      try {
        await deleteCardDocument(token, cardId, documentId);
        setDocuments((prev) => prev.filter((d) => d.id !== documentId));
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : "Failed to delete document",
        );
      } finally {
        setDeletingId(null);
      }
    },
    [cardId, getToken],
  );

  // -- Download ---------------------------------------------------------------
  const handleDownload = useCallback(
    async (doc: CardDocumentResponse) => {
      const token = getToken();
      if (!token) return;

      setDownloadingId(doc.id);
      try {
        const result = await getDocumentDownloadUrl(token, cardId, doc.id);
        window.open(result.url, "_blank", "noopener,noreferrer");
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : "Failed to get download URL",
        );
      } finally {
        setDownloadingId(null);
      }
    },
    [cardId, getToken],
  );

  // -- Clear selected file ----------------------------------------------------
  const clearSelectedFile = useCallback(() => {
    setSelectedFile(null);
    setUploadError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  // ==========================================================================
  // Render
  // ==========================================================================

  // Loading state
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400 mb-4" />
        <p className="text-gray-500 dark:text-gray-400">Loading documents...</p>
      </div>
    );
  }

  // Fatal error state
  if (error && documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <div className="text-red-500 mb-4">
          <AlertCircle className="h-12 w-12" />
        </div>
        <p className="text-gray-900 dark:text-white font-medium mb-2">
          Failed to load documents
        </p>
        <p className="text-gray-500 dark:text-gray-400 text-sm mb-4">{error}</p>
        <button
          onClick={loadDocuments}
          className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Inline error banner */}
      {error && documents.length > 0 && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
          <AlertCircle className="h-4 w-4 text-red-500 flex-shrink-0" />
          <p className="text-sm text-red-700 dark:text-red-300 flex-1">
            {error}
          </p>
          <button
            onClick={() => setError(null)}
            className="text-red-500 hover:text-red-700"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* ================================================================== */}
      {/* Upload Area                                                        */}
      {/* ================================================================== */}
      <div
        className={cn(
          "rounded-lg border-2 border-dashed transition-colors",
          isDragOver
            ? "border-blue-400 bg-blue-50 dark:bg-blue-900/20"
            : "border-gray-300 dark:border-gray-600 bg-white dark:bg-dark-surface",
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="p-6">
          {!selectedFile ? (
            /* Drop zone / file picker */
            <div className="flex flex-col items-center text-center">
              <div
                className={cn(
                  "p-3 rounded-full mb-3",
                  isDragOver
                    ? "bg-blue-100 dark:bg-blue-800/40"
                    : "bg-gray-100 dark:bg-gray-700/50",
                )}
              >
                <Upload
                  className={cn(
                    "h-6 w-6",
                    isDragOver
                      ? "text-blue-500"
                      : "text-gray-400 dark:text-gray-500",
                  )}
                />
              </div>
              <p className="text-sm font-medium text-gray-900 dark:text-white mb-1">
                {isDragOver ? "Drop file here" : "Drag and drop a file, or"}
              </p>
              {!isDragOver && (
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 font-medium"
                >
                  click to browse
                </button>
              )}
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                PDF, DOCX, TXT, PPTX, XLSX — max 25 MB
              </p>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept={ACCEPTED_EXTENSIONS.join(",")}
                onChange={handleInputChange}
              />
            </div>
          ) : (
            /* Selected file + metadata form */
            <div className="space-y-4">
              {/* Selected file info */}
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-gray-100 dark:bg-gray-700/50">
                  <FileText className="h-5 w-5 text-gray-500 dark:text-gray-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                    {selectedFile.name}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {formatFileSize(selectedFile.size)} &middot;{" "}
                    {getFileExtension(selectedFile.name)}
                  </p>
                </div>
                <button
                  onClick={clearSelectedFile}
                  className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  title="Remove file"
                >
                  <X className="h-4 w-4 text-gray-500" />
                </button>
              </div>

              {/* Document type + description */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Document type dropdown */}
                <div className="relative" ref={dropdownRef}>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Document Type
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowTypeDropdown(!showTypeDropdown)}
                    className={cn(
                      "w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg",
                      "border border-gray-200 dark:border-gray-700",
                      "bg-white dark:bg-dark-surface",
                      "text-gray-900 dark:text-white",
                      "hover:bg-gray-50 dark:hover:bg-gray-700/50",
                      "transition-colors",
                    )}
                  >
                    {DOCUMENT_TYPE_LABELS[documentType] || "Other"}
                    <ChevronDown
                      className={cn(
                        "h-4 w-4 text-gray-400 transition-transform",
                        showTypeDropdown && "rotate-180",
                      )}
                    />
                  </button>
                  {showTypeDropdown && (
                    <div className="absolute z-10 mt-1 w-full bg-white dark:bg-dark-surface rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1">
                      {DOCUMENT_TYPE_OPTIONS.map((opt) => (
                        <button
                          key={opt.value}
                          onClick={() => {
                            setDocumentType(opt.value);
                            setShowTypeDropdown(false);
                          }}
                          className={cn(
                            "w-full px-3 py-2 text-sm text-left",
                            "hover:bg-gray-100 dark:hover:bg-gray-700",
                            "text-gray-900 dark:text-white",
                            documentType === opt.value &&
                              "bg-gray-100 dark:bg-gray-700",
                          )}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Description */}
                <div>
                  <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Description{" "}
                    <span className="text-gray-400 font-normal">
                      (optional)
                    </span>
                  </label>
                  <input
                    type="text"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Brief description..."
                    className={cn(
                      "w-full px-3 py-2 text-sm rounded-lg",
                      "border border-gray-200 dark:border-gray-700",
                      "bg-white dark:bg-dark-surface",
                      "text-gray-900 dark:text-white",
                      "placeholder-gray-500 dark:placeholder-gray-400",
                      "focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                    )}
                  />
                </div>
              </div>

              {/* Upload error */}
              {uploadError && (
                <div className="flex items-center gap-2 p-2.5 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                  <AlertCircle className="h-4 w-4 text-red-500 flex-shrink-0" />
                  <p className="text-sm text-red-700 dark:text-red-300">
                    {uploadError}
                  </p>
                </div>
              )}

              {/* Upload button */}
              <div className="flex justify-end">
                <button
                  onClick={handleUpload}
                  disabled={uploading}
                  className={cn(
                    "inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg",
                    "text-white transition-colors",
                    uploading
                      ? "bg-gray-400 cursor-not-allowed"
                      : "bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600",
                  )}
                >
                  {uploading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="h-4 w-4" />
                      Upload Document
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ================================================================== */}
      {/* Document List                                                      */}
      {/* ================================================================== */}
      {documents.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8">
          <div className="p-4 rounded-full mb-4 bg-gray-100 dark:bg-gray-700/50">
            <FileText className="h-8 w-8 text-gray-400 dark:text-gray-500" />
          </div>
          <p className="text-gray-900 dark:text-white font-medium mb-1">
            No documents yet
          </p>
          <p className="text-gray-500 dark:text-gray-400 text-sm text-center max-w-sm">
            Upload grant documents like NOFOs, budgets, narratives, and letters
            of support to keep everything organized.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {documents.length} document{documents.length !== 1 ? "s" : ""}
          </p>

          {documents.map((doc) => {
            const typeColors =
              DOCUMENT_TYPE_COLORS[doc.document_type] ||
              DOCUMENT_TYPE_COLORS.other;
            const isDeleting = deletingId === doc.id;
            const isDownloading = downloadingId === doc.id;

            return (
              <div
                key={doc.id}
                className={cn(
                  "group relative p-4 rounded-lg border transition-all duration-200",
                  "bg-white dark:bg-dark-surface",
                  "border-gray-200 dark:border-gray-700",
                  "hover:border-gray-300 dark:hover:border-gray-600",
                  "hover:shadow-md",
                )}
              >
                <div className="flex items-start gap-4">
                  {/* File icon */}
                  <div className="flex-shrink-0 p-2.5 rounded-lg bg-gray-100 dark:bg-gray-700/50">
                    <FileText className="h-5 w-5 text-gray-500 dark:text-gray-400" />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h4 className="font-medium text-gray-900 dark:text-white truncate">
                          {doc.original_filename}
                        </h4>
                        <div className="flex items-center gap-2 mt-1 flex-wrap">
                          {/* Type badge */}
                          <span
                            className={cn(
                              "text-xs font-medium px-2 py-0.5 rounded-full",
                              typeColors.bg,
                              typeColors.text,
                            )}
                          >
                            {DOCUMENT_TYPE_LABELS[doc.document_type] ||
                              doc.document_type}
                          </span>
                          {/* File extension */}
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {getFileExtension(doc.original_filename)}
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                        <button
                          onClick={() => handleDownload(doc)}
                          disabled={isDownloading}
                          className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                          title="Download"
                        >
                          {isDownloading ? (
                            <Loader2 className="h-4 w-4 animate-spin text-gray-500" />
                          ) : (
                            <Download className="h-4 w-4 text-gray-500" />
                          )}
                        </button>
                        <button
                          onClick={() => handleDelete(doc.id)}
                          disabled={isDeleting}
                          className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                          title="Delete"
                        >
                          {isDeleting ? (
                            <Loader2 className="h-4 w-4 animate-spin text-red-500" />
                          ) : (
                            <Trash2 className="h-4 w-4 text-red-500" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Description */}
                    {doc.description && (
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">
                        {doc.description}
                      </p>
                    )}

                    {/* Metadata row */}
                    <div className="flex items-center gap-3 mt-2 text-xs text-gray-500 dark:text-gray-400">
                      {doc.created_at && (
                        <span>{formatDate(doc.created_at)}</span>
                      )}
                      <span>{formatFileSize(doc.file_size_bytes)}</span>
                      {doc.extraction_status === "completed" && (
                        <span className="text-green-600 dark:text-green-400">
                          Text extracted
                        </span>
                      )}
                      {doc.extraction_status === "failed" && (
                        <span className="text-amber-600 dark:text-amber-400">
                          Extraction failed
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default CardDocuments;
