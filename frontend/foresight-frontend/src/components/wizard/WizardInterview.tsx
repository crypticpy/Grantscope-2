/**
 * WizardInterview Component
 *
 * Step 2 of the Grant Application Wizard - the core conversational interview.
 * Two-column layout: chat messages + input on the left, interview progress
 * sidebar on the right. Responsive with collapsible progress panel on mobile.
 *
 * @module components/wizard/WizardInterview
 */

import React, { useRef, useEffect, useState, useCallback } from "react";
import {
  Send,
  StopCircle,
  AlertCircle,
  RefreshCw,
  Check,
  ChevronDown,
  ChevronUp,
  Loader2,
  Clock,
  Calendar,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useWizardInterview } from "../../hooks/useWizardInterview";
import type { GrantContext } from "../../lib/wizard-api";

// ============================================================================
// Types
// ============================================================================

export interface WizardInterviewProps {
  /** Wizard session UUID */
  sessionId: string;
  /** Existing conversation to resume, or null for a new interview */
  conversationId: string | null;
  /** Pre-loaded grant context for display */
  grantContext?: GrantContext;
  /** Called when user is ready to move to the plan review step */
  onComplete: () => void;
  /** Called when user navigates back to the previous step */
  onBack: () => void;
}

// ============================================================================
// Constants
// ============================================================================

/** Topic labels keyed by identifier */
const TOPIC_LABELS: Record<string, string> = {
  program_overview: "Program Overview",
  staffing: "Staffing",
  budget: "Budget",
  timeline: "Timeline",
  deliverables: "Deliverables",
  evaluation: "Evaluation",
  capacity: "Capacity",
};

/** Display order for topics */
const TOPIC_ORDER = [
  "program_overview",
  "staffing",
  "budget",
  "timeline",
  "deliverables",
  "evaluation",
  "capacity",
] as const;

const TOTAL_TOPICS = TOPIC_ORDER.length;

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Renders simple markdown: bold, bullet lists, paragraphs.
 * Avoids pulling in a full markdown library.
 */
function SimpleMarkdown({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let listItems: string[] = [];

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul
          key={`list-${elements.length}`}
          className="list-disc list-inside space-y-1 my-2"
        >
          {listItems.map((item, i) => (
            <li key={i}>{renderInline(item)}</li>
          ))}
        </ul>,
      );
      listItems = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i] ?? "";
    const trimmed = line.trim();

    // Bullet point
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      listItems.push(trimmed.slice(2));
      continue;
    }

    // Numbered list
    if (/^\d+\.\s/.test(trimmed)) {
      listItems.push(trimmed.replace(/^\d+\.\s/, ""));
      continue;
    }

    flushList();

    // Empty line = paragraph break
    if (!trimmed) {
      elements.push(<br key={`br-${i}`} />);
      continue;
    }

    // Heading-like lines (### or ##)
    if (trimmed.startsWith("### ")) {
      elements.push(
        <p key={`h3-${i}`} className="font-semibold mt-3 mb-1">
          {renderInline(trimmed.slice(4))}
        </p>,
      );
      continue;
    }
    if (trimmed.startsWith("## ")) {
      elements.push(
        <p key={`h2-${i}`} className="font-bold mt-3 mb-1">
          {renderInline(trimmed.slice(3))}
        </p>,
      );
      continue;
    }

    // Regular paragraph
    elements.push(
      <p key={`p-${i}`} className="my-1">
        {renderInline(trimmed)}
      </p>,
    );
  }

  flushList();

  return <div className="text-sm leading-relaxed">{elements}</div>;
}

/**
 * Renders inline formatting: **bold** and *italic*.
 */
