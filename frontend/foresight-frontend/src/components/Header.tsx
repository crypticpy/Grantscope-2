import React, { useState, useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Home,
  Compass,
  FolderOpen,
  Settings,
  LogOut,
  Menu,
  X,
  Sun,
  Moon,
  BarChart3,
  ChevronDown,
  MoreHorizontal,
  User,
  BookOpen,
  Radio,
} from "lucide-react";
import { useAuthContext } from "../hooks/useAuthContext";

const Header: React.FC = () => {
  const { user, signOut } = useAuthContext();
  const location = useLocation();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isUserDropdownOpen, setIsUserDropdownOpen] = useState(false);
  const [isMoreDropdownOpen, setIsMoreDropdownOpen] = useState(false);
  const userDropdownRef = useRef<HTMLDivElement>(null);
  const moreDropdownRef = useRef<HTMLDivElement>(null);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    // Check localStorage first, then system preference
    const stored = localStorage.getItem("theme");
    if (stored) return stored === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    // Apply theme on mount and changes
    if (isDarkMode) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [isDarkMode]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        userDropdownRef.current &&
        !userDropdownRef.current.contains(event.target as Node)
      ) {
        setIsUserDropdownOpen(false);
      }
      if (
        moreDropdownRef.current &&
        !moreDropdownRef.current.contains(event.target as Node)
      ) {
        setIsMoreDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode);
  };

  // Main navigation items (Queue removed - accessible via Discover page)
  const navigation = [
    { name: "Dashboard", href: "/", icon: Home },
    { name: "Discover", href: "/discover", icon: Compass },
    { name: "Signals", href: "/signals", icon: Radio },
    { name: "Workstreams", href: "/workstreams", icon: FolderOpen },
  ];

  // Items in the "More" dropdown
  const moreNavigation = [
    { name: "Analytics", href: "/analytics", icon: BarChart3 },
    { name: "Methodology", href: "/methodology", icon: BookOpen },
  ];

  const handleSignOut = async () => {
    try {
      await signOut();
    } catch (error) {
      console.error("Error signing out:", error);
    }
  };

  return (
    <header className="glass-header fixed w-full top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo and Title */}
          <Link
            to="/"
            className="flex items-center gap-3 hover:opacity-90 transition-opacity"
          >
            <img
              src="/logo-horizontal.png"
              alt="City of Austin"
              className="h-8 w-auto"
            />
            <div className="hidden sm:flex flex-col">
              <span className="text-sm font-semibold text-brand-blue leading-tight">
                Foresight
              </span>
              <span className="text-xs text-gray-500 dark:text-gray-400 leading-tight">
                Strategic Research
              </span>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center space-x-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive =
                location.pathname === item.href ||
                (item.href === "/discover" &&
                  location.pathname.startsWith("/discover")) ||
                (item.href === "/signals" &&
                  location.pathname.startsWith("/signals")) ||
                (item.href === "/workstreams" &&
                  location.pathname.startsWith("/workstreams"));
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  aria-current={isActive ? "page" : undefined}
                  className={`inline-flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors duration-150 ${
                    isActive
                      ? "text-brand-blue bg-brand-blue/10"
                      : "text-gray-600 hover:text-brand-dark-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10"
                  }`}
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {item.name}
                </Link>
              );
            })}

            {/* More Dropdown */}
            <div className="relative" ref={moreDropdownRef}>
              <button
                onClick={() => setIsMoreDropdownOpen(!isMoreDropdownOpen)}
                className={`inline-flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors duration-150 ${
                  moreNavigation.some((item) => location.pathname === item.href)
                    ? "text-brand-blue bg-brand-blue/10"
                    : "text-gray-600 hover:text-brand-dark-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10"
                }`}
              >
                <MoreHorizontal className="w-4 h-4 mr-2" />
                More
                <ChevronDown
                  className={`w-3 h-3 ml-1 transition-transform ${isMoreDropdownOpen ? "rotate-180" : ""}`}
                />
              </button>
              {isMoreDropdownOpen && (
                <div className="absolute right-0 mt-1 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50">
                  {moreNavigation.map((item) => {
                    const Icon = item.icon;
                    const isActive = location.pathname === item.href;
                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        onClick={() => setIsMoreDropdownOpen(false)}
                        className={`flex items-center px-4 py-2 text-sm transition-colors ${
                          isActive
                            ? "text-brand-blue bg-brand-blue/10"
                            : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                        }`}
                      >
                        <Icon className="w-4 h-4 mr-3" />
                        {item.name}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </nav>

          {/* User Menu Dropdown */}
          <div className="hidden md:flex items-center" ref={userDropdownRef}>
            <div className="relative">
              <button
                onClick={() => setIsUserDropdownOpen(!isUserDropdownOpen)}
                className="inline-flex items-center px-3 py-2 text-sm font-medium text-gray-600 hover:text-brand-dark-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10 rounded-md transition-colors duration-150"
              >
                <User className="w-4 h-4 mr-2" />
                <span className="max-w-[150px] truncate">
                  {user?.email?.split("@")[0]}
                </span>
                <ChevronDown
                  className={`w-3 h-3 ml-1 transition-transform ${isUserDropdownOpen ? "rotate-180" : ""}`}
                />
              </button>
              {isUserDropdownOpen && (
                <div className="absolute right-0 mt-1 w-56 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50">
                  {/* User email display */}
                  <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700">
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Signed in as
                    </p>
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {user?.email}
                    </p>
                  </div>

                  {/* Theme Toggle */}
                  <button
                    onClick={toggleTheme}
                    className="w-full flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  >
                    {isDarkMode ? (
                      <>
                        <Sun className="w-4 h-4 mr-3" />
                        Light Mode
                      </>
                    ) : (
                      <>
                        <Moon className="w-4 h-4 mr-3" />
                        Dark Mode
                      </>
                    )}
                  </button>

                  {/* Settings */}
                  <Link
                    to="/settings"
                    onClick={() => setIsUserDropdownOpen(false)}
                    className={`flex items-center px-4 py-2 text-sm transition-colors ${
                      location.pathname === "/settings"
                        ? "text-brand-blue bg-brand-blue/10"
                        : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                    }`}
                  >
                    <Settings className="w-4 h-4 mr-3" />
                    Settings
                  </Link>

                  <div className="border-t border-gray-200 dark:border-gray-700 my-1"></div>

                  {/* Sign Out */}
                  <button
                    onClick={() => {
                      setIsUserDropdownOpen(false);
                      handleSignOut();
                    }}
                    className="w-full flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  >
                    <LogOut className="w-4 h-4 mr-3" />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Mobile menu button - 44px minimum touch target */}
          <div className="md:hidden">
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              aria-expanded={isMenuOpen}
              aria-label="Toggle navigation menu"
              className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] p-2 rounded-md text-gray-600 hover:text-brand-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-brand-blue active:scale-95 transition-all duration-150"
            >
              {isMenuOpen ? (
                <X className="block h-6 w-6" />
              ) : (
                <Menu className="block h-6 w-6" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Navigation - 44px minimum touch targets */}
      {isMenuOpen && (
        <div className="md:hidden">
          <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3 bg-white/95 dark:bg-brand-dark-blue/95 backdrop-blur-md border-t border-gray-200/50 dark:border-gray-700/50">
            {/* Main Navigation */}
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive =
                location.pathname === item.href ||
                (item.href === "/discover" &&
                  location.pathname.startsWith("/discover")) ||
                (item.href === "/signals" &&
                  location.pathname.startsWith("/signals")) ||
                (item.href === "/workstreams" &&
                  location.pathname.startsWith("/workstreams"));
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setIsMenuOpen(false)}
                  aria-current={isActive ? "page" : undefined}
                  className={`flex items-center min-h-[44px] px-3 py-2 text-base font-medium rounded-md active:scale-[0.98] transition-all duration-150 ${
                    isActive
                      ? "text-brand-blue bg-brand-blue/10"
                      : "text-gray-600 hover:text-brand-dark-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10"
                  }`}
                >
                  <Icon className="w-5 h-5 mr-3 flex-shrink-0" />
                  <span className="flex-grow">{item.name}</span>
                </Link>
              );
            })}

            {/* More Navigation Items */}
            {moreNavigation.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.href;
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setIsMenuOpen(false)}
                  aria-current={isActive ? "page" : undefined}
                  className={`flex items-center min-h-[44px] px-3 py-2 text-base font-medium rounded-md active:scale-[0.98] transition-all duration-150 ${
                    isActive
                      ? "text-brand-blue bg-brand-blue/10"
                      : "text-gray-600 hover:text-brand-dark-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10"
                  }`}
                >
                  <Icon className="w-5 h-5 mr-3 flex-shrink-0" />
                  <span className="flex-grow">{item.name}</span>
                </Link>
              );
            })}

            {/* Settings */}
            <Link
              to="/settings"
              onClick={() => setIsMenuOpen(false)}
              aria-current={
                location.pathname === "/settings" ? "page" : undefined
              }
              className={`flex items-center min-h-[44px] px-3 py-2 text-base font-medium rounded-md active:scale-[0.98] transition-all duration-150 ${
                location.pathname === "/settings"
                  ? "text-brand-blue bg-brand-blue/10"
                  : "text-gray-600 hover:text-brand-dark-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10"
              }`}
            >
              <Settings className="w-5 h-5 mr-3 flex-shrink-0" />
              <span className="flex-grow">Settings</span>
            </Link>

            <div className="border-t border-gray-200/50 dark:border-gray-700/50 pt-4 mt-4">
              {/* Theme Toggle for Mobile - 44px touch target */}
              <button
                onClick={toggleTheme}
                className="w-full flex items-center min-h-[44px] px-3 py-2 text-base font-medium text-gray-600 hover:text-brand-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10 rounded-md active:scale-[0.98] transition-all duration-150"
              >
                {isDarkMode ? (
                  <>
                    <Sun className="w-5 h-5 mr-3 flex-shrink-0" />
                    <span>Light Mode</span>
                  </>
                ) : (
                  <>
                    <Moon className="w-5 h-5 mr-3 flex-shrink-0" />
                    <span>Dark Mode</span>
                  </>
                )}
              </button>

              <div className="px-3 py-2 min-h-[44px] flex items-center text-sm text-gray-600 dark:text-gray-300">
                <User className="w-5 h-5 mr-3 flex-shrink-0" />
                <span className="font-medium truncate">{user?.email}</span>
              </div>
              <button
                onClick={handleSignOut}
                className="w-full flex items-center min-h-[44px] px-3 py-2 text-base font-medium text-gray-600 hover:text-brand-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10 rounded-md active:scale-[0.98] transition-all duration-150"
              >
                <LogOut className="w-5 h-5 mr-3 flex-shrink-0" />
                <span>Sign Out</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

export default Header;
