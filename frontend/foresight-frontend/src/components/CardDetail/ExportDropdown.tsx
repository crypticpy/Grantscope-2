/**
 * ExportDropdown Component
 *
 * A dropdown menu component for exporting card data in various formats.
 * Supports PDF, PowerPoint (PPTX), and CSV export options with loading
 * states and proper accessibility.
 *
 * @example
 * ```tsx
 * <ExportDropdown
 *   cardId={card.id}
 *   cardSlug={card.slug}
 *   getAuthToken={getAuthToken}
 *   onError={(error) => setExportError(error)}
 * />
 * ```
 */

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Download,
  ChevronDown,
  Loader2,
  FileText,
  Presentation,
  FileSpreadsheet,
} from "lucide-react";
import { Tooltip } from "../ui/Tooltip";
import { API_BASE_URL } from "./utils";

/**
 * Supported export format types
 */
export type ExportFormat = "pdf" | "pptx" | "csv";

/**
 * Props for the ExportDropdown component
 */
export interface ExportDropdownProps {
  /** The ID of the card to export */
  cardId: string;
  /** The slug of the card (used for filename) */
  cardSlug: string;
  /** Function to get the current auth token */
  getAuthToken: () => Promise<string | undefined>;
  /** Callback when an export error occurs */
  onError?: (error: string) => void;
  /** Optional callback when export starts */
  onExportStart?: (format: ExportFormat) => void;
  /** Optional callback when export completes successfully */
  onExportComplete?: (format: ExportFormat) => void;
  /** Optional additional class names */
  className?: string;
}

/**
 * Configuration for each export format option
 */
interface ExportOption {
  /** The export format identifier */
  format: ExportFormat;
  /** Display label for the option */
  label: string;
  /** Lucide icon component */
  icon: React.ComponentType<{ className?: string }>;
  /** Icon color class */
  iconColor: string;
}

/**
 * Available export format options
 */
const exportOptions: ExportOption[] = [
  {
    format: "pdf",
    label: "Export as PDF",
    icon: FileText,
    iconColor: "text-red-500",
  },
  {
    format: "pptx",
    label: "Export as PowerPoint",
    icon: Presentation,
    iconColor: "text-orange-500",
  },
  {
    format: "csv",
    label: "Export as CSV",
    icon: FileSpreadsheet,
    iconColor: "text-green-500",
  },
];

/**
 * ExportDropdown - A dropdown menu for exporting card data
 *
 * Provides options to export a card in PDF, PowerPoint, or CSV format.
 * Handles authentication, loading states, and file downloads automatically.
 *
 * Features:
 * - Dropdown closes on outside click
 * - Loading spinner during export
 * - Automatic file download on success
 * - Error handling via callback
 * - Touch-friendly with proper hit targets
 * - Dark mode support
 */
export const ExportDropdown: React.FC<ExportDropdownProps> = ({
  cardId,
  cardSlug,
  getAuthToken,
  onError,
  onExportStart,
  onExportComplete,
  className,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  /**
   * Handle clicks outside the dropdown to close it
   */
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [isOpen]);

  /**
   * Handle keyboard navigation and escape to close
   */
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      return () => {
        document.removeEventListener("keydown", handleKeyDown);
      };
    }
  }, [isOpen]);

  /**
   * Handle export to the specified format
   */
  const handleExport = useCallback(
    async (format: ExportFormat) => {
      if (isExporting) return;

      setIsExporting(true);
      setIsOpen(false);
      onExportStart?.(format);

      try {
        const token = await getAuthToken();
        if (!token) {
          throw new Error("Not authenticated");
        }

        const response = await fetch(
          `${API_BASE_URL}/api/v1/cards/${cardId}/export/${format}`,
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
        a.download = `${cardSlug}-export.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        onExportComplete?.(format);
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : "Failed to export signal";
        onError?.(errorMessage);
      } finally {
        setIsExporting(false);
      }
    },
    [
      cardId,
      cardSlug,
      getAuthToken,
      isExporting,
      onError,
      onExportStart,
      onExportComplete,
    ],
  );

  /**
   * Toggle dropdown open/closed
   */
  const toggleDropdown = useCallback(() => {
    if (!isExporting) {
      setIsOpen((prev) => !prev);
    }
  }, [isExporting]);

  return (
    <div ref={dropdownRef} className={`relative ${className || ""}`}>
      <Tooltip
        content={
          <div className="max-w-[200px]">
            <p className="font-medium">Export Signal</p>
            <p className="text-xs text-gray-500">
              Download this signal in various formats for sharing and analysis
            </p>
          </div>
        }
        side="bottom"
      >
        <button
          onClick={toggleDropdown}
          disabled={isExporting}
          aria-expanded={isOpen}
          aria-haspopup="menu"
          aria-label="Export signal options"
          className="inline-flex items-center justify-center min-h-[44px] sm:min-h-0 px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors active:scale-95 dark:bg-dark-surface-elevated dark:border-gray-600 dark:text-gray-200 dark:hover:bg-dark-surface-hover"
        >
          {isExporting ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Download className="h-4 w-4 mr-2" />
          )}
          Export
          <ChevronDown
            className={`h-4 w-4 ml-1 transition-transform ${isOpen ? "rotate-180" : ""}`}
          />
        </button>
      </Tooltip>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          role="menu"
          aria-orientation="vertical"
          className="absolute right-0 mt-1 w-48 bg-white dark:bg-dark-surface-elevated rounded-md shadow-lg border border-gray-200 dark:border-gray-600 py-1 z-20"
        >
          {exportOptions.map((option) => {
            const Icon = option.icon;
            return (
              <button
                key={option.format}
                onClick={() => handleExport(option.format)}
                role="menuitem"
                className="w-full flex items-center min-h-[44px] sm:min-h-0 px-4 py-3 sm:py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors active:bg-gray-200 dark:active:bg-gray-600"
              >
                <Icon className={`h-4 w-4 mr-3 ${option.iconColor}`} />
                {option.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ExportDropdown;
