import { useCallback, useEffect, useState } from "react";

export interface EditResendPayload {
  originalMessageId?: string;
  editedContent: string;
}

export type EditResendHandler = (
  payload: EditResendPayload,
) => boolean | void | Promise<boolean | void>;

interface UseEditableMessageOptions {
  messageId?: string;
  messageContent: string;
  onEditResend?: EditResendHandler;
}

export interface UseEditableMessageResult {
  isEditing: boolean;
  draftContent: string;
  isSubmitting: boolean;
  setDraftContent: (value: string) => void;
  startEditing: () => void;
  cancelEditing: () => void;
  submitEdit: () => Promise<boolean>;
}

/**
 * Shared edit-and-resend state machine used by chat message bubbles.
 * Keeps behavior consistent across chat surfaces.
 */
export function useEditableMessage({
  messageId,
  messageContent,
  onEditResend,
}: UseEditableMessageOptions): UseEditableMessageResult {
  const [isEditing, setIsEditing] = useState(false);
  const [draftContent, setDraftContent] = useState(messageContent);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isEditing) {
      setDraftContent(messageContent);
    }
  }, [isEditing, messageContent]);

  const startEditing = useCallback(() => {
    setDraftContent(messageContent);
    setIsEditing(true);
  }, [messageContent]);

  const cancelEditing = useCallback(() => {
    setDraftContent(messageContent);
    setIsEditing(false);
  }, [messageContent]);

  const submitEdit = useCallback(async (): Promise<boolean> => {
    const editedContent = draftContent.trim();
    if (!editedContent || isSubmitting || !onEditResend) {
      return false;
    }

    setIsSubmitting(true);
    try {
      const result = await onEditResend({
        originalMessageId: messageId,
        editedContent,
      });

      const success = result !== false;
      if (success) {
        setIsEditing(false);
        setDraftContent(editedContent);
      }
      return success;
    } finally {
      setIsSubmitting(false);
    }
  }, [draftContent, isSubmitting, onEditResend, messageId]);

  return {
    isEditing,
    draftContent,
    isSubmitting,
    setDraftContent,
    startEditing,
    cancelEditing,
    submitEdit,
  };
}

