/**
 * ChatMessage Component
 *
 * Renders an individual chat message with distinct styling for user and
 * assistant roles. Supports inline markdown rendering, citation chips,
 * copy-to-clipboard, and streaming cursor animation.
 *
 * @module components/Chat/ChatMessage
 */

import React, { useState, useCallback, useMemo } from "react";
import { Copy, Check, Sparkles } from "lucide-react";
import { cn } from "../../lib/utils";
import { ChatCitation } from "./ChatCitation";
import type { Citation } from "../../lib/chat-api";

// ============================================================================
// Types
// ============================================================================

export interface ChatMessageProps {
  /** The message data to render */
  message: {
    role: "user" | "assistant";
    content: string;
    citations: Citation[];
    created_at?: string;
  };
  /** Whether this message is currently being streamed */
  isStreaming?: boolean;
  /** Callback when a citation is clicked */
  onCitationClick?: (citation: Citation) => void;
}

// ============================================================================
// Markdown Parser
// ============================================================================

/**
 * Lightweight markdown parser that converts a subset of markdown syntax
 * to React elements. Handles bold, italic, inline code, code blocks,
 * bullet lists, numbered lists, newlines, and citation references.
 *
 * Does not use an external library to keep the bundle lean.
 */
function parseMarkdown(
  text: string,
  citations: Citation[],
  onCitationClick?: (citation: Citation) => void,
): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const lines = text.split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Code block: ```...```
    if (line!.trimStart().startsWith("```")) {
      const codeLines: string[] = [];
      i++; // Skip opening ```
      while (i < lines.length && !lines[i]!.trimStart().startsWith("```")) {
        codeLines.push(lines[i]!);
        i++;
      }
      i++; // Skip closing ```

      nodes.push(
        <pre
          key={`code-${i}`}
          className={cn(
            "my-2 p-3 rounded-lg overflow-x-auto text-xs",
            "bg-gray-900 text-gray-100 dark:bg-black/40",
            "border border-gray-700 dark:border-gray-600",
          )}
        >
          <code>{codeLines.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    // Bullet list item: - or *
    if (/^\s*[-*]\s/.test(line!)) {
      const listItems: string[] = [];
      while (i < lines.length && /^\s*[-*]\s/.test(lines[i]!)) {
        listItems.push(lines[i]!.replace(/^\s*[-*]\s/, ""));
        i++;
      }
      nodes.push(
        <ul key={`ul-${i}`} className="my-1.5 ml-4 space-y-0.5 list-disc">
          {listItems.map((item, idx) => (
            <li
              key={idx}
              className="text-gray-700 dark:text-gray-300 text-sm leading-relaxed"
            >
              {parseInline(item, citations, onCitationClick)}
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    // Numbered list item: 1. or 1)
    if (/^\s*\d+[.)]\s/.test(line!)) {
      const listItems: string[] = [];
      while (i < lines.length && /^\s*\d+[.)]\s/.test(lines[i]!)) {
        listItems.push(lines[i]!.replace(/^\s*\d+[.)]\s/, ""));
        i++;
      }
      nodes.push(
        <ol key={`ol-${i}`} className="my-1.5 ml-4 space-y-0.5 list-decimal">
          {listItems.map((item, idx) => (
            <li
              key={idx}
              className="text-gray-700 dark:text-gray-300 text-sm leading-relaxed"
            >
              {parseInline(item, citations, onCitationClick)}
            </li>
          ))}
        </ol>,
      );
      continue;
    }

    // Empty line -> line break
    if (line.trim() === "") {
      nodes.push(<br key={`br-${i}`} />);
      i++;
      continue;
    }

    // Regular paragraph
    nodes.push(
      <p
        key={`p-${i}`}
        className="text-sm leading-relaxed text-gray-700 dark:text-gray-300"
      >
        {parseInline(line, citations, onCitationClick)}
      </p>,
    );
    i++;
  }

  return nodes;
}

/**
 * Parses inline markdown formatting within a single line of text.
 * Handles bold, italic, inline code, and citation references [1].
 */
function parseInline(
  text: string,
  citations: Citation[],
  onCitationClick?: (citation: Citation) => void,
): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];

  // Combined regex for all inline elements
  // Match: **bold**, *italic*, `code`, or [number] citation
  const regex = /(\*\*(.+?)\*\*)|(\*(.+?)\*)|(`(.+?)`)|(\[(\d+)\])/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    // Add text before the match
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    if (match[1]) {
      // **bold**
      nodes.push(
        <strong key={`b-${match.index}`} className="font-semibold">
          {match[2]}
        </strong>,
      );
    } else if (match[3]) {
      // *italic*
      nodes.push(
        <em key={`i-${match.index}`} className="italic">
          {match[4]}
        </em>,
      );
    } else if (match[5]) {
      // `code`
      nodes.push(
        <code
          key={`c-${match.index}`}
          className={cn(
            "px-1.5 py-0.5 rounded text-xs font-mono",
            "bg-gray-100 dark:bg-dark-surface-elevated",
            "text-red-600 dark:text-red-400",
          )}
        >
          {match[6]}
        </code>,
      );
    } else if (match[7]) {
      // [number] citation reference
      const citationIndex = parseInt(match[8]!, 10);
      const citation = citations.find((c) => c.index === citationIndex);

      if (citation) {
        nodes.push(
          <button
            key={`cite-${match.index}`}
            type="button"
            onClick={() => onCitationClick?.(citation)}
            className={cn(
              "inline-flex items-center justify-center",
              "min-w-[1.25rem] h-5 px-1 mx-0.5",
              "text-[10px] font-semibold rounded-full",
              "bg-brand-blue/10 text-brand-blue",
              "hover:bg-brand-blue/20",
              "dark:bg-brand-blue/20 dark:text-blue-300 dark:hover:bg-brand-blue/30",
              "cursor-pointer transition-colors duration-150",
              "align-super",
            )}
            title={citation.title}
            aria-label={`Citation ${citationIndex}: ${citation.title}`}
          >
            {citationIndex}
          </button>,
        );
      } else {
        // No matching citation found, render as plain text
        nodes.push(match[7]);
      }
    }

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text after last match
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

// ============================================================================
// Component
// ============================================================================

export function ChatMessage({
  message,
  isStreaming = false,
  onCitationClick,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [showTimestamp, setShowTimestamp] = useState(false);
  const isUser = message.role === "user";

  // Format timestamp for display
  const formattedTime = useMemo(() => {
    if (!message.created_at) return "";
    try {
      return new Date(message.created_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  }, [message.created_at]);

  // Copy message content to clipboard
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may not be available
    }
  }, [message.content]);

  // Parse markdown content
  const renderedContent = useMemo(
    () => parseMarkdown(message.content, message.citations, onCitationClick),
    [message.content, message.citations, onCitationClick],
  );

  return (
    <div
      className={cn("flex gap-2.5", isUser ? "flex-row-reverse" : "flex-row")}
      onMouseEnter={() => setShowTimestamp(true)}
      onMouseLeave={() => setShowTimestamp(false)}
    >
      {/* Avatar for assistant */}
      {!isUser && (
        <div
          className={cn(
            "flex items-center justify-center shrink-0",
            "w-7 h-7 rounded-full mt-0.5",
            "bg-brand-blue/10 dark:bg-brand-blue/20",
          )}
          aria-hidden="true"
        >
          <Sparkles className="h-3.5 w-3.5 text-brand-blue" />
        </div>
      )}

      {/* Message bubble */}
      <div
        className={cn(
          "relative group max-w-[85%] sm:max-w-[75%]",
          isUser ? "ml-auto" : "mr-auto",
        )}
      >
        <div
          className={cn(
            "px-4 py-2.5",
            isUser
              ? "bg-brand-blue text-white rounded-2xl rounded-br-md"
              : "bg-gray-100 dark:bg-dark-surface-elevated rounded-2xl rounded-bl-md",
          )}
        >
          {/* Message content */}
          {isUser ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap">
              {message.content}
            </p>
          ) : (
            <div className="space-y-1">{renderedContent}</div>
          )}

          {/* Streaming cursor */}
          {isStreaming && (
            <span
              className="inline-block w-2 h-4 ml-0.5 bg-brand-blue animate-pulse rounded-sm align-text-bottom"
              aria-label="Generating response"
            />
          )}
        </div>

        {/* Citations section for assistant messages */}
        {!isUser && message.citations.length > 0 && !isStreaming && (
          <div className="mt-2 space-y-1">
            <p className="text-[10px] font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
              Sources
            </p>
            <div className="flex flex-wrap gap-1.5">
              {message.citations.map((citation) => (
                <ChatCitation
                  key={`${citation.index}-${citation.card_id || citation.source_id || citation.title}`}
                  citation={citation}
                  onClick={onCitationClick}
                />
              ))}
            </div>
          </div>
        )}

        {/* Copy button for assistant messages (hover) */}
        {!isUser && !isStreaming && (
          <button
            type="button"
            onClick={handleCopy}
            className={cn(
              "absolute -top-2 -right-2",
              "inline-flex items-center justify-center",
              "w-7 h-7 rounded-md",
              "bg-white dark:bg-dark-surface-elevated",
              "border border-gray-200 dark:border-gray-600",
              "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300",
              "shadow-sm",
              "focus:outline-none focus:ring-2 focus:ring-brand-blue",
              "transition-all duration-200",
              "opacity-0 group-hover:opacity-100",
            )}
            aria-label={copied ? "Copied to clipboard" : "Copy message"}
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-brand-green" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>
        )}

        {/* Timestamp on hover */}
        {showTimestamp && formattedTime && (
          <div
            className={cn(
              "mt-1 text-[10px] text-gray-400 dark:text-gray-500",
              isUser ? "text-right" : "text-left",
              "animate-in fade-in-0 duration-150",
            )}
          >
            {formattedTime}
          </div>
        )}
      </div>
    </div>
  );
}

export default ChatMessage;
