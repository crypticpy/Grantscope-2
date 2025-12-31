import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'
import './index.css'
import App from './App.tsx'

// Handle chunk load failures by auto-reloading the page once
// This fixes issues when a new deployment changes chunk hashes
// and users have a cached HTML file referencing old chunks
window.addEventListener('error', (event) => {
  const target = event.target as HTMLElement | null;
  // Check if it's a script load error
  if (target?.tagName === 'SCRIPT') {
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
window.addEventListener('unhandledrejection', (event) => {
  const error = event.reason;
  const isChunkError = 
    error?.message?.includes('Failed to fetch dynamically imported module') ||
    error?.message?.includes('Failed to load module script') ||
    error?.message?.includes('Loading chunk') ||
    error?.message?.includes('Loading CSS chunk');
  
  if (isChunkError) {
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
