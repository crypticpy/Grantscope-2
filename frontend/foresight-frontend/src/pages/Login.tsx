import React, { useState } from 'react';
import { useAuthContext } from '../hooks/useAuthContext';
import { LoadingButton } from '../components/ui/LoadingButton';

const Login: React.FC = () => {
  const { signIn } = useAuthContext();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await signIn(email, password);
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to sign in';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-brand-faded-white dark:bg-brand-dark-blue py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          {/* Logo */}
          <div className="flex justify-center">
            <img
              src="/logo-icon.png"
              alt="City of Austin"
              className="h-16 w-16"
            />
          </div>
          <h2 className="mt-6 text-center text-3xl font-bold text-brand-dark-blue dark:text-white">
            Austin Foresight
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">
            Strategic Research & Intelligence System
          </p>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="bg-extended-red/10 border border-extended-red/30 text-extended-red px-4 py-3 rounded-md" role="alert">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label htmlFor="email-address" className="block text-sm font-medium text-gray-900 dark:text-white mb-1">
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
              <label htmlFor="password" className="block text-sm font-medium text-gray-900 dark:text-white mb-1">
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
              For pilot testing, please contact the system administrator for credentials.
            </p>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;
