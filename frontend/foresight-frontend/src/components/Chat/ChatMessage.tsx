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
import { Copy, Check, Sparkles, ExternalLink, FileText } from "lucide-react";
import { cn } from "../../lib/utils";
import { ChatCitation } from "./ChatCitation";
import { ChatMessageActions } from "./ChatMessageActions";
import type { Citation } from "../../lib/chat-api";

// ============================================================================
// Types
// ============================================================================

export interface ChatMessageProps {
  /** The message data to render */
  message: {
    id?: string;
    role: "user" | "assistant";
    content: string;
    citations: Citation[];
    created_at?: string;
    metadata?: {
      source_count?: number;
      citation_count?: number;
      signal_name?: string;
      workstream_name?: string;
      matched_cards?: number;
      card_count?: number;
    };
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
 * Represents a parsed bullet list item with its nesting depth and text content.
 */
interface NestedListItem {
  depth: number;
  text: string;
}

/**
 * Recursively renders nested bullet list items grouped by indentation depth.
 * Items at the current depth are rendered as `<li>`, and deeper items are
 * wrapped in a nested `<ul>` inside the preceding `<li>`.
 */
function renderNestedList(
  items: NestedListItem[],
  baseDepth: number,
  citations: Citation[],
  onCitationClick?: (citation: Citation) => void,
  keyPrefix = "ul",
): React.ReactNode {
  const elements: React.ReactNode[] = [];
  let idx = 0;

  while (idx < items.length) {
    const item = items[idx]!;

    if (item.depth === baseDepth) {
      // Check if following items are deeper (children of this item)
      const children: NestedListItem[] = [];
      let next = idx + 1;
      while (next < items.length && items[next]!.depth > baseDepth) {
        children.push(items[next]!);
        next++;
      }

      elements.push(
        <li
          key={`${keyPrefix}-li-${idx}`}
          className="text-gray-700 dark:text-gray-300 text-sm leading-relaxed"
        >
          {parseInline(item.text, citations, onCitationClick)}
          {children.length > 0 && (
            <ul className="ml-4 mt-0.5 space-y-0.5 list-disc">
              {renderNestedList(
                children,
                children[0]!.depth,
                citations,
                onCitationClick,
                `${keyPrefix}-${idx}`,
              )}
            </ul>
          )}
        </li>,
      );
      idx = next;
    } else {
      // Shouldn't happen at correct baseDepth, but advance to avoid infinite loop
      idx++;
    }
  }

  return <>{elements}</>;
}

/**
 * Lightweight markdown parser that converts a subset of markdown syntax
 * to React elements. Handles headings, code blocks, horizontal rules,
 * tables, blockquotes, nested bullet lists, numbered lists, bold, italic,
 * inline code, links, and citation references.
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
    const line = lines[i]!;

    // 1. Code block: ```...``` (existing — checked first)
    if (line.trimStart().startsWith("```")) {
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

    // 2. Horizontal rule: ---, ***, ___ (possibly with spaces)
    if (/^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(line)) {
      nodes.push(
        <hr
          key={`hr-${i}`}
          className="my-4 border-gray-200 dark:border-gray-700"
        />,
      );
      i++;
      continue;
    }

    // 3. Table: consecutive lines starting with |
    if (/^\s*\|/.test(line)) {
      const tableLines: string[] = [];
      while (i < lines.length && /^\s*\|/.test(lines[i]!)) {
        tableLines.push(lines[i]!);
        i++;
      }

      // Parse table rows — split each line by | and trim cells
      const parseRow = (rowLine: string): string[] =>
        rowLine
          .replace(/^\s*\|/, "")
          .replace(/\|\s*$/, "")
          .split("|")
          .map((cell) => cell.trim());

      // Check if second line is a separator (contains ---)
      const hasSeparator =
        tableLines.length >= 2 && /^\s*\|[\s:|-]+\|\s*$/.test(tableLines[1]!);

      const headerRow = hasSeparator ? parseRow(tableLines[0]!) : null;
      const bodyStartIndex = hasSeparator ? 2 : 0;
      const bodyRows = tableLines.slice(bodyStartIndex).map(parseRow);

      nodes.push(
        <div key={`table-${i}`} className="my-2 overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            {headerRow && (
              <thead>
                <tr className="border-b border-gray-300 dark:border-gray-600">
                  {headerRow.map((cell, cIdx) => (
                    <th
                      key={cIdx}
                      className="px-3 py-1.5 text-left font-semibold text-gray-900 dark:text-gray-100"
                    >
                      {parseInline(cell, citations, onCitationClick)}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {bodyRows.map((row, rIdx) => (
                <tr
                  key={rIdx}
                  className={cn(
                    rIdx % 2 === 0
                      ? "bg-gray-50 dark:bg-dark-surface"
                      : "bg-white dark:bg-dark-surface-elevated",
                  )}
                >
                  {row.map((cell, cIdx) => (
                    <td
                      key={cIdx}
                      className="px-3 py-1.5 text-left text-sm text-gray-700 dark:text-gray-300"
                    >
                      {parseInline(cell, citations, onCitationClick)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    // 4. Blockquote: > text
    if (/^>\s?/.test(line)) {
      const quoteLines: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i]!)) {
        quoteLines.push(lines[i]!.replace(/^>\s?/, ""));
        i++;
      }

      nodes.push(
        <blockquote
          key={`bq-${i}`}
          className={cn(
            "my-2 pl-4 py-2",
            "border-l-[3px] border-brand-blue dark:border-brand-blue/50",
            "bg-gray-50 dark:bg-dark-surface",
            "text-sm italic text-gray-700 dark:text-gray-300",
          )}
        >
          {quoteLines.map((qLine, qIdx) => (
            <p key={qIdx} className="leading-relaxed">
              {parseInline(qLine, citations, onCitationClick)}
            </p>
          ))}
        </blockquote>,
      );
      continue;
    }

    // 5. Heading: # through #### (existing)
    const headingMatch = line.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1]!.length;
      const content = headingMatch[2] ?? "";
      const Tag = `h${level + 1}` as keyof JSX.IntrinsicElements; // h2-h5
      const sizeClass =
        level === 1
          ? "text-lg font-bold"
          : level === 2
            ? "text-base font-semibold"
            : "text-sm font-semibold";
      nodes.push(
        <Tag
          key={`h-${i}`}
          className={cn(
            sizeClass,
            "mt-3 mb-1.5 text-gray-900 dark:text-gray-100",
          )}
        >
          {parseInline(content, citations, onCitationClick)}
        </Tag>,
      );
      i++;
      continue;
    }

    // 6. Bullet list item: - or * (with nesting support)
    if (/^\s*[-*]\s/.test(line)) {
      const listItems: NestedListItem[] = [];
      while (i < lines.length && /^\s*[-*]\s/.test(lines[i]!)) {
        const raw = lines[i]!;
        const indentMatch = raw.match(/^(\s*)[-*]\s/)!;
        const depth = Math.floor(indentMatch[1]!.length / 2);
        const itemText = raw.replace(/^\s*[-*]\s/, "");
        listItems.push({ depth, text: itemText });
        i++;
      }

      const baseDepth = listItems[0]!.depth;

      nodes.push(
        <ul key={`ul-${i}`} className="my-1.5 ml-4 space-y-0.5 list-disc">
          {renderNestedList(
            listItems,
            baseDepth,
            citations,
            onCitationClick,
            `ul-${i}`,
          )}
        </ul>,
      );
      continue;
    }

    // 7. Numbered list item: 1. or 1) (existing)
    if (/^\s*\d+[.)]\s/.test(line)) {
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

    // 8. Empty line -> line break
    if (line.trim() === "") {
      nodes.push(<br key={`br-${i}`} />);
      i++;
      continue;
    }

    // 9. Regular paragraph
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
 * Handles links [text](url), bold, italic, inline code, and citation references [1].
 */
function parseInline(
  rawText: string,
  citations: Citation[],
  onCitationClick?: (citation: Citation) => void,
): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];

