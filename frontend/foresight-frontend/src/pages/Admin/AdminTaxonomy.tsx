/**
 * AdminTaxonomy Page
 *
 * Tabbed interface for managing all taxonomy types:
 * Pillars, Goals, Departments, Priorities, Categories, Anchors, Stages.
 *
 * Supports inline add/edit and delete with confirmation for types that have
 * backend CRUD endpoints (pillars, goals). Other types are read-only until
 * backend endpoints are added.
 *
 * @module pages/Admin/AdminTaxonomy
 */

import { useState, useEffect, useCallback } from "react";
import {
  Tags,
  Plus,
  Pencil,
  Trash2,
  Check,
  X,
  Loader2,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import {
  fetchTaxonomy,
  createPillar,
  updatePillar,
  deletePillar,
  createGoal,
  updateGoal,
  deleteGoal,
} from "../../lib/admin-api";
import type {
  TaxonomyData,
  TaxonomyItem,
  TaxonomyGoal,
} from "../../lib/admin-api";

// ============================================================================
// Types
// ============================================================================

type TaxonomyTab =
  | "pillars"
  | "goals"
  | "departments"
  | "priorities"
  | "categories"
  | "anchors"
  | "stages";

interface TabConfig {
  id: TaxonomyTab;
  label: string;
  description: string;
  editable: boolean;
}

interface EditingRow {
  id: string | null; // null = new item
  fields: Record<string, string>;
}

// ============================================================================
// Constants
// ============================================================================

const TABS: TabConfig[] = [
  {
    id: "pillars",
    label: "Pillars",
    description: "Top-level strategic alignment categories",
    editable: true,
  },
  {
    id: "goals",
    label: "Goals",
    description: "Strategic goals within each pillar",
    editable: true,
  },
  {
    id: "departments",
    label: "Departments",
    description: "City of Austin departments",
    editable: false,
  },
  {
    id: "priorities",
    label: "Priorities",
    description: "CMO Top 25 priorities",
    editable: false,
  },
  {
    id: "categories",
    label: "Categories",
    description: "Grant funding categories",
    editable: false,
  },
  {
    id: "anchors",
    label: "Anchors",
    description: "Cross-cutting thematic anchors",
    editable: false,
  },
  {
    id: "stages",
    label: "Stages",
    description: "Maturity lifecycle stages for signals",
    editable: false,
  },
];

// ============================================================================
// Helpers
// ============================================================================

function truncate(text: string | undefined | null, maxLen: number): string {
  if (!text) return "";
  return text.length > maxLen ? text.slice(0, maxLen) + "..." : text;
}

// ============================================================================
// Sub-Components
// ============================================================================

/** Color swatch badge */
function ColorSwatch({ color }: { color?: string | null }) {
  if (!color) return <span className="text-gray-400 text-xs">--</span>;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="w-4 h-4 rounded border border-gray-200 dark:border-gray-600 flex-shrink-0"
        style={{ backgroundColor: color }}
      />
      <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
        {color}
      </span>
    </span>
  );
}

