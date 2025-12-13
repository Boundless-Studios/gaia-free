/**
 * Frontend Logging Utility
 *
 * Provides controlled logging with:
 * - Log levels: debug, info, warn, error
 * - Namespace filtering for targeted debugging
 * - Environment-aware defaults (verbose in dev only when enabled)
 *
 * Usage:
 *   import { createLogger } from './utils/logger';
 *   const log = createLogger('MyComponent');
 *   log.debug('Detailed info');  // Only shows when DEBUG enabled
 *   log.info('General info');    // Only shows when LOG_LEVEL <= info
 *   log.warn('Warning');         // Shows in dev, can be filtered in prod
 *   log.error('Error');          // Always shows
 *
 * Configuration (via localStorage or env):
 *   localStorage.setItem('GAIA_LOG_LEVEL', 'debug');  // debug|info|warn|error|silent
 *   localStorage.setItem('GAIA_LOG_NAMESPACES', 'Socket,Auth');  // comma-separated
 */

const LOG_LEVELS = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
  silent: 4,
};

// Check if we're in development mode
const isDev = typeof import.meta !== 'undefined'
  ? import.meta.env?.DEV
  : process.env.NODE_ENV !== 'production';

/**
 * Get the current log level from localStorage or environment
 */
function getLogLevel() {
  // Check localStorage first (allows runtime control)
  if (typeof localStorage !== 'undefined') {
    const stored = localStorage.getItem('GAIA_LOG_LEVEL');
    if (stored && LOG_LEVELS[stored] !== undefined) {
      return LOG_LEVELS[stored];
    }
  }

  // Check environment variable
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_LOG_LEVEL) {
    const envLevel = import.meta.env.VITE_LOG_LEVEL.toLowerCase();
    if (LOG_LEVELS[envLevel] !== undefined) {
      return LOG_LEVELS[envLevel];
    }
  }

  // Default: warn in production, info in dev (not debug by default to reduce noise)
  return isDev ? LOG_LEVELS.warn : LOG_LEVELS.error;
}

/**
 * Get enabled namespaces from localStorage
 * If set, only these namespaces will log (for debug/info levels)
 */
function getEnabledNamespaces() {
  if (typeof localStorage !== 'undefined') {
    const stored = localStorage.getItem('GAIA_LOG_NAMESPACES');
    if (stored) {
      return stored.split(',').map(s => s.trim().toLowerCase());
    }
  }
  return null; // null means all namespaces enabled
}

/**
 * Check if a namespace should log at debug/info level
 */
function isNamespaceEnabled(namespace, enabledNamespaces) {
  if (!enabledNamespaces) return true; // All enabled if not filtered
  const lowerNs = namespace.toLowerCase();
  return enabledNamespaces.some(enabled =>
    lowerNs.includes(enabled) || enabled.includes(lowerNs)
  );
}

/**
 * Create a logger for a specific namespace/component
 * @param {string} namespace - Name of the component/module (e.g., 'Socket', 'Auth', 'App')
 * @returns {Object} Logger with debug, info, warn, error methods
 */
export function createLogger(namespace) {
  const prefix = `[${namespace}]`;

  return {
    /**
     * Debug level - very verbose, for development troubleshooting
     * Only shows when log level is 'debug' AND namespace is enabled
     */
    debug: (...args) => {
      const level = getLogLevel();
      if (level > LOG_LEVELS.debug) return;

      const enabledNs = getEnabledNamespaces();
      if (!isNamespaceEnabled(namespace, enabledNs)) return;

      console.log(prefix, ...args);
    },

    /**
     * Info level - general operational info
     * Shows when log level is 'info' or lower
     */
    info: (...args) => {
      const level = getLogLevel();
      if (level > LOG_LEVELS.info) return;

      const enabledNs = getEnabledNamespaces();
      if (!isNamespaceEnabled(namespace, enabledNs)) return;

      console.log(prefix, ...args);
    },

    /**
     * Warn level - potential issues
     * Shows when log level is 'warn' or lower
     */
    warn: (...args) => {
      const level = getLogLevel();
      if (level > LOG_LEVELS.warn) return;

      console.warn(prefix, ...args);
    },

    /**
     * Error level - always shows (unless silent)
     */
    error: (...args) => {
      const level = getLogLevel();
      if (level >= LOG_LEVELS.silent) return;

      console.error(prefix, ...args);
    },

    /**
     * Group related logs together (for complex operations)
     */
    group: (label) => {
      const level = getLogLevel();
      if (level > LOG_LEVELS.debug) return;

      const enabledNs = getEnabledNamespaces();
      if (!isNamespaceEnabled(namespace, enabledNs)) return;

      console.groupCollapsed(`${prefix} ${label}`);
    },

    groupEnd: () => {
      const level = getLogLevel();
      if (level > LOG_LEVELS.debug) return;

      const enabledNs = getEnabledNamespaces();
      if (!isNamespaceEnabled(namespace, enabledNs)) return;

      console.groupEnd();
    },
  };
}

/**
 * Set log level at runtime (useful for debugging in production)
 * @param {'debug'|'info'|'warn'|'error'|'silent'} level
 */
export function setLogLevel(level) {
  if (LOG_LEVELS[level] !== undefined) {
    localStorage.setItem('GAIA_LOG_LEVEL', level);
    console.log(`[Logger] Log level set to: ${level}`);
  } else {
    console.error(`[Logger] Invalid log level: ${level}. Use: debug, info, warn, error, silent`);
  }
}

/**
 * Set namespace filter at runtime
 * @param {string|string[]|null} namespaces - Namespaces to enable, or null for all
 */
export function setLogNamespaces(namespaces) {
  if (namespaces === null) {
    localStorage.removeItem('GAIA_LOG_NAMESPACES');
    console.log('[Logger] Namespace filter cleared - all namespaces enabled');
  } else {
    const nsArray = Array.isArray(namespaces) ? namespaces : [namespaces];
    localStorage.setItem('GAIA_LOG_NAMESPACES', nsArray.join(','));
    console.log(`[Logger] Enabled namespaces: ${nsArray.join(', ')}`);
  }
}

/**
 * Convenience: expose control functions globally for console debugging
 */
if (typeof window !== 'undefined') {
  window.gaiaLog = {
    setLevel: setLogLevel,
    setNamespaces: setLogNamespaces,
    levels: Object.keys(LOG_LEVELS),
    help: () => {
      console.log(`
Gaia Logging Control:
  gaiaLog.setLevel('debug')     - Show all logs
  gaiaLog.setLevel('info')      - Show info, warn, error
  gaiaLog.setLevel('warn')      - Show warn, error only (default in dev)
  gaiaLog.setLevel('error')     - Show errors only (default in prod)
  gaiaLog.setLevel('silent')    - Silence all logs

  gaiaLog.setNamespaces('Socket,Auth')  - Only show these namespaces
  gaiaLog.setNamespaces(null)           - Show all namespaces
      `);
    },
  };
}

// Pre-created loggers for common namespaces
export const loggers = {
  app: createLogger('App'),
  auth: createLogger('Auth'),
  socket: createLogger('Socket'),
  api: createLogger('API'),
  campaign: createLogger('Campaign'),
  streaming: createLogger('Streaming'),
  collab: createLogger('Collab'),
  audio: createLogger('Audio'),
  room: createLogger('Room'),
  ui: createLogger('UI'),
};

export default createLogger;
