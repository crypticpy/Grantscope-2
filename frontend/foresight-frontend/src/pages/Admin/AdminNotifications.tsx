/**
 * AdminNotifications Page
 *
 * Notification settings management dashboard with:
 * - SMTP config status (read-only display: configured yes/no, from address)
 * - User preference summary: stat cards (how many daily/weekly/none)
 * - "Send Test Email" button
 * - System notification configuration overview
 *
 * @module pages/Admin/AdminNotifications
 */

import { useState, useEffect, useCallback } from "react";
import {
  Bell,
  Mail,
  Send,
  Users,
  Loader2,
  AlertCircle,
  CheckCircle2,
  X,
  Clock,
} from "lucide-react";
import {
  fetchNotificationConfig,
  fetchNotificationPreferences,
  sendTestEmail,
} from "../../lib/admin-api";
import type {
  NotificationConfig,
  NotificationPreferencesSummary,
} from "../../lib/admin-api";

// ============================================================================
// Types
// ============================================================================

interface ToastState {
  message: string;
  type: "success" | "error";
}

// ============================================================================
// Sub-Components
// ============================================================================

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

function StatCard({
  label,
  value,
  icon: Icon,
  color = "text-gray-900 dark:text-white",
  loading,
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  color?: string;
  loading: boolean;
}) {
  return (
    <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-gray-400" />
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          {label}
        </span>
      </div>
      {loading ? (
        <div className="animate-pulse h-7 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
      ) : (
        <p className={`text-2xl font-semibold ${color}`}>{value}</p>
      )}
    </div>
  );
}

