import {
  useState,
  useEffect,
  useRef,
  useCallback,
  lazy,
  Suspense,
} from "react";
import { useNavigate } from "react-router-dom";
import { WizardStepProgress } from "@/components/wizard/WizardStepProgress";
import { PageLoadingSpinner } from "@/components/PageLoadingSpinner";
import { getStoredToken } from "@/App";
import { getProfile, updateProfile, type ProfileData } from "@/lib/profile-api";
import { markProfileWizardSkipped } from "@/lib/onboarding-state";

const ProfileStepIdentity = lazy(
  () => import("@/components/profile-wizard/ProfileStepIdentity"),
);
const ProfileStepProgram = lazy(
  () => import("@/components/profile-wizard/ProfileStepProgram"),
);
const ProfileStepGrants = lazy(
  () => import("@/components/profile-wizard/ProfileStepGrants"),
);
const ProfileStepPriorities = lazy(
  () => import("@/components/profile-wizard/ProfileStepPriorities"),
);
const ProfileStepReview = lazy(
  () => import("@/components/profile-wizard/ProfileStepReview"),
);

const STEP_LABELS = [
  "About You",
  "Your Program",
  "Grant Interests",
  "Priorities",
  "Review",
];

export default function ProfileSetup() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [profileData, setProfileData] = useState<ProfileData>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const prevStep = useRef(currentStep);
  const initialLoadDone = useRef(false);

  // Load existing profile on mount
  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setLoading(false);
      return;
    }
    getProfile(token)
      .then((data) => {
        setProfileData(data);
        // Resume from saved step
        if (data.profile_step && data.profile_step > 0) {
          setCurrentStep(data.profile_step);
          prevStep.current = data.profile_step;
        }
        initialLoadDone.current = true;
      })
      .catch((err) => {
        console.error("Failed to load profile:", err);
        initialLoadDone.current = true;
      })
      .finally(() => setLoading(false));
  }, []);

  // Auto-save on step change
  useEffect(() => {
    if (!initialLoadDone.current) return;
    if (currentStep === prevStep.current) return;
    prevStep.current = currentStep;

    const token = getStoredToken();
    if (!token) return;

    updateProfile(token, { profile_step: currentStep }).catch((err) =>
      console.error("Failed to save step progress:", err),
    );
  }, [currentStep]);

  const handleUpdate = useCallback(async (partial: Partial<ProfileData>) => {
    setProfileData((prev) => ({ ...prev, ...partial }));
    const token = getStoredToken();
    if (!token) return;
    setSaving(true);
    try {
      const updated = await updateProfile(token, partial);
      setProfileData((prev) => ({ ...prev, ...updated }));
    } catch (err) {
      console.error("Failed to save profile:", err);
      setError("Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }, []);

  const goNext = useCallback(() => {
    setCurrentStep((s) => Math.min(s + 1, STEP_LABELS.length - 1));
    setError("");
  }, []);

  const goBack = useCallback(() => {
    setCurrentStep((s) => Math.max(s - 1, 0));
    setError("");
  }, []);

  const goToStep = useCallback((step: number) => {
    setCurrentStep(Math.max(0, Math.min(step, STEP_LABELS.length - 1)));
    setError("");
  }, []);

  const handleSkip = useCallback(() => {
    markProfileWizardSkipped();
    navigate("/");
  }, [navigate]);

  const handleComplete = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    setSaving(true);
    try {
      // profile_completed_at is auto-set server-side when profile_step >= 4
      const updated = await updateProfile(token, {
        profile_step: STEP_LABELS.length - 1,
      });
      // Update cached user in localStorage
      const cachedUser = localStorage.getItem("gs2_user");
      if (cachedUser) {
        try {
          const user = JSON.parse(cachedUser);
          user.profile_completed_at = updated.profile_completed_at;
          localStorage.setItem("gs2_user", JSON.stringify(user));
        } catch {
          /* ignore */
        }
      }
      navigate("/");
    } catch (err) {
      console.error("Failed to complete profile:", err);
      setError("Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }, [navigate]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <PageLoadingSpinner message="Loading your profile..." />
      </div>
    );
  }

  const renderStep = () => {
    const commonProps = {
      data: profileData,
      onUpdate: handleUpdate,
      onNext: goNext,
      onBack: goBack,
      onSkip: handleSkip,
      saving,
    };

    switch (currentStep) {
      case 0:
        return <ProfileStepIdentity {...commonProps} />;
      case 1:
        return <ProfileStepProgram {...commonProps} />;
      case 2:
        return <ProfileStepGrants {...commonProps} />;
      case 3:
        return <ProfileStepPriorities {...commonProps} />;
      case 4:
        return (
          <ProfileStepReview
            data={profileData}
            onComplete={handleComplete}
            onBack={goBack}
            onGoToStep={goToStep}
            saving={saving}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-brand-faded-white dark:bg-brand-dark-blue">
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Set Up Your Profile
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Help us personalize your grant recommendations and proposals
          </p>
        </div>

        {/* Step progress */}
        <div className="bg-white dark:bg-gray-800 rounded-t-xl border border-gray-200 dark:border-gray-700 border-b-0">
          <WizardStepProgress currentStep={currentStep} labels={STEP_LABELS} />
        </div>

        {/* Step content */}
        <div className="bg-white dark:bg-gray-800 rounded-b-xl border border-gray-200 dark:border-gray-700 border-t-0">
          {error && (
            <div className="mx-6 mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
              {error}
            </div>
          )}
          <Suspense fallback={<PageLoadingSpinner message="Loading step..." />}>
            {renderStep()}
          </Suspense>
        </div>
      </div>
    </div>
  );
}
