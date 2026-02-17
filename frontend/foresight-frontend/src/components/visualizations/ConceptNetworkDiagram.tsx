/**
 * ConceptNetworkDiagram Component
 *
 * Displays an interactive network graph showing relationships between cards
 * using React Flow. Cards are represented as nodes with horizon-based coloring,
 * and relationships are shown as labeled edges with configurable thickness.
 *
 * Features:
 * - Interactive pan and zoom
 * - Clickable nodes that navigate to card detail
 * - Horizon-based color coding (H1=green, H2=amber, H3=purple)
 * - Edge labels showing relationship type
 * - Edge thickness based on relationship strength
 * - Empty state for no related cards
 * - Auto-layout for node positioning
 */

import { useMemo, useCallback, memo } from "react";
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  BackgroundVariant,
  NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { GitBranch, ExternalLink, AlertCircle } from "lucide-react";
import { cn } from "../../lib/utils";
import type { RelatedCard } from "../../lib/discovery-api";

// ============================================================================
// Type Definitions
// ============================================================================

export interface ConceptNetworkDiagramProps {
  /** ID of the source/central card */
  sourceCardId: string;
  /** Name of the source card (displayed in center) */
  sourceCardName: string;
  /** Optional summary of the source card */
  sourceCardSummary?: string | null;
  /** Horizon of the source card */
  sourceCardHorizon?: "H1" | "H2" | "H3" | null;
  /** Related cards data */
  relatedCards: RelatedCard[];
  /** Height of the diagram container */
  height?: number;
  /** Additional className for container */
  className?: string;
  /** Loading state */
  loading?: boolean;
  /** Error message */
  error?: string | null;
  /** Retry callback for error state */
  onRetry?: () => void;
  /** Callback when a card node is clicked */
  onCardClick?: (cardId: string, cardSlug: string) => void;
  /** Whether to show the minimap */
  showMinimap?: boolean;
  /** Whether to show background */
  showBackground?: boolean;
  /** Title for the section */
  title?: string;
}

/** Node data structure for React Flow */
interface CardNodeData extends Record<string, unknown> {
  id: string;
  name: string;
  slug: string;
  summary?: string | null;
  horizon?: "H1" | "H2" | "H3" | null;
  relationshipType?: string | null;
  relationshipStrength?: number | null;
  isSource: boolean;
  onCardClick?: (cardId: string, cardSlug: string) => void;
}

// ============================================================================
// Horizon Color Configuration
// ============================================================================

/**
 * Get color classes based on horizon alignment
 * Matches StageBadge.tsx patterns for consistency
 */
function getHorizonColors(horizon?: "H1" | "H2" | "H3" | null): {
  bg: string;
  border: string;
  text: string;
  fill: string;
} {
  const colorMap: Record<
    string,
    { bg: string; border: string; text: string; fill: string }
  > = {
    H1: {
      bg: "bg-green-50 dark:bg-green-900/30",
      border: "border-green-400 dark:border-green-500",
      text: "text-green-800 dark:text-green-200",
      fill: "#22c55e",
    },
    H2: {
      bg: "bg-amber-50 dark:bg-amber-900/30",
      border: "border-amber-400 dark:border-amber-500",
      text: "text-amber-800 dark:text-amber-200",
      fill: "#f59e0b",
    },
    H3: {
      bg: "bg-purple-50 dark:bg-purple-900/30",
      border: "border-purple-400 dark:border-purple-500",
      text: "text-purple-800 dark:text-purple-200",
      fill: "#a855f7",
    },
  };

  return (
    colorMap[horizon || ""] || {
      bg: "bg-gray-50 dark:bg-dark-surface",
      border: "border-gray-300 dark:border-gray-600",
      text: "text-gray-800 dark:text-gray-200",
      fill: "#6b7280",
    }
  );
}

/**
 * Format relationship type for display
 */
