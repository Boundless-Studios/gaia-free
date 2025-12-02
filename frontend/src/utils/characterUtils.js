/**
 * Character Utility Functions
 *
 * Centralized utilities for character-related calculations and formatting
 * following D&D 5e rules and game conventions.
 */

/**
 * Calculate HP color based on current/max HP percentage
 *
 * Color scheme:
 * - Green (75-100%): Healthy
 * - Orange (50-74%): Injured
 * - Red-Orange (25-49%): Badly wounded
 * - Red (0-24%): Critical
 *
 * @param {number} hpCurrent - Current hit points
 * @param {number} hpMax - Maximum hit points
 * @returns {string} Hex color code
 */
export const getHPColor = (hpCurrent, hpMax) => {
  if (hpMax <= 0) return '#4caf50'; // Default to green if max HP is invalid

  const hpPercentage = (hpCurrent / hpMax) * 100;

  if (hpPercentage >= 75) return '#4caf50'; // Green
  if (hpPercentage >= 50) return '#ff9800'; // Orange
  if (hpPercentage >= 25) return '#ff5722'; // Red-orange
  return '#f44336'; // Red
};

/**
 * Calculate D&D 5e ability modifier from ability score
 *
 * Formula: Math.floor((abilityScore - 10) / 2)
 *
 * Examples:
 * - Score 10 → Modifier +0
 * - Score 20 → Modifier +5
 * - Score 8 → Modifier -1
 *
 * @param {number} abilityScore - Ability score (default 10 if not provided)
 * @returns {number} Ability modifier
 */
export const calculateAbilityModifier = (abilityScore = 10) => {
  return Math.floor((abilityScore - 10) / 2);
};

/**
 * Format ability modifier with appropriate sign
 *
 * Examples:
 * - +5 → "+5"
 * - 0 → "+0"
 * - -2 → "-2"
 *
 * @param {number} modifier - The ability modifier to format
 * @returns {string} Formatted modifier with sign
 */
export const formatAbilityModifier = (modifier) => {
  return modifier >= 0 ? `+${modifier}` : `${modifier}`;
};

/**
 * Calculate and format ability modifier from ability score
 *
 * Convenience function combining calculateAbilityModifier and formatAbilityModifier
 *
 * @param {number} abilityScore - Ability score (default 10 if not provided)
 * @returns {string} Formatted modifier (e.g., "+3", "-1", "+0")
 */
export const getFormattedAbilityModifier = (abilityScore = 10) => {
  const modifier = calculateAbilityModifier(abilityScore);
  return formatAbilityModifier(modifier);
};

/**
 * Get HP percentage as a number between 0 and 100
 *
 * @param {number} hpCurrent - Current hit points
 * @param {number} hpMax - Maximum hit points
 * @returns {number} HP percentage (0-100)
 */
export const getHPPercentage = (hpCurrent, hpMax) => {
  if (hpMax <= 0) return 100;
  return Math.max(0, Math.min(100, (hpCurrent / hpMax) * 100));
};
