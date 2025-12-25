import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, Compass, FolderOpen, Settings, LogOut, Menu, X, Sun, Moon, Inbox, BarChart3 } from 'lucide-react';
import { useAuthContext } from '../hooks/useAuthContext';
import { supabase } from '../App';
import { fetchPendingCount } from '../lib/discovery-api';

const Header: React.FC = () => {
  const { user, signOut } = useAuthContext();
  const location = useLocation();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    // Check localStorage first, then system preference
    const stored = localStorage.getItem('theme');
    if (stored) return stored === 'dark';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    // Apply theme on mount and changes
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [isDarkMode]);

  // Load pending count on mount and periodically
  useEffect(() => {
    const loadPendingCount = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (session?.access_token) {
          const count = await fetchPendingCount(session.access_token);
          setPendingCount(count);
        }
      } catch (err) {
        // Silently fail - don't block header rendering
        console.debug('Could not fetch pending count:', err);
      }
    };

    loadPendingCount();
    // Refresh every 5 minutes
    const interval = setInterval(loadPendingCount, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [user]);

  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode);
  };

  const navigation = [
    { name: 'Dashboard', href: '/', icon: Home },
    { name: 'Discover', href: '/discover', icon: Compass },
    { name: 'Queue', href: '/discover/queue', icon: Inbox, badge: pendingCount > 0 ? pendingCount : undefined },
    { name: 'Workstreams', href: '/workstreams', icon: FolderOpen },
    { name: 'Analytics', href: '/analytics', icon: BarChart3 },
    { name: 'Settings', href: '/settings', icon: Settings },
  ];

  const handleSignOut = async () => {
    try {
      await signOut();
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  return (
    <header className="glass-header fixed w-full top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo and Title */}
          <Link to="/" className="flex items-center gap-3 hover:opacity-90 transition-opacity">
            <img
              src="/logo-horizontal.png"
              alt="City of Austin"
              className="h-8 w-auto"
            />
            <div className="hidden sm:flex flex-col">
              <span className="text-sm font-semibold text-brand-blue leading-tight">Foresight</span>
              <span className="text-xs text-gray-500 dark:text-gray-400 leading-tight">Strategic Research</span>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex space-x-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.href ||
                (item.href === '/discover/queue' && location.pathname.startsWith('/discover/queue'));
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  aria-current={isActive ? 'page' : undefined}
                  className={`inline-flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors duration-150 ${
                    isActive
                      ? 'text-brand-blue bg-brand-blue/10'
                      : 'text-gray-600 hover:text-brand-dark-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10'
                  }`}
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {item.name}
                  {item.badge && (
                    <span className="ml-1.5 inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-bold leading-none text-white bg-brand-blue rounded-full min-w-[1.25rem]">
                      {item.badge > 99 ? '99+' : item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          {/* User Menu */}
          <div className="hidden md:flex items-center space-x-2">
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg text-gray-600 hover:text-brand-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10 transition-colors duration-150"
              aria-label={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDarkMode ? (
                <Sun className="w-5 h-5" />
              ) : (
                <Moon className="w-5 h-5" />
              )}
            </button>

            <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-1"></div>

            <div className="text-sm text-gray-600 dark:text-gray-300">
              <span className="font-medium">{user?.email}</span>
            </div>
            <button
              onClick={handleSignOut}
              className="inline-flex items-center px-3 py-2 text-sm font-medium text-gray-600 hover:text-brand-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10 rounded-md transition-colors duration-150"
            >
              <LogOut className="w-4 h-4 mr-1" />
              Sign Out
            </button>
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
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.href ||
                (item.href === '/discover/queue' && location.pathname.startsWith('/discover/queue'));
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setIsMenuOpen(false)}
                  aria-current={isActive ? 'page' : undefined}
                  className={`flex items-center min-h-[44px] px-3 py-2 text-base font-medium rounded-md active:scale-[0.98] transition-all duration-150 ${
                    isActive
                      ? 'text-brand-blue bg-brand-blue/10'
                      : 'text-gray-600 hover:text-brand-dark-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10'
                  }`}
                >
                  <Icon className="w-5 h-5 mr-3 flex-shrink-0" />
                  <span className="flex-grow">{item.name}</span>
                  {item.badge && (
                    <span className="ml-auto inline-flex items-center justify-center px-2 py-0.5 text-xs font-bold leading-none text-white bg-brand-blue rounded-full">
                      {item.badge > 99 ? '99+' : item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
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
