/**
 * WorkstreamForm Component
 *
 * A comprehensive form for creating and editing workstreams.
 * Supports:
 * - CREATE mode (empty form, POST)
 * - EDIT mode (pre-filled form, PATCH)
 * - Multi-select pillars with PillarBadge components
 * - Goals filtered by selected pillars
 * - Stage selection (1-8)
 * - Horizon selection (H1, H2, H3, ALL)
 * - Keyword tag input
 * - Active toggle
 */

import React, {
  useState,
  useEffect,
  useCallback,
  KeyboardEvent,
  useRef,
} from "react";
import {
  X,
  Plus,
  Loader2,
  AlertCircle,
  Sparkles,
  Search,
  Wand2,
  Radar,
} from "lucide-react";
import { supabase } from "../App";
import { useAuthContext } from "../hooks/useAuthContext";
import { cn } from "../lib/utils";
import { PillarBadge } from "./PillarBadge";
import { pillars, stages, horizons, getGoalsByPillar } from "../data/taxonomy";
import { suggestKeywords } from "../lib/discovery-api";

// ============================================================================
// Filter Preview Types & API
// ============================================================================

interface FilterPreviewResult {
  estimated_count: number;
  sample_cards: Array<{
    id: string;
    name: string;
    pillar_id?: string;
    horizon?: string;
  }>;
}

async function fetchFilterPreview(
  token: string,
  filters: {
    pillar_ids: string[];
    goal_ids: string[];
    stage_ids: string[];
    horizon: string;
    keywords: string[];
  },
): Promise<FilterPreviewResult> {
  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  const response = await fetch(`${API_BASE_URL}/api/v1/cards/filter-preview`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      pillar_ids: filters.pillar_ids,
      goal_ids: filters.goal_ids,
      stage_ids: filters.stage_ids,
      horizon: filters.horizon === "ALL" ? null : filters.horizon,
      keywords: filters.keywords,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to fetch filter preview");
  }

  return response.json();
}

// ============================================================================
// Types
// ============================================================================

export interface Workstream {
  id: string;
  name: string;
  description: string;
  pillar_ids: string[];
  goal_ids: string[];
  stage_ids: string[];
  horizon: string;
  keywords: string[];
  is_active: boolean;
  auto_add: boolean;
  created_at: string;
}

export interface WorkstreamFormProps {
  /** If provided, form operates in EDIT mode; otherwise CREATE mode */
  workstream?: Workstream;
  /** Called after successful save */
  onSuccess: () => void;
  /** Called when form is cancelled */
  onCancel: () => void;
  /** Called after creation when auto-populate finds zero matching cards */
  onCreatedWithZeroMatches?: (workstreamId: string) => void;
}

interface FormData {
  name: string;
  description: string;
  pillar_ids: string[];
  goal_ids: string[];
  stage_ids: string[];
  horizon: string;
  keywords: string[];
  is_active: boolean;
  analyze_now: boolean;
  auto_scan: boolean;
}

interface FormErrors {
  name?: string;
  filters?: string;
  submit?: string;
}

// ============================================================================
// Workstream Templates
// ============================================================================

interface WorkstreamTemplate {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  config: {
    name: string;
    description: string;
    pillar_ids: string[];
    goal_ids: string[];
    stage_ids: string[];
    horizon: string;
    keywords: string[];
  };
}

