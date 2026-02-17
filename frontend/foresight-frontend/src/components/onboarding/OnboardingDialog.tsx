/**
 * OnboardingDialog
 *
 * Multi-step welcome dialog shown to first-time users.
 * Three steps: Welcome -> Key Features -> Quick Start.
 * Fully accessible with focus trap, escape-to-close, and reduced-motion support.
 */

import React, { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Compass,
  Sparkles,
  FolderOpen,
  FileText,
  ChevronRight,
  ChevronLeft,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useFocusTrap } from "../../hooks/useFocusTrap";
import {
  ONBOARDING_FEATURES,
  QUICK_START_ACTIONS,
} from "../../lib/onboarding-content";

// Map icon name strings to actual lucide components
const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  Compass,
  Sparkles,
  FolderOpen,
  FileText,
};

interface OnboardingDialogProps {
  open: boolean;
  onClose: () => void;
  /** For quick-start action navigation. Falls back to react-router useNavigate. */
  onNavigate?: (path: string) => void;
}

const TOTAL_STEPS = 3;

export function OnboardingDialog({
  open,
  onClose,
  onNavigate,
}: OnboardingDialogProps) {
  const [step, setStep] = useState(0);
  const navigate = useNavigate();
  const containerRef = useFocusTrap(open);

  const handleNavigate = useCallback(
    (path: string) => {
      if (onNavigate) {
        onNavigate(path);
      } else {
        navigate(path);
      }
      onClose();
    },
    [onNavigate, navigate, onClose],
  );

  // Escape key closes dialog
  useEffect(() => {
    if (!open) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  // Prevent body scroll while dialog is open
  useEffect(() => {
    if (!open) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  // Reset step when dialog reopens
  useEffect(() => {
    if (open) {
      setStep(0);
    }
  }, [open]);

  if (!open) return null;

  const goNext = () => setStep((s) => Math.min(s + 1, TOTAL_STEPS - 1));
  const goBack = () => setStep((s) => Math.max(s - 1, 0));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      aria-modal="true"
      role="dialog"
      aria-label="Welcome to GrantScope"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog content */}
      <div
        ref={containerRef}
        className={cn(
          "relative w-full max-w-lg rounded-2xl shadow-2xl",
          "bg-white dark:bg-dark-surface",
          "border border-gray-200 dark:border-gray-700",
          "motion-safe:animate-in motion-safe:fade-in-0 motion-safe:zoom-in-95 motion-safe:slide-in-from-bottom-4 motion-safe:duration-300",
        )}
      >
        {/* Gradient accent strip */}
        <div className="bg-gradient-to-r from-brand-blue to-brand-green h-1 rounded-t-2xl" />

        <div className="px-8 pt-6 pb-8">
          {/* Step 1: Welcome */}
          {step === 0 && (
            <div className="text-center">
              <img
                src="/logo-icon.png"
                alt="GrantScope logo"
                className="h-16 w-16 mx-auto mb-5"
              />
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
                Welcome to GrantScope
              </h2>
              <p className="text-gray-600 dark:text-gray-300 leading-relaxed max-w-sm mx-auto">
                Your AI-powered grant intelligence platform. We help City of
                Austin staff discover, track, and apply for grant opportunities
                -- all in one place.
              </p>
            </div>
          )}

          {/* Step 2: Key Features */}
          {step === 1 && (
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2 text-center">
                What you can do
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-6 text-center">
                Four tools to streamline your grant workflow
              </p>
              <div className="grid grid-cols-2 gap-3">
                {ONBOARDING_FEATURES.map((feature) => {
                  const IconComponent = ICON_MAP[feature.icon];
                  return (
                    <div
                      key={feature.title}
                      className={cn(
                        "rounded-xl p-4 border",
                        "border-gray-200 dark:border-gray-700",
                        "bg-gray-50 dark:bg-dark-surface-elevated",
                      )}
                    >
                      {IconComponent && (
                        <div className="mb-2.5 inline-flex items-center justify-center w-9 h-9 rounded-lg bg-brand-blue/10 dark:bg-brand-blue/20">
                          <IconComponent className="h-5 w-5 text-brand-blue dark:text-brand-light-blue" />
                        </div>
                      )}
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
                        {feature.title}
                      </h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                        {feature.description}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Step 3: Quick Start */}
          {step === 2 && (
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2 text-center">
                Where would you like to start?
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-6 text-center">
                Pick one to jump right in
              </p>
              <div className="space-y-3">
                {QUICK_START_ACTIONS.map((action) => {
                  const IconComponent = ICON_MAP[action.icon];
                  return (
                    <button
                      key={action.href}
                      onClick={() => handleNavigate(action.href)}
                      className={cn(
                        "w-full flex items-center gap-4 p-4 rounded-xl border text-left",
                        "border-gray-200 dark:border-gray-700",
                        "bg-gray-50 dark:bg-dark-surface-elevated",
                        "hover:border-brand-blue dark:hover:border-brand-blue",
                        "hover:bg-brand-blue/5 dark:hover:bg-brand-blue/10",
                        "transition-colors duration-150",
                        "group",
                      )}
                    >
                      {IconComponent && (
                        <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-brand-blue/10 dark:bg-brand-blue/20 flex items-center justify-center">
                          <IconComponent className="h-5 w-5 text-brand-blue dark:text-brand-light-blue" />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">
                          {action.label}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {action.description}
                        </div>
                      </div>
                      <ChevronRight className="h-4 w-4 text-gray-400 group-hover:text-brand-blue transition-colors flex-shrink-0" />
                    </button>
                  );
                })}
              </div>
              <button
                onClick={onClose}
                className="block mx-auto mt-5 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
              >
                Or just explore on your own
              </button>
            </div>
          )}

          {/* Navigation: dots + buttons */}
          <div className="flex items-center justify-between mt-8">
            {/* Back button */}
            <div className="w-24">
              {step > 0 && (
                <button
                  onClick={goBack}
                  className={cn(
                    "inline-flex items-center gap-1 text-sm font-medium",
                    "text-gray-500 dark:text-gray-400",
                    "hover:text-gray-700 dark:hover:text-gray-200",
                    "transition-colors",
                  )}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Back
                </button>
              )}
            </div>

            {/* Dot indicators */}
            <div className="flex items-center gap-2">
              {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
                <button
                  key={i}
                  onClick={() => setStep(i)}
                  aria-label={`Go to step ${i + 1}`}
                  className={cn(
                    "h-2 rounded-full transition-all duration-200",
                    i === step
                      ? "w-6 bg-brand-blue"
                      : "w-2 bg-gray-300 dark:bg-gray-600 hover:bg-gray-400 dark:hover:bg-gray-500",
                  )}
                />
              ))}
            </div>

            {/* Next / Get Started button */}
            <div className="w-24 flex justify-end">
              {step < TOTAL_STEPS - 1 && (
                <button
                  onClick={goNext}
                  className={cn(
                    "inline-flex items-center gap-1 px-4 py-2 rounded-lg text-sm font-medium",
                    "bg-brand-blue text-white",
                    "hover:bg-brand-dark-blue",
                    "transition-colors",
                  )}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OnboardingDialog;
