import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, Compass, FolderOpen, Settings, LogOut, Menu, X } from 'lucide-react';
import { useAuthContext } from '../hooks/useAuthContext';

const Header: React.FC = () => {
  const { user, signOut } = useAuthContext();
  const location = useLocation();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const navigation = [
    { name: 'Dashboard', href: '/', icon: Home },
    { name: 'Discover', href: '/discover', icon: Compass },
    { name: 'Workstreams', href: '/workstreams', icon: FolderOpen },
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
              const isActive = location.pathname === item.href;
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
                </Link>
              );
            })}
          </nav>

          {/* User Menu */}
          <div className="hidden md:flex items-center space-x-4">
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

          {/* Mobile menu button */}
          <div className="md:hidden">
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              aria-expanded={isMenuOpen}
              aria-label="Toggle navigation menu"
              className="inline-flex items-center justify-center p-2 rounded-md text-gray-600 hover:text-brand-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-brand-blue transition-colors duration-150"
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

      {/* Mobile Navigation */}
      {isMenuOpen && (
        <div className="md:hidden">
          <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3 bg-white/95 dark:bg-brand-dark-blue/95 backdrop-blur-md border-t border-gray-200/50 dark:border-gray-700/50">
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.href;
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setIsMenuOpen(false)}
                  aria-current={isActive ? 'page' : undefined}
                  className={`block px-3 py-2 text-base font-medium rounded-md transition-colors duration-150 ${
                    isActive
                      ? 'text-brand-blue bg-brand-blue/10'
                      : 'text-gray-600 hover:text-brand-dark-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10'
                  }`}
                >
                  <div className="flex items-center">
                    <Icon className="w-5 h-5 mr-3" />
                    {item.name}
                  </div>
                </Link>
              );
            })}
            <div className="border-t border-gray-200/50 dark:border-gray-700/50 pt-4 mt-4">
              <div className="px-3 py-2 text-sm text-gray-600 dark:text-gray-300">
                <span className="font-medium">{user?.email}</span>
              </div>
              <button
                onClick={handleSignOut}
                className="block w-full text-left px-3 py-2 text-base font-medium text-gray-600 hover:text-brand-blue hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/10 rounded-md transition-colors duration-150"
              >
                <div className="flex items-center">
                  <LogOut className="w-5 h-5 mr-3" />
                  Sign Out
                </div>
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

export default Header;
