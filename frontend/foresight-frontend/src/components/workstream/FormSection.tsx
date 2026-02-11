/**
 * FormSection - Section wrapper for form groups
 *
 * Provides consistent heading + description + children layout
 * for both WorkstreamForm and WorkstreamWizard steps.
 */

import React from "react";

interface FormSectionProps {
  title: string;
  description?: string;
  children: React.ReactNode;
}

export function FormSection({
  title,
  description,
  children,
}: FormSectionProps) {
  return (
    <div className="space-y-3">
      <div>
        <h4 className="text-sm font-medium text-gray-900 dark:text-white">
          {title}
        </h4>
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            {description}
          </p>
        )}
      </div>
      {children}
    </div>
  );
}
