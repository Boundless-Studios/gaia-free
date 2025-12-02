/**
 * Shared unique ID generator
 * Uses a single global counter to ensure IDs are unique across all components
 */

let idCounter = 0;

/**
 * Generates a unique ID using timestamp + incrementing counter
 * @returns {string} Unique ID in format "timestamp_counter"
 */
export function generateUniqueId() {
  return `${Date.now()}_${idCounter++}`;
}

/**
 * Resets the counter (mainly for testing purposes)
 */
export function resetIdCounter() {
  idCounter = 0;
}