function formatRelationshipType(type?: string | null): string {
  if (!type) return "";
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ============================================================================
// Custom Node Component
// ============================================================================

/** Custom card node component for React Flow */
const CardNode = memo(({ data }: NodeProps<Node<CardNodeData>>) => {
  const colors = getHorizonColors(data.horizon);
  const isSource = data.isSource;

  const handleClick = useCallback(() => {
    if (data.onCardClick && data.id && data.slug) {
      data.onCardClick(data.id, data.slug);
    }
  }, [data]);

  return (
    <>
      {/* Connection handles */}
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2 !h-2 !bg-gray-400 dark:!bg-gray-500 !border-none"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2 !h-2 !bg-gray-400 dark:!bg-gray-500 !border-none"
      />
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2 !h-2 !bg-gray-400 dark:!bg-gray-500 !border-none"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!w-2 !h-2 !bg-gray-400 dark:!bg-gray-500 !border-none"
      />

      {/* Card node content */}
      <div
        onClick={handleClick}
        className={cn(
          "px-4 py-3 rounded-lg border-2 shadow-md cursor-pointer transition-all duration-200",
          "hover:shadow-lg hover:scale-[1.02]",
          "min-w-[180px] max-w-[240px]",
          colors.bg,
          colors.border,
          isSource && "ring-2 ring-offset-2 ring-blue-500 dark:ring-blue-400",
        )}
        role="button"
        tabIndex={0}
        aria-label={`View ${data.name} opportunity details`}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            handleClick();
          }
        }}
      >
        {/* Source indicator */}
        {isSource && (
          <div className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center">
            <span className="text-white text-xs font-bold">C</span>
          </div>
        )}

        {/* Card name */}
        <div
          className={cn("font-semibold text-sm truncate", colors.text)}
          title={data.name}
        >
          {data.name}
        </div>

        {/* Summary preview */}
        {data.summary && (
          <div
            className="text-xs text-gray-600 dark:text-gray-400 mt-1 line-clamp-2"
            title={data.summary}
          >
            {data.summary}
          </div>
        )}

        {/* Footer with horizon badge and link icon */}
        <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
          {data.horizon && (
            <span
              className={cn(
                "px-1.5 py-0.5 rounded text-[10px] font-medium",
                colors.bg,
                colors.text,
              )}
            >
              {data.horizon}
            </span>
          )}
          {!isSource && data.relationshipType && (
            <span className="text-[10px] text-gray-500 dark:text-gray-400 truncate max-w-[80px]">
              {formatRelationshipType(data.relationshipType)}
            </span>
          )}
          <ExternalLink className="h-3 w-3 text-gray-400 dark:text-gray-500 ml-auto flex-shrink-0" />
        </div>
      </div>
    </>
  );
});

CardNode.displayName = "CardNode";

// Register custom node types
const nodeTypes = {
  cardNode: CardNode,
};

// ============================================================================
// Layout Utilities
// ============================================================================

/**
 * Calculate radial layout positions for nodes around a center point
 */
function calculateRadialLayout(
  centerX: number,
  centerY: number,
  radius: number,
  nodeCount: number,
): { x: number; y: number }[] {
  if (nodeCount === 0) return [];
  if (nodeCount === 1) return [{ x: centerX + radius, y: centerY }];

  const positions: { x: number; y: number }[] = [];
  const angleStep = (2 * Math.PI) / nodeCount;
  // Start from top and go clockwise
  const startAngle = -Math.PI / 2;

  for (let i = 0; i < nodeCount; i++) {
    const angle = startAngle + i * angleStep;
    positions.push({
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    });
  }

  return positions;
}

/**
 * Calculate edge stroke width based on relationship strength
 */
function getEdgeStrokeWidth(strength?: number | null): number {
  if (strength === null || strength === undefined) return 2;
  // Map strength (0-1) to stroke width (1-4)
  return 1 + strength * 3;
}

// ============================================================================
// Data Transformation
// ============================================================================