/** Success/error toast banner */
function Toast({
  message,
  type,
  onDismiss,
}: {
  message: string;
  type: "success" | "error";
  onDismiss: () => void;
}) {
  useEffect(() => {
    if (type === "success") {
      const t = setTimeout(onDismiss, 3000);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [type, onDismiss]);

  const isSuccess = type === "success";
  return (
    <div
      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm ${
        isSuccess
          ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800/50"
          : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800/50"
      }`}
    >
      {isSuccess ? (
        <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
      ) : (
        <AlertCircle className="w-4 h-4 flex-shrink-0" />
      )}
      <span className="flex-1">{message}</span>
      <button
        onClick={onDismiss}
        className="p-0.5 rounded hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

/** Skeleton loading rows */
function LoadingSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse flex items-center gap-4 px-4 py-3 border-b border-gray-100 dark:border-gray-800 last:border-0"
        >
          <div className="h-4 w-4 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="flex-1" />
          <div className="h-4 w-48 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-6 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Inline Edit Row for Pillars
// ============================================================================

function PillarEditRow({
  editing,
  onSave,
  onCancel,
  saving,
}: {
  editing: EditingRow;
  onSave: (fields: Record<string, string>) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [fields, setFields] = useState(editing.fields);
  const set = (key: string, value: string) =>
    setFields((prev) => ({ ...prev, [key]: value }));

  return (
    <tr className="bg-brand-blue/5 dark:bg-brand-blue/10">
      <td className="px-4 py-2">
        <input
          type="text"
          value={fields.name || ""}
          onChange={(e) => set("name", e.target.value)}
          placeholder="Pillar name"
          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
          autoFocus
        />
      </td>
      <td className="px-4 py-2">
        <input
          type="text"
          value={fields.code || ""}
          onChange={(e) => set("code", e.target.value)}
          placeholder="e.g. CH"
          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
        />
      </td>
      <td className="px-4 py-2">
        <input
          type="text"
          value={fields.color || ""}
          onChange={(e) => set("color", e.target.value)}
          placeholder="#44499C"
          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
        />
      </td>
      <td className="px-4 py-2">
        <input
          type="text"
          value={fields.description || ""}
          onChange={(e) => set("description", e.target.value)}
          placeholder="Description"
          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
        />
      </td>
      <td className="px-4 py-2 text-right">
        <div className="flex items-center justify-end gap-1">
          <button
            onClick={() => onSave(fields)}
            disabled={saving || !fields.name?.trim()}
            className="p-1.5 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors disabled:opacity-50"
            title="Save"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Check className="w-4 h-4" />
            )}
          </button>
          <button
            onClick={onCancel}
            disabled={saving}
            className="p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
            title="Cancel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </td>
    </tr>
  );
}

// ============================================================================
// Inline Edit Row for Goals
// ============================================================================

function GoalEditRow({
  editing,
  pillars,
  onSave,
  onCancel,
  saving,
}: {
  editing: EditingRow;
  pillars: TaxonomyItem[];
  onSave: (fields: Record<string, string>) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [fields, setFields] = useState(editing.fields);
  const set = (key: string, value: string) =>
    setFields((prev) => ({ ...prev, [key]: value }));

  return (
    <tr className="bg-brand-blue/5 dark:bg-brand-blue/10">
      <td className="px-4 py-2">
        <select
          value={fields.pillar_id || ""}
          onChange={(e) => set("pillar_id", e.target.value)}
          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
        >
          <option value="">Select pillar...</option>
          {pillars.map((p) => (
            <option key={p.id} value={p.id}>
              {p.code || p.name} - {p.name}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-2">
        <input
          type="text"
          value={fields.name || ""}
          onChange={(e) => set("name", e.target.value)}
          placeholder="Goal name"
          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
          autoFocus
        />
      </td>
      <td className="px-4 py-2">
        <input
          type="text"
          value={fields.description || ""}
          onChange={(e) => set("description", e.target.value)}
          placeholder="Description"
          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
        />
      </td>
      <td className="px-4 py-2">
        <input
          type="number"
          value={fields.sort_order || ""}
          onChange={(e) => set("sort_order", e.target.value)}
          placeholder="0"
          className="w-20 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-1 focus:ring-brand-blue outline-none"
        />
      </td>
      <td className="px-4 py-2 text-right">
        <div className="flex items-center justify-end gap-1">
          <button
            onClick={() => onSave(fields)}
            disabled={saving || !fields.name?.trim()}
            className="p-1.5 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors disabled:opacity-50"
            title="Save"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Check className="w-4 h-4" />
            )}
          </button>
          <button
            onClick={onCancel}
            disabled={saving}
            className="p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
            title="Cancel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </td>
    </tr>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function AdminTaxonomy() {
  const [activeTab, setActiveTab] = useState<TaxonomyTab>("pillars");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  // Taxonomy data
  const [taxonomy, setTaxonomy] = useState<TaxonomyData | null>(null);

  // Inline editing
  const [editing, setEditing] = useState<EditingRow | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const token = localStorage.getItem("gs2_token") || "";
  const currentTab = TABS.find((t) => t.id === activeTab)!;

  // --------------------------------------------------------------------------
  // Load taxonomy data
  // --------------------------------------------------------------------------

  const loadTaxonomy = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTaxonomy(token);
      setTaxonomy(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load taxonomy data",
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadTaxonomy();
  }, [loadTaxonomy]);

  // --------------------------------------------------------------------------
  // Pillar CRUD
  // --------------------------------------------------------------------------

  const handleSavePillar = async (fields: Record<string, string>) => {
    setSaving(true);
    try {
      if (editing?.id) {
        await updatePillar(token, editing.id, {
          name: fields.name,
          code: fields.code || undefined,
          color: fields.color || undefined,
          description: fields.description || undefined,
        });
        setToast({ message: "Pillar updated successfully.", type: "success" });
      } else {
        await createPillar(token, {
          id: (fields.code || fields.name || "pillar")
            .toLowerCase()
            .replace(/\s+/g, "_")
            .slice(0, 50),
          name: fields.name,
          code: fields.code || undefined,
          color: fields.color || undefined,
          description: fields.description || undefined,
        });
        setToast({ message: "Pillar created successfully.", type: "success" });
      }
      setEditing(null);
      await loadTaxonomy();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to save pillar.",
        type: "error",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePillar = async (id: string) => {
    if (!window.confirm("Are you sure you want to delete this pillar?")) return;
    setDeletingId(id);
    try {
      await deletePillar(token, id);
      setToast({ message: "Pillar deleted.", type: "success" });
      await loadTaxonomy();
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to delete pillar.",
        type: "error",
      });
    } finally {
      setDeletingId(null);
    }
  };

  // --------------------------------------------------------------------------
  // Goal CRUD
  // --------------------------------------------------------------------------

  const handleSaveGoal = async (fields: Record<string, string>) => {
    setSaving(true);
    try {
      if (!editing?.id && !fields.pillar_id) {
        setToast({
          message: "Please select a pillar for the goal.",
          type: "error",
        });
        setSaving(false);
        return;
      }
      const data: Partial<TaxonomyGoal> = {
        name: fields.name,
        pillar_id: fields.pillar_id || undefined,
        description: fields.description || undefined,
        sort_order: fields.sort_order
          ? parseInt(fields.sort_order, 10)
          : undefined,
      };
      if (editing?.id) {
        await updateGoal(token, editing.id, data);
        setToast({ message: "Goal updated successfully.", type: "success" });
      } else {
        const goalName = fields.name ?? "goal";
        await createGoal(token, {
          ...data,
          id: goalName.toLowerCase().replace(/\s+/g, "_").slice(0, 50),
          pillar_id: fields.pillar_id ?? "",
        });
        setToast({ message: "Goal created successfully.", type: "success" });
      }
      setEditing(null);
      await loadTaxonomy();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to save goal.",
        type: "error",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteGoal = async (id: string) => {
    if (!window.confirm("Are you sure you want to delete this goal?")) return;
    setDeletingId(id);
    try {
      await deleteGoal(token, id);
      setToast({ message: "Goal deleted.", type: "success" });
      await loadTaxonomy();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to delete goal.",
        type: "error",
      });
    } finally {
      setDeletingId(null);
    }
  };

  // --------------------------------------------------------------------------
  // Start editing / adding
  // --------------------------------------------------------------------------

  const startAdd = () => {
    if (activeTab === "pillars") {
      setEditing({
        id: null,
        fields: { name: "", code: "", color: "", description: "" },
      });
    } else if (activeTab === "goals") {
      setEditing({
        id: null,
        fields: { pillar_id: "", name: "", description: "", sort_order: "" },
      });
    }
  };

  const startEditPillar = (item: TaxonomyItem) => {
    setEditing({
      id: item.id,
      fields: {
        name: item.name || "",
        code: item.code || "",
        color: item.color || "",
        description: item.description || "",
      },
    });
  };

  const startEditGoal = (item: TaxonomyGoal) => {
    setEditing({
      id: item.id,
      fields: {
        pillar_id: item.pillar_id || "",
        name: item.name || "",
        description: item.description || "",
        sort_order: item.sort_order != null ? String(item.sort_order) : "",
      },
    });
  };

  // --------------------------------------------------------------------------
  // Helper: find pillar name by id
  // --------------------------------------------------------------------------

  const pillarName = (id: string | undefined): string => {
    if (!id || !taxonomy) return "--";
    const p = taxonomy.pillars.find((p) => p.id === id);
    return p ? p.code || p.name : id;
  };

  // --------------------------------------------------------------------------
  // Render table per tab
  // --------------------------------------------------------------------------

  const renderPillarsTable = () => {
    const items = taxonomy?.pillars || [];
    return (
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Name
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Code
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Color
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Description
            </th>
            <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {editing && editing.id === null && (
            <PillarEditRow
              editing={editing}
              onSave={handleSavePillar}
              onCancel={() => setEditing(null)}
              saving={saving}
            />
          )}
          {items.map((item) =>
            editing && editing.id === item.id ? (
              <PillarEditRow
                key={item.id}
                editing={editing}
                onSave={handleSavePillar}
                onCancel={() => setEditing(null)}
                saving={saving}
              />
            ) : (
              <tr
                key={item.id}
                className="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
              >
                <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                  {item.name}
                </td>
                <td className="px-4 py-3">
                  {item.code ? (
                    <span className="inline-flex px-2 py-0.5 text-xs font-semibold rounded-full bg-brand-blue/10 text-brand-blue">
                      {item.code}
                    </span>
                  ) : (
                    <span className="text-gray-400 text-xs">--</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <ColorSwatch color={item.color} />
                </td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-400 max-w-xs">
                  {truncate(item.description, 80)}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => startEditPillar(item)}
                      className="p-1.5 text-gray-400 hover:text-brand-blue hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                      title="Edit"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDeletePillar(item.id)}
                      disabled={deletingId === item.id}
                      className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors disabled:opacity-50"
                      title="Delete"
                    >
                      {deletingId === item.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </td>
              </tr>
            ),
          )}
          {items.length === 0 && !editing && (
            <tr>
              <td
                colSpan={5}
                className="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
              >
                No pillars found. Click "Add Pillar" to create one.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    );
  };

  const renderGoalsTable = () => {
    const items = taxonomy?.goals || [];
    const pillars = taxonomy?.pillars || [];
    return (
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Pillar
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Name
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Description
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Sort Order
            </th>
            <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {editing && editing.id === null && (
            <GoalEditRow
              editing={editing}
              pillars={pillars}
              onSave={handleSaveGoal}
              onCancel={() => setEditing(null)}
              saving={saving}
            />
          )}
          {items.map((item) =>
            editing && editing.id === item.id ? (
              <GoalEditRow
                key={item.id}
                editing={editing}
                pillars={pillars}
                onSave={handleSaveGoal}
                onCancel={() => setEditing(null)}
                saving={saving}
              />
            ) : (
              <tr
                key={item.id}
                className="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
              >
                <td className="px-4 py-3">
                  <span className="inline-flex px-2 py-0.5 text-xs font-semibold rounded-full bg-brand-blue/10 text-brand-blue">
                    {pillarName(item.pillar_id)}
                  </span>
                </td>
                <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                  {item.name}
                </td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-400 max-w-xs">
                  {truncate(item.description, 80)}
                </td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                  {item.sort_order ?? "--"}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() => startEditGoal(item)}
                      className="p-1.5 text-gray-400 hover:text-brand-blue hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                      title="Edit"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteGoal(item.id)}
                      disabled={deletingId === item.id}
                      className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors disabled:opacity-50"
                      title="Delete"
                    >
                      {deletingId === item.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </td>
              </tr>
            ),
          )}
          {items.length === 0 && !editing && (
            <tr>
              <td
                colSpan={5}
                className="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
              >
                No goals found. Click "Add Goal" to create one.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    );
  };

  const renderAnchorsTable = () => {
    const items = taxonomy?.anchors || [];
    return (
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Name
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Color
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Description
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              className="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
            >
              <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                {item.name}
              </td>
              <td className="px-4 py-3">
                <ColorSwatch color={item.color} />
              </td>
              <td className="px-4 py-3 text-gray-600 dark:text-gray-400 max-w-md">
                {truncate(item.description, 120)}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td
                colSpan={3}
                className="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
              >
                No anchors found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    );
  };

  const renderStagesTable = () => {
    const items = taxonomy?.stages || [];
    return (
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Name
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Sort Order
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Horizon
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
              Description
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              className="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
            >
              <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                {item.name}
              </td>
              <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                {item.sort_order ?? "--"}
              </td>
              <td className="px-4 py-3">
                {(item as TaxonomyItem & { horizon?: string }).horizon ? (
                  <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded-full bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300">
                    {(item as TaxonomyItem & { horizon?: string }).horizon}
                  </span>
                ) : (
                  <span className="text-gray-400 text-xs">--</span>
                )}
              </td>
              <td className="px-4 py-3 text-gray-600 dark:text-gray-400 max-w-md">
                {truncate(item.description, 120)}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td
                colSpan={4}
                className="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
              >
                No stages found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    );
  };

  const renderReadOnlyPlaceholder = () => (
    <div className="px-4 py-12 text-center">
      <Tags className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
      <h3 className="text-base font-medium text-gray-700 dark:text-gray-300 mb-1">
        Read-Only View
      </h3>
      <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
        {currentTab.label} are managed via database seeds. CRUD API endpoints
        for this taxonomy type are not yet available. Contact an administrator
        to make changes.
      </p>
    </div>
  );

  const renderTabContent = () => {
    if (loading) return <LoadingSkeleton />;

    if (error) {
      return (
        <div className="px-4 py-12 text-center">
          <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            {error}
          </p>
          <button
            onClick={loadTaxonomy}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            Retry
          </button>
        </div>
      );
    }

    switch (activeTab) {
      case "pillars":
        return renderPillarsTable();
      case "goals":
        return renderGoalsTable();
      case "anchors":
        return renderAnchorsTable();
      case "stages":
        return renderStagesTable();
      default:
        return renderReadOnlyPlaceholder();
    }
  };

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Taxonomy Management
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Manage strategic pillars, goals, anchors, and maturity stages.
          </p>
        </div>
        {currentTab.editable && (
          <button
            onClick={startAdd}
            disabled={!!editing}
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-blue hover:bg-brand-blue/90 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus className="w-4 h-4" />
            Add {currentTab.label.replace(/s$/, "")}
          </button>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}

      {/* Tab navigation */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav
          className="flex -mb-px space-x-6 overflow-x-auto"
          aria-label="Taxonomy tabs"
        >
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                setEditing(null);
              }}
              className={`whitespace-nowrap pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-brand-blue text-brand-blue"
                  : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2">
          <Tags className="w-4 h-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {currentTab.label}
          </span>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            -- {currentTab.description}
          </span>
          {!currentTab.editable && !loading && !error && (
            <span className="ml-auto inline-flex px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400">
              Read-only
            </span>
          )}
        </div>
        <div className="overflow-x-auto">{renderTabContent()}</div>
      </div>
    </div>
  );
}