  // Strip empty brackets [] (no number inside) before parsing
  const text = rawText.replace(/\[\]/g, "");

  // Combined regex for all inline elements
  // Match: [text](url) link, **bold**, *italic*, `code`, or [number] citation
  const regex =
    /(\[([^\]]+)\]\(([^)]+)\))|(\*\*(.+?)\*\*)|(\*(.+?)\*)|(`(.+?)`)|(\[(\d+)\])/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    // Add text before the match
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    if (match[1]) {
      // [text](url) link
      const linkText = match[2]!;
      const linkUrl = match[3]!;
      nodes.push(
        <a
          key={`link-${match.index}`}
          href={linkUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-brand-blue hover:underline inline-flex items-center gap-0.5"
        >
          {linkText}
          <ExternalLink className="inline h-3 w-3 shrink-0" />
        </a>,
      );
    } else if (match[4]) {
      // **bold**
      nodes.push(
        <strong key={`b-${match.index}`} className="font-semibold">
          {match[5]}
        </strong>,
      );
    } else if (match[6]) {
      // *italic*
      nodes.push(
        <em key={`i-${match.index}`} className="italic">
          {match[7]}
        </em>,
      );
    } else if (match[8]) {
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
          {match[9]}
        </code>,
      );
    } else if (match[10]) {
      // [number] citation reference
      const citationIndex = parseInt(match[11]!, 10);
      const citation = citations.find((c) => c.index === citationIndex);

      if (citation) {
        nodes.push(
          <button
            key={`cite-${match.index}`}
            type="button"
            onClick={() => {
              if (onCitationClick) {
                onCitationClick(citation);
              } else if (citation.url) {
                window.open(citation.url, "_blank", "noopener,noreferrer");
              }
            }}
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
        nodes.push(match[10]);
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
// Tone Detection
// ============================================================================

/**
 * Detects the dominant tone of a message via keyword analysis.
 * Returns a Tailwind border color class.
 */
function detectToneBorder(content: string): string {
  const lower = content.toLowerCase();

  // Risk/warning keywords
  const riskWords = [
    "risk",
    "warning",
    "threat",
    "concern",
    "danger",
    "decline",
    "challenge",
    "vulnerability",
    "disruption",
    "failure",
    "obstacle",
  ];
  const riskScore = riskWords.reduce(
    (count, word) => count + (lower.includes(word) ? 1 : 0),
    0,
  );

  // Opportunity/positive keywords
  const opportunityWords = [
    "opportunity",
    "growth",
    "innovation",
    "benefit",
    "advantage",
    "improvement",
    "progress",
    "success",
    "promising",
    "potential",
    "recommend",
  ];
  const opportunityScore = opportunityWords.reduce(
    (count, word) => count + (lower.includes(word) ? 1 : 0),
    0,
  );

  // Need at least 2 keyword matches for a tone accent
  if (riskScore >= 2 && riskScore > opportunityScore) {
    return "border-l-[2px] border-l-amber-400 dark:border-l-amber-500/60";
  }
  if (opportunityScore >= 2 && opportunityScore > riskScore) {
    return "border-l-[2px] border-l-teal-400 dark:border-l-teal-500/60";
  }

  return "";
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

  // Detect response tone for subtle left-border accent
  const toneBorder = useMemo(
    () => (!isUser && !isStreaming ? detectToneBorder(message.content) : ""),
    [message.content, isUser, isStreaming],
  );

  return (
    <div
      className={cn(
        "flex gap-2.5 animate-slide-up-fade-in",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
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
              : cn(
                  "bg-gray-100 dark:bg-dark-surface-elevated rounded-2xl rounded-bl-md",
                  toneBorder,
                ),
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
              className="inline-block w-2 h-4 ml-0.5 bg-brand-blue animate-smooth-pulse rounded-sm align-text-bottom"
              aria-label="Generating response"
            />
          )}
        </div>

        {/* Citations section for assistant messages */}
        {!isUser && message.citations.length > 0 && !isStreaming && (
          <div className="mt-2 space-y-1">
            <p className="text-[10px] font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 animate-fade-in">
              Sources
            </p>
            <div className="flex flex-wrap gap-1.5">
              {message.citations.map((citation, index) => (
                <div
                  key={`${citation.index}-${citation.card_id || citation.source_id || citation.title}`}
                  className="animate-fade-in"
                  style={{ animationDelay: `${index * 100}ms` }}
                >
                  <ChatCitation citation={citation} onClick={onCitationClick} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Confidence metadata indicator */}
        {!isUser && message.metadata && !isStreaming && (
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-gray-400 dark:text-gray-500">
            <FileText className="h-3 w-3 shrink-0" aria-hidden="true" />
            <span>
              Based on {message.metadata.source_count ?? 0} sources
              {message.metadata.matched_cards
                ? ` across ${message.metadata.matched_cards} signals`
                : ""}
              {message.metadata.card_count
                ? ` from ${message.metadata.card_count} signals`
                : ""}
            </span>
          </div>
        )}

        {/* Action buttons for assistant messages (hover) */}
        {!isUser && !isStreaming && (
          <div
            className={cn(
              "absolute -top-2 -right-2",
              "flex items-center gap-0.5",
              "opacity-0 group-hover:opacity-100",
              "transition-all duration-200",
            )}
          >
            <ChatMessageActions
              content={message.content}
              messageId={message.id}
            />
            <button
              type="button"
              onClick={handleCopy}
              className={cn(
                "inline-flex items-center justify-center",
                "w-7 h-7 rounded-md",
                "bg-white dark:bg-dark-surface-elevated",
                "border border-gray-200 dark:border-gray-600",
                "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300",
                "shadow-sm",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue",
                "transition-colors duration-200",
              )}
              aria-label={copied ? "Copied to clipboard" : "Copy message"}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-brand-green" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
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
