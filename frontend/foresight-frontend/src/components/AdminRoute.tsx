import React, { Suspense } from "react";
import { Navigate } from "react-router-dom";
import { useAuthContext } from "../hooks/useAuthContext";
import { ErrorBoundary } from "./ErrorBoundary";
import { PageLoadingSpinner } from "./PageLoadingSpinner";

/**
 * Props for the AdminRoute component.
 */
export interface AdminRouteProps {
  /** The element to render if the user is an authenticated admin */
  element: React.ReactNode;
  /** Optional custom loading message for the spinner */
  loadingMessage?: string;
  /** Path to redirect non-admin users to (default: /) */
  redirectTo?: string;
  /** Whether to wrap in Suspense boundary (default: true) */
  withSuspense?: boolean;
}

/**
 * AdminRoute Component
 *
 * A route guard that combines authentication checking with admin role verification.
 * Redirects unauthenticated users to /login and non-admin users to /.
 * Wraps lazy-loaded components in Suspense with loading spinner and ErrorBoundary.
 *
 * Admin roles: "admin" and "service_role" are granted access.
 *
 * @example
 * // Basic usage with lazy component
 * <Route
 *   path="/admin"
 *   element={<AdminRoute element={<AdminLayout />} />}
 * />
 *
 * @example
 * // With custom loading message
 * <Route
 *   path="/admin/users"
 *   element={
 *     <AdminRoute
 *       element={<AdminUsers />}
 *       loadingMessage="Loading user management..."
 *     />
 *   }
 * />
 */
export function AdminRoute({
  element,
  loadingMessage,
  redirectTo = "/",
  withSuspense = true,
}: AdminRouteProps) {
  const { user } = useAuthContext();

  // Redirect to login if not authenticated
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // Redirect non-admin users to the specified path
  const isAdmin = user.role === "admin" || user.role === "service_role";
  if (!isAdmin) {
    return <Navigate to={redirectTo} replace />;
  }

  const handleRetry = () => {
    // ErrorBoundary will reset its state and re-render children,
    // giving React.lazy another chance to load the module.
  };

  const content = withSuspense ? (
    <Suspense fallback={<PageLoadingSpinner message={loadingMessage} />}>
      {element}
    </Suspense>
  ) : (
    element
  );

  return <ErrorBoundary onRetry={handleRetry}>{content}</ErrorBoundary>;
}

export default AdminRoute;
