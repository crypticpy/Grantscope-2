import { useState, useEffect, useCallback } from "react";
import {
  Settings,
  Search,
  ChevronDown,
  ChevronRight,
  Save,
  X,
  Pencil,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import {
  fetchSettings,
  updateSetting,
  type SystemSetting,
} from "../../lib/admin-api";

// ---------------------------------------------------------------------------
// Category mapping
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  search: "Search & Sources",
  ai: "AI & Models",
  discovery: "Discovery Pipeline",
  worker: "Worker & Background Jobs",
  scheduler: "Scheduler",
  content: "Content Management",
  quality: "Quality & Scoring",
  rss: "RSS Feeds",
  rate_limit: "Rate Limiting",
};

/** Extract category prefix from a setting key (handles underscored multi-word prefixes like rate_limit). */
function getCategory(key: string): string {
  // Check multi-word prefixes first
  for (const prefix of Object.keys(CATEGORY_LABELS)) {
    if (key.startsWith(prefix + ".")) {
      return prefix;
    }
  }
  // Fallback: first segment before "."
  const dot = key.indexOf(".");
  return dot > 0 ? key.substring(0, dot) : "other";
}

function getCategoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

// ---------------------------------------------------------------------------
// Value type helpers
// ---------------------------------------------------------------------------

type ValueKind = "boolean" | "number" | "json" | "string";

function detectKind(value: unknown): ValueKind {
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "number") return "number";
  if (typeof value === "object" && value !== null) return "json";
  return "string";
}

/** Format a value for display in the table (non-editing mode). */
function formatDisplay(value: unknown): string {
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  if (typeof value === "object" && value !== null)
    return JSON.stringify(value, null, 2);
  return String(value ?? "");
}

/** Parse a draft string back to the proper typed value. */
function parseDraft(raw: string, kind: ValueKind): unknown {
  if (kind === "boolean") return raw === "true";
  if (kind === "number") {
    const n = Number(raw);
    if (Number.isNaN(n)) throw new Error("Invalid number");
    return n;
  }
  if (kind === "json") return JSON.parse(raw);
  return raw;
}

// ---------------------------------------------------------------------------
// Toggle Switch
// ---------------------------------------------------------------------------