function renderInline(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  // Match **bold** or *italic*
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    // Text before the match
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    if (match[2]) {
      // **bold**
      parts.push(
        <strong key={match.index} className="font-semibold">
          {match[2]}
        </strong>,
      );
    } else if (match[3]) {
      // *italic*
      parts.push(<em key={match.index}>{match[3]}</em>);
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}

/**
 * Grant context summary card (collapsible).
 */
function GrantContextCard({ context }: { context: GrantContext }) {
  const [expanded, setExpanded] = useState(false);

  if (!context.grant_name && !context.grantor && !context.deadline) {
    return null;
  }

  return (
    <div className="mx-4 mt-3 mb-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-dark-surface-deep overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      >
        <span className="font-medium truncate">
          {context.grant_name || "Grant Details"}
        </span>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 flex-shrink-0" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 flex-shrink-0" />
        )}
      </button>
      {expanded && (
        <div className="px-3 pb-2 space-y-1 text-xs text-gray-500 dark:text-gray-400 border-t border-gray-200 dark:border-gray-700">
          {context.grantor && (
            <p>
              <span className="font-medium">Grantor:</span> {context.grantor}
            </p>
          )}
          {context.deadline && (
            <p className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              <span className="font-medium">Deadline:</span> {context.deadline}
            </p>
          )}
          {context.funding_amount_max && (
            <p>
              <span className="font-medium">Funding:</span>{" "}
              {context.funding_amount_min
                ? `$${context.funding_amount_min.toLocaleString()} - $${context.funding_amount_max.toLocaleString()}`
                : `Up to $${context.funding_amount_max.toLocaleString()}`}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Computes days until a deadline string (ISO date or common date formats).
 */
function daysUntilDeadline(deadline: string): number | null {
  try {
    const date = new Date(deadline);
    if (isNaN(date.getTime())) return null;
    const now = new Date();
    const diffMs = date.getTime() - now.getTime();
    return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  } catch {
    return null;
  }
}

// ============================================================================
// Main Component
// ============================================================================

const WizardInterview: React.FC<WizardInterviewProps> = ({
  sessionId,
  conversationId,
  grantContext,
  onComplete,
  onBack,
}) => {
  const interview = useWizardInterview({ sessionId, conversationId });
  const {
    messages,
    isStreaming,
    streamingContent,
    error,
    sendMessage,
    stopGenerating,
    retryLastMessage,
    progressStep,
    completedTopics,
    topicProgress,
    isInterviewComplete,
  } = interview;

  // Local state
  const [inputValue, setInputValue] = useState("");
  const [mobileProgressOpen, setMobileProgressOpen] = useState(false);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // ---------------------------------------------------------------------------
  // Auto-scroll to bottom when messages change
  // ---------------------------------------------------------------------------

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // ---------------------------------------------------------------------------
  // Auto-resize textarea
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  }, [inputValue]);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleSend = useCallback(() => {
    const trimmed = inputValue.trim();
    if (!trimmed || isStreaming) return;
    setInputValue("");
    sendMessage(trimmed);
  }, [inputValue, isStreaming, sendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  // Deadline reminder
  const deadlineDays = grantContext?.deadline
    ? daysUntilDeadline(grantContext.deadline)
    : null;
  const showDeadlineWarning =
    deadlineDays !== null && deadlineDays >= 0 && deadlineDays <= 30;

  // ---------------------------------------------------------------------------
  // Progress Sidebar Content (shared between desktop and mobile)
  // ---------------------------------------------------------------------------

  const progressContent = (
    <div className="space-y-4">
      {/* Topic checklist */}
      <div className="space-y-2">
        {TOPIC_ORDER.map((topic) => {
          const isComplete = completedTopics.has(topic);
          return (
            <div key={topic} className="flex items-center gap-2.5">
              {isComplete ? (
                <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center flex-shrink-0">
                  <Check className="h-3 w-3 text-white" />
                </div>
              ) : (
                <div className="w-5 h-5 rounded-full border-2 border-gray-300 dark:border-gray-600 flex-shrink-0" />
              )}
              <span
                className={cn(
                  "text-sm",
                  isComplete
                    ? "font-semibold text-gray-900 dark:text-white"
                    : "text-gray-500 dark:text-gray-400",
                )}
              >
                {TOPIC_LABELS[topic]}
              </span>
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1.5">
          <span>Progress</span>
          <span>
            {topicProgress}/{TOTAL_TOPICS} topics
          </span>
        </div>
        <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-brand-blue rounded-full transition-all duration-500 ease-out"
            style={{
              width: `${(topicProgress / TOTAL_TOPICS) * 100}%`,
            }}
          />
        </div>
      </div>

      {/* Deadline warning */}
      {showDeadlineWarning && (
        <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
          <Clock className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
          <span className="text-xs font-medium text-amber-700 dark:text-amber-300">
            {deadlineDays === 0
              ? "Deadline is today!"
              : `${deadlineDays} day${deadlineDays === 1 ? "" : "s"} until deadline`}
          </span>
        </div>
      )}

      {/* Complete button */}
      <button
        onClick={onComplete}
        disabled={!isInterviewComplete}
        className={cn(
          "w-full py-2.5 px-4 rounded-lg text-sm font-medium transition-colors",
          isInterviewComplete
            ? "bg-brand-blue text-white hover:bg-brand-dark-blue"
            : "bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-not-allowed",
        )}
      >
        {isInterviewComplete
          ? "Review my plan"
          : "Complete core topics to continue"}
      </button>

      {!isInterviewComplete && (
        <p className="text-xs text-gray-400 dark:text-gray-500 text-center">
          Complete all 4 core topics (Program Overview, Staffing, Budget,
          Timeline) to proceed.
        </p>
      )}
    </div>
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="flex flex-col lg:flex-row gap-0 lg:gap-0 h-[calc(100vh-14rem)] min-h-[500px]">
      {/* Mobile progress toggle */}
      <div className="lg:hidden">
        <button
          onClick={() => setMobileProgressOpen(!mobileProgressOpen)}
          className="w-full flex items-center justify-between px-4 py-3 bg-white dark:bg-dark-surface border border-gray-200 dark:border-gray-700 rounded-t-lg"
        >
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Interview Progress
          </span>
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-brand-blue">
              {topicProgress}/{TOTAL_TOPICS} topics
            </span>
            {mobileProgressOpen ? (
              <ChevronUp className="h-4 w-4 text-gray-400" />
            ) : (
              <ChevronDown className="h-4 w-4 text-gray-400" />
            )}
          </div>
        </button>
        {mobileProgressOpen && (
          <div className="px-4 pb-4 bg-white dark:bg-dark-surface border-x border-b border-gray-200 dark:border-gray-700 rounded-b-lg mb-3">
            {progressContent}
          </div>
        )}
      </div>

      {/* Left panel: Chat */}
      <div className="flex-1 flex flex-col bg-white dark:bg-dark-surface rounded-lg lg:rounded-r-none border border-gray-200 dark:border-gray-700 overflow-hidden min-w-0">
        {/* Grant context header */}
        {grantContext && <GrantContextCard context={grantContext} />}

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                "flex",
                msg.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cn(
                  "max-w-[85%] rounded-lg px-4 py-3",
                  msg.role === "user"
                    ? "bg-brand-blue text-white"
                    : "bg-gray-50 dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700",
                )}
              >
                {msg.role === "assistant" ? (
                  <SimpleMarkdown content={msg.content} />
                ) : (
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                )}
              </div>
            </div>
          ))}

          {/* Streaming content */}
          {isStreaming && streamingContent && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-lg px-4 py-3 bg-gray-50 dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700">
                <SimpleMarkdown content={streamingContent} />
                <span className="inline-block w-1.5 h-4 bg-brand-blue animate-pulse ml-0.5 align-text-bottom" />
              </div>
            </div>
          )}

          {/* Streaming with no content yet (loading indicator) */}
          {isStreaming && !streamingContent && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-lg px-4 py-3 bg-gray-50 dark:bg-dark-surface-deep border border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {progressStep ? (
                    <span>
                      {progressStep.step}
                      {progressStep.detail ? `: ${progressStep.detail}` : ""}
                    </span>
                  ) : (
                    <span>Thinking...</span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Error display */}
          {error && (
            <div className="flex justify-center">
              <div className="flex items-center gap-2 px-4 py-2.5 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg max-w-[85%]">
                <AlertCircle className="h-4 w-4 text-red-500 flex-shrink-0" />
                <span className="text-sm text-red-700 dark:text-red-300">
                  {error}
                </span>
                <button
                  onClick={retryLastMessage}
                  className="ml-2 flex items-center gap-1 text-xs font-medium text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200 transition-colors"
                >
                  <RefreshCw className="h-3 w-3" />
                  Retry
                </button>
              </div>
            </div>
          )}

          {/* Scroll anchor */}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="border-t border-gray-200 dark:border-gray-700 px-4 py-3">
          {/* Stop generating button */}
          {isStreaming && (
            <div className="flex justify-center mb-2">
              <button
                onClick={stopGenerating}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
                <StopCircle className="h-3.5 w-3.5" />
                Stop generating
              </button>
            </div>
          )}

          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your response..."
              disabled={isStreaming}
              rows={1}
              className={cn(
                "flex-1 resize-none rounded-lg border border-gray-300 dark:border-gray-600",
                "bg-white dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100",
                "px-3 py-2.5 text-sm leading-relaxed",
                "placeholder:text-gray-400 dark:placeholder:text-gray-500",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "max-h-[150px]",
              )}
            />
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || isStreaming}
              className={cn(
                "flex items-center justify-center w-10 h-10 rounded-lg transition-colors flex-shrink-0",
                inputValue.trim() && !isStreaming
                  ? "bg-brand-blue text-white hover:bg-brand-dark-blue"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed",
              )}
              aria-label="Send message"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Right panel: Progress sidebar (desktop) */}
      <div className="hidden lg:flex lg:flex-col lg:w-64 xl:w-72 bg-gray-50 dark:bg-dark-surface border border-l-0 border-gray-200 dark:border-gray-700 rounded-r-lg p-5 overflow-y-auto">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
          Interview Progress
        </h3>
        {progressContent}
      </div>
    </div>
  );
};

export default WizardInterview;