/**
 * Transform related cards data into React Flow nodes and edges
 */
function transformToGraphData(
  sourceCardId: string,
  sourceCardName: string,
  sourceCardSummary: string | null | undefined,
  sourceCardHorizon: "H1" | "H2" | "H3" | null | undefined,
  relatedCards: RelatedCard[],
  onCardClick?: (cardId: string, cardSlug: string) => void,
): { nodes: Node<CardNodeData>[]; edges: Edge[] } {
  const centerX = 400;
  const centerY = 300;
  const radius = 250;

  // Calculate positions for related cards
  const positions = calculateRadialLayout(
    centerX,
    centerY,
    radius,
    relatedCards.length,
  );

  // Create source node (center)
  const sourceNode: Node<CardNodeData> = {
    id: sourceCardId,
    type: "cardNode",
    position: { x: centerX - 100, y: centerY - 50 },
    data: {
      id: sourceCardId,
      name: sourceCardName,
      slug: "", // Source card already on this page
      summary: sourceCardSummary,
      horizon: sourceCardHorizon,
      isSource: true,
      onCardClick: undefined, // Don't navigate to self
    },
    draggable: true,
  };

  // Create related card nodes
  const relatedNodes: Node<CardNodeData>[] = relatedCards.map(
    (card, index) => ({
      id: card.id,
      type: "cardNode",
      position: positions[index]
        ? { x: positions[index].x - 100, y: positions[index].y - 50 }
        : { x: 0, y: 0 },
      data: {
        id: card.id,
        name: card.name,
        slug: card.slug,
        summary: card.summary,
        horizon: card.horizon,
        relationshipType: card.relationship_type,
        relationshipStrength: card.relationship_strength,
        isSource: false,
        onCardClick,
      },
      draggable: true,
    }),
  );

  // Create edges connecting source to related cards
  const edges: Edge[] = relatedCards.map((card) => {
    const colors = getHorizonColors(card.horizon);
    return {
      id: `e-${sourceCardId}-${card.id}`,
      source: sourceCardId,
      target: card.id,
      type: "default",
      animated: false,
      label: formatRelationshipType(card.relationship_type),
      labelStyle: { fontSize: 10, fill: "#6b7280" },
      labelBgStyle: {
        fill: "white",
        fillOpacity: 0.8,
      },
      style: {
        stroke: colors.fill,
        strokeWidth: getEdgeStrokeWidth(card.relationship_strength),
      },
    };
  });

  return {
    nodes: [sourceNode, ...relatedNodes],
    edges,
  };
}

// ============================================================================
// State Components
// ============================================================================

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-center px-4">
      <GitBranch className="h-12 w-12 text-gray-300 dark:text-gray-600 mb-3" />
      <p className="text-gray-500 dark:text-gray-400 text-sm font-medium">
        No related trends found
      </p>
      <p className="text-gray-400 dark:text-gray-500 text-xs mt-1 max-w-[250px]">
        Related cards will appear here once relationships are established
      </p>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[300px]">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue mb-3" />
      <p className="text-gray-500 dark:text-gray-400 text-sm">
        Loading network...
      </p>
    </div>
  );
}

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-center px-4">
      <AlertCircle className="h-12 w-12 text-red-400 mb-3" />
      <p className="text-red-600 dark:text-red-400 text-sm font-medium mb-2">
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-brand-blue hover:text-brand-dark-blue text-sm underline"
        >
          Try again
        </button>
      )}
    </div>
  );
}

// ============================================================================
// Minimap Color Function
// ============================================================================

