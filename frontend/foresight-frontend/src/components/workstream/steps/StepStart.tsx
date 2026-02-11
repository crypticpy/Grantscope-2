/**
 * StepStart - Template Selection (Step 1)
 *
 * Displays template cards in a 2x3 grid plus a "Build Your Own" option.
 * Selecting a template applies it and auto-advances to step 2.
 */

import { Plus, Sparkles, Search, AlertCircle } from "lucide-react";
import { cn } from "../../../lib/utils";
import { TemplateCard } from "../TemplateCard";
import type { WorkstreamTemplate } from "../../../types/workstream";

// Template definitions (extracted from original WorkstreamForm)
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

interface StepStartProps {
  onSelectTemplate: (template: WorkstreamTemplate) => void;
  onBuildYourOwn: () => void;
}

export function StepStart({
  onSelectTemplate,
  onBuildYourOwn,
}: StepStartProps) {
  return (
    <div className="space-y-6">
      {/* Help text */}
      <div className="bg-brand-light-blue/30 dark:bg-brand-blue/10 rounded-lg p-4 border border-brand-blue/20">
        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
          Choose a template to get started quickly, or build a custom workstream
          from scratch.
        </p>
      </div>

      {/* Template grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {WORKSTREAM_TEMPLATES.map((template) => (
          <TemplateCard
            key={template.id}
            template={template}
            onSelect={onSelectTemplate}
          />
        ))}
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
          "w-full flex items-center justify-center gap-3 p-4 rounded-lg border-2 border-dashed transition-all",
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
            Build Your Own
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            Start with a blank slate and customize everything
          </div>
        </div>
      </button>
    </div>
  );
}

export { WORKSTREAM_TEMPLATES };
