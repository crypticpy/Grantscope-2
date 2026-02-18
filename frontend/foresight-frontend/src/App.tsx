import { useState, useEffect, useCallback, lazy } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useParams,
  useLocation,
} from "react-router-dom";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import Header from "./components/Header";
import { AuthContextProvider } from "./hooks/useAuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { API_BASE_URL } from "./lib/config";

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

// Proposal pages
const ProposalEditor = lazy(() => import("./pages/ProposalEditor"));

// Grant Application Wizard
const GrantWizard = lazy(() => import("./pages/GrantWizard"));

// Profile Setup Wizard
const ProfileSetup = lazy(() => import("./pages/ProfileSetup"));

// Standalone pages
const Settings = lazy(() => import("./pages/Settings"));
const Analytics = lazy(() => import("./pages/AnalyticsV2"));
const Methodology = lazy(() => import("./pages/Methodology"));
const Signals = lazy(() => import("./pages/Signals"));
const AskGrantScope = lazy(() => import("./pages/AskGrantScope"));
const Feeds = lazy(() => import("./pages/Feeds"));

// Guide pages
const GuideSignals = lazy(() => import("./pages/GuideSignals"));
const GuideDiscover = lazy(() => import("./pages/GuideDiscover"));
const GuideWorkstreams = lazy(() => import("./pages/GuideWorkstreams"));

// ---------------------------------------------------------------------------
// Custom user type
// ---------------------------------------------------------------------------
export interface GS2User {
  id: string;
  email: string;
  display_name: string;
  department: string;
  role: string;
  created_at?: string;
  department_id?: string;
  title?: string;
  bio?: string;
  profile_completed_at?: string | null;
  profile_step?: number;
}

export interface AuthContextType {
  user: GS2User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------
const API_URL = API_BASE_URL;
const TOKEN_KEY = "gs2_token";
const USER_KEY = "gs2_user";

/**
 * Read the stored JWT from localStorage.
 * Exported so API client files can call it directly.
 */
export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

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
  const [user, setUser] = useState<GS2User | null>(null);
  const [loading, setLoading] = useState(true);

  // Validate an existing token on mount
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    const storedUser = localStorage.getItem(USER_KEY);

    if (!token) {
      setLoading(false);
      return;
    }

    // Optimistically restore user from localStorage while we validate
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch {
        // ignore parse errors
      }
    }

    // Validate the token against the backend
    fetch(`${API_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) {
          // Token expired or invalid -- clear
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
          setUser(null);
          return null;
        }
        return res.json();
      })
      .then((data) => {
        if (data) {
          setUser(data);
          localStorage.setItem(USER_KEY, JSON.stringify(data));
        }
      })
      .catch(() => {
        // Network error on validation -- keep the optimistic user
        // so the app doesn't flash to login on transient failures
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Invalid email or password");
    }

    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    setUser(data.user);
  }, []);

  const signOut = useCallback(async () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
  }, []);

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
                      loadingMessage="Loading opportunity details..."
                    />
                  }
                />
                <Route
                  path="/signals"
                  element={
                    <ProtectedRoute
                      element={<Signals />}
                      loadingMessage="Loading opportunities..."
                    />
                  }
                />

                {/* Ask GrantScope - AI chat interface */}
                <Route
                  path="/ask"
                  element={
                    <ProtectedRoute
                      element={<AskGrantScope />}
                      loadingMessage="Loading Ask GrantScope..."
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

                {/* Feeds management */}
                <Route
                  path="/feeds"
                  element={
                    <ProtectedRoute
                      element={<Feeds />}
                      loadingMessage="Loading feeds..."
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

                {/* Grant-oriented route aliases */}
                <Route
                  path="/opportunities"
                  element={
                    <ProtectedRoute
                      element={<Signals />}
                      loadingMessage="Loading opportunities..."
                    />
                  }
                />
                <Route
                  path="/opportunities/:slug"
                  element={
                    <ProtectedRoute
                      element={<CardDetail />}
                      loadingMessage="Loading opportunity details..."
                    />
                  }
                />
                <Route
                  path="/programs"
                  element={
                    <ProtectedRoute
                      element={<Workstreams />}
                      loadingMessage="Loading programs..."
                    />
                  }
                />
                <Route
                  path="/programs/:id/board"
                  element={
                    <ProtectedRoute
                      element={<WorkstreamKanban />}
                      loadingMessage="Loading pipeline..."
                    />
                  }
                />
                <Route
                  path="/programs/:id"
                  element={
                    <ProtectedRoute
                      element={<WorkstreamFeed />}
                      loadingMessage="Loading program..."
                    />
                  }
                />
                <Route
                  path="/guide/programs"
                  element={
                    <ProtectedRoute
                      element={<GuideWorkstreams />}
                      loadingMessage="Loading guide..."
                    />
                  }
                />
                <Route
                  path="/guide/opportunities"
                  element={
                    <ProtectedRoute
                      element={<GuideSignals />}
                      loadingMessage="Loading guide..."
                    />
                  }
                />

                {/* Proposal editor */}
                <Route
                  path="/proposals/:id"
                  element={
                    <ProtectedRoute
                      element={<ProposalEditor />}
                      loadingMessage="Loading proposal editor..."
                    />
                  }
                />

                {/* Profile Setup Wizard */}
                <Route
                  path="/profile-setup"
                  element={
                    <ProtectedRoute
                      element={<ProfileSetup />}
                      loadingMessage="Loading profile setup..."
                    />
                  }
                />

                {/* Grant Application Wizard */}
                <Route
                  path="/apply"
                  element={
                    <ProtectedRoute
                      element={<GrantWizard />}
                      loadingMessage="Loading grant wizard..."
                    />
                  }
                />
                <Route
                  path="/apply/:sessionId"
                  element={
                    <ProtectedRoute
                      element={<GrantWizard />}
                      loadingMessage="Loading grant wizard..."
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
