/**
 * Vitest Test Setup
 *
 * Configures the testing environment with:
 * - @testing-library/jest-dom matchers
 * - Mock implementations for browser APIs
 * - ResizeObserver and IntersectionObserver polyfills
 */

import '@testing-library/jest-dom';
import { beforeEach, vi } from 'vitest';

// Mock ResizeObserver (required for Recharts, React Flow, and virtualization)
// Note: This is a minimal mock. For virtualization tests that need actual
// ResizeObserver callbacks, individual test files should provide their own mock.
class MockResizeObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

window.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;

// Mock IntersectionObserver (required for some components)
class MockIntersectionObserver {
  root = null;
  rootMargin = '';
  thresholds: number[] = [];

  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  takeRecords = vi.fn(() => []);
}

window.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver;

// Stable in-memory storage for tests.
// Node 22 can expose a partial global localStorage object, which breaks tests
// expecting full browser Storage behavior.
const createStorageMock = (): Storage => {
  const store = new Map<string, string>();

  return {
    get length() {
      return store.size;
    },
    clear: () => {
      store.clear();
    },
    getItem: (key: string) => {
      return store.has(key) ? store.get(key)! : null;
    },
    key: (index: number) => {
      const keys = Array.from(store.keys());
      return keys[index] ?? null;
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value));
    },
  } as Storage;
};

const localStorageMock = createStorageMock();
const sessionStorageMock = createStorageMock();

Object.defineProperty(window, 'localStorage', {
  configurable: true,
  value: localStorageMock,
});
Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: localStorageMock,
});

Object.defineProperty(window, 'sessionStorage', {
  configurable: true,
  value: sessionStorageMock,
});
Object.defineProperty(globalThis, 'sessionStorage', {
  configurable: true,
  value: sessionStorageMock,
});

beforeEach(() => {
  localStorageMock.clear();
  sessionStorageMock.clear();
});

// Mock matchMedia (required for responsive components)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock scrollTo (not implemented in jsdom)
window.scrollTo = vi.fn();

// Mock getBoundingClientRect for React Flow
Element.prototype.getBoundingClientRect = vi.fn(() => ({
  width: 800,
  height: 600,
  top: 0,
  left: 0,
  bottom: 600,
  right: 800,
  x: 0,
  y: 0,
  toJSON: vi.fn(),
}));

// Suppress console.error for expected warnings during tests
const originalError = console.error;
console.error = (...args: unknown[]) => {
  // Ignore specific React warnings in tests
  if (
    typeof args[0] === 'string' &&
    (args[0].includes('Warning: ReactDOM.render') ||
     args[0].includes('Warning: An update to') ||
     args[0].includes('act(...)'))
  ) {
    return;
  }
  originalError.call(console, ...args);
};