const WORKSTREAM_TEMPLATES: WorkstreamTemplate[] = [
  {
    id: "emerging-tech",
    name: "Emerging Technology",
    description: "Track early-stage innovations and R&D across all sectors",
    icon: <Sparkles className="h-5 w-5" />,
    color: "purple",
    config: {
      name: "Emerging Technology Watch",
      description:
        "Monitoring early-stage innovations, research breakthroughs, and emerging technologies that could impact city operations in the coming years.",
      pillar_ids: [],
      goal_ids: [],
      stage_ids: ["1", "2", "3"],
      horizon: "H3",
      keywords: [
        "innovation",
        "research",
        "emerging",
        "breakthrough",
        "startup",
      ],
    },
  },
  {
    id: "smart-city",
    name: "Smart City & Infrastructure",
    description: "Focus on mobility, utilities, and city infrastructure tech",
    icon: <Search className="h-5 w-5" />,
    color: "amber",
    config: {
      name: "Smart City & Infrastructure",
      description:
        "Tracking smart city technologies, mobility innovations, and infrastructure modernization relevant to Austin.",
      pillar_ids: ["MC"],
      goal_ids: [],
      stage_ids: ["3", "4", "5", "6"],
      horizon: "H2",
      keywords: [
        "smart city",
        "IoT",
        "mobility",
        "transit",
        "infrastructure",
        "utilities",
      ],
    },
  },
  {
    id: "leadership-ready",
    name: "Leadership Ready",
    description: "Mature technologies ready for executive briefings",
    icon: <AlertCircle className="h-5 w-5" />,
    color: "green",
    config: {
      name: "Leadership Ready",
      description:
        "Technologies and trends at sufficient maturity for executive consideration and potential implementation.",
      pillar_ids: [],
      goal_ids: [],
      stage_ids: ["5", "6", "7"],
      horizon: "H1",
      keywords: [],
    },
  },
  {
    id: "climate-sustainability",
    name: "Climate & Sustainability",
    description: "Environmental tech and climate resilience innovations",
    icon: <Search className="h-5 w-5" />,
    color: "green",
    config: {
      name: "Climate & Sustainability",
      description:
        "Monitoring climate technology, sustainability innovations, and environmental resilience solutions.",
      pillar_ids: ["CH"],
      goal_ids: ["CH.3", "CH.4"],
      stage_ids: [],
      horizon: "ALL",
      keywords: [
        "climate",
        "sustainability",
        "renewable",
        "resilience",
        "green",
        "carbon",
      ],
    },
  },
  {
    id: "public-safety",
    name: "Public Safety Tech",
    description: "Safety, emergency response, and community protection",
    icon: <Search className="h-5 w-5" />,
    color: "red",
    config: {
      name: "Public Safety Technology",
      description:
        "Innovations in public safety, emergency response, disaster preparedness, and community protection.",
      pillar_ids: ["PS"],
      goal_ids: [],
      stage_ids: [],
      horizon: "ALL",
      keywords: ["safety", "emergency", "disaster", "response", "security"],
    },
  },
  {
    id: "govtech",
    name: "GovTech & Digital Services",
    description: "Government technology and citizen service innovations",
    icon: <Search className="h-5 w-5" />,
    color: "indigo",
    config: {
      name: "GovTech & Digital Services",
      description:
        "Digital government innovations, citizen services technology, and public sector modernization.",
      pillar_ids: ["HG"],
      goal_ids: ["HG.2"],
      stage_ids: [],
      horizon: "ALL",
      keywords: [
        "govtech",
        "digital services",
        "citizen",
        "automation",
        "AI",
        "data",
      ],
    },
  },
];

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Template color classes
 */
function getTemplateColorClasses(color: string): {
  bg: string;
  border: string;
  text: string;
  hover: string;
} {
  const defaultColor = {
    bg: "bg-blue-50 dark:bg-blue-900/20",
    border: "border-blue-200 dark:border-blue-700",
    text: "text-blue-700 dark:text-blue-300",
    hover: "hover:bg-blue-100 dark:hover:bg-blue-900/40",
  };
  const colorMap: Record<
    string,
    { bg: string; border: string; text: string; hover: string }
  > = {
    purple: {
      bg: "bg-purple-50 dark:bg-purple-900/20",
      border: "border-purple-200 dark:border-purple-700",
      text: "text-purple-700 dark:text-purple-300",
      hover: "hover:bg-purple-100 dark:hover:bg-purple-900/40",
    },
    amber: {
      bg: "bg-amber-50 dark:bg-amber-900/20",
      border: "border-amber-200 dark:border-amber-700",
      text: "text-amber-700 dark:text-amber-300",
      hover: "hover:bg-amber-100 dark:hover:bg-amber-900/40",
    },
    green: {
      bg: "bg-green-50 dark:bg-green-900/20",
      border: "border-green-200 dark:border-green-700",
      text: "text-green-700 dark:text-green-300",
      hover: "hover:bg-green-100 dark:hover:bg-green-900/40",
    },
    red: {
      bg: "bg-red-50 dark:bg-red-900/20",
      border: "border-red-200 dark:border-red-700",
      text: "text-red-700 dark:text-red-300",
      hover: "hover:bg-red-100 dark:hover:bg-red-900/40",
    },
    indigo: {
      bg: "bg-indigo-50 dark:bg-indigo-900/20",
      border: "border-indigo-200 dark:border-indigo-700",
      text: "text-indigo-700 dark:text-indigo-300",
      hover: "hover:bg-indigo-100 dark:hover:bg-indigo-900/40",
    },
    blue: defaultColor,
  };
  return colorMap[color] ?? defaultColor;
}

