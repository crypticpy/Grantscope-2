/**
 * SourcePreferencesStep Component
 *
 * Step 2 of the Create Signal wizard. Allows users to configure
 * source preferences for their new intelligence signal, including:
 *
 * - Source category toggles (News, Academic, Government, Tech Blogs, RSS)
 * - Source type preference (radio group)
 * - Priority domains (tag input)
 * - Custom RSS feeds (tag input)
 * - Keywords for monitoring (tag input)
 *
 * @module CreateSignal/SourcePreferencesStep
 */

import React, { useState, useCallback } from "react";
import {
  Newspaper,
  GraduationCap,
  Landmark,
  Cpu,
  Rss,
  X,
  Plus,
  Globe,
  Tag,
  Link as LinkIcon,
} from "lucide-react";
import { cn } from "../../lib/utils";

// =============================================================================
// Types
// =============================================================================

export interface SourcePreferences {
  /** Enabled source categories */
  enabled_categories: string[];
  /** Preferred content type */
  preferred_type: string;
  /** Priority domains to weight higher */
  priority_domains: string[];
  /** Custom RSS feed URLs */
  custom_rss_feeds: string[];
  /** Keywords for ongoing monitoring */
  keywords: string[];
}

export interface SourcePreferencesStepProps {
  /** Current source preferences value */
  value: SourcePreferences;
  /** Callback when preferences change */
  onChange: (prefs: SourcePreferences) => void;
}

// =============================================================================
// Constants
// =============================================================================

/** Source category configuration */
interface CategoryConfig {
  id: string;
  label: string;
  icon: React.ElementType;
  subtitle: string;
}

const SOURCE_CATEGORIES: CategoryConfig[] = [
  {
    id: "news",
    label: "News",
    icon: Newspaper,
    subtitle: "Reuters, AP, GCN, GovTech, StateScoop",
  },
  {
    id: "academic",
    label: "Academic",
    icon: GraduationCap,
    subtitle: "arXiv -- AI, ML, Computers & Society",
  },
  {
    id: "government",
    label: "Government",
    icon: Landmark,
    subtitle: ".gov -- GSA, NIST, Census, HUD, DOT, EPA, FCC",
  },
  {
    id: "tech_blog",
    label: "Tech Blogs",
    icon: Cpu,
    subtitle: "TechCrunch, Ars Technica, Wired",
  },
  {
    id: "rss",
    label: "RSS Feeds",
    icon: Rss,
    subtitle: "Custom feeds you configure below",
  },
];

/** Source type preference options */
interface SourceTypeOption {
  value: string;
  label: string;
}

const SOURCE_TYPE_OPTIONS: SourceTypeOption[] = [
  { value: "news", label: "News articles" },
  { value: "blogs", label: "Blog posts" },
  { value: "academic", label: "Academic papers" },
  { value: "federal", label: "Federal/government reports" },
  { value: "pdf", label: "PDF documents" },
];

// =============================================================================
// Sub-components
// =============================================================================

/**
 * Reusable tag input for adding/removing string items (domains, URLs, keywords).
 */
interface TagInputProps {
  label: string;
  items: string[];
  onAdd: (item: string) => void;
  onRemove: (item: string) => void;
  placeholder: string;
  icon: React.ElementType;
  validate?: (value: string) => string | null;
  maxItems?: number;
}