function ToggleSwitch({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-brand-blue/50 focus:ring-offset-2 ${
        checked ? "bg-brand-blue" : "bg-gray-300 dark:bg-gray-600"
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          checked ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Inline Editor
// ---------------------------------------------------------------------------

function InlineEditor({
  value,
  kind,
  onChange,
}: {
  value: string;
  kind: ValueKind;
  onChange: (v: string) => void;
}) {
  if (kind === "boolean") {
    return (
      <ToggleSwitch
        checked={value === "true"}
        onChange={(v) => onChange(String(v))}
      />
    );
  }

  if (kind === "number") {
    return (
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full max-w-[200px] px-2 py-1 text-sm font-mono bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded focus:ring-2 focus:ring-brand-blue/50 focus:border-brand-blue text-gray-900 dark:text-white transition-colors"
      />
    );
  }

  if (kind === "json") {
    return (
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={4}
        className="w-full px-2 py-1 text-sm font-mono bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded focus:ring-2 focus:ring-brand-blue/50 focus:border-brand-blue text-gray-900 dark:text-white transition-colors resize-y"
      />
    );
  }

  // string
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full max-w-[300px] px-2 py-1 text-sm bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded focus:ring-2 focus:ring-brand-blue/50 focus:border-brand-blue text-gray-900 dark:text-white transition-colors"
    />
  );
}

// ---------------------------------------------------------------------------
// Setting Row
// ---------------------------------------------------------------------------

function SettingRow({
  setting,
  isEditing,
  onStartEdit,
  onCancel,
  onSave,
  savingKey,
}: {
  setting: SystemSetting;
  isEditing: boolean;
  onStartEdit: () => void;
  onCancel: () => void;
  onSave: (key: string, value: unknown) => Promise<void>;
  savingKey: string | null;
}) {
  const kind = detectKind(setting.value);
  const [draft, setDraft] = useState(() => {
    if (kind === "json") return JSON.stringify(setting.value, null, 2);
    return String(setting.value ?? "");
  });
  const [parseError, setParseError] = useState<string | null>(null);
  const isSaving = savingKey === setting.key;

  // Reset draft when entering edit mode
  useEffect(() => {
    if (isEditing) {
      if (kind === "json") {
        setDraft(JSON.stringify(setting.value, null, 2));
      } else {
        setDraft(String(setting.value ?? ""));
      }
      setParseError(null);
    }
  }, [isEditing, setting.value, kind]);

  const handleSave = async () => {
    try {
      const parsed = parseDraft(draft, kind);
      setParseError(null);
      await onSave(setting.key, parsed);
    } catch (err) {
      setParseError(err instanceof Error ? err.message : "Invalid value");
    }
  };

  const updatedLabel = setting.updated_at
    ? new Date(setting.updated_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "--";

  return (
    <tr className="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors">
      {/* Key */}
      <td className="px-4 py-3 align-top">
        <code className="text-xs font-mono text-gray-900 dark:text-gray-100 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded whitespace-nowrap">
          {setting.key}
        </code>
      </td>

      {/* Value */}
      <td className="px-4 py-3 align-top">
        {isEditing ? (
          <div className="space-y-1">
            <InlineEditor value={draft} kind={kind} onChange={setDraft} />
            {parseError && (
              <p className="text-xs text-red-500 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                {parseError}
              </p>
            )}
          </div>
        ) : (
          <span
            className={`text-sm text-gray-900 dark:text-gray-100 ${
              kind === "json" || kind === "string"
                ? "font-mono whitespace-pre-wrap break-all"
                : ""
            } ${kind === "boolean" ? (setting.value ? "text-green-600 dark:text-green-400" : "text-gray-400") : ""}`}
          >
            {formatDisplay(setting.value)}
          </span>
        )}
      </td>

      {/* Description */}
      <td className="px-4 py-3 align-top">
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {setting.description ?? "--"}
        </span>
      </td>

      {/* Updated */}
      <td className="px-4 py-3 align-top whitespace-nowrap">
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {updatedLabel}
        </span>
      </td>

      {/* Actions */}
      <td className="px-4 py-3 align-top text-right">
        {isEditing ? (
          <div className="flex items-center justify-end gap-2">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-white bg-brand-blue rounded hover:bg-brand-blue/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSaving ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Save className="w-3 h-3" />
              )}
              Save
            </button>
            <button
              onClick={onCancel}
              disabled={isSaving}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 rounded hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <X className="w-3 h-3" />
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={onStartEdit}
            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-brand-blue hover:text-brand-blue/80 hover:bg-brand-blue/5 rounded transition-colors"
          >
            <Pencil className="w-3 h-3" />
            Edit
          </button>
        )}
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Category Group
// ---------------------------------------------------------------------------

function CategoryGroup({
  category,
  settings,
  editingKey,
  onStartEdit,
  onCancel,
  onSave,
  savingKey,
  defaultOpen,
}: {
  category: string;
  settings: SystemSetting[];
  editingKey: string | null;
  onStartEdit: (key: string) => void;
  onCancel: () => void;
  onSave: (key: string, value: unknown) => Promise<void>;
  savingKey: string | null;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Group header */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800/70 transition-colors"
      >
        <div className="flex items-center gap-2">
          {open ? (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-400" />
          )}
          <span className="text-sm font-semibold text-gray-900 dark:text-white">
            {getCategoryLabel(category)}
          </span>
          <span className="text-xs text-gray-400 dark:text-gray-500 font-normal">
            ({settings.length} setting{settings.length !== 1 ? "s" : ""})
          </span>
        </div>
      </button>

      {/* Settings table */}
      {open && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30">
                <th className="text-left px-4 py-2 font-medium text-gray-500 dark:text-gray-400 text-xs w-[200px]">
                  <div className="flex items-center gap-1.5">
                    <Settings className="w-3.5 h-3.5" />
                    Key
                  </div>
                </th>
                <th className="text-left px-4 py-2 font-medium text-gray-500 dark:text-gray-400 text-xs">
                  Value
                </th>
                <th className="text-left px-4 py-2 font-medium text-gray-500 dark:text-gray-400 text-xs w-[240px]">
                  Description
                </th>
                <th className="text-left px-4 py-2 font-medium text-gray-500 dark:text-gray-400 text-xs w-[140px]">
                  Updated
                </th>
                <th className="text-right px-4 py-2 font-medium text-gray-500 dark:text-gray-400 text-xs w-[120px]">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {settings.map((s) => (
                <SettingRow
                  key={s.key}
                  setting={s}
                  isEditing={editingKey === s.key}
                  onStartEdit={() => onStartEdit(s.key)}
                  onCancel={onCancel}
                  onSave={onSave}
                  savingKey={savingKey}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AdminSettings() {
  const [settings, setSettings] = useState<SystemSetting[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Fetch all settings on mount
  useEffect(() => {
    const token = localStorage.getItem("gs2_token");
    if (!token) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    fetchSettings(token)
      .then((data) => {
        setSettings(data);
        setError(null);
      })
      .catch((err) => {
        setError(
          err instanceof Error ? err.message : "Failed to load settings",
        );
      })
      .finally(() => setLoading(false));
  }, []);

  // Auto-dismiss success message
  useEffect(() => {
    if (!successMsg) return;
    const timer = setTimeout(() => setSuccessMsg(null), 3000);
    return () => clearTimeout(timer);
  }, [successMsg]);

  // Filter settings by search query
  const filtered = settings.filter((s) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      s.key.toLowerCase().includes(q) ||
      (s.description ?? "").toLowerCase().includes(q)
    );
  });

  // Group settings by category
  const grouped = filtered.reduce<Record<string, SystemSetting[]>>((acc, s) => {
    const cat = getCategory(s.key);
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(s);
    return acc;
  }, {});

  // Sort categories by the order they appear in CATEGORY_LABELS
  const categoryOrder = Object.keys(CATEGORY_LABELS);
  const sortedCategories = Object.keys(grouped).sort((a, b) => {
    const ai = categoryOrder.indexOf(a);
    const bi = categoryOrder.indexOf(b);
    const aIdx = ai >= 0 ? ai : 999;
    const bIdx = bi >= 0 ? bi : 999;
    return aIdx - bIdx;
  });

  const handleStartEdit = useCallback((key: string) => {
    setEditingKey(key);
    setSuccessMsg(null);
  }, []);

  const handleCancel = useCallback(() => {
    setEditingKey(null);
  }, []);

  const handleSave = useCallback(async (key: string, value: unknown) => {
    const token = localStorage.getItem("gs2_token");
    if (!token) {
      setError("Not authenticated");
      return;
    }

    setSavingKey(key);
    try {
      await updateSetting(token, key, value);
      // Update local state
      setSettings((prev) =>
        prev.map((s) =>
          s.key === key
            ? { ...s, value, updated_at: new Date().toISOString() }
            : s,
        ),
      );
      setEditingKey(null);
      setSuccessMsg(`Setting "${key}" updated successfully.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update setting");
    } finally {
      setSavingKey(null);
    }
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            System Settings
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            View and manage system-wide configuration settings.
          </p>
        </div>
        <div className="text-xs text-gray-400 dark:text-gray-500">
          {settings.length} setting{settings.length !== 1 ? "s" : ""} total
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search settings by key or description..."
          className="w-full pl-10 pr-4 py-2.5 text-sm bg-white dark:bg-dark-surface border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-brand-blue/50 focus:border-brand-blue transition-colors"
        />
      </div>

      {/* Success message */}
      {successMsg && (
        <div className="flex items-center gap-2 px-4 py-3 text-sm text-green-700 dark:text-green-300 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          {successMsg}
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 text-sm text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-auto text-red-500 hover:text-red-700 dark:hover:text-red-300"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-brand-blue" />
          <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">
            Loading settings...
          </span>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && filtered.length === 0 && (
        <div className="text-center py-16">
          <Settings className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {searchQuery
              ? `No settings matching "${searchQuery}"`
              : "No settings configured yet."}
          </p>
        </div>
      )}

      {/* Category groups */}
      {!loading &&
        sortedCategories.map((category) => (
          <CategoryGroup
            key={category}
            category={category}
            settings={grouped[category] ?? []}
            editingKey={editingKey}
            onStartEdit={handleStartEdit}
            onCancel={handleCancel}
            onSave={handleSave}
            savingKey={savingKey}
            defaultOpen={true}
          />
        ))}
    </div>
  );
}
