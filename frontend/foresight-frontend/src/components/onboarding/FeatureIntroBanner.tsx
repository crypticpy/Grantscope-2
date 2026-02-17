/**
 * FeatureIntroBanner
 *
 * A dismissible first-use intro banner shown once per feature.
 * Displays a heading, body, and tip with a gradient accent strip.
 * Dismissal persists in localStorage via the onboarding-state manager.
 */

import { useState } from "react";
import { X } from "lucide-react";
import { cn } from "../../lib/utils";
import {
  hasSeenFeature,
  markFeatureSeen,
  type FeatureKey,
} from "../../lib/onboarding-state";
import { PAGE_INTROS } from "../../lib/onboarding-content";

interface FeatureIntroBannerProps {
  /** Which feature this banner introduces */
  feature: FeatureKey;
  /** Additional className for the outer container */
  className?: string;
}

export function FeatureIntroBanner({
  feature,
  className,
}: FeatureIntroBannerProps) {
  const [visible, setVisible] = useState(() => !hasSeenFeature(feature));

  if (!visible) return null;

  const intro = PAGE_INTROS[feature];

  return (
    <div
      className={cn(
        "bg-white dark:bg-dark-surface rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden",
        className,
      )}
    >
      <div className="bg-gradient-to-r from-brand-blue to-brand-green h-1" />
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
              {intro.heading}
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">
              {intro.body}
            </p>
            <p className="text-xs text-brand-blue dark:text-blue-400 italic">
              {intro.tipText}
            </p>
          </div>
          <button
            onClick={() => {
              markFeatureSeen(feature);
              setVisible(false);
            }}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded transition-colors flex-shrink-0"
            aria-label="Dismiss introduction"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default FeatureIntroBanner;
