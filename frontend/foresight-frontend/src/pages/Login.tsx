import React, { useState } from "react";
import { useAuthContext } from "../hooks/useAuthContext";
import { LoadingButton } from "../components/ui/LoadingButton";
import { Search, Sparkles, LayoutDashboard, FileText } from "lucide-react";
import { cn } from "../lib/utils";

const features = [
  {
    icon: Search,
    title: "Discover Grants",
    description: "AI scans federal, state, and foundation sources daily",
  },
  {
    icon: Sparkles,
    title: "AI-Powered Analysis",
    description:
      "Get instant answers about eligibility, deadlines, and alignment",
  },
  {
    icon: LayoutDashboard,
    title: "Track & Organize",
    description: "Manage your grant pipeline with intelligent workflows",
  },
  {
    icon: FileText,
    title: "Apply with Confidence",
    description: "AI-guided wizard helps you build professional proposals",
  },
];

const Login: React.FC = () => {
  const { signIn } = useAuthContext();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      await signIn(email, password);
    } catch (err: unknown) {
      const message =
        err instanceof Error && err.message ? err.message : "Failed to sign in";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Left panel - Product showcase (hidden on mobile, shown on md+) */}
      <div
        className={cn(
          "hidden md:flex md:w-[60%] flex-col justify-center items-center px-12 lg:px-20 py-16",
          "bg-gradient-to-br from-brand-faded-white via-white to-blue-50",
          "dark:from-brand-dark-blue dark:via-dark-surface dark:to-dark-surface-deep",
          "relative overflow-hidden",
        )}
      >
        {/* Subtle decorative background circles */}
        <div className="absolute top-[-10%] right-[-5%] w-96 h-96 rounded-full bg-brand-blue/5 dark:bg-brand-blue/10 blur-3xl" />
        <div className="absolute bottom-[-10%] left-[-5%] w-80 h-80 rounded-full bg-brand-green/5 dark:bg-brand-green/10 blur-3xl" />

        <div className="relative z-10 max-w-lg w-full space-y-10">
          {/* Logo and heading */}
          <div className="text-center space-y-4">
            <div className="flex justify-center">
              <img
                src="/logo-icon.png"
                alt="City of Austin"
                className="h-20 w-20"
              />
            </div>
            <h1 className="text-4xl font-bold text-brand-dark-blue dark:text-white tracking-tight">
              GrantScope2
            </h1>
            <p className="text-lg text-gray-600 dark:text-gray-300">
              AI-Powered Grant Intelligence for the City of Austin
            </p>
          </div>

          {/* Feature highlights */}
          <div className="space-y-5">
            {features.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <div
                  key={feature.title}
                  className={cn(
                    "flex items-start gap-4",
                    "motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-2",
                    index === 0 && "motion-safe:delay-100",
                    index === 1 && "motion-safe:delay-200",
                    index === 2 && "motion-safe:delay-300",
                    index === 3 && "motion-safe:delay-500",
                  )}
                  style={{
                    animationDuration: "0.5s",
                    animationFillMode: "both",
                  }}
                >
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-brand-blue/10 dark:bg-brand-blue/20 flex items-center justify-center">
                    <Icon className="w-5 h-5 text-brand-blue dark:text-brand-blue" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-brand-dark-blue dark:text-white">
                      {feature.title}
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                      {feature.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Social proof */}
          <div className="pt-4 border-t border-gray-200/60 dark:border-gray-700/40">
            <p className="text-xs text-gray-400 dark:text-gray-500 text-center tracking-wide">
              Trusted by City of Austin departments
            </p>
          </div>
        </div>
      </div>

      {/* Mobile header (compact, shown below md) */}
      <div
        className={cn(
          "md:hidden px-6 pt-12 pb-6 text-center",
          "bg-gradient-to-b from-brand-faded-white to-white",
          "dark:from-brand-dark-blue dark:to-dark-surface",
        )}
      >
        <div className="flex justify-center">
          <img
            src="/logo-icon.png"
            alt="City of Austin"
            className="h-14 w-14"
          />
        </div>
        <h1 className="mt-4 text-2xl font-bold text-brand-dark-blue dark:text-white">
          GrantScope2
        </h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
          AI-Powered Grant Intelligence for the City of Austin
        </p>
      </div>

      {/* Right panel - Login form */}
      <div
        className={cn(
          "flex-1 flex items-center justify-center px-6 py-12",
          "bg-white dark:bg-dark-surface",
          "md:w-[40%] md:shadow-[-4px_0_24px_-8px_rgba(0,0,0,0.08)]",
          "dark:md:shadow-[-4px_0_24px_-8px_rgba(0,0,0,0.3)]",
        )}
      >
        <div className="w-full max-w-sm space-y-8">
          <div>
            <h2 className="text-2xl font-bold text-brand-dark-blue dark:text-white">
              Sign in to your account
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Enter your credentials to get started
            </p>
          </div>

          <form className="space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div
                className="bg-extended-red/10 border border-extended-red/30 text-extended-red px-4 py-3 rounded-md"
                role="alert"
              >
                {error}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label
                  htmlFor="email-address"
                  className="block text-sm font-medium text-gray-900 dark:text-white mb-1"
                >
                  Email address
                </label>
                <input
                  id="email-address"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  className="appearance-none relative block w-full px-3 py-2.5 border border-gray-300 dark:border-gray-600 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white dark:bg-brand-dark-blue/50 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue focus:z-10 sm:text-sm transition-colors"
                  placeholder="Email address"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div>
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-gray-900 dark:text-white mb-1"
                >
                  Password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  className="appearance-none relative block w-full px-3 py-2.5 border border-gray-300 dark:border-gray-600 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white dark:bg-brand-dark-blue/50 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-brand-blue focus:z-10 sm:text-sm transition-colors"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <div>
              <LoadingButton
                type="submit"
                loading={loading}
                loadingText="Signing in..."
                className="w-full font-semibold"
              >
                Sign in
              </LoadingButton>
            </div>

            <div className="text-center">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                For pilot testing, please contact the system administrator for
                credentials.
              </p>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Login;
