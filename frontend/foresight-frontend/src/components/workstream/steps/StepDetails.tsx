/**
 * StepDetails - Grant Interests (Step 2)
 *
 * Grant category multi-select, funding range inputs, and grant type checkboxes.
 */

import { cn } from "../../../lib/utils";
import { grantCategories } from "../../../data/taxonomy";
import type { FormData } from "../../../types/workstream";

const GRANT_TYPES = [
  {
    id: "federal",
    label: "Federal",
    description: "Grants.gov, SAM.gov, agency NOFOs",
  },
  { id: "state", label: "State", description: "Texas state agency funding" },
  {
    id: "foundation",
    label: "Foundation",
    description: "Private and community foundations",
  },
  { id: "local", label: "Local", description: "County and regional programs" },
  { id: "other", label: "Other", description: "Corporate, pass-through, etc." },
];

// Map grant category icon names to simple display
const CATEGORY_ICONS: Record<string, string> = {
  Heart: "H",
  Shield: "S",
  Home: "Ho",
  Construction: "I",
  Leaf: "E",
  Briefcase: "C",
  Cpu: "T",
  GraduationCap: "Ed",
};

interface StepDetailsProps {
  formData: FormData;
  onCategoryToggle: (categoryCode: string) => void;
  onGrantTypeToggle: (grantType: string) => void;
  onBudgetMinChange: (value: number | null) => void;
  onBudgetMaxChange: (value: number | null) => void;
}

export function StepDetails({
  formData,
  onCategoryToggle,
  onGrantTypeToggle,
  onBudgetMinChange,
  onBudgetMaxChange,
}: StepDetailsProps) {
  const formatCurrency = (value: number | null): string => {
    if (value === null || value === 0) return "";
    return value.toLocaleString();
  };

  const parseCurrency = (input: string): number | null => {
    const cleaned = input.replace(/[^0-9]/g, "");
    if (!cleaned) return null;
    return parseInt(cleaned, 10);
  };

  return (
    <div className="space-y-8">
      {/* Inline help */}
      <div className="bg-brand-light-blue/30 dark:bg-brand-blue/10 rounded-lg p-4 border border-brand-blue/20">
        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
          Select the grant categories your department is interested in, set your
          target funding range, and choose which grant types to monitor.
        </p>
      </div>

      {/* Section 1: Grant Categories */}
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
            Grant Categories
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Select the focus areas for your grant search. Choose multiple
            categories to broaden your results.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {grantCategories.map((category) => {
            const isSelected = formData.category_ids.includes(category.code);
            return (
              <button
                key={category.code}
                type="button"
                onClick={() => onCategoryToggle(category.code)}
                className={cn(
                  "flex items-start gap-3 p-3 rounded-lg border text-left transition-all duration-200",
                  isSelected
                    ? "border-brand-blue bg-brand-light-blue/30 dark:bg-brand-blue/10 ring-1 ring-brand-blue/30"
                    : "border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                )}
                aria-pressed={isSelected}
              >
                <div
                  className={cn(
                    "w-8 h-8 rounded-md flex items-center justify-center text-xs font-bold flex-shrink-0",
                    isSelected
                      ? "text-white"
                      : "text-gray-600 dark:text-gray-300",
                  )}
                  style={{
                    backgroundColor: isSelected
                      ? category.color
                      : category.colorLight,
                  }}
                >
                  {CATEGORY_ICONS[category.icon] || category.code}
                </div>
                <div className="min-w-0">
                  <div
                    className={cn(
                      "text-sm font-medium",
                      isSelected
                        ? "text-brand-dark-blue dark:text-brand-light-blue"
                        : "text-gray-900 dark:text-white",
                    )}
                  >
                    {category.name}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 line-clamp-1">
                    {category.description}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Section 2: Funding Range */}
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
            Funding Range
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Set the target dollar range for grant opportunities. Leave blank for
            no restriction.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="wizard-budget-min"
              className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Minimum ($)
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">
                $
              </span>
              <input
                id="wizard-budget-min"
                type="text"
                inputMode="numeric"
                value={formatCurrency(formData.budget_range_min)}
                onChange={(e) =>
                  onBudgetMinChange(parseCurrency(e.target.value))
                }
                placeholder="0"
                className="w-full pl-7 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue bg-white dark:bg-dark-surface-elevated dark:text-white dark:placeholder-gray-400"
              />
            </div>
          </div>
          <div>
            <label
              htmlFor="wizard-budget-max"
              className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1"
            >
              Maximum ($)
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">
                $
              </span>
              <input
                id="wizard-budget-max"
                type="text"
                inputMode="numeric"
                value={formatCurrency(formData.budget_range_max)}
                onChange={(e) =>
                  onBudgetMaxChange(parseCurrency(e.target.value))
                }
                placeholder="No limit"
                className="w-full pl-7 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue bg-white dark:bg-dark-surface-elevated dark:text-white dark:placeholder-gray-400"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Section 3: Grant Types */}
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
            Grant Types
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Select which types of funding sources to monitor.
          </p>
        </div>

        <div className="space-y-2">
          {GRANT_TYPES.map((grantType) => {
            const isChecked = formData.grant_types.includes(grantType.id);
            return (
              <label
                key={grantType.id}
                className={cn(
                  "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all duration-200",
                  isChecked
                    ? "border-brand-blue bg-brand-light-blue/20 dark:bg-brand-blue/10"
                    : "border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-dark-surface-hover",
                )}
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => onGrantTypeToggle(grantType.id)}
                  className="h-4 w-4 text-brand-blue border-gray-300 dark:border-gray-500 rounded focus:ring-brand-blue"
                />
                <div>
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {grantType.label}
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                    {grantType.description}
                  </span>
                </div>
              </label>
            );
          })}
        </div>
      </div>
    </div>
  );
}