function TagInput({
  label,
  items,
  onAdd,
  onRemove,
  placeholder,
  icon: Icon,
  validate,
  maxItems = 20,
}: TagInputProps) {
  const [inputValue, setInputValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const canAddMore = items.length < maxItems;

  const handleAdd = useCallback(() => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;

    if (validate) {
      const validationError = validate(trimmed);
      if (validationError) {
        setError(validationError);
        return;
      }
    }

    if (items.includes(trimmed)) {
      setError("Already added");
      return;
    }

    if (items.length >= maxItems) {
      setError(`Maximum of ${maxItems} items allowed`);
      return;
    }

    setError(null);
    setInputValue("");
    onAdd(trimmed);
  }, [inputValue, items, maxItems, validate, onAdd]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        handleAdd();
      } else if (e.key === "Escape") {
        setInputValue("");
        setError(null);
      }
    },
    [handleAdd],
  );

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
          {label}
        </label>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {items.length} / {maxItems}
        </span>
      </div>

      {canAddMore && (
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Icon
              className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400"
              aria-hidden="true"
            />
            <input
              type="text"
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value);
                if (error) setError(null);
              }}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              className={cn(
                "w-full pl-8 pr-3 py-2 text-sm rounded-md border",
                "bg-white dark:bg-[#2d3166]",
                "text-gray-900 dark:text-gray-100",
                "placeholder-gray-400 dark:placeholder-gray-500",
                "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent",
                error
                  ? "border-red-300 dark:border-red-700"
                  : "border-gray-300 dark:border-gray-600",
              )}
              aria-label={`Add ${label.toLowerCase()}`}
              aria-invalid={!!error}
            />
          </div>
          <button
            type="button"
            onClick={handleAdd}
            disabled={!inputValue.trim()}
            className={cn(
              "inline-flex items-center gap-1 px-3 py-2 text-sm font-medium rounded-md",
              "bg-brand-blue text-white hover:bg-brand-dark-blue",
              "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "transition-colors duration-150",
            )}
            aria-label={`Add ${label.toLowerCase()}`}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Add
          </button>
        </div>
      )}

      {error && (
        <p className="text-xs text-red-600 dark:text-red-400" role="alert">
          {error}
        </p>
      )}

      {items.length > 0 && (
        <div
          className="flex flex-wrap gap-2"
          role="list"
          aria-label={`Added ${label.toLowerCase()}`}
        >
          {items.map((item) => (
            <div
              key={item}
              role="listitem"
              className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full",
                "bg-gray-100 dark:bg-[#3d4176]",
                "text-xs text-gray-700 dark:text-gray-300",
                "border border-gray-200 dark:border-gray-600",
                "max-w-[300px]",
              )}
            >
              <Icon
                className="h-3 w-3 shrink-0 text-gray-400"
                aria-hidden="true"
              />
              <span className="truncate" title={item}>
                {item}
              </span>
              <button
                type="button"
                onClick={() => onRemove(item)}
                className={cn(
                  "shrink-0 p-0.5 rounded-full",
                  "text-gray-400 hover:text-red-500 dark:hover:text-red-400",
                  "hover:bg-gray-200 dark:hover:bg-gray-600",
                  "focus:outline-none focus:ring-1 focus:ring-red-400",
                  "transition-colors duration-150",
                )}
                aria-label={`Remove ${item}`}
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Component
// =============================================================================

/**
 * SourcePreferencesStep provides the second step of the Create Signal
 * wizard, allowing users to configure which sources should be searched,
 * which domains to prioritize, and keywords for monitoring.
 */
export function SourcePreferencesStep({
  value,
  onChange,
}: SourcePreferencesStepProps) {
  /**
   * Toggle a source category on or off.
   */
  const handleToggleCategory = useCallback(
    (categoryId: string) => {
      const updated = value.enabled_categories.includes(categoryId)
        ? value.enabled_categories.filter((c) => c !== categoryId)
        : [...value.enabled_categories, categoryId];
      onChange({ ...value, enabled_categories: updated });
    },
    [value, onChange],
  );

  /**
   * Set the preferred source type.
   */
  const handleSetPreferredType = useCallback(
    (type: string) => {
      onChange({ ...value, preferred_type: type });
    },
    [value, onChange],
  );

  /**
   * Add a priority domain.
   */
  const handleAddDomain = useCallback(
    (domain: string) => {
      onChange({
        ...value,
        priority_domains: [...value.priority_domains, domain],
      });
    },
    [value, onChange],
  );

  /**
   * Remove a priority domain.
   */
  const handleRemoveDomain = useCallback(
    (domain: string) => {
      onChange({
        ...value,
        priority_domains: value.priority_domains.filter((d) => d !== domain),
      });
    },
    [value, onChange],
  );

  /**
   * Add a custom RSS feed URL.
   */
  const handleAddRssFeed = useCallback(
    (url: string) => {
      onChange({
        ...value,
        custom_rss_feeds: [...value.custom_rss_feeds, url],
      });
    },
    [value, onChange],
  );

  /**
   * Remove a custom RSS feed URL.
   */
  const handleRemoveRssFeed = useCallback(
    (url: string) => {
      onChange({
        ...value,
        custom_rss_feeds: value.custom_rss_feeds.filter((u) => u !== url),
      });
    },
    [value, onChange],
  );

  /**
   * Add a keyword.
   */
  const handleAddKeyword = useCallback(
    (keyword: string) => {
      onChange({
        ...value,
        keywords: [...value.keywords, keyword],
      });
    },
    [value, onChange],
  );

  /**
   * Remove a keyword.
   */
  const handleRemoveKeyword = useCallback(
    (keyword: string) => {
      onChange({
        ...value,
        keywords: value.keywords.filter((k) => k !== keyword),
      });
    },
    [value, onChange],
  );

  /**
   * Validate RSS feed URL format.
   */
  const validateRssUrl = useCallback((url: string): string | null => {
    if (!/^https?:\/\/.+/i.test(url)) {
      return "URL must start with http:// or https://";
    }
    return null;
  }, []);

  return (
    <div className="space-y-6">
      {/* Source Categories */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
          Source Categories
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
          Select which source categories to search for this signal.
        </p>
        <div className="space-y-2">
          {SOURCE_CATEGORIES.map((category) => {
            const Icon = category.icon;
            const isEnabled = value.enabled_categories.includes(category.id);
            return (
              <button
                key={category.id}
                type="button"
                onClick={() => handleToggleCategory(category.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-3 rounded-xl border text-left",
                  "transition-colors duration-150",
                  "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-inset",
                  isEnabled
                    ? "bg-brand-blue/10 border-brand-blue dark:bg-brand-blue/20 dark:border-brand-blue/60"
                    : "bg-white dark:bg-[#2d3166] border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500",
                )}
              >
                <div
                  className={cn(
                    "flex items-center justify-center w-9 h-9 rounded-lg shrink-0",
                    isEnabled
                      ? "bg-brand-blue/20 text-brand-blue dark:bg-brand-blue/30"
                      : "bg-gray-100 dark:bg-[#3d4176] text-gray-500 dark:text-gray-400",
                  )}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <div className="flex-1 min-w-0">
                  <div
                    className={cn(
                      "text-sm font-medium",
                      isEnabled
                        ? "text-brand-blue dark:text-blue-300"
                        : "text-gray-900 dark:text-gray-100",
                    )}
                  >
                    {category.label}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                    {category.subtitle}
                  </div>
                </div>
                {/* Toggle indicator */}
                <div
                  className={cn(
                    "w-10 h-6 rounded-full shrink-0 relative transition-colors duration-150",
                    isEnabled
                      ? "bg-brand-blue"
                      : "bg-gray-300 dark:bg-gray-600",
                  )}
                >
                  <div
                    className={cn(
                      "absolute top-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform duration-150",
                      isEnabled ? "translate-x-[18px]" : "translate-x-0.5",
                    )}
                  />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Source Type Preference */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
          Source Type Preference
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
          Choose which type of content to prioritize in results.
        </p>
        <div
          className="space-y-2"
          role="radiogroup"
          aria-label="Source type preference"
        >
          {SOURCE_TYPE_OPTIONS.map((option) => {
            const isSelected = value.preferred_type === option.value;
            return (
              <label
                key={option.value}
                className={cn(
                  "flex items-center gap-3 px-4 py-2.5 rounded-md border cursor-pointer",
                  "transition-colors duration-150",
                  isSelected
                    ? "bg-brand-blue/10 border-brand-blue dark:bg-brand-blue/20 dark:border-brand-blue/60"
                    : "bg-white dark:bg-[#2d3166] border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500",
                )}
              >
                <input
                  type="radio"
                  name="preferred_type"
                  value={option.value}
                  checked={isSelected}
                  onChange={() => handleSetPreferredType(option.value)}
                  className={cn(
                    "h-4 w-4 border-gray-300 dark:border-gray-600",
                    "text-brand-blue focus:ring-brand-blue",
                  )}
                />
                <span
                  className={cn(
                    "text-sm",
                    isSelected
                      ? "text-brand-blue dark:text-blue-300 font-medium"
                      : "text-gray-700 dark:text-gray-300",
                  )}
                >
                  {option.label}
                </span>
              </label>
            );
          })}
        </div>
      </div>

      {/* Priority Domains */}
      <TagInput
        label="Priority Domains"
        items={value.priority_domains}
        onAdd={handleAddDomain}
        onRemove={handleRemoveDomain}
        placeholder="e.g., gartner.com, mckinsey.com"
        icon={Globe}
        maxItems={20}
      />

      {/* Custom RSS Feeds */}
      <TagInput
        label="Custom RSS Feeds"
        items={value.custom_rss_feeds}
        onAdd={handleAddRssFeed}
        onRemove={handleRemoveRssFeed}
        placeholder="https://example.com/feed.xml"
        icon={LinkIcon}
        validate={validateRssUrl}
        maxItems={10}
      />

      {/* Keywords */}
      <TagInput
        label="Keywords"
        items={value.keywords}
        onAdd={handleAddKeyword}
        onRemove={handleRemoveKeyword}
        placeholder="e.g., smart city, digital twin"
        icon={Tag}
        maxItems={30}
      />
    </div>
  );
}

export default SourcePreferencesStep;
