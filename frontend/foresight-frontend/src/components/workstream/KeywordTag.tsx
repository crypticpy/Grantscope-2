/**
 * KeywordTag - Removable keyword tag component
 *
 * Displays a keyword with a remove button.
 */

import { X } from "lucide-react";

interface KeywordTagProps {
  keyword: string;
  onRemove: () => void;
}

export function KeywordTag({ keyword, onRemove }: KeywordTagProps) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-brand-light-blue dark:bg-brand-blue/20 text-brand-dark-blue dark:text-brand-light-blue text-sm">
      {keyword}
      <button
        type="button"
        onClick={onRemove}
        className="p-0.5 hover:bg-brand-blue/20 dark:hover:bg-brand-blue/40 rounded transition-colors"
        aria-label={`Remove keyword: ${keyword}`}
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  );
}
