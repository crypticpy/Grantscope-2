import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Copy, Pencil } from "lucide-react";
import { cn } from "../../lib/utils";
import { UserMessageEditor } from "../Chat/UserMessageEditor";
import { useEditableMessage } from "../Chat/useEditableMessage";
import { WizardSimpleMarkdown } from "./WizardSimpleMarkdown";

interface WizardMessageBubbleProps {
  message: {
    id: string;
    role: "user" | "assistant";
    content: string;
  };
  isConversationStreaming: boolean;
  isStreamingMessage?: boolean;
  onResendEdited?: (editedContent: string) => boolean | Promise<boolean>;
}

export function WizardMessageBubble({
  message,
  isConversationStreaming,
  isStreamingMessage = false,
  onResendEdited,
}: WizardMessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const copyResetTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const isUser = message.role === "user";

  const {
    isEditing,
    draftContent,
    isSubmitting,
    setDraftContent,
    startEditing,
    cancelEditing,
    submitEdit,
  } = useEditableMessage({
    messageId: message.id,
    messageContent: message.content,
    onEditResend: onResendEdited
      ? ({ editedContent }) => onResendEdited(editedContent)
      : undefined,
  });

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);

      if (copyResetTimeoutRef.current) {
        clearTimeout(copyResetTimeoutRef.current);
      }

      copyResetTimeoutRef.current = setTimeout(() => {
        setCopied(false);
        copyResetTimeoutRef.current = null;
      }, 1800);
    } catch {
      // Clipboard API unavailable
    }
  }, [message.content]);

  const handleResendEdited = useCallback(async () => {
    await submitEdit();
  }, [submitEdit]);

  useEffect(() => {
    return () => {
      if (copyResetTimeoutRef.current) {
        clearTimeout(copyResetTimeoutRef.current);
        copyResetTimeoutRef.current = null;
      }
    };
  }, []);

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "relative group max-w-[85%] rounded-lg px-4 py-3 select-text",
          isUser
            ? "bg-brand-blue text-white"
            : "bg-gray-50 dark:bg-dark-surface-deep text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700",
        )}
      >
        {isUser && isEditing ? (
          <UserMessageEditor
            value={draftContent}
            onChange={setDraftContent}
            onCancel={cancelEditing}
            onSubmit={handleResendEdited}
            submitDisabled={
              !draftContent.trim() || isConversationStreaming || isSubmitting
            }
          />
        ) : isUser ? (
          <p className="text-sm whitespace-pre-wrap select-text selection:bg-white/35 selection:text-white">
            {message.content}
          </p>
        ) : (
          <div className="select-text selection:bg-brand-blue/25">
            <WizardSimpleMarkdown content={message.content} />
            {isStreamingMessage && (
              <span className="inline-block w-1.5 h-4 bg-brand-blue animate-pulse ml-0.5 align-text-bottom" />
            )}
          </div>
        )}

        {!isStreamingMessage && (
          <div
            className={cn(
              "absolute -top-2",
              isUser ? "-left-2" : "-right-2",
              "flex items-center gap-1",
              "opacity-0 pointer-events-none",
              "group-hover:opacity-100 group-hover:pointer-events-auto",
              "group-focus-within:opacity-100 group-focus-within:pointer-events-auto",
              "transition-opacity",
            )}
          >
            {isUser && !isEditing && onResendEdited && (
              <button
                type="button"
                onClick={startEditing}
                className={cn(
                  "inline-flex items-center justify-center w-7 h-7 rounded-md",
                  "bg-white dark:bg-dark-surface border border-gray-200 dark:border-gray-600",
                  "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300",
                  "shadow-sm",
                  "focus:outline-none focus:ring-2 focus:ring-brand-blue",
                )}
                title="Edit and resend"
                aria-label="Edit and resend"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            )}

            <button
              type="button"
              onClick={handleCopy}
              className={cn(
                "inline-flex items-center justify-center w-7 h-7 rounded-md",
                "bg-white dark:bg-dark-surface border border-gray-200 dark:border-gray-600",
                "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300",
                "shadow-sm",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue",
              )}
              title={copied ? "Copied" : "Copy message"}
              aria-label={copied ? "Copied" : "Copy message"}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-brand-green" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default WizardMessageBubble;

