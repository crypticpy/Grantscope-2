/**
 * StepStart - Program Setup (Step 1)
 *
 * Department selector, program description, and grant program templates.
 * Selecting a template applies it and auto-advances to step 2.
 */

import { Plus, Building2, DollarSign, Shield, Home, Leaf } from "lucide-react";
import { cn } from "../../../lib/utils";
import { TemplateCard } from "../TemplateCard";
import { departments } from "../../../data/taxonomy";
import type { WorkstreamTemplate, FormData } from "../../../types/workstream";

// Grant program templates (replaces horizon scanning templates)
const GRANT_TEMPLATES: WorkstreamTemplate[] = [
  {
    id: "federal-grants",
    name: "Federal Grants Monitor",
    description:
      "Track federal grant opportunities from Grants.gov and SAM.gov",
    icon: <Building2 className="h-5 w-5" />,
    color: "blue",
    config: {
      name: "Federal Grants Monitor",
      description:
        "Monitoring federal grant opportunities including NOFOs, cooperative agreements, and formula grants from Grants.gov and SAM.gov.",
      pillar_ids: [],
      goal_ids: [],
      stage_ids: [],
      horizon: "ALL",
      keywords: [
        "federal grant",
        "NOFO",
        "notice of funding",
        "SAM.gov",
        "Grants.gov",
      ],
    },
  },
  {
    id: "infrastructure",
    name: "Infrastructure & Transportation",
    description: "DOT, FEMA, and infrastructure funding opportunities",
    icon: <DollarSign className="h-5 w-5" />,
    color: "amber",
    config: {
      name: "Infrastructure & Transportation Funding",
      description:
        "Tracking DOT, FEMA, and infrastructure funding opportunities for roads, bridges, transit, water systems, and facilities.",
      pillar_ids: ["IN"],
      goal_ids: [],
      stage_ids: [],
      horizon: "ALL",
      keywords: [
        "infrastructure grant",
        "DOT",
        "FEMA",
        "transportation funding",
        "IIJA",
      ],
    },
  },
  {
    id: "public-safety",
    name: "Public Safety & Emergency",
    description:
      "DOJ COPS grants, FEMA preparedness, and public safety funding",
    icon: <Shield className="h-5 w-5" />,
    color: "red",
    config: {
      name: "Public Safety & Emergency Funding",
      description:
        "DOJ COPS grants, FEMA preparedness programs, and other public safety funding for law enforcement, fire services, and emergency response.",
      pillar_ids: ["PS"],
      goal_ids: [],
      stage_ids: [],
      horizon: "ALL",
      keywords: [
        "COPS grant",
        "FEMA preparedness",
        "public safety funding",
        "DOJ grant",
      ],
    },
  },
  {
    id: "housing",
    name: "Housing & Community Development",
    description: "HUD grants, CDBG, HOME, and housing assistance programs",
    icon: <Home className="h-5 w-5" />,
    color: "purple",
    config: {
      name: "Housing & Community Development Grants",
      description:
        "HUD grants, CDBG, HOME program, and housing assistance programs for affordable housing and community development.",
      pillar_ids: ["HD"],
      goal_ids: [],
      stage_ids: [],
      horizon: "ALL",
      keywords: [
        "HUD grant",
        "CDBG",
        "HOME program",
        "affordable housing",
        "housing assistance",
      ],
    },
  },
  {
    id: "environment",
    name: "Environment & Sustainability",
    description: "EPA grants, DOE clean energy, and environmental programs",
    icon: <Leaf className="h-5 w-5" />,
    color: "green",
    config: {
      name: "Environment & Sustainability Grants",
      description:
        "EPA grants, DOE clean energy funding, and environmental programs for climate resilience, conservation, and sustainability.",
      pillar_ids: ["EN"],
      goal_ids: [],
      stage_ids: [],
      horizon: "ALL",
      keywords: [
        "EPA grant",
        "DOE funding",
        "clean energy",
        "environmental grant",
        "IRA funding",
      ],
    },
  },
];

interface StepStartProps {
  formData: FormData;
  onSelectTemplate: (template: WorkstreamTemplate) => void;
  onBuildYourOwn: () => void;
  onDepartmentChange: (departmentId: string) => void;
  onDescriptionChange: (description: string) => void;
  onNameChange: (name: string) => void;
}

