import React, { useState, useEffect, useRef, useCallback } from 'react';
import * as THREE from 'three';

// Import dice configs from main component
const DICE_CONFIGS = {
  d4: { faces: 4, radius: 0.6, color: '#d4a574' },
  d6: { faces: 6, radius: 0.55, color: '#f59e0b' },
  d8: { faces: 8, radius: 0.6, color: '#d4a574' },
  d10: { faces: 10, radius: 0.6, color: '#fbbf24' },
  d12: { faces: 12, radius: 0.65, color: '#d4a574' },
  d20: { faces: 20, radius: 0.7, color: '#f59e0b' },
};

// Create geometry for different dice types
function createDiceGeometry(type) {
  const config = DICE_CONFIGS[type];
  if (!config) return new THREE.BoxGeometry(1, 1, 1);

  switch (type) {
    case 'd4':
      return new THREE.TetrahedronGeometry(config.radius);
    case 'd6':
      return new THREE.BoxGeometry(config.radius * 1.3, config.radius * 1.3, config.radius * 1.3);
    case 'd8':
      return new THREE.OctahedronGeometry(config.radius);
    case 'd10':
      return new THREE.DodecahedronGeometry(config.radius * 0.85);
    case 'd12':
      return new THREE.DodecahedronGeometry(config.radius);
    case 'd20':
      return new THREE.IcosahedronGeometry(config.radius);
    default:
      return new THREE.BoxGeometry(1, 1, 1);
  }
}

