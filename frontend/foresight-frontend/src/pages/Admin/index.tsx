import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  Tags,
  FileText,
  Compass,
  Globe,
  Brain,
  Cog,
  Clock,
  Shield,
  Bell,
  Settings,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// ---------------------------------------------------------------------------
// Navigation configuration
// ---------------------------------------------------------------------------

interface AdminNavItem {
  name: string;
  href: string;
  icon: LucideIcon;
  description: string;
}

const adminNavigation: AdminNavItem[] = [
  {
    name: "Dashboard",
    href: "/admin",
    icon: LayoutDashboard,
    description: "System overview and metrics",
  },
  {
    name: "Users",
    href: "/admin/users",
    icon: Users,
    description: "User management",
  },
  {
    name: "Taxonomy",
    href: "/admin/taxonomy",
    icon: Tags,
    description: "Pillars, goals, stages",
  },
  {
    name: "Content",
    href: "/admin/content",
    icon: FileText,
    description: "Card management",
  },
  {
    name: "Discovery",
    href: "/admin/discovery",
    icon: Compass,
    description: "Discovery pipeline",
  },
  {
    name: "Sources",
    href: "/admin/sources",
    icon: Globe,
    description: "Source configuration",
  },
  {
    name: "AI Settings",
    href: "/admin/ai",
    icon: Brain,
    description: "Model configuration",
  },
  {
    name: "Jobs",
    href: "/admin/jobs",
    icon: Cog,
    description: "Background job queue",
  },
  {
    name: "Scheduler",
    href: "/admin/scheduler",
    icon: Clock,
    description: "Scheduled tasks",
  },
  {
    name: "Quality",
    href: "/admin/quality",
    icon: Shield,
    description: "Quality scoring",
  },
  {
    name: "Notifications",
    href: "/admin/notifications",
    icon: Bell,
    description: "Notification settings",
  },
  {
    name: "Settings",
    href: "/admin/settings",
    icon: Settings,
    description: "System configuration",
  },
];

// ---------------------------------------------------------------------------
// Sidebar nav item component
// ---------------------------------------------------------------------------

function SidebarItem({
  item,
  collapsed,
}: {
  item: AdminNavItem;
  collapsed: boolean;
}) {
  const Icon = item.icon;

  return (
    <NavLink
      to={item.href}
      end={item.href === "/admin"}
      className={({ isActive }) =>
        `group flex items-center rounded-lg transition-colors duration-150 ${
          collapsed ? "justify-center px-2 py-2.5" : "px-3 py-2.5"
        } ${
          isActive
            ? "bg-brand-blue/10 text-brand-blue dark:bg-brand-blue/20 dark:text-blue-300"
            : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50 hover:text-gray-900 dark:hover:text-white"
        }`
      }
      title={collapsed ? item.name : undefined}
    >
      <Icon className={`flex-shrink-0 w-5 h-5 ${collapsed ? "" : "mr-3"}`} />
      {!collapsed && (
        <span className="text-sm font-medium truncate">{item.name}</span>
      )}
    </NavLink>
  );
}

// ---------------------------------------------------------------------------
// Mobile nav item component
// ---------------------------------------------------------------------------

function MobileNavItem({
  item,
  onNavigate,
}: {
  item: AdminNavItem;
  onNavigate: () => void;
}) {
  const Icon = item.icon;

  return (
    <NavLink
      to={item.href}
      end={item.href === "/admin"}
      onClick={onNavigate}
      className={({ isActive }) =>
        `flex items-center min-h-[44px] px-3 py-2 text-sm font-medium rounded-lg transition-colors active:scale-[0.98] ${
          isActive
            ? "bg-brand-blue/10 text-brand-blue dark:bg-brand-blue/20 dark:text-blue-300"
            : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50"
        }`
      }
    >
      <Icon className="w-5 h-5 mr-3 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <span className="block truncate">{item.name}</span>
        <span className="block text-xs text-gray-400 dark:text-gray-500 truncate">
          {item.description}
        </span>
      </div>
    </NavLink>
  );
}

// ---------------------------------------------------------------------------
// Admin Layout
// ---------------------------------------------------------------------------

export default function AdminLayout() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Find current page for mobile header
  const currentPage = adminNavigation.find((item) =>
    item.href === "/admin"
      ? location.pathname === "/admin"
      : location.pathname.startsWith(item.href),
  );

  return (
    <div className="flex min-h-[calc(100vh-4rem)]">
      {/* Desktop sidebar */}
      <aside
        className={`hidden lg:flex flex-col border-r border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-dark-surface/80 backdrop-blur-sm transition-all duration-200 ${
          collapsed ? "w-16" : "w-64"
        }`}
      >
        {/* Sidebar header */}
        <div
          className={`flex items-center h-14 border-b border-gray-200 dark:border-gray-700 ${
            collapsed ? "justify-center px-2" : "justify-between px-4"
          }`}
        >
          {!collapsed && (
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-brand-blue" />
              <span className="text-sm font-semibold text-gray-900 dark:text-white">
                Administration
              </span>
            </div>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Navigation links */}
        <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-1">
          {adminNavigation.map((item) => (
            <SidebarItem key={item.href} item={item} collapsed={collapsed} />
          ))}
        </nav>

        {/* Sidebar footer */}
        <div
          className={`border-t border-gray-200 dark:border-gray-700 p-3 ${
            collapsed ? "text-center" : ""
          }`}
        >
          <NavLink
            to="/settings"
            className="flex items-center text-xs text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-400 transition-colors"
            title="Back to user settings"
          >
            <ChevronLeft
              className={`w-3.5 h-3.5 ${collapsed ? "" : "mr-1.5"}`}
            />
            {!collapsed && <span>Back to Settings</span>}
          </NavLink>
        </div>
      </aside>

      {/* Mobile header & nav */}
      <div className="lg:hidden fixed top-16 left-0 right-0 z-40 bg-white/95 dark:bg-dark-surface/95 backdrop-blur-sm border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between px-4 h-12">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-brand-blue" />
            <span className="text-sm font-semibold text-gray-900 dark:text-white">
              {currentPage?.name || "Admin"}
            </span>
          </div>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="p-2 rounded-md text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label="Toggle admin navigation"
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? (
              <X className="w-5 h-5" />
            ) : (
              <Menu className="w-5 h-5" />
            )}
          </button>
        </div>

        {/* Mobile dropdown nav */}
        {mobileOpen && (
          <div className="px-3 pb-3 space-y-1 max-h-[60vh] overflow-y-auto animate-in fade-in slide-in-from-top-2 duration-200">
            {adminNavigation.map((item) => (
              <MobileNavItem
                key={item.href}
                item={item}
                onNavigate={() => setMobileOpen(false)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Main content area */}
      <main className="flex-1 min-w-0 overflow-auto">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-8 mt-12 lg:mt-0">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
