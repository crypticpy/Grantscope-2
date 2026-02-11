/**
 * TemplateCard - Template selection card for quick start
 */

import { cn } from "../../lib/utils";
import type { WorkstreamTemplate } from "../../types/workstream";
import { getTemplateColorClasses } from "../../types/workstream";

interface TemplateCardProps {
  template: WorkstreamTemplate;
  onSelect: (template: WorkstreamTemplate) => void;
}

export function TemplateCard({ template, onSelect }: TemplateCardProps) {
  const colors = getTemplateColorClasses(template.color);

  return (
    <button
      type="button"
      onClick={() => onSelect(template)}
      className={cn(
        "flex flex-col items-start p-3 rounded-lg border text-left transition-all",
        colors.bg,
        colors.border,
        colors.hover,
        "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-1 dark:focus:ring-offset-gray-800",
      )}
    >
      <div className={cn("mb-2", colors.text)}>{template.icon}</div>
      <div className="font-medium text-sm text-gray-900 dark:text-white">
        {template.name}
      </div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
        {template.description}
      </div>
    </button>
  );
}
