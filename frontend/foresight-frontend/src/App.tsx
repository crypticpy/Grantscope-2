import { useState, useEffect, lazy } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useParams,
  useLocation,
} from "react-router-dom";
import { createClient, User } from "@supabase/supabase-js";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import Header from "./components/Header";
import { AuthContextProvider } from "./hooks/useAuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";

// Synchronous imports for critical path components (login + landing page)
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";

// Lazy-loaded page components for route-based code splitting
// Discovery pages - share common discovery patterns
const Discover = lazy(() => import("./pages/Discover"));
const DiscoveryQueue = lazy(() => import("./pages/DiscoveryQueue"));
const DiscoveryHistory = lazy(() => import("./pages/DiscoveryHistory"));

// Card visualization pages - share React Flow and related viz libraries
const CardDetail = lazy(() => import("./pages/CardDetail"));
const Compare = lazy(() => import("./pages/Compare"));

// Workstream pages - share workstream components
const Workstreams = lazy(() => import("./pages/Workstreams"));
const WorkstreamFeed = lazy(() => import("./pages/WorkstreamFeed"));
const WorkstreamKanban = lazy(() => import("./pages/WorkstreamKanban"));

// Standalone pages
const Settings = lazy(() => import("./pages/Settings"));
const Analytics = lazy(() => import("./pages/AnalyticsV2"));
const Methodology = lazy(() => import("./pages/Methodology"));
const Signals = lazy(() => import("./pages/Signals"));
const AskForesight = lazy(() => import("./pages/AskForesight"));

// Guide pages
const GuideSignals = lazy(() => import("./pages/GuideSignals"));
const GuideDiscover = lazy(() => import("./pages/GuideDiscover"));
const GuideWorkstreams = lazy(() => import("./pages/GuideWorkstreams"));

// Supabase configuration
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.error(
    "Missing Supabase environment variables. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.",
  );
}

export const supabase =
  supabaseUrl && supabaseAnonKey
    ? createClient(supabaseUrl, supabaseAnonKey)
    : (null as unknown as ReturnType<typeof createClient>);

export interface AuthContextType {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

// AuthContext is provided by AuthContextProvider from hooks/useAuthContext

function CardRedirect() {
  const { slug } = useParams<{ slug: string }>();
  const location = useLocation();
  return (
    <Navigate
      to={`/signals/${slug || ""}${location.search}`}
      state={location.state}
      replace
    />
  );
}

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
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-blue mx-auto"></div>
          <p className="mt-4 text-gray-500 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={200}>
      <AuthContextProvider value={authValue}>
        <Router
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <div className="min-h-screen bg-brand-faded-white dark:bg-brand-dark-blue transition-colors">
            <a
              href="#main-content"
              className="sr-only focus:not-sr-only focus:absolute focus:z-[100] focus:bg-brand-blue focus:text-white focus:p-3 focus:rounded-md"
            >
              Skip to main content
            </a>
            {user && <Header />}
            <main id="main-content" className={user ? "pt-16" : ""}>
              <Routes>
                {/* Login route - public, redirects to home if already authenticated */}
                <Route
                  path="/login"
                  element={user ? <Navigate to="/" replace /> : <Login />}
                />

                {/* Dashboard - synchronous landing page (critical path) */}
                <Route
                  path="/"
                  element={
                    <ProtectedRoute
                      element={<Dashboard />}
                      withSuspense={false}
                    />
                  }
                />

                {/* Discovery pages - lazy-loaded with Suspense */}
                <Route
                  path="/discover"
                  element={
                    <ProtectedRoute
                      element={<Discover />}
                      loadingMessage="Loading discovery..."
                    />
                  }
                />
                <Route
                  path="/discover/queue"
                  element={
                    <ProtectedRoute
                      element={<DiscoveryQueue />}
                      loadingMessage="Loading queue..."
                    />
                  }
                />
                <Route
                  path="/discover/history"
                  element={
                    <ProtectedRoute
                      element={<DiscoveryHistory />}
                      loadingMessage="Loading history..."
                    />
                  }
                />

                {/* Signal pages */}
                <Route
                  path="/signals/:slug"
                  element={
                    <ProtectedRoute
                      element={<CardDetail />}
                      loadingMessage="Loading signal details..."
                    />
                  }
                />
                <Route
                  path="/signals"
                  element={
                    <ProtectedRoute
                      element={<Signals />}
                      loadingMessage="Loading signals..."
                    />
                  }
                />

                {/* Ask Foresight - AI chat interface */}
                <Route
                  path="/ask"
                  element={
                    <ProtectedRoute
                      element={<AskForesight />}
                      loadingMessage="Loading Ask Foresight..."
                    />
                  }
                />

                {/* Legacy card routes - redirect to signals */}
                <Route
                  path="/cards/:slug"
                  element={
                    <ProtectedRoute
                      element={<CardRedirect />}
                      withSuspense={false}
                    />
                  }
                />

                {/* Comparison page - lazy-loaded with React Flow */}
                <Route
                  path="/compare"
                  element={
                    <ProtectedRoute
                      element={<Compare />}
                      loadingMessage="Loading comparison..."
                    />
                  }
                />

                {/* Workstream pages - lazy-loaded */}
                <Route
                  path="/workstreams/:id/board"
                  element={
                    <ProtectedRoute
                      element={<WorkstreamKanban />}
                      loadingMessage="Loading kanban board..."
                    />
                  }
                />
                <Route
                  path="/workstreams"
                  element={
                    <ProtectedRoute
                      element={<Workstreams />}
                      loadingMessage="Loading workstreams..."
                    />
                  }
                />
                <Route
                  path="/workstreams/:id"
                  element={
                    <ProtectedRoute
                      element={<WorkstreamFeed />}
                      loadingMessage="Loading workstream..."
                    />
                  }
                />

                {/* Settings and Analytics - lazy-loaded standalone pages */}
                <Route
                  path="/settings"
                  element={
                    <ProtectedRoute
                      element={<Settings />}
                      loadingMessage="Loading settings..."
                    />
                  }
                />
                <Route
                  path="/analytics"
                  element={
                    <ProtectedRoute
                      element={<Analytics />}
                      loadingMessage="Loading analytics..."
                    />
                  }
                />
                <Route
                  path="/methodology"
                  element={
                    <ProtectedRoute
                      element={<Methodology />}
                      loadingMessage="Loading methodology..."
                    />
                  }
                />

                {/* Guide pages */}
                <Route
                  path="/guide/signals"
                  element={
                    <ProtectedRoute
                      element={<GuideSignals />}
                      loadingMessage="Loading guide..."
                    />
                  }
                />
                <Route
                  path="/guide/discover"
                  element={
                    <ProtectedRoute
                      element={<GuideDiscover />}
                      loadingMessage="Loading guide..."
                    />
                  }
                />
                <Route
                  path="/guide/workstreams"
                  element={
                    <ProtectedRoute
                      element={<GuideWorkstreams />}
                      loadingMessage="Loading guide..."
                    />
                  }
                />

                {/* 404 catch-all - redirect to home */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>
          </div>
        </Router>
      </AuthContextProvider>
    </TooltipProvider>
  );
}

export default App;