export function StepStart({
  formData,
  onSelectTemplate,
  onBuildYourOwn,
  onDepartmentChange,
  onDescriptionChange,
  onNameChange,
}: StepStartProps) {
  // Filter templates based on department category alignment
  const selectedDept = departments.find((d) => d.id === formData.department_id);
  const relevantTemplates = selectedDept?.categoryIds.length
    ? GRANT_TEMPLATES.filter(
        (t) =>
          t.config.pillar_ids.length === 0 ||
          t.config.pillar_ids.some((id) =>
            selectedDept.categoryIds.includes(id),
          ),
      )
    : GRANT_TEMPLATES;

  return (
    <div className="space-y-6">
      {/* Help text */}
      <div className="bg-brand-light-blue/30 dark:bg-brand-blue/10 rounded-lg p-4 border border-brand-blue/20">
        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
          Set up your grant program by selecting your department and describing
          what you are looking for. Choose a template to get started quickly, or
          build a custom program from scratch.
        </p>
      </div>

      {/* Department selector */}
      <div>
        <label
          htmlFor="wizard-department"
          className="block text-sm font-medium text-gray-900 dark:text-white mb-1"
        >
          Department
        </label>
        <select
          id="wizard-department"
          value={formData.department_id}
          onChange={(e) => onDepartmentChange(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue bg-white dark:bg-dark-surface-elevated dark:text-white"
        >
          <option value="">Select your department...</option>
          {departments.map((dept) => (
            <option key={dept.id} value={dept.id}>
              {dept.abbreviation} - {dept.name}
            </option>
          ))}
        </select>
      </div>

      {/* Program name */}
      <div>
        <label
          htmlFor="wizard-program-name"
          className="block text-sm font-medium text-gray-900 dark:text-white mb-1"
        >
          Program Name <span className="text-red-500">*</span>
        </label>
        <input
          id="wizard-program-name"
          type="text"
          value={formData.name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="e.g., FY2026 Federal Infrastructure Grants"
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue bg-white dark:bg-dark-surface-elevated dark:text-white dark:placeholder-gray-400"
        />
      </div>

      {/* Program description */}
      <div>
        <label
          htmlFor="wizard-program-description"
          className="block text-sm font-medium text-gray-900 dark:text-white mb-1"
        >
          Program Description
        </label>
        <textarea
          id="wizard-program-description"
          value={formData.description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          placeholder="Describe the goals and focus areas for this grant program..."
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue bg-white dark:bg-dark-surface-elevated dark:text-white dark:placeholder-gray-400 resize-none"
        />
      </div>

      {/* Template grid */}
      <div>
        <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">
          {selectedDept
            ? `Recommended Templates for ${selectedDept.abbreviation}`
            : "Grant Program Templates"}
        </h4>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {relevantTemplates.map((template) => (
            <TemplateCard
              key={template.id}
              template={template}
              onSelect={onSelectTemplate}
            />
          ))}
        </div>
      </div>

      {/* Divider */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-200 dark:border-gray-700" />
        </div>
        <div className="relative flex justify-center text-xs">
          <span className="bg-white dark:bg-dark-surface px-2 text-gray-500 dark:text-gray-400">
            or
          </span>
        </div>
      </div>

      {/* Build Your Own */}
      <button
        type="button"
        onClick={onBuildYourOwn}
        className={cn(
          "w-full flex items-center justify-center gap-3 p-4 rounded-lg border-2 border-dashed transition-all duration-200",
          "border-gray-300 dark:border-gray-600",
          "hover:border-brand-blue dark:hover:border-brand-blue",
          "hover:bg-brand-light-blue/20 dark:hover:bg-brand-blue/10",
          "focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-1 dark:focus:ring-offset-gray-800",
        )}
      >
        <div className="w-10 h-10 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
          <Plus className="h-5 w-5 text-gray-500 dark:text-gray-400" />
        </div>
        <div className="text-left">
          <div className="font-medium text-sm text-gray-900 dark:text-white">
            Build Custom Program
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            Start from scratch and configure all grant search parameters
          </div>
        </div>
      </button>
    </div>
  );
}

// Export templates for use by WorkstreamForm (edit mode)
export { GRANT_TEMPLATES as WORKSTREAM_TEMPLATES };
