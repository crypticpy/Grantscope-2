import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'
import './index.css'
import App from './App.tsx'

// Handle chunk load failures by auto-reloading the page once
// This fixes issues when a new deployment changes chunk hashes
// and users have a cached HTML file referencing old chunks
// IMPORTANT: Don't reload during exports to prevent data loss
window.addEventListener('error', (event) => {
  const target = event.target as HTMLElement | null;
  // Check if it's a script load error
  if (target?.tagName === 'SCRIPT') {
    // Don't reload if we're in the middle of an export (check for export modal)
    const isExportInProgress = document.querySelector('[role="dialog"][aria-labelledby="export-modal-title"]');
    if (isExportInProgress) {
      console.warn('Script load error detected but export in progress, skipping reload');
      return;
    }
    
    const reloadKey = 'chunk-reload-attempted';
    const hasReloaded = sessionStorage.getItem(reloadKey);
    
    if (!hasReloaded) {
      sessionStorage.setItem(reloadKey, 'true');
      console.warn('Script load failed, reloading page to fetch latest assets...');
      window.location.reload();
    }
  }
}, true);

// Handle unhandled promise rejections for dynamic imports
// IMPORTANT: Only reload for actual chunk/module load failures, NOT regular API errors
window.addEventListener('unhandledrejection', (event) => {
  const error = event.reason;
  const errorMessage = error?.message || '';
  
  // Only treat as chunk error if it's specifically about module/chunk loading
  // AND it's not a regular network request (which would have different error patterns)
  const isChunkError = (
    errorMessage.includes('Failed to fetch dynamically imported module') ||
    errorMessage.includes('Failed to load module script') ||
    errorMessage.includes('Loading chunk') ||
    errorMessage.includes('Loading CSS chunk')
  ) && (
    // Additional check: chunk errors typically include file paths with .js or .mjs
    errorMessage.includes('.js') ||
    errorMessage.includes('.mjs') ||
    errorMessage.includes('.css')
  );
  
  // Don't reload if we're in the middle of an export (check for export modal)
  const isExportInProgress = document.querySelector('[role="dialog"][aria-labelledby="export-modal-title"]');
  
  if (isChunkError && !isExportInProgress) {
    const reloadKey = 'chunk-reload-attempted';
    const hasReloaded = sessionStorage.getItem(reloadKey);
    
    if (!hasReloaded) {
      sessionStorage.setItem(reloadKey, 'true');
      console.warn('Dynamic import failed, reloading page to fetch latest assets...');
      window.location.reload();
    }
  }
});

// Clear the reload flag on successful page load after a short delay
// This allows future chunk errors to trigger a reload again
setTimeout(() => {
  sessionStorage.removeItem('chunk-reload-attempted');
}, 5000);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
