import { Send, X } from "lucide-react";
import { cn } from "../../lib/utils";

interface UserMessageEditorProps {
  value: string;
  onChange: (value: string) => void;
  onCancel: () => void;
  onSubmit: () => void;
  submitDisabled?: boolean;
}

export function UserMessageEditor({
  value,
  onChange,
  onCancel,
  onSubmit,
  submitDisabled = false,
}: UserMessageEditorProps) {
  return (
    <div className="space-y-2">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        maxLength={4000}
        className={cn(
          "w-full resize-y min-h-[70px] max-h-56 rounded-lg",
          "px-2.5 py-2 text-sm leading-relaxed",
          "bg-white/95 text-gray-900",
          "border border-white/80",
          "focus:outline-none focus:ring-2 focus:ring-white/80",
        )}
        aria-label="Edit message content"
      />
      <div className="flex items-center justify-end gap-1.5">
        <button
          type="button"
          onClick={onCancel}
          className={cn(
            "inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium",
            "bg-white/20 hover:bg-white/30 text-white",
            "focus:outline-none focus:ring-2 focus:ring-white/70",
          )}
          title="Cancel edit"
          aria-label="Cancel edit"
        >
          <X className="h-3 w-3" />
          Cancel
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={submitDisabled}
          className={cn(
            "inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium",
            "bg-white text-brand-blue hover:bg-gray-100",
            "disabled:opacity-60 disabled:cursor-not-allowed",
            "focus:outline-none focus:ring-2 focus:ring-white/70",
          )}
          title="Resend edited message"
          aria-label="Resend edited message"
        >
          <Send className="h-3 w-3" />
          Resend
        </button>
      </div>
    </div>
  );
}

export default UserMessageEditor;