// Create high-res texture for dice
function createDiceTexture(number) {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 256;
  const ctx = canvas.getContext('2d');

  // Translucent amber gradient
  const gradient = ctx.createRadialGradient(128, 128, 0, 128, 128, 180);
  gradient.addColorStop(0, 'rgba(251, 191, 36, 0.9)');
  gradient.addColorStop(0.6, 'rgba(217, 150, 50, 0.85)');
  gradient.addColorStop(1, 'rgba(160, 100, 30, 0.8)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 256, 256);

  // Number
  ctx.font = 'bold 80px "Cinzel", Georgia, serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
  ctx.shadowBlur = 4;
  ctx.fillStyle = '#ffffff';
  ctx.fillText(number.toString(), 128, 130);

  const texture = new THREE.CanvasTexture(canvas);
  texture.anisotropy = 8;
  return texture;
}

/**
 * DiceRollModal - A popup modal for rolling dice with 3D animation
 *
 * Supports rolling multiple dice at once with individual results.
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether the modal is open
 * @param {Function} props.onClose - Close handler
 * @param {Array} props.diceToRoll - Array of dice to roll: [{ type: 'd20', count: 1 }, ...]
 * @param {number} [props.modifier=0] - Modifier to add to total
 * @param {string} [props.rollLabel] - Label for the roll (e.g., "Attack Roll")
 * @param {Function} [props.onRollComplete] - Callback with all results
 * @param {boolean} [props.autoRoll=true] - Auto-start rolling when opened
 */
const DiceRollModal = ({
  isOpen,
  onClose,
  diceToRoll = [{ type: 'd20', count: 1 }],
  modifier = 0,
  rollLabel = 'Dice Roll',
  onRollComplete,
  autoRoll = true,
}) => {
  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef = useRef(null);
  const animationRef = useRef(null);
  const diceObjectsRef = useRef([]);

  const [isRolling, setIsRolling] = useState(false);
  const [results, setResults] = useState([]);
  const [displayNumbers, setDisplayNumbers] = useState([]);
  const [isComplete, setIsComplete] = useState(false);

  // Calculate total dice to create
  const totalDice = diceToRoll.reduce((sum, d) => sum + (d.count || 1), 0);

  // Roll state for each die
  const rollStatesRef = useRef([]);

  // Initialize Three.js scene
  useEffect(() => {
    if (!isOpen || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a1a);
    sceneRef.current = scene;

    // Camera - adjust based on dice count
    const cameraDistance = totalDice <= 2 ? 4 : totalDice <= 4 ? 5 : 6;
    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000);
    camera.position.set(0, cameraDistance * 0.7, cameraDistance);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x404050, 0.8);
    scene.add(ambientLight);

    const spotlight = new THREE.SpotLight(0xfff5e6, 2);
    spotlight.position.set(2, 6, 3);
    spotlight.castShadow = true;
    scene.add(spotlight);

    const goldLight = new THREE.PointLight(0xf59e0b, 0.6, 12);
    goldLight.position.set(-2, 2, 1);
    scene.add(goldLight);

    // Ground
    const groundGeometry = new THREE.CircleGeometry(5, 64);
    const groundMaterial = new THREE.MeshStandardMaterial({
      color: 0x151525,
      metalness: 0.1,
      roughness: 0.9,
    });
    const ground = new THREE.Mesh(groundGeometry, groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -1.2;
    ground.receiveShadow = true;
    scene.add(ground);

    // Create dice
    createAllDice();

    // Animation loop
    let burstParticles = [];

    const animate = () => {
      animationRef.current = requestAnimationFrame(animate);

      // Animate each die
      let allComplete = true;
      diceObjectsRef.current.forEach((dice, index) => {
        const state = rollStatesRef.current[index];
        if (!state || !dice) return;

        if (state.isRolling) {
          allComplete = false;
          const elapsed = Date.now() - state.startTime;
          const progress = Math.min(elapsed / state.duration, 1);
          const easeOut = 1 - Math.pow(1 - progress, 4);

          // Rotation
          const rotSpeed = (1 - easeOut) * 10 + 0.05;
          dice.rotation.x += rotSpeed * 0.1 * state.rotationDirection.x;
          dice.rotation.y += rotSpeed * 0.08 * state.rotationDirection.y;
          dice.rotation.z += rotSpeed * 0.06 * state.rotationDirection.z;

          // Bounce
          const bounceHeight = Math.sin(progress * Math.PI * 3) * (1 - progress) * 1.5;
          dice.position.y = state.baseY + Math.max(0, bounceHeight);

          // Scale pulse
          const scalePulse = 1 + Math.sin(progress * Math.PI * 4) * (1 - progress) * 0.06;
          dice.scale.setScalar(scalePulse);

          // Update display number
          if (progress < 0.8) {
            const config = DICE_CONFIGS[state.diceType];
            state.displayNumber = Math.floor(Math.random() * config.faces) + 1;
          } else {
            state.displayNumber = state.targetResult;
          }

          // Complete this die
          if (progress >= 1) {
            state.isRolling = false;
            dice.position.y = state.baseY;
            dice.scale.setScalar(1);
          }
        } else if (!state.isRolling && state.targetResult) {
          // Idle animation
          dice.rotation.y += 0.003;
          dice.position.y = state.baseY + Math.sin(Date.now() * 0.002 + index) * 0.03;
        }
      });

      // Update display numbers state
      const newDisplayNumbers = rollStatesRef.current.map(s => s?.displayNumber || null);
      setDisplayNumbers([...newDisplayNumbers]);

      // Check if all dice are complete
      if (allComplete && rollStatesRef.current.length > 0 && rollStatesRef.current.every(s => !s.isRolling && s.targetResult)) {
        if (!isComplete) {
          setIsComplete(true);
          setIsRolling(false);
          const finalResults = rollStatesRef.current.map(s => ({
            diceType: s.diceType,
            result: s.targetResult,
          }));
          setResults(finalResults);
          if (onRollComplete) {
            const total = finalResults.reduce((sum, r) => sum + r.result, 0) + modifier;
            onRollComplete({ results: finalResults, total, modifier });
          }
        }
      }

      // Animate burst particles
      burstParticles = burstParticles.filter(burst => {
        burst.userData.life -= 0.02;
        if (burst.userData.life <= 0) {
          scene.remove(burst);
          burst.geometry.dispose();
          burst.material.dispose();
          return false;
        }
        burst.material.opacity = burst.userData.life;
        const positions = burst.geometry.attributes.position.array;
        burst.userData.velocities.forEach((v, i) => {
          positions[i * 3] += v.x;
          positions[i * 3 + 1] += v.y;
          positions[i * 3 + 2] += v.z;
          v.y -= 0.008;
        });
        burst.geometry.attributes.position.needsUpdate = true;
        return true;
      });

      renderer.render(scene, camera);
    };

    animate();

    // Start rolling if autoRoll
    if (autoRoll) {
      setTimeout(startRolling, 300);
    }

    // Cleanup
    return () => {
      cancelAnimationFrame(animationRef.current);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      diceObjectsRef.current = [];
      rollStatesRef.current = [];
    };
  }, [isOpen, totalDice]);

  // Create all dice meshes
  const createAllDice = useCallback(() => {
    if (!sceneRef.current) return;

    // Clear existing
    diceObjectsRef.current.forEach(dice => {
      if (dice) {
        sceneRef.current.remove(dice);
        dice.geometry.dispose();
        if (dice.material) dice.material.dispose();
      }
    });
    diceObjectsRef.current = [];
    rollStatesRef.current = [];

    // Calculate positions for dice
    let diceIndex = 0;
    const positions = calculateDicePositions(totalDice);

    diceToRoll.forEach(diceGroup => {
      const { type, count = 1 } = diceGroup;
      for (let i = 0; i < count; i++) {
        const pos = positions[diceIndex] || { x: 0, z: 0 };
        const dice = createSingleDice(type, pos);
        diceObjectsRef.current.push(dice);
        sceneRef.current.add(dice);

        // Initialize roll state
        rollStatesRef.current.push({
          diceType: type,
          isRolling: false,
          startTime: 0,
          duration: 2000 + Math.random() * 500,
          targetResult: null,
          displayNumber: null,
          baseY: 0,
          rotationDirection: {
            x: Math.random() > 0.5 ? 1 : -1,
            y: Math.random() > 0.5 ? 1 : -1,
            z: Math.random() > 0.5 ? 1 : -1,
          },
        });

        diceIndex++;
      }
    });
  }, [diceToRoll, totalDice]);

  // Calculate positions for multiple dice
  const calculateDicePositions = (count) => {
    if (count === 1) return [{ x: 0, z: 0 }];
    if (count === 2) return [{ x: -0.8, z: 0 }, { x: 0.8, z: 0 }];
    if (count === 3) return [{ x: -1, z: 0.3 }, { x: 1, z: 0.3 }, { x: 0, z: -0.6 }];
    if (count === 4) return [{ x: -0.9, z: 0.5 }, { x: 0.9, z: 0.5 }, { x: -0.9, z: -0.5 }, { x: 0.9, z: -0.5 }];

    // For more dice, arrange in a grid
    const positions = [];
    const cols = Math.ceil(Math.sqrt(count));
    const spacing = 1.2;
    for (let i = 0; i < count; i++) {
      const row = Math.floor(i / cols);
      const col = i % cols;
      const offsetX = (cols - 1) * spacing / 2;
      const offsetZ = (Math.ceil(count / cols) - 1) * spacing / 2;
      positions.push({
        x: col * spacing - offsetX,
        z: row * spacing - offsetZ,
      });
    }
    return positions;
  };

  // Create a single dice mesh
  const createSingleDice = (type, position) => {
    const geometry = createDiceGeometry(type);
    const config = DICE_CONFIGS[type];
    const texture = createDiceTexture(config.faces);

    const material = new THREE.MeshStandardMaterial({
      map: texture,
      metalness: 0.15,
      roughness: 0.35,
      emissive: 0x3d2a10,
      emissiveIntensity: 0.08,
      transparent: true,
      opacity: 0.9,
    });

    const dice = new THREE.Mesh(geometry, material);
    dice.position.set(position.x, 0, position.z);
    dice.castShadow = true;
    return dice;
  };

  // Start rolling all dice
  const startRolling = () => {
    if (isRolling) return;

    setIsRolling(true);
    setIsComplete(false);
    setResults([]);

    // Start each die with slight delay
    rollStatesRef.current.forEach((state, index) => {
      const config = DICE_CONFIGS[state.diceType];
      setTimeout(() => {
        state.isRolling = true;
        state.startTime = Date.now();
        state.targetResult = Math.floor(Math.random() * config.faces) + 1;
        state.baseY = 0;
      }, index * 100);
    });
  };

  // Calculate total
  const total = results.reduce((sum, r) => sum + r.result, 0) + modifier;
  const hasCritical = results.some(r => r.result === DICE_CONFIGS[r.diceType]?.faces);
  const hasFail = results.some(r => r.result === 1);

  if (!isOpen) return null;

  return (
    <div className="dice-roll-modal-overlay" onClick={onClose}>
      <div className="dice-roll-modal" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="dice-modal-header">
          <h3>{rollLabel}</h3>
          <button className="dice-modal-close" onClick={onClose}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* 3D Canvas */}
        <div ref={containerRef} className="dice-modal-canvas" />

        {/* Rolling Numbers Display */}
        <div className="dice-numbers-display">
          {displayNumbers.map((num, i) => (
            <span
              key={i}
              className={`dice-single-number ${isComplete ? 'final' : 'rolling'} ${
                isComplete && results[i]?.result === DICE_CONFIGS[results[i]?.diceType]?.faces ? 'critical' : ''
              } ${isComplete && results[i]?.result === 1 ? 'fail' : ''}`}
            >
              {num || '-'}
            </span>
          ))}
          {modifier !== 0 && (
            <span className="dice-modifier">
              {modifier > 0 ? '+' : ''}{modifier}
            </span>
          )}
        </div>

        {/* Total Display */}
        {isComplete && (
          <div className={`dice-total-display ${hasCritical ? 'critical' : ''} ${hasFail ? 'fail' : ''}`}>
            <span className="total-label">Total</span>
            <span className="total-value">{total}</span>
            {hasCritical && <span className="total-tag critical">CRITICAL!</span>}
            {hasFail && <span className="total-tag fail">CRIT FAIL!</span>}
          </div>
        )}

        {/* Actions */}
        <div className="dice-modal-actions">
          {!isRolling && !isComplete && (
            <button className="dice-roll-btn" onClick={startRolling}>
              Roll Dice
            </button>
          )}
          {isComplete && (
            <button className="dice-roll-btn secondary" onClick={startRolling}>
              Roll Again
            </button>
          )}
        </div>

        <style>{`
          .dice-roll-modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.85);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            animation: fadeIn 0.2s ease;
          }

          @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
          }

          .dice-roll-modal {
            background: linear-gradient(135deg, #1a1a2e 0%, #0f0f1a 100%);
            border: 1px solid rgba(212, 165, 116, 0.3);
            border-radius: 16px;
            width: 90%;
            max-width: 480px;
            overflow: hidden;
            box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5), 0 0 60px rgba(212, 165, 116, 0.1);
            animation: scaleIn 0.3s ease;
          }

          @keyframes scaleIn {
            from { transform: scale(0.9); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
          }

          .dice-modal-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 20px;
            border-bottom: 1px solid rgba(212, 165, 116, 0.15);
          }

          .dice-modal-header h3 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
            color: #e0e0e0;
            font-family: 'Cinzel', Georgia, serif;
          }

          .dice-modal-close {
            background: none;
            border: none;
            color: #666;
            cursor: pointer;
            padding: 4px;
            display: flex;
            transition: color 0.2s;
          }

          .dice-modal-close:hover {
            color: #fff;
          }

          .dice-modal-canvas {
            width: 100%;
            height: 280px;
            background: radial-gradient(ellipse at center, #1a1a2e 0%, #0a0a1a 100%);
          }

          .dice-numbers-display {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            padding: 16px;
            flex-wrap: wrap;
          }

          .dice-single-number {
            font-size: 32px;
            font-weight: bold;
            font-family: 'Cinzel', Georgia, serif;
            color: #ffffff;
            min-width: 50px;
            text-align: center;
            text-shadow: 0 0 12px rgba(245, 158, 11, 0.5);
            transition: all 0.15s ease;
          }

          .dice-single-number.rolling {
            opacity: 0.7;
            animation: numberFlicker 0.1s ease infinite;
          }

          .dice-single-number.final {
            font-size: 40px;
            animation: numberPop 0.3s ease;
          }

          .dice-single-number.critical {
            color: #ffd700;
            text-shadow: 0 0 20px rgba(255, 215, 0, 0.7);
          }

          .dice-single-number.fail {
            color: #ef4444;
            text-shadow: 0 0 20px rgba(239, 68, 68, 0.7);
          }

          .dice-modifier {
            font-size: 24px;
            font-weight: 600;
            color: #8b5cf6;
            margin-left: 8px;
          }

          @keyframes numberFlicker {
            0%, 100% { opacity: 0.7; }
            50% { opacity: 1; }
          }

          @keyframes numberPop {
            0% { transform: scale(1.3); }
            100% { transform: scale(1); }
          }

          .dice-total-display {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            padding: 16px;
            background: rgba(0, 0, 0, 0.3);
            margin: 0 16px;
            border-radius: 12px;
            animation: slideUp 0.3s ease;
          }

          @keyframes slideUp {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
          }

          .total-label {
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #888;
          }

          .total-value {
            font-size: 56px;
            font-weight: bold;
            font-family: 'Cinzel', Georgia, serif;
            color: #ffffff;
            text-shadow: 0 0 20px rgba(245, 158, 11, 0.5);
          }

          .dice-total-display.critical .total-value {
            color: #ffd700;
            text-shadow: 0 0 30px rgba(255, 215, 0, 0.6);
          }

          .dice-total-display.fail .total-value {
            color: #ef4444;
            text-shadow: 0 0 30px rgba(239, 68, 68, 0.6);
          }

          .total-tag {
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 2px;
            padding: 4px 12px;
            border-radius: 4px;
            margin-top: 4px;
          }

          .total-tag.critical {
            background: rgba(255, 215, 0, 0.2);
            color: #ffd700;
          }

          .total-tag.fail {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
          }

          .dice-modal-actions {
            display: flex;
            justify-content: center;
            padding: 16px;
            gap: 12px;
          }

          .dice-roll-btn {
            padding: 12px 32px;
            font-size: 16px;
            font-weight: bold;
            color: #1a1a2e;
            background: linear-gradient(135deg, #f59e0b 0%, #d4a574 100%);
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
          }

          .dice-roll-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(245, 158, 11, 0.4);
          }

          .dice-roll-btn.secondary {
            background: rgba(212, 165, 116, 0.2);
            color: #d4a574;
            border: 1px solid rgba(212, 165, 116, 0.4);
          }

          .dice-roll-btn.secondary:hover {
            background: rgba(212, 165, 116, 0.3);
          }
        `}</style>
      </div>
    </div>
  );
};

export default DiceRollModal;
