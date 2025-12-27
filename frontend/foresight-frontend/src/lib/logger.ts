/**
 * Production-safe logger utility
 *
 * This module provides logging functions that are automatically disabled in production.
 * Use these instead of direct console.* calls to prevent debug information from
 * leaking to end users in production builds.
 *
 * IMPORTANT: console.error is intentionally NOT wrapped here - errors should always
 * be logged for debugging production issues. Use console.error directly for legitimate
 * error handling.
 *
 * @example
 * ```typescript
 * import { logger } from '@/lib/logger';
 *
 * // These are silenced in production
 * logger.debug('Fetching data...', { id: 123 });
 * logger.warn('Deprecated API usage');
 * logger.log('User action completed');
 *
 * // For errors, use console.error directly (not wrapped)
 * console.error('Critical error:', error);
 * ```
 */

/**
 * Determines if the current environment is production.
 * In Vite, import.meta.env.PROD is true when running `vite build`.
 */
const isProduction = import.meta.env.PROD;

/**
 * No-operation function for silencing logs in production.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const noop = (..._args: unknown[]): void => {
  // Intentionally empty - silences logs in production
};

/**
 * Production-safe logger object.
 *
 * All methods are no-ops in production builds to prevent
 * sensitive debug information from being exposed to end users.
 *
 * Note: console.error is intentionally excluded - errors should
 * always be logged regardless of environment for debugging purposes.
 */
export const logger = {
  /**
   * Logs debug-level messages. Silenced in production.
   * Use for detailed debugging information during development.
   */
  debug: isProduction ? noop : console.debug.bind(console),

  /**
   * Logs general information. Silenced in production.
   * Use for standard logging during development.
   */
  log: isProduction ? noop : console.log.bind(console),

  /**
   * Logs warning messages. Silenced in production.
   * Use for non-critical issues or deprecation warnings.
   */
  warn: isProduction ? noop : console.warn.bind(console),

  /**
   * Logs informational messages. Silenced in production.
   * Use for status updates or informational output.
   */
  info: isProduction ? noop : console.info.bind(console),
} as const;

/**
 * Type definition for the logger object.
 * Useful for dependency injection or testing scenarios.
 */
export type Logger = typeof logger;
