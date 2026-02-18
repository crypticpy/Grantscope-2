/**
 * Onboarding State Manager
 *
 * Lightweight localStorage-backed state for onboarding and getting-started flows.
 * All keys are namespaced under `grantscope:` to avoid collisions.
 * All functions are safe for SSR and private browsing (try/catch wrapped).
 */

const KEYS = {
  hasSeenOnboarding: "grantscope:onboarding:completed",
  discoverFilterMode: "grantscope:discover:filter-mode",
  gettingStartedDismissed: "grantscope:getting-started:dismissed",
  completedSteps: "grantscope:getting-started:completed",
  nudgeDismissed: "grantscope:nudge:dismissed",
  profileWizardSkipped: "grantscope:profile-wizard:skipped",
} as const;

/** Known feature intro keys for type safety */
export type FeatureKey = "discover" | "ask" | "programs";

function safeGetItem(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSetItem(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // localStorage unavailable (SSR, private browsing, quota exceeded)
  }
}

export function hasCompletedOnboarding(): boolean {
  return safeGetItem(KEYS.hasSeenOnboarding) === "true";
}

export function markOnboardingComplete(): void {
  safeSetItem(KEYS.hasSeenOnboarding, "true");
}

export function hasSeenFeature(feature: FeatureKey): boolean {
  const key = `grantscope:${feature}:intro-seen`;
  return safeGetItem(key) === "true";
}

export function markFeatureSeen(feature: FeatureKey): void {
  const key = `grantscope:${feature}:intro-seen`;
  safeSetItem(key, "true");
}

export function getFilterMode(): "essential" | "advanced" {
  const mode = safeGetItem(KEYS.discoverFilterMode);
  return mode === "advanced" ? "advanced" : "essential";
}

export function setFilterMode(mode: "essential" | "advanced"): void {
  safeSetItem(KEYS.discoverFilterMode, mode);
}

export function getCompletedSteps(): string[] {
  const raw = safeGetItem(KEYS.completedSteps);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function markStepCompleted(stepId: string): void {
  const steps = getCompletedSteps();
  if (!steps.includes(stepId)) {
    steps.push(stepId);
    safeSetItem(KEYS.completedSteps, JSON.stringify(steps));
  }
}

export function isGettingStartedDismissed(): boolean {
  return safeGetItem(KEYS.gettingStartedDismissed) === "true";
}

export function dismissGettingStarted(): void {
  safeSetItem(KEYS.gettingStartedDismissed, "true");
}

export function isNudgeDismissed(nudgeType: string): boolean {
  const raw = safeGetItem(KEYS.nudgeDismissed);
  if (!raw) return false;
  try {
    const dismissed = JSON.parse(raw);
    return (
      typeof dismissed === "object" &&
      dismissed !== null &&
      dismissed[nudgeType] === true
    );
  } catch {
    return false;
  }
}

export function dismissNudge(nudgeType: string): void {
  const raw = safeGetItem(KEYS.nudgeDismissed);
  let dismissed: Record<string, boolean> = {};
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed === "object" && parsed !== null) {
        dismissed = parsed;
      }
    } catch {
      // corrupted data, start fresh
    }
  }
  dismissed[nudgeType] = true;
  safeSetItem(KEYS.nudgeDismissed, JSON.stringify(dismissed));
}

export function hasSkippedProfileWizard(): boolean {
  return safeGetItem(KEYS.profileWizardSkipped) === "true";
}

export function markProfileWizardSkipped(): void {
  safeSetItem(KEYS.profileWizardSkipped, "true");
}

export function clearProfileWizardSkip(): void {
  try {
    localStorage.removeItem(KEYS.profileWizardSkipped);
  } catch {
    // localStorage unavailable
  }
}

export function resetAllOnboarding(): void {
  try {
    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith("grantscope:")) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach((key) => localStorage.removeItem(key));
  } catch {
    // localStorage unavailable
  }
}