function ConfigBadge({
  value,
  variant = "boolean",
}: {
  value: boolean | string;
  variant?: "boolean" | "text";
}) {
  if (variant === "boolean") {
    const boolVal = value as boolean;
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full ${
          boolVal
            ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
            : "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400"
        }`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full ${boolVal ? "bg-green-500" : "bg-gray-400"}`}
        />
        {boolVal ? "Yes" : "No"}
      </span>
    );
  }
  return (
    <span className="inline-flex px-2.5 py-1 text-xs font-medium rounded-full bg-brand-blue/10 text-brand-blue dark:bg-brand-blue/20 dark:text-blue-300">
      {value as string}
    </span>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function AdminNotifications() {
  const token = localStorage.getItem("gs2_token") || "";

  // Data state
  const [config, setConfig] = useState<NotificationConfig | null>(null);
  const [preferences, setPreferences] =
    useState<NotificationPreferencesSummary | null>(null);

  // Loading
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [loadingPrefs, setLoadingPrefs] = useState(true);
  const [sendingTest, setSendingTest] = useState(false);

  // Toast
  const [toast, setToast] = useState<ToastState | null>(null);

  // --------------------------------------------------------------------------
  // Load data
  // --------------------------------------------------------------------------

  const loadConfig = useCallback(async () => {
    setLoadingConfig(true);
    try {
      const data = await fetchNotificationConfig(token);
      setConfig(data);
    } catch (err) {
      setToast({
        message:
          err instanceof Error
            ? err.message
            : "Failed to load notification config",
        type: "error",
      });
    } finally {
      setLoadingConfig(false);
    }
  }, [token]);

  const loadPreferences = useCallback(async () => {
    setLoadingPrefs(true);
    try {
      const data = await fetchNotificationPreferences(token);
      setPreferences(data);
    } catch (err) {
      setToast({
        message:
          err instanceof Error
            ? err.message
            : "Failed to load notification preferences",
        type: "error",
      });
    } finally {
      setLoadingPrefs(false);
    }
  }, [token]);

  useEffect(() => {
    loadConfig();
    loadPreferences();
  }, [loadConfig, loadPreferences]);

  // --------------------------------------------------------------------------
  // Send test email
  // --------------------------------------------------------------------------

  const handleSendTestEmail = async () => {
    setSendingTest(true);
    try {
      await sendTestEmail(token);
      setToast({
        message: "Test email sent successfully. Check your inbox.",
        type: "success",
      });
    } catch (err) {
      setToast({
        message:
          err instanceof Error ? err.message : "Failed to send test email",
        type: "error",
      });
    } finally {
      setSendingTest(false);
    }
  };

  // --------------------------------------------------------------------------
  // Config items
  // --------------------------------------------------------------------------

  const configItems = config
    ? [
        {
          label: "Email Notifications",
          description: "Enable email delivery system",
          value: config.email_enabled,
          variant: "boolean" as const,
        },
        {
          label: "Digest Enabled",
          description: "Enable periodic digest emails",
          value: config.digest_enabled,
          variant: "boolean" as const,
        },
        {
          label: "SMTP Configured",
          description: "SMTP server connection status",
          value: config.smtp_configured,
          variant: "boolean" as const,
        },
        {
          label: "Default Frequency",
          description: "Default digest frequency for new users",
          value: config.default_frequency,
          variant: "text" as const,
        },
      ]
    : [];

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Notification Settings
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Configure email notifications, digest settings, and delivery
            preferences.
          </p>
        </div>
        <button
          onClick={handleSendTestEmail}
          disabled={sendingTest || (config !== null && !config.smtp_configured)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand-blue hover:bg-brand-blue/90 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {sendingTest ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
          Send Test Email
        </button>
      </div>

      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}

      {/* Email Configuration */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Mail className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Email Configuration
          </h2>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            (read-only)
          </span>
        </div>

        {loadingConfig ? (
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse flex items-center justify-between p-3 rounded-lg border border-gray-100 dark:border-gray-800"
              >
                <div>
                  <div className="h-4 w-28 bg-gray-200 dark:bg-gray-700 rounded mb-1" />
                  <div className="h-3 w-40 bg-gray-200 dark:bg-gray-700 rounded" />
                </div>
                <div className="h-6 w-16 bg-gray-200 dark:bg-gray-700 rounded-full" />
              </div>
            ))}
          </div>
        ) : config ? (
          <div className="space-y-3">
            {configItems.map((item) => (
              <div
                key={item.label}
                className="flex items-center justify-between p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
              >
                <div>
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {item.label}
                  </span>
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                    {item.description}
                  </p>
                </div>
                <ConfigBadge value={item.value} variant={item.variant} />
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {/* User Preference Summary */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Users className="w-5 h-5 text-brand-blue" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            User Preference Summary
          </h2>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Users"
            value={
              preferences ? preferences.total_users.toLocaleString() : "--"
            }
            icon={Users}
            loading={loadingPrefs}
          />
          <StatCard
            label="Daily Digest"
            value={
              preferences ? preferences.daily_count.toLocaleString() : "--"
            }
            icon={Bell}
            color="text-brand-blue"
            loading={loadingPrefs}
          />
          <StatCard
            label="Weekly Digest"
            value={
              preferences ? preferences.weekly_count.toLocaleString() : "--"
            }
            icon={Clock}
            color="text-brand-green"
            loading={loadingPrefs}
          />
          <StatCard
            label="No Notifications"
            value={preferences ? preferences.none_count.toLocaleString() : "--"}
            icon={Bell}
            color="text-gray-500"
            loading={loadingPrefs}
          />
        </div>

        {/* Distribution bar */}
        {preferences && preferences.total_users > 0 && (
          <div className="mt-4">
            <div className="w-full h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden flex">
              {preferences.daily_count > 0 && (
                <div
                  className="h-full bg-brand-blue transition-all duration-500"
                  style={{
                    width: `${(preferences.daily_count / preferences.total_users) * 100}%`,
                  }}
                  title={`Daily: ${preferences.daily_count}`}
                />
              )}
              {preferences.weekly_count > 0 && (
                <div
                  className="h-full bg-brand-green transition-all duration-500"
                  style={{
                    width: `${(preferences.weekly_count / preferences.total_users) * 100}%`,
                  }}
                  title={`Weekly: ${preferences.weekly_count}`}
                />
              )}
              {preferences.none_count > 0 && (
                <div
                  className="h-full bg-gray-400 transition-all duration-500"
                  style={{
                    width: `${(preferences.none_count / preferences.total_users) * 100}%`,
                  }}
                  title={`None: ${preferences.none_count}`}
                />
              )}
            </div>
            <div className="flex items-center justify-between mt-1.5 text-xs text-gray-500 dark:text-gray-400">
              <span>{preferences.total_users} total users</span>
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-brand-blue" />
                  Daily
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-brand-green" />
                  Weekly
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-gray-400" />
                  None
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* SMTP Status Details */}
      {config && !config.smtp_configured && (
        <div className="flex items-center gap-2 px-4 py-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/50 rounded-lg text-sm text-yellow-800 dark:text-yellow-300">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>
            SMTP is not configured. Set the SMTP environment variables to enable
            email notifications. Test emails cannot be sent until SMTP is
            configured.
          </span>
        </div>
      )}
    </div>
  );
}
