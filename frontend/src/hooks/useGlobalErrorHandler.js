import { useEffect } from 'react';

/**
 * Custom hook to handle global errors and unhandled promise rejections
 * Sets up event listeners for catching uncaught errors application-wide
 *
 * @param {Function} setAppError - Callback to set application error state
 */
export function useGlobalErrorHandler(setAppError) {
  useEffect(() => {
    const handleGlobalError = (event) => {
      console.error("🚨 Global error caught:", event.error);
      setAppError({
        message: event.error?.message || 'Unknown error occurred',
        stack: event.error?.stack || '',
        type: 'Global Error',
      });
    };

    const handleUnhandledRejection = (event) => {
      console.error("🚨 Unhandled promise rejection:", event.reason);
      setAppError({
        message: event.reason?.message || 'Unhandled promise rejection',
        stack: event.reason?.stack || '',
        type: 'Promise Rejection',
      });
    };

    window.addEventListener('error', handleGlobalError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('error', handleGlobalError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, [setAppError]);
}
