/**
 * DownloadButton - Reusable download button with PDF/DOCX format selection
 *
 * Split-button design: primary action downloads PDF, dropdown chevron
 * reveals a menu with PDF and Word (DOCX) options.
 *
 * @module components/wizard/DownloadButton
 */

import React, { useState, useCallback, useRef, useEffect } from "react";
import { Download, FileText, ChevronDown, Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

// ============================================================================
// Types
// ============================================================================

interface DownloadButtonProps {
  /** Label for the button */
  label: string;
  /** Called when user selects a format to download */
  onDownload: (format: "pdf" | "docx") => Promise<void>;
  /** Whether download is in progress */
  loading?: boolean;
  /** Disable the button */
  disabled?: boolean;
  /** Size variant */
  size?: "sm" | "md";
}

// ============================================================================
// Component
// ============================================================================

export const DownloadButton: React.FC<DownloadButtonProps> = ({
  label,
  onDownload,
  loading = false,
  disabled = false,
  size = "md",
}) => {
  const [open, setOpen] = useState(false);
  const [activeFormat, setActiveFormat] = useState<"pdf" | "docx" | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleDownload = useCallback(
    async (format: "pdf" | "docx") => {
      setActiveFormat(format);
      setOpen(false);
      try {
        await onDownload(format);
      } finally {
        setActiveFormat(null);
      }
    },
    [onDownload],
  );

  const isLoading = loading || activeFormat !== null;
  const sizeClasses =
    size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm";

  return (
    <div className="relative inline-flex" ref={dropdownRef}>
      {/* Primary button: Download PDF */}
      <button
        onClick={() => handleDownload("pdf")}
        disabled={disabled || isLoading}
        className={cn(
          "inline-flex items-center gap-1.5 font-medium rounded-l-lg border border-r-0 transition-colors",
          sizeClasses,
          isLoading || disabled
            ? "bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed border-gray-200 dark:border-gray-700"
            : "bg-white dark:bg-dark-surface text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800",
        )}
      >
        {isLoading && activeFormat === "pdf" ? (
          <Loader2
            className={cn(
              "animate-spin",
              size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4",
            )}
          />
        ) : (
          <Download className={cn(size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4")} />
        )}
        {isLoading
          ? `Preparing ${activeFormat?.toUpperCase() ?? "file"}...`
          : label}
      </button>

      {/* Dropdown toggle */}
      <button
        onClick={() => setOpen(!open)}
        disabled={disabled || isLoading}
        aria-label="Download format options"
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          "inline-flex items-center px-2 font-medium rounded-r-lg border transition-colors",
          sizeClasses,
          isLoading || disabled
            ? "bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed border-gray-200 dark:border-gray-700"
            : "bg-white dark:bg-dark-surface text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800",
        )}
      >
        <ChevronDown
          className={cn(size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5")}
        />
      </button>

      {/* Dropdown menu */}
      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white dark:bg-dark-surface border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-20 min-w-[160px]">
          <button
            onClick={() => handleDownload("pdf")}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-t-lg"
          >
            <Download className="h-4 w-4 text-red-500" />
            Download PDF
          </button>
          <button
            onClick={() => handleDownload("docx")}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-b-lg"
          >
            <FileText className="h-4 w-4 text-blue-500" />
            Download Word
          </button>
        </div>
      )}
    </div>
  );
};

export default DownloadButton;