function minimapNodeColor(node: Node): string {
  if (node.data?.isSource) return "#3b82f6";
  const horizon = node.data?.horizon;
  if (horizon === "H1") return "#22c55e";
  if (horizon === "H2") return "#f59e0b";
  if (horizon === "H3") return "#a855f7";
  return "#6b7280";
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ConceptNetworkDiagram - Visualize card relationships as an interactive network
 */
export function ConceptNetworkDiagram({
  sourceCardId,
  sourceCardName,
  sourceCardSummary,
  sourceCardHorizon,
  relatedCards,
  height = 500,
  className,
  loading = false,
  error = null,
  onRetry,
  onCardClick,
  showMinimap = true,
  showBackground = true,
  title = "Related Trends Network",
}: ConceptNetworkDiagramProps) {
  // Transform data to React Flow format
  const { initialNodes, initialEdges } = useMemo(() => {
    const { nodes, edges } = transformToGraphData(
      sourceCardId,
      sourceCardName,
      sourceCardSummary,
      sourceCardHorizon,
      relatedCards,
      onCardClick,
    );
    return { initialNodes: nodes, initialEdges: edges };
  }, [
    sourceCardId,
    sourceCardName,
    sourceCardSummary,
    sourceCardHorizon,
    relatedCards,
    onCardClick,
  ]);

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update nodes/edges when data changes
  useMemo(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  // Show loading state
  if (loading) {
    return (
      <div
        className={cn(
          "bg-white dark:bg-dark-surface rounded-lg shadow p-6",
          className,
        )}
      >
        {title && (
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-brand-blue" />
            {title}
          </h3>
        )}
        <div style={{ height }}>
          <LoadingState />
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div
        className={cn(
          "bg-white dark:bg-dark-surface rounded-lg shadow p-6",
          className,
        )}
      >
        {title && (
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-brand-blue" />
            {title}
          </h3>
        )}
        <div style={{ height }}>
          <ErrorState message={error} onRetry={onRetry} />
        </div>
      </div>
    );
  }

  // Show empty state if no related cards
  if (relatedCards.length === 0) {
    return (
      <div
        className={cn(
          "bg-white dark:bg-dark-surface rounded-lg shadow p-6",
          className,
        )}
      >
        {title && (
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-brand-blue" />
            {title}
          </h3>
        )}
        <div style={{ height }}>
          <EmptyState />
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "bg-white dark:bg-dark-surface rounded-lg shadow p-6",
        className,
      )}
    >
      {title && (
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <GitBranch className="h-5 w-5 text-brand-blue" />
          {title}
        </h3>
      )}

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 mb-4 text-xs text-gray-500 dark:text-gray-400">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-blue-500" />
          <span>Current Signal</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-green-500" />
          <span>H1 (Mainstream)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-amber-500" />
          <span>H2 (Transitional)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-purple-500" />
          <span>H3 (Transformative)</span>
        </div>
      </div>

      {/* React Flow container */}
      <div
        style={{ height }}
        className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden"
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.2}
          maxZoom={2}
          attributionPosition="bottom-right"
          proOptions={{ hideAttribution: true }}
        >
          {showBackground && (
            <Background
              variant={BackgroundVariant.Dots}
              gap={12}
              size={1}
              className="bg-gray-50 dark:bg-gray-900"
            />
          )}
          <Controls
            showZoom={true}
            showFitView={true}
            showInteractive={false}
            className="!bg-white dark:!bg-gray-800 !border-gray-200 dark:!border-gray-700 !shadow-md"
          />
          {showMinimap && (
            <MiniMap
              nodeColor={minimapNodeColor}
              maskColor="rgba(0, 0, 0, 0.1)"
              className="!bg-white dark:!bg-gray-800 !border-gray-200 dark:!border-gray-700 !shadow-md"
              pannable
              zoomable
            />
          )}
        </ReactFlow>
      </div>

      {/* Footer with card count */}
      <div className="flex items-center justify-between mt-3 text-xs text-gray-500 dark:text-gray-400">
        <span>
          {relatedCards.length} related trend
          {relatedCards.length !== 1 ? "s" : ""}
        </span>
        <span>Click a signal to view details</span>
      </div>
    </div>
  );
}

export default ConceptNetworkDiagram;
