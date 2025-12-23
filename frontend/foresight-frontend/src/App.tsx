import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { createClient } from '@supabase/supabase-js';
import { TooltipProvider } from '@radix-ui/react-tooltip';
import Header from './components/Header';
import Dashboard from './pages/Dashboard';
import Discover from './pages/Discover';
import DiscoveryQueue from './pages/DiscoveryQueue';
import DiscoveryHistory from './pages/DiscoveryHistory';
import CardDetail from './pages/CardDetail';
import Workstreams from './pages/Workstreams';
import WorkstreamFeed from './pages/WorkstreamFeed';
import Settings from './pages/Settings';
import Login from './pages/Login';
import { User } from '@supabase/supabase-js';
import { AuthContextProvider, useAuthContext } from './hooks/useAuthContext';

// Supabase configuration
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';
export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export interface AuthContextType {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextType | undefined>(undefined);

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw error;
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  };

  const authValue: AuthContextType = {
    user,
    loading,
    signIn,
    signOut,
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-brand-faded-white dark:bg-brand-dark-blue">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-brand-blue"></div>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={200}>
      <AuthContextProvider value={authValue}>
        <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <div className="min-h-screen bg-brand-faded-white dark:bg-brand-dark-blue transition-colors">
            {user && <Header />}
            <main className={user ? "pt-16" : ""}>
              <Routes>
              <Route
                path="/login"
                element={
                  user ? (
                    <Navigate to="/" replace />
                  ) : (
                    <Login />
                  )
                }
              />
              <Route
                path="/"
                element={
                  user ? (
                    <Dashboard />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              <Route
                path="/discover"
                element={
                  user ? (
                    <Discover />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              <Route
                path="/discover/queue"
                element={
                  user ? (
                    <DiscoveryQueue />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              <Route
                path="/discover/history"
                element={
                  user ? (
                    <DiscoveryHistory />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              <Route
                path="/cards/:slug"
                element={
                  user ? (
                    <CardDetail />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              <Route
                path="/workstreams"
                element={
                  user ? (
                    <Workstreams />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              <Route
                path="/workstreams/:id"
                element={
                  user ? (
                    <WorkstreamFeed />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              <Route
                path="/settings"
                element={
                  user ? (
                    <Settings />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
              </Routes>
            </main>
          </div>
        </Router>
      </AuthContextProvider>
    </TooltipProvider>
  );
}

export default App;
