/**
 * Discover Page Types
 *
 * TypeScript interfaces and type definitions for the Discover page.
 * These types support the card grid, filtering, sorting, and search
 * functionality on the main discovery interface.
 *
 * @module pages/Discover/types
 */

import type {
  FullCard,
  DiscoveryMetadata as SharedDiscoveryMetadata,
} from "../../types/card";

/**
 * Card data structure for display on the Discover page.
 * Re-exported from the shared card types for backward compatibility.
 */
export type Card = FullCard;

/**
 * Metadata attached to cards by the discovery pipeline.
 * Re-exported from the shared card types for backward compatibility.
 */
export type DiscoveryMetadata = SharedDiscoveryMetadata;

/**
 * Strategic pillar data structure.
 *
 * Represents one of Austin's strategic framework pillars used for
 * categorizing intelligence cards.
 */
export interface Pillar {
  /** Pillar identifier code (e.g., 'CH', 'MC') */
  id: string;
  /** Human-readable pillar name (e.g., 'Community Health') */
  name: string;
  /** Display color for the pillar badge (hex or Tailwind class) */
  color: string;
}

/**
 * Maturity stage data structure.
 *
 * Represents a stage in the technology maturity lifecycle
 * (Concept through Declining).
 */
export interface Stage {
  /** Stage identifier */
  id: string;
  /** Human-readable stage name (e.g., 'Concept', 'Pilot', 'Scaling') */
  name: string;
  /** Sort position for ordering stages in the lifecycle progression */
  sort_order: number;
}

/**
 * Sort options for card ordering in the Discover grid.
 *
 * Each option maps to a database column and sort direction
 * in the `getSortConfig` utility function.
 */
export type SortOption =
  | "newest"
  | "oldest"
  | "recently_updated"
  | "least_recently_updated"
  | "signal_quality_score";

/**
 * Filter state object used for debounced search and score filtering.
 *
 * All filter values are combined with AND logic when querying cards.
 */
export interface FilterState {
  /** Text search term matched against card name and summary */
  searchTerm: string;
  /** Minimum impact score threshold (0-100) */
  impactMin: number;
  /** Minimum relevance score threshold (0-100) */
  relevanceMin: number;
  /** Minimum novelty score threshold (0-100) */
  noveltyMin: number;
}
