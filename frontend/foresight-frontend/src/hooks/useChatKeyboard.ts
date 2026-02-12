/**
 * useChatKeyboard Hook
 *
 * Provides keyboard shortcuts for the chat interface.
 */

import { useEffect, useCallback } from "react";

interface UseChatKeyboardOptions {
  /** Focus the chat input */
  onFocusInput?: () => void;
  /** Start a new conversation */
  onNewConversation?: () => void;
  /** Copy the last assistant response */
  onCopyLastResponse?: () => void;
  /** Stop generating */
  onStopGenerating?: () => void;
  /** Whether the chat is currently streaming */
  isStreaming?: boolean;
}

/**
 * Keyboard shortcuts for the chat:
 * - `/` — Focus chat input (when not in an input/textarea)
 * - `Cmd/Ctrl+Shift+N` — New conversation
 * - `Cmd/Ctrl+Shift+C` — Copy last assistant response
 * - `Escape` — Stop generating (when streaming)
 */
export function useChatKeyboard(options: UseChatKeyboardOptions): void {
  const {
    onFocusInput,
    onNewConversation,
    onCopyLastResponse,
    onStopGenerating,
    isStreaming,
  } = options;

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable;
      const metaKey = e.metaKey || e.ctrlKey;

      // `/` — Focus chat input (only when not already in an input)
      if (e.key === "/" && !isInput && !metaKey) {
        e.preventDefault();
        onFocusInput?.();
        return;
      }

      // `Escape` — Stop generating
      if (e.key === "Escape" && isStreaming) {
        e.preventDefault();
        onStopGenerating?.();
        return;
      }

      // `Cmd/Ctrl+Shift+N` — New conversation
      if (metaKey && e.shiftKey && e.key.toLowerCase() === "n") {
        e.preventDefault();
        onNewConversation?.();
        return;
      }

      // `Cmd/Ctrl+Shift+C` — Copy last response (only when not in input)
      if (metaKey && e.shiftKey && e.key.toLowerCase() === "c" && !isInput) {
        e.preventDefault();
        onCopyLastResponse?.();
        return;
      }
    },
    [
      onFocusInput,
      onNewConversation,
      onCopyLastResponse,
      onStopGenerating,
      isStreaming,
    ],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);
}
