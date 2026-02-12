/**
 * Application Configuration
 *
 * Centralised runtime constants derived from environment variables.
 * Import from here instead of duplicating `import.meta.env` look-ups.
 */

export const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";
