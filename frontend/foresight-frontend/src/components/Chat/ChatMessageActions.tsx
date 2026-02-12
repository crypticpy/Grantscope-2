import React, { useState, useRef, useEffect } from "react";
import {
  Bookmark,
  Download,
  Copy,
  FileText,
  ClipboardCheck,
} from "lucide-react";
import { cn } from "../../lib/utils";

interface ChatMessageActionsProps {
  /** The message content in markdown format */
  content: string;
  /** The message ID (for pinning) */
  messageId?: string;
  /** Whether the message is currently pinned */
  isPinned?: boolean;
  /** Callback to pin/unpin the message */
  onTogglePin?: (messageId: string) => void;
  /** Additional class name */
  className?: string;
}

export function ChatMessageActions({
  content,
  messageId,
  isPinned = false,
  onTogglePin,
  className,
}: ChatMessageActionsProps) {
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on click outside
  useEffect(() => {
    if (!showExportMenu) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowExportMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showExportMenu]);

  const handleCopyMarkdown = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopyFeedback("Copied as Markdown");
      setShowExportMenu(false);
      setTimeout(() => setCopyFeedback(null), 2000);
    } catch {
      /* clipboard unavailable */
    }
  };

  const handleCopyPlainText = async () => {
    try {
      // Strip markdown formatting
      const plain = content
        .replace(/\*\*(.+?)\*\*/g, "$1")
        .replace(/\*(.+?)\*/g, "$1")
        .replace(/`(.+?)`/g, "$1")
        .replace(/#{1,4}\s/g, "")
        .replace(/\[(\d+)\]/g, "")
        .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
        .replace(/^[-*]\s/gm, "• ")
        .replace(/^>\s?/gm, "");
      await navigator.clipboard.writeText(plain);
      setCopyFeedback("Copied as plain text");
      setShowExportMenu(false);
      setTimeout(() => setCopyFeedback(null), 2000);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className={cn("flex items-center gap-0.5", className)}>
      {/* Copy feedback toast */}
      {copyFeedback && (
        <span
          className={cn(
            "absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap",
            "text-[10px] font-medium px-2 py-1 rounded-md",
            "bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900",
            "animate-in fade-in-0 zoom-in-95 duration-150",
            "shadow-sm",
          )}
        >
          <ClipboardCheck className="inline h-3 w-3 mr-1" />
          {copyFeedback}
        </span>
      )}

      {/* Pin button */}
      {messageId && onTogglePin && (
        <button
          type="button"
          onClick={() => onTogglePin(messageId)}
          className={cn(
            "p-1 rounded-md transition-colors duration-150",
            isPinned
              ? "text-amber-500 hover:text-amber-600 dark:text-amber-400"
              : "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300",
            "hover:bg-gray-100 dark:hover:bg-dark-surface-hover",
            "focus:outline-none focus:ring-1 focus:ring-brand-blue",
          )}
          title={isPinned ? "Unpin response" : "Pin response"}
          aria-label={isPinned ? "Unpin response" : "Pin response"}
        >
          <Bookmark className={cn("h-3.5 w-3.5", isPinned && "fill-current")} />
        </button>
      )}

      {/* Export button + dropdown */}
      <div className="relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => setShowExportMenu(!showExportMenu)}
          className={cn(
            "p-1 rounded-md transition-colors duration-150",
            "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300",
            "hover:bg-gray-100 dark:hover:bg-dark-surface-hover",
            "focus:outline-none focus:ring-1 focus:ring-brand-blue",
          )}
          title="Export response"
          aria-label="Export response"
          aria-expanded={showExportMenu}
        >
          <Download className="h-3.5 w-3.5" />
        </button>

        {showExportMenu && (
          <div
            className={cn(
              "absolute right-0 top-full mt-1 z-50",
              "w-48 py-1",
              "bg-white dark:bg-dark-surface-elevated",
              "border border-gray-200 dark:border-gray-700",
              "rounded-lg shadow-lg",
              "animate-in fade-in-0 zoom-in-95 duration-150",
            )}
            role="menu"
          >
            <button
              type="button"
              onClick={handleCopyMarkdown}
              className={cn(
                "w-full flex items-center gap-2 px-3 py-2 text-sm text-left",
                "text-gray-700 dark:text-gray-300",
                "hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                "transition-colors duration-100",
              )}
              role="menuitem"
            >
              <Copy className="h-3.5 w-3.5 text-gray-400" />
              Copy as Markdown
            </button>
            <button
              type="button"
              onClick={handleCopyPlainText}
              className={cn(
                "w-full flex items-center gap-2 px-3 py-2 text-sm text-left",
                "text-gray-700 dark:text-gray-300",
                "hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                "transition-colors duration-100",
              )}
              role="menuitem"
            >
              <FileText className="h-3.5 w-3.5 text-gray-400" />
              Copy as Plain Text
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default ChatMessageActions;
