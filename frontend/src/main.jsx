import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import AppWithAuth0 from './AppWithAuth0.jsx'

// Store the root instance
let rootInstance = null;

// Global error handler for the entire app
window.addEventListener('error', (event) => {
  console.error('🚨 Main.jsx caught global error:', event.error);
  
  // Check if it's a React internal error we should ignore
  const errorMessage = event.error?.message || '';
  if (errorMessage.includes('removeChild') || errorMessage.includes('insertBefore')) {
    console.warn('Ignoring React DOM manipulation error - this is likely a React internal issue');
    event.preventDefault();
    return;
  }
  
  // Only show error UI for critical errors
  if (errorMessage.includes('ChunkLoadError') || errorMessage.includes('NetworkError')) {
    const root = document.getElementById('root');
    if (root && rootInstance) {
      rootInstance.unmount();
      root.innerHTML = `
        <div style="padding: 20px; color: red; background-color: #ffe6e6; border: 2px solid red; margin: 20px;">
          <h2>🚨 Critical App Error!</h2>
          <p><strong>Error:</strong> ${event.error?.message || 'Unknown error occurred'}</p>
          <details style="white-space: pre-wrap;">
            <summary>Stack Trace</summary>
            <pre>${event.error?.stack || 'No stack trace available'}</pre>
          </details>
          <button onclick="window.location.reload()" style="margin-top: 10px; padding: 10px;">
            🔄 Reload Page
          </button>
        </div>
      `;
    }
  }
});

window.addEventListener('unhandledrejection', (event) => {
  console.error('🚨 Main.jsx caught unhandled promise rejection:', event.reason);
  // Log but don't destroy the app for promise rejections
});

try {
  rootInstance = createRoot(document.getElementById('root'));
  rootInstance.render(
    <StrictMode>
      <AppWithAuth0 />
    </StrictMode>,
  )
} catch (error) {
  console.error('🚨 Error during app initialization:', error);
  const root = document.getElementById('root');
  if (root) {
    root.innerHTML = `
      <div style="padding: 20px; color: red; background-color: #ffe6e6; border: 2px solid red; margin: 20px;">
        <h2>🚨 App Initialization Error!</h2>
        <p><strong>Error:</strong> ${error?.message || 'Unknown initialization error'}</p>
        <details style="white-space: pre-wrap;">
          <summary>Stack Trace</summary>
          <pre>${error?.stack || 'No stack trace available'}</pre>
        </details>
        <button onclick="window.location.reload()" style="margin-top: 10px; padding: 10px;">
          🔄 Reload Page
        </button>
      </div>
    `;
  }
}