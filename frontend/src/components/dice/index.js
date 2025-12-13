/**
 * Dice Components
 *
 * A complete 3D dice rolling system with gold/amber styling
 *
 * Components:
 * - DiceRoller3D: Full 3D dice roller with controls
 * - DiceTrigger: Small embeddable button to trigger dice rolls
 * - DiceRollModal: Popup modal for dice rolls (supports multiple dice)
 *
 * Usage Examples:
 *
 * // Basic dice roller
 * <DiceRoller3D onRollComplete={(result) => console.log(result)} />
 *
 * // Compact dice roller for embedding
 * <DiceRoller3D compact height={250} showControls={false} />
 *
 * // Dice trigger button
 * <DiceTrigger diceType="d20" onClick={() => setModalOpen(true)} />
 *
 * // Dice roll modal with multiple dice
 * <DiceRollModal
 *   isOpen={isOpen}
 *   onClose={() => setIsOpen(false)}
 *   diceToRoll={[{ type: 'd6', count: 2 }]}
 *   modifier={3}
 *   rollLabel="Damage Roll"
 *   onRollComplete={(data) => console.log(data.total)}
 * />
 */

export { default as DiceRoller3D, DICE_CONFIGS, COLORS } from './DiceRoller3D.jsx';
export { default as DiceTrigger } from './DiceTrigger.jsx';
export { default as DiceRollModal } from './DiceRollModal.jsx';