/**
 * Template card component for quick start
 */
function TemplateCard({
  template,
  onSelect,
}: {
  template: WorkstreamTemplate;
  onSelect: (template: WorkstreamTemplate) => void;
}) {
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

/**
 * Section wrapper for form groups
 */
function FormSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
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

/**
 * Removable tag component for keywords
 */
function KeywordTag({
  keyword,
  onRemove,
}: {
  keyword: string;
  onRemove: () => void;
}) {
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

/**
 * Toggle switch component
 */
function ToggleSwitch({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
}) {
  return (
    <label className="flex items-start gap-3 cursor-pointer">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2 dark:focus:ring-offset-[#2d3166]",
          checked ? "bg-brand-blue" : "bg-gray-200 dark:bg-gray-600",
        )}
      >
        <span
          className={cn(
            "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out",
            checked ? "translate-x-5" : "translate-x-0",
          )}
        />
      </button>
      <div className="flex-1">
        <span className="text-sm font-medium text-gray-900 dark:text-white">
          {label}
        </span>
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            {description}
          </p>
        )}
      </div>
    </label>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function WorkstreamForm({
  workstream,
  onSuccess,
  onCancel,
  onCreatedWithZeroMatches,
}: WorkstreamFormProps) {
  const { user } = useAuthContext();
  const isEditMode = Boolean(workstream);

  // Form state
  const [formData, setFormData] = useState<FormData>({
    name: workstream?.name || "",
    description: workstream?.description || "",
    pillar_ids: workstream?.pillar_ids || [],
    goal_ids: workstream?.goal_ids || [],
    stage_ids: workstream?.stage_ids || [],
    horizon: workstream?.horizon || "ALL",
    keywords: workstream?.keywords || [],
    is_active: workstream?.is_active ?? true,
    analyze_now: false, // Only used in CREATE mode
    auto_scan: false, // Defaults updated based on pillar selection
  });

  // UI state
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [keywordInput, setKeywordInput] = useState("");

  // Suggest keywords state
  const [suggestedKeywords, setSuggestedKeywords] = useState<string[]>([]);
  const [isSuggestingKeywords, setIsSuggestingKeywords] = useState(false);

  // Post-creation zero-match prompt state
  const [showZeroMatchPrompt, setShowZeroMatchPrompt] = useState(false);
  const [createdWorkstreamId, setCreatedWorkstreamId] = useState<string | null>(
    null,
  );

  // Filter preview state
  const [preview, setPreview] = useState<FilterPreviewResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Derived state: available goals based on selected pillars
  const availableGoals = formData.pillar_ids.flatMap((pillarCode) =>
    getGoalsByPillar(pillarCode),
  );

  // Check if any filters are set
  const hasFilters =
    formData.pillar_ids.length > 0 ||
    formData.goal_ids.length > 0 ||
    formData.stage_ids.length > 0 ||
    formData.horizon !== "ALL" ||
    formData.keywords.length > 0;

  // Fetch filter preview when filters change
  useEffect(() => {
    // Clear previous timeout
    if (previewDebounceRef.current) {
      clearTimeout(previewDebounceRef.current);
    }

    // Don't fetch if no filters
    if (!hasFilters) {
      setPreview(null);
      return;
    }

    // Debounce the preview fetch
    previewDebounceRef.current = setTimeout(async () => {
      setPreviewLoading(true);
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session?.access_token) return;

        const result = await fetchFilterPreview(session.access_token, {
          pillar_ids: formData.pillar_ids,
          goal_ids: formData.goal_ids,
          stage_ids: formData.stage_ids,
          horizon: formData.horizon,
          keywords: formData.keywords,
        });
        setPreview(result);
      } catch (error) {
        console.error("Failed to fetch filter preview:", error);
        setPreview(null);
      } finally {
        setPreviewLoading(false);
      }
    }, 500); // 500ms debounce

    return () => {
      if (previewDebounceRef.current) {
        clearTimeout(previewDebounceRef.current);
      }
    };
  }, [
    formData.pillar_ids,
    formData.goal_ids,
    formData.stage_ids,
    formData.horizon,
    formData.keywords,
    hasFilters,
  ]);

  // When pillars change, filter out goals that are no longer valid
  useEffect(() => {
    const validGoalCodes = new Set(availableGoals.map((g) => g.code));
    const filteredGoals = formData.goal_ids.filter((id) =>
      validGoalCodes.has(id),
    );
    if (filteredGoals.length !== formData.goal_ids.length) {
      setFormData((prev) => ({ ...prev, goal_ids: filteredGoals }));
    }
  }, [formData.pillar_ids, availableGoals, formData.goal_ids]);

  // ============================================================================
  // Validation
  // ============================================================================

  const validateForm = useCallback((): boolean => {
    const newErrors: FormErrors = {};

    // Name is required
    if (!formData.name.trim()) {
      newErrors.name = "Name is required";
    }

    // Pillar selection is optional - topic-first workstreams can use keywords only
    // No filter validation required; workstreams can be purely topic-driven

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData]);

  // ============================================================================
  // Handlers
  // ============================================================================

  const handlePillarToggle = (pillarCode: string) => {
    setFormData((prev) => ({
      ...prev,
      pillar_ids: prev.pillar_ids.includes(pillarCode)
        ? prev.pillar_ids.filter((id) => id !== pillarCode)
        : [...prev.pillar_ids, pillarCode],
    }));
    // Clear filter error when user makes a selection
    if (errors.filters) {
      setErrors((prev) => ({ ...prev, filters: undefined }));
    }
  };

  const handleGoalToggle = (goalCode: string) => {
    setFormData((prev) => ({
      ...prev,
      goal_ids: prev.goal_ids.includes(goalCode)
        ? prev.goal_ids.filter((id) => id !== goalCode)
        : [...prev.goal_ids, goalCode],
    }));
    if (errors.filters) {
      setErrors((prev) => ({ ...prev, filters: undefined }));
    }
  };

  const handleStageToggle = (stageNum: number) => {
    const stageId = stageNum.toString();
    setFormData((prev) => ({
      ...prev,
      stage_ids: prev.stage_ids.includes(stageId)
        ? prev.stage_ids.filter((id) => id !== stageId)
        : [...prev.stage_ids, stageId],
    }));
    if (errors.filters) {
      setErrors((prev) => ({ ...prev, filters: undefined }));
    }
  };

  const handleHorizonChange = (horizon: string) => {
    setFormData((prev) => ({ ...prev, horizon }));
    if (errors.filters) {
      setErrors((prev) => ({ ...prev, filters: undefined }));
    }
  };

  const handleKeywordAdd = () => {
    const trimmed = keywordInput.trim();
    if (trimmed && !formData.keywords.includes(trimmed)) {
      setFormData((prev) => ({
        ...prev,
        keywords: [...prev.keywords, trimmed],
      }));
      setKeywordInput("");
      if (errors.filters) {
        setErrors((prev) => ({ ...prev, filters: undefined }));
      }
    }
  };

  const handleKeywordInputKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleKeywordAdd();
    } else if (e.key === "," && keywordInput.trim()) {
      e.preventDefault();
      handleKeywordAdd();
    }
  };

  const handleKeywordRemove = (keyword: string) => {
    setFormData((prev) => ({
      ...prev,
      keywords: prev.keywords.filter((k) => k !== keyword),
    }));
  };

  // Suggest related keywords using AI
  const handleSuggestKeywords = async () => {
    // Use current keyword input, name, or description as the topic
    const topic =
      keywordInput.trim() ||
      formData.name.trim() ||
      formData.description.trim();
    if (!topic) return;

    setIsSuggestingKeywords(true);
    setSuggestedKeywords([]);
    try {
      const token = await getAuthToken();
      if (!token) return;
      const result = await suggestKeywords(topic, token);
      // Filter out keywords already in the form
      const newSuggestions = result.keywords.filter(
        (kw) => !formData.keywords.includes(kw),
      );
      setSuggestedKeywords(newSuggestions);
    } catch (error) {
      console.error("Failed to suggest keywords:", error);
    } finally {
      setIsSuggestingKeywords(false);
    }
  };

  // Add a suggested keyword to the form
  const handleAddSuggestedKeyword = (keyword: string) => {
    if (!formData.keywords.includes(keyword)) {
      setFormData((prev) => ({
        ...prev,
        keywords: [...prev.keywords, keyword],
      }));
      if (errors.filters) {
        setErrors((prev) => ({ ...prev, filters: undefined }));
      }
    }
    // Remove from suggestions
    setSuggestedKeywords((prev) => prev.filter((kw) => kw !== keyword));
  };

  // Sync auto_scan default based on pillar selection (topic-first = ON, pillar-based = OFF)
  useEffect(() => {
    if (!isEditMode) {
      setFormData((prev) => ({
        ...prev,
        auto_scan: prev.pillar_ids.length === 0,
      }));
    }
  }, [formData.pillar_ids.length, isEditMode]);

  // Apply a template to the form
  const handleApplyTemplate = useCallback((template: WorkstreamTemplate) => {
    setFormData((prev) => ({
      ...prev,
      name: template.config.name,
      description: template.config.description,
      pillar_ids: template.config.pillar_ids,
      goal_ids: template.config.goal_ids,
      stage_ids: template.config.stage_ids,
      horizon: template.config.horizon,
      keywords: template.config.keywords,
    }));
    // Clear any validation errors
    setErrors({});
  }, []);

  // Helper to get auth token
  const getAuthToken = async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token;
  };

  // Trigger workstream analysis via API
  const triggerWorkstreamAnalysis = async (workstreamId: string) => {
    const token = await getAuthToken();
    if (!token) return;

    const API_BASE_URL =
      import.meta.env.VITE_API_URL || "http://localhost:8000";

    try {
      await fetch(`${API_BASE_URL}/api/v1/research`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          workstream_id: workstreamId,
          task_type: "workstream_analysis",
        }),
      });
      // Fire and forget - analysis runs in background
    } catch (error) {
      console.error("Error triggering workstream analysis:", error);
      // Don't fail the form submission if analysis fails to start
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    setErrors({});

    try {
      const payload = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        pillar_ids: formData.pillar_ids,
        goal_ids: formData.goal_ids,
        stage_ids: formData.stage_ids,
        horizon: formData.horizon,
        keywords: formData.keywords,
        is_active: formData.is_active,
        ...(formData.auto_scan ? { auto_scan: true } : {}),
      };

      if (isEditMode && workstream) {
        // PATCH: Update existing workstream
        const { error } = await supabase
          .from("workstreams")
          .update(payload)
          .eq("id", workstream.id)
          .eq("user_id", user?.id);

        if (error) throw error;
      } else {
        // POST: Create new workstream
        const { data, error } = await supabase
          .from("workstreams")
          .insert({
            ...payload,
            user_id: user?.id,
            auto_add: false, // Default value, deferred for later
          })
          .select("id")
          .single();

        if (error) throw error;

        // If analyze_now is enabled, trigger analysis
        if (formData.analyze_now && data?.id) {
          await triggerWorkstreamAnalysis(data.id);
        }

        // Check if auto-populate returned zero matches and show prompt
        if (data?.id && preview?.estimated_count === 0) {
          setCreatedWorkstreamId(data.id);
          setShowZeroMatchPrompt(true);
          if (onCreatedWithZeroMatches) {
            onCreatedWithZeroMatches(data.id);
          }
        }
      }

      onSuccess();
    } catch (error) {
      console.error("Error saving workstream:", error);
      setErrors({
        submit:
          error instanceof Error
            ? error.message
            : "Failed to save workstream. Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Quick Start Templates - Only in CREATE mode */}
      {!isEditMode && (
        <div className="space-y-3">
          <div>
            <h4 className="text-sm font-medium text-gray-900 dark:text-white">
              Quick Start Templates
            </h4>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Choose a template to pre-fill the form, or start from scratch
              below
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {WORKSTREAM_TEMPLATES.map((template) => (
              <TemplateCard
                key={template.id}
                template={template}
                onSelect={handleApplyTemplate}
              />
            ))}
          </div>
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200 dark:border-gray-700" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-white dark:bg-[#2d3166] px-2 text-gray-500 dark:text-gray-400">
                or customize your own
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Name Field */}
      <div>
        <label
          htmlFor="workstream-name"
          className="block text-sm font-medium text-gray-900 dark:text-white mb-1"
        >
          Name <span className="text-red-500">*</span>
        </label>
        <input
          id="workstream-name"
          type="text"
          value={formData.name}
          onChange={(e) => {
            setFormData((prev) => ({ ...prev, name: e.target.value }));
            if (errors.name) {
              setErrors((prev) => ({ ...prev, name: undefined }));
            }
          }}
          placeholder="e.g., Smart Mobility Initiatives"
          className={cn(
            "w-full px-3 py-2 border rounded-md shadow-sm text-sm",
            "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue",
            "dark:bg-[#3d4176] dark:text-white dark:placeholder-gray-400",
            errors.name
              ? "border-red-300 bg-red-50 dark:border-red-500 dark:bg-red-900/20"
              : "border-gray-300 bg-white dark:border-gray-600",
          )}
          aria-invalid={Boolean(errors.name)}
          aria-describedby={errors.name ? "name-error" : undefined}
        />
        {errors.name && (
          <p
            id="name-error"
            className="mt-1 text-xs text-red-600 dark:text-red-400"
          >
            {errors.name}
          </p>
        )}
      </div>

      {/* Description Field */}
      <div>
        <label
          htmlFor="workstream-description"
          className="block text-sm font-medium text-gray-900 dark:text-white mb-1"
        >
          Description
        </label>
        <textarea
          id="workstream-description"
          value={formData.description}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, description: e.target.value }))
          }
          placeholder="Describe the focus and purpose of this workstream..."
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue bg-white dark:bg-[#3d4176] dark:text-white dark:placeholder-gray-400 resize-none"
        />
      </div>

      {/* Pillars Selection */}
      <FormSection
        title="Pillars"
        description="Optionally select strategic pillars to filter by, or leave empty for a topic-driven workstream"
      >
        <div className="flex flex-wrap gap-2">
          {pillars.map((pillar) => (
            <button
              key={pillar.code}
              type="button"
              onClick={() => handlePillarToggle(pillar.code)}
              className={cn(
                "transition-all duration-150",
                formData.pillar_ids.includes(pillar.code)
                  ? "ring-2 ring-brand-blue ring-offset-1 dark:ring-offset-[#2d3166] rounded"
                  : "opacity-60 hover:opacity-100",
              )}
              aria-pressed={formData.pillar_ids.includes(pillar.code)}
              aria-label={`${pillar.name} pillar`}
            >
              <PillarBadge
                pillarId={pillar.code}
                size="md"
                showIcon={true}
                disableTooltip
              />
            </button>
          ))}
        </div>
      </FormSection>

      {/* Goals Selection (grouped by pillar, only show if pillars selected) */}
      {formData.pillar_ids.length > 0 && (
        <FormSection
          title="Goals"
          description="Narrow down by specific goals within selected pillars"
        >
          <div className="space-y-4 max-h-48 overflow-y-auto border border-gray-200 dark:border-gray-600 rounded-md p-3 bg-gray-50 dark:bg-[#3d4176]">
            {formData.pillar_ids.map((pillarCode) => {
              const pillarGoals = getGoalsByPillar(pillarCode);
              const pillar = pillars.find((p) => p.code === pillarCode);
              if (!pillar || pillarGoals.length === 0) return null;

              return (
                <div key={pillarCode}>
                  <div className="flex items-center gap-2 mb-2">
                    <PillarBadge
                      pillarId={pillarCode}
                      size="sm"
                      showIcon={false}
                      disableTooltip
                    />
                    <span className="text-xs font-medium text-gray-600 dark:text-gray-300">
                      {pillar.name}
                    </span>
                  </div>
                  <div className="space-y-1 ml-4">
                    {pillarGoals.map((goal) => (
                      <label
                        key={goal.code}
                        className="flex items-start gap-2 cursor-pointer group"
                      >
                        <input
                          type="checkbox"
                          checked={formData.goal_ids.includes(goal.code)}
                          onChange={() => handleGoalToggle(goal.code)}
                          className="mt-0.5 h-4 w-4 text-brand-blue border-gray-300 dark:border-gray-500 rounded focus:ring-brand-blue"
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white">
                          <span className="font-mono text-xs text-gray-500 dark:text-gray-400 mr-1">
                            {goal.code}
                          </span>
                          {goal.name}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </FormSection>
      )}

      {/* Stages Selection */}
      <FormSection
        title="Maturity Stages"
        description="Filter by technology maturity stage (1-8)"
      >
        <div className="flex flex-wrap gap-2">
          {stages.map((stage) => (
            <button
              key={stage.stage}
              type="button"
              onClick={() => handleStageToggle(stage.stage)}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-md border transition-colors",
                formData.stage_ids.includes(stage.stage.toString())
                  ? "bg-brand-light-blue dark:bg-brand-blue/20 border-brand-blue text-brand-dark-blue dark:text-brand-light-blue"
                  : "bg-white dark:bg-[#3d4176] border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#4d5186]",
              )}
              aria-pressed={formData.stage_ids.includes(stage.stage.toString())}
              title={`${stage.name}: ${stage.description}`}
            >
              {stage.stage}. {stage.name}
            </button>
          ))}
        </div>
      </FormSection>

      {/* Horizon Selection */}
      <FormSection
        title="Horizon"
        description="Filter by strategic planning horizon"
      >
        <div className="flex flex-wrap gap-2">
          {[
            { code: "ALL", name: "All Horizons", timeframe: "" },
            ...horizons,
          ].map((h) => (
            <button
              key={h.code}
              type="button"
              onClick={() => handleHorizonChange(h.code)}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-md border transition-colors",
                formData.horizon === h.code
                  ? "bg-brand-light-blue dark:bg-brand-blue/20 border-brand-blue text-brand-dark-blue dark:text-brand-light-blue"
                  : "bg-white dark:bg-[#3d4176] border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#4d5186]",
              )}
              aria-pressed={formData.horizon === h.code}
            >
              {h.code === "ALL" ? "All" : h.code}
              {h.code !== "ALL" && (
                <span className="ml-1 text-xs text-gray-500 dark:text-gray-400">
                  ({(h as (typeof horizons)[0]).timeframe})
                </span>
              )}
            </button>
          ))}
        </div>
      </FormSection>

      {/* Keywords Input */}
      <FormSection
        title="Keywords"
        description="Add keywords to match against card content (press Enter or comma to add)"
      >
        <div className="space-y-2">
          <div className="flex gap-2">
            <input
              type="text"
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyDown={handleKeywordInputKeyDown}
              placeholder="Type a keyword and press Enter..."
              className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue bg-white dark:bg-[#3d4176] dark:text-white dark:placeholder-gray-400"
            />
            <button
              type="button"
              onClick={handleKeywordAdd}
              disabled={!keywordInput.trim()}
              className={cn(
                "px-3 py-2 text-sm font-medium rounded-md border transition-colors",
                keywordInput.trim()
                  ? "bg-brand-blue border-brand-blue text-white hover:bg-brand-dark-blue"
                  : "bg-gray-100 dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-400 cursor-not-allowed",
              )}
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
          {formData.keywords.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {formData.keywords.map((keyword) => (
                <KeywordTag
                  key={keyword}
                  keyword={keyword}
                  onRemove={() => handleKeywordRemove(keyword)}
                />
              ))}
            </div>
          )}
          {/* Suggest Related Terms */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSuggestKeywords}
              disabled={
                isSuggestingKeywords ||
                (!keywordInput.trim() &&
                  !formData.name.trim() &&
                  !formData.description.trim())
              }
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border transition-colors",
                isSuggestingKeywords ||
                  (!keywordInput.trim() &&
                    !formData.name.trim() &&
                    !formData.description.trim())
                  ? "bg-gray-100 dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-400 cursor-not-allowed"
                  : "bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-700 text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/40",
              )}
            >
              {isSuggestingKeywords ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Wand2 className="h-3.5 w-3.5" />
              )}
              {isSuggestingKeywords ? "Suggesting..." : "Suggest Related Terms"}
            </button>
          </div>
          {/* Suggested Keywords Chips */}
          {suggestedKeywords.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Click to add suggested terms:
              </p>
              <div className="flex flex-wrap gap-1.5">
                {suggestedKeywords.map((kw) => (
                  <button
                    key={kw}
                    type="button"
                    onClick={() => handleAddSuggestedKeyword(kw)}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border border-dashed border-purple-300 dark:border-purple-600 text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-900/10 hover:bg-purple-100 dark:hover:bg-purple-900/30 transition-colors"
                  >
                    <Plus className="h-3 w-3" />
                    {kw}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </FormSection>

      {/* Active Toggle */}
      <div className="pt-2">
        <ToggleSwitch
          checked={formData.is_active}
          onChange={(checked) =>
            setFormData((prev) => ({ ...prev, is_active: checked }))
          }
          label="Active"
          description="Active workstreams will appear in your feed and receive new cards"
        />
      </div>

      {/* Analyze Now Toggle - Only in CREATE mode */}
      {!isEditMode && (
        <div className="pt-2">
          <ToggleSwitch
            checked={formData.analyze_now}
            onChange={(checked) =>
              setFormData((prev) => ({ ...prev, analyze_now: checked }))
            }
            label="Analyze Now"
            description="Immediately run AI research to find matching cards and discover new technologies based on your keywords"
          />
        </div>
      )}

      {/* Auto-scan on Create Toggle - Only in CREATE mode */}
      {!isEditMode && (
        <div className="pt-2">
          <ToggleSwitch
            checked={formData.auto_scan}
            onChange={(checked) =>
              setFormData((prev) => ({ ...prev, auto_scan: checked }))
            }
            label="Auto-scan for sources on create"
            description={
              formData.pillar_ids.length === 0
                ? "Recommended for topic-driven workstreams without pillars -- automatically discover relevant content sources"
                : "Automatically scan for content sources matching your workstream filters"
            }
          />
        </div>
      )}

      {/* Filter Preview - Match Count */}
      {hasFilters && (
        <div
          className={cn(
            "rounded-lg p-4 border transition-all",
            preview && preview.estimated_count > 0
              ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700"
              : preview && preview.estimated_count === 0
                ? "bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-700"
                : "bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700",
          )}
        >
          <div className="flex items-center gap-3">
            {previewLoading ? (
              <>
                <Loader2 className="h-5 w-5 text-gray-400 animate-spin" />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Searching for matching cards...
                </span>
              </>
            ) : preview ? (
              <>
                {preview.estimated_count > 0 ? (
                  <Search className="h-5 w-5 text-green-600 dark:text-green-400" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                )}
                <div className="flex-1">
                  <div className="flex items-baseline gap-2">
                    <span
                      className={cn(
                        "text-2xl font-bold",
                        preview.estimated_count > 0
                          ? "text-green-700 dark:text-green-300"
                          : "text-amber-700 dark:text-amber-300",
                      )}
                    >
                      ~{preview.estimated_count}
                    </span>
                    <span
                      className={cn(
                        "text-sm",
                        preview.estimated_count > 0
                          ? "text-green-600 dark:text-green-400"
                          : "text-amber-600 dark:text-amber-400",
                      )}
                    >
                      {preview.estimated_count === 1
                        ? "card matches"
                        : "cards match"}{" "}
                      these filters
                    </span>
                  </div>
                  {preview.sample_cards.length > 0 && (
                    <div className="mt-2">
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                        Sample matches:
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {preview.sample_cards.slice(0, 3).map((card) => (
                          <span
                            key={card.id}
                            className="text-xs px-2 py-0.5 rounded bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-600 truncate max-w-[200px]"
                            title={card.name}
                          >
                            {card.name}
                          </span>
                        ))}
                        {preview.estimated_count > 3 && (
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            +{preview.estimated_count - 3} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                  {preview.estimated_count === 0 && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                      Try broadening your filters or adding different keywords
                    </p>
                  )}
                </div>
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5 text-gray-400" />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Add filters to see matching cards
                </span>
              </>
            )}
          </div>
        </div>
      )}

      {/* Validation Error for Filters */}
      {errors.filters && (
        <div className="flex items-start gap-2 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-md">
          <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <p className="text-sm text-amber-800 dark:text-amber-300">
            {errors.filters}
          </p>
        </div>
      )}

      {/* Submit Error */}
      {errors.submit && (
        <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-md">
          <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
          <p className="text-sm text-red-800 dark:text-red-300">
            {errors.submit}
          </p>
        </div>
      )}

      {/* Zero Match Prompt - shown after creation when no existing cards match */}
      {showZeroMatchPrompt && createdWorkstreamId && (
        <div className="rounded-lg p-4 border border-blue-200 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20">
          <div className="flex items-start gap-3">
            <Radar className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <div className="flex-1 space-y-2">
              <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                No existing signals match this topic.
              </p>
              <p className="text-xs text-blue-600 dark:text-blue-400">
                Would you like to discover new content?
              </p>
              <button
                type="button"
                onClick={() => {
                  if (onCreatedWithZeroMatches) {
                    onCreatedWithZeroMatches(createdWorkstreamId);
                  }
                  setShowZeroMatchPrompt(false);
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors"
              >
                <Radar className="h-3.5 w-3.5" />
                Start Discovery Scan
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Form Actions */}
      <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-600">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-[#3d4176] border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-[#4d5186] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-[#2d3166] disabled:opacity-50 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className={cn(
            "inline-flex items-center px-4 py-2 text-sm font-medium text-white rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue dark:focus:ring-offset-[#2d3166] transition-colors",
            isSubmitting
              ? "bg-brand-blue/60 cursor-not-allowed"
              : "bg-brand-blue hover:bg-brand-dark-blue",
          )}
        >
          {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          {isEditMode ? "Save Changes" : "Create Workstream"}
        </button>
      </div>
    </form>
  );
}

export default WorkstreamForm;
