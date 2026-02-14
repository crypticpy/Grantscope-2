/**
 * KeyEntitiesPanel Component
 *
 * Displays extracted entities for a card in the Overview tab sidebar.
 * Fetches entities from the backend API on mount, groups them by type
 * (technology, organization, concept, person, location), and renders
 * each group as a labeled section with color-coded chips.
 *
 * Follows the same panel styling conventions as ActivityStatsPanel and
 * ImpactMetricsPanel (white card with shadow, rounded corners, consistent spacing).
 *
 * @module CardDetail/tabs/OverviewTab/KeyEntitiesPanel
 */

import React, { useState, useEffect, useCallback } from "react";
import { Cpu, Building2, User, MapPin, Lightbulb, Loader2 } from "lucide-react";
import { cn } from "../../../../lib/utils";
import { supabase } from "../../../../App";
import { API_BASE_URL } from "../../utils";

// =============================================================================
// Types
// =============================================================================

/**
 * Props for the KeyEntitiesPanel component.
 */
export interface KeyEntitiesPanelProps {
  /** UUID of the card whose entities to display */
  cardId: string;

  /** Optional additional CSS class names for the outer container */
  className?: string;
}

/**
 * Entity record returned from the backend API.
 */
interface Entity {
  /** Unique entity identifier */
  id: string;
  /** Display name of the entity */
  name: string;
  /** Type classification of the entity */
  entity_type: EntityType;
  /** Relevance or confidence score (0-1) */
  relevance_score?: number | null;
}

/**
 * Supported entity type classifications.
 */
type EntityType =
  | "technology"
  | "organization"
  | "concept"
  | "person"
  | "location";

// =============================================================================
// Configuration
// =============================================================================

/**
 * Metadata for each entity type including icon, label, and color classes.
 */
interface EntityTypeMeta {
  /** Human-readable label for the entity type */
  label: string;
  /** Lucide icon component for the entity type */
  icon: React.FC<{ className?: string }>;
  /** Tailwind background class for the chip */
  chipBg: string;
  /** Tailwind text color class for the chip */
  chipText: string;
  /** Tailwind background class for the chip in dark mode */
  chipBgDark: string;
  /** Tailwind text color class for the chip in dark mode */
  chipTextDark: string;
}

const ENTITY_TYPE_META: Record<EntityType, EntityTypeMeta> = {
  technology: {
    label: "Technologies",
    icon: Cpu,
    chipBg: "bg-blue-50",
    chipText: "text-blue-700",
    chipBgDark: "dark:bg-blue-900/30",
    chipTextDark: "dark:text-blue-300",
  },
  organization: {
    label: "Organizations",
    icon: Building2,
    chipBg: "bg-emerald-50",
    chipText: "text-emerald-700",
    chipBgDark: "dark:bg-emerald-900/30",
    chipTextDark: "dark:text-emerald-300",
  },
  person: {
    label: "People",
    icon: User,
    chipBg: "bg-violet-50",
    chipText: "text-violet-700",
    chipBgDark: "dark:bg-violet-900/30",
    chipTextDark: "dark:text-violet-300",
  },
  location: {
    label: "Locations",
    icon: MapPin,
    chipBg: "bg-amber-50",
    chipText: "text-amber-700",
    chipBgDark: "dark:bg-amber-900/30",
    chipTextDark: "dark:text-amber-300",
  },
  concept: {
    label: "Concepts",
    icon: Lightbulb,
    chipBg: "bg-gray-100",
    chipText: "text-gray-600",
    chipBgDark: "dark:bg-gray-800",
    chipTextDark: "dark:text-gray-300",
  },
};

/**
 * Display order for entity type groups.
 */
const ENTITY_TYPE_ORDER: EntityType[] = [
  "technology",
  "organization",
  "concept",
  "person",
  "location",
];

// =============================================================================
// Component
// =============================================================================

/**
 * KeyEntitiesPanel fetches and displays extracted entities for a card,
 * grouped by entity type with color-coded chips.
 *
 * @example
 * ```tsx
 * <KeyEntitiesPanel cardId={card.id} />
 * ```
 *
 * @example
 * ```tsx
 * <KeyEntitiesPanel cardId={card.id} className="mt-4" />
 * ```
 */
export const KeyEntitiesPanel: React.FC<KeyEntitiesPanelProps> = ({
  cardId,
  className,
}) => {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Data Fetching
  // ---------------------------------------------------------------------------

  const fetchEntities = useCallback(async () => {
    try {
      setError(null);
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) {
        setError("Not authenticated");
        setLoading(false);
        return;
      }

      const response = await fetch(
        `${API_BASE_URL}/api/v1/cards/${cardId}/entities`,
        {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.access_token}`,
          },
        },
      );

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({ message: "Request failed" }));
        throw new Error(errorData.message || `API error: ${response.status}`);
      }

      const data = await response.json();
      // The API may return { entities: [...] } or an array directly
      const entityList = Array.isArray(data) ? data : (data.entities ?? []);
      setEntities(entityList);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load entities");
    } finally {
      setLoading(false);
    }
  }, [cardId]);

  useEffect(() => {
    fetchEntities();
  }, [fetchEntities]);

  // ---------------------------------------------------------------------------
  // Group entities by type
  // ---------------------------------------------------------------------------

  const groupedEntities = ENTITY_TYPE_ORDER.reduce<
    Record<EntityType, Entity[]>
  >(
    (acc, type) => {
      acc[type] = entities.filter((e) => e.entity_type === type);
      return acc;
    },
    {
      technology: [],
      organization: [],
      concept: [],
      person: [],
      location: [],
    },
  );

  // ---------------------------------------------------------------------------
  // Render: Loading State
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div
        className={cn(
          "bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6",
          className,
        )}
      >
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Key Entities
        </h3>
        <div className="flex items-center justify-center py-6">
          <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
          <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">
            Loading entities...
          </span>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Error State
  // ---------------------------------------------------------------------------

  if (error) {
    return (
      <div
        className={cn(
          "bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6",
          className,
        )}
      >
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Key Entities
        </h3>
        <p className="text-sm text-red-500 dark:text-red-400">{error}</p>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Empty State
  // ---------------------------------------------------------------------------

  if (entities.length === 0) {
    return (
      <div
        className={cn(
          "bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6",
          className,
        )}
      >
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Key Entities
        </h3>
        <p className="text-sm text-gray-400 dark:text-gray-500">
          No entities extracted yet
        </p>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Main Panel
  // ---------------------------------------------------------------------------

  return (
    <div
      className={cn(
        "bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6",
        className,
      )}
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Key Entities
      </h3>

      <div className="space-y-4">
        {ENTITY_TYPE_ORDER.map((type) => {
          const group = groupedEntities[type];
          if (group.length === 0) return null;

          const meta = ENTITY_TYPE_META[type];
          const Icon = meta.icon;

          return (
            <div key={type}>
              {/* Section label with icon */}
              <div className="flex items-center gap-1.5 mb-2">
                <Icon className="h-3.5 w-3.5 text-gray-500 dark:text-gray-400" />
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  {meta.label}
                </span>
              </div>

              {/* Entity chips */}
              <div className="flex flex-wrap gap-1.5">
                {group.map((entity) => (
                  <span
                    key={entity.id}
                    className={cn(
                      "inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium",
                      meta.chipBg,
                      meta.chipText,
                      meta.chipBgDark,
                      meta.chipTextDark,
                    )}
                  >
                    {entity.name}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default KeyEntitiesPanel;
