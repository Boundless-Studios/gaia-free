import React, { useRef, useEffect, useState, useCallback, useImperativeHandle, forwardRef } from 'react';
import * as THREE from 'three';

// Dice types with their geometry and face values
const DICE_CONFIGS = {
  d4: { faces: 4, radius: 0.8, detail: 0 },
  d6: { faces: 6, radius: 0.7, detail: 0 },
  d8: { faces: 8, radius: 0.75, detail: 0 },
  d10: { faces: 10, radius: 0.75, detail: 0 },
  d12: { faces: 12, radius: 0.8, detail: 0 },
  d20: { faces: 20, radius: 0.85, detail: 0 },
};

// Design color palette - consistent with app styling
const COLORS = {
  diceBase: '#1a1a2e',           // Dark base matching app background
  diceHighlight: '#2a2a4e',      // Subtle highlight
  diceAccent: '#d4a574',         // Gold accent (from SceneImageTrio)
  diceGlow: '#f59e0b',           // Amber glow (gaia-warning)
  textPrimary: '#ffffff',
  textGlow: '#fcd34d',           // Light gold for text glow
  particleGold: '#f59e0b',
  particleAmber: '#fbbf24',
  accentPurple: '#8b5cf6',       // Subtle purple accent (gaia-accent)
  bgDark: '#0a0a1a',
  bgMid: '#1a1a2e',
  success: '#10b981',
  critical: '#ffd700',
  fail: '#ef4444',
};

// Create geometry for different dice types
function createDiceGeometry(type) {
  const config = DICE_CONFIGS[type];
  if (!config) return new THREE.BoxGeometry(1, 1, 1);

  switch (type) {
    case 'd4':
      return new THREE.TetrahedronGeometry(config.radius);
    case 'd6':
      return new THREE.BoxGeometry(config.radius * 1.4, config.radius * 1.4, config.radius * 1.4);
    case 'd8':
      return new THREE.OctahedronGeometry(config.radius);
    case 'd10':
      return new THREE.DodecahedronGeometry(config.radius * 0.9);
    case 'd12':
      return new THREE.DodecahedronGeometry(config.radius);
    case 'd20':
      return new THREE.IcosahedronGeometry(config.radius);
    default:
      return new THREE.BoxGeometry(1, 1, 1);
  }
}

// Create high-resolution number textures for dice faces
function createDiceTexture(number, diceType, isHighlight = false) {
  const canvas = document.createElement('canvas');
  // Higher resolution for crisp numbers
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext('2d');

  // Enable font smoothing
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';

  // Translucent amber/gold gradient background
  const gradient = ctx.createRadialGradient(256, 256, 0, 256, 256, 360);
  if (isHighlight) {
    gradient.addColorStop(0, 'rgba(251, 191, 36, 0.95)'); // Bright amber center
    gradient.addColorStop(0.5, 'rgba(245, 158, 11, 0.9)'); // Gold mid
    gradient.addColorStop(1, 'rgba(180, 120, 40, 0.85)'); // Darker edge
  } else {
    gradient.addColorStop(0, 'rgba(251, 191, 36, 0.85)'); // Amber center
    gradient.addColorStop(0.5, 'rgba(217, 150, 50, 0.8)'); // Gold mid
    gradient.addColorStop(1, 'rgba(160, 100, 30, 0.75)'); // Darker gold edge
  }
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 512, 512);

  // Add subtle crystalline texture
  ctx.fillStyle = 'rgba(255, 255, 255, 0.08)';
  for (let i = 0; i < 30; i++) {
    ctx.beginPath();
    const x = Math.random() * 512;
    const y = Math.random() * 512;
    ctx.moveTo(x, y);
    ctx.lineTo(x + Math.random() * 40 - 20, y + Math.random() * 40 - 20);
    ctx.lineTo(x + Math.random() * 40 - 20, y + Math.random() * 40 - 20);
    ctx.closePath();
    ctx.fill();
  }

  // Number text with crisp rendering
  const fontSize = diceType === 'd4' ? 140 : 160;
  ctx.font = `bold ${fontSize}px "Cinzel", "Georgia", serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  // Dark shadow for depth
  ctx.shadowColor = 'rgba(0, 0, 0, 0.6)';
  ctx.shadowBlur = 8;
  ctx.shadowOffsetX = 4;
  ctx.shadowOffsetY = 4;
  ctx.fillStyle = '#1a1a2e';
  ctx.fillText(number.toString(), 258, 262);

  // Main number - white with subtle gold tint
  ctx.shadowColor = 'rgba(212, 165, 116, 0.4)';
  ctx.shadowBlur = 12;
  ctx.shadowOffsetX = 0;
  ctx.shadowOffsetY = 0;
  ctx.fillStyle = '#ffffff';
  ctx.fillText(number.toString(), 256, 260);

  // Light highlight pass
  ctx.shadowBlur = 0;
  ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
  ctx.fillText(number.toString(), 255, 258);

  const texture = new THREE.CanvasTexture(canvas);
  texture.anisotropy = 16; // Better texture filtering
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  return texture;
}

// Create ambient particle system with gold tones
function createParticleSystem(scene) {
  const particleCount = 80;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(particleCount * 3);
  const colors = new Float32Array(particleCount * 3);
  const sizes = new Float32Array(particleCount);

  for (let i = 0; i < particleCount; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 8;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 8;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 8;

    // Gold/amber color palette
    const goldVariant = Math.random();
    colors[i * 3] = 0.9 + Math.random() * 0.1;     // R: high
    colors[i * 3 + 1] = 0.6 + Math.random() * 0.3; // G: medium-high
    colors[i * 3 + 2] = 0.1 + Math.random() * 0.2; // B: low

    sizes[i] = Math.random() * 2.5 + 0.5;
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

  const material = new THREE.PointsMaterial({
    size: 0.08,
    vertexColors: true,
    transparent: true,
    opacity: 0.5,
    blending: THREE.AdditiveBlending,
  });

  return new THREE.Points(geometry, material);
}

// Create burst particles for roll completion
function createBurstParticles(position, scene, isCritical = false, isFail = false) {
  const particleCount = 60;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(particleCount * 3);
  const velocities = [];
  const colors = new Float32Array(particleCount * 3);

  for (let i = 0; i < particleCount; i++) {
    positions[i * 3] = position.x;
    positions[i * 3 + 1] = position.y;
    positions[i * 3 + 2] = position.z;

    // Spherical burst pattern
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.random() * Math.PI;
    const speed = 0.15 + Math.random() * 0.2;
    velocities.push({
      x: Math.sin(phi) * Math.cos(theta) * speed,
      y: Math.abs(Math.sin(phi) * Math.sin(theta) * speed) + 0.1,
      z: Math.cos(phi) * speed,
    });

    // Color based on result type
    if (isCritical) {
      // Bright gold for critical
      colors[i * 3] = 1;
      colors[i * 3 + 1] = 0.85 + Math.random() * 0.15;
      colors[i * 3 + 2] = 0.2;
    } else if (isFail) {
      // Red for critical fail
      colors[i * 3] = 1;
      colors[i * 3 + 1] = 0.2 + Math.random() * 0.2;
      colors[i * 3 + 2] = 0.2;
    } else {
      // Standard amber/gold
      colors[i * 3] = 0.95 + Math.random() * 0.05;
      colors[i * 3 + 1] = 0.7 + Math.random() * 0.2;
      colors[i * 3 + 2] = 0.2 + Math.random() * 0.1;
    }
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 0.12,
    vertexColors: true,
    transparent: true,
    opacity: 1,
    blending: THREE.AdditiveBlending,
  });

  const particles = new THREE.Points(geometry, material);
  particles.userData.velocities = velocities;
  particles.userData.life = 1;

  scene.add(particles);
  return particles;
}

// Main 3D Dice Roller Component
const DiceRoller3D = forwardRef(({
  onRollComplete,
  diceType = 'd20',
  autoRoll = false,
  compact = false,
  showControls = true,
  height = 400,
}, ref) => {
  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef = useRef(null);
  const diceRef = useRef(null);
  const animationRef = useRef(null);
  const particlesRef = useRef(null);
  const burstParticlesRef = useRef([]);
  const ringRef = useRef(null);

  const [isRolling, setIsRolling] = useState(false);
  const [result, setResult] = useState(null);
  const [selectedDice, setSelectedDice] = useState(diceType);
  const [displayNumber, setDisplayNumber] = useState(null);

  // Rolling animation state
  const rollStateRef = useRef({
    isRolling: false,
    startTime: 0,
    duration: 2200,
    targetResult: 1,
    currentDisplayNumber: 1,
  });

  // Expose roll function to parent via ref
  useImperativeHandle(ref, () => ({
    roll: rollDice,
    setDiceType: setSelectedDice,
    isRolling: () => rollStateRef.current.isRolling,
  }));

  // Initialize Three.js scene
  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const containerHeight = compact ? Math.min(height, 250) : height;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(COLORS.bgDark);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(55, width / containerHeight, 0.1, 1000);
    camera.position.set(0, 2.5, compact ? 3.5 : 4);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    // Renderer with better quality
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, containerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lighting - warm gold tones
    const ambientLight = new THREE.AmbientLight(0x404050, 0.6);
    scene.add(ambientLight);

    // Main spotlight - warm white
    const spotlight = new THREE.SpotLight(0xfff5e6, 2.5);
    spotlight.position.set(3, 8, 4);
    spotlight.castShadow = true;
    spotlight.shadow.mapSize.width = 1024;
    spotlight.shadow.mapSize.height = 1024;
    spotlight.angle = Math.PI / 5;
    spotlight.penumbra = 0.4;
    scene.add(spotlight);

    // Gold accent light
    const goldLight = new THREE.PointLight(0xf59e0b, 0.8, 15);
    goldLight.position.set(-3, 2, 2);
    scene.add(goldLight);

    // Subtle purple accent (matching app theme)
    const accentLight = new THREE.PointLight(0x8b5cf6, 0.4, 15);
    accentLight.position.set(3, 2, -2);
    scene.add(accentLight);

    // Ground plane - dark with subtle texture
    const groundGeometry = new THREE.CircleGeometry(4, 64);
    const groundMaterial = new THREE.MeshStandardMaterial({
      color: 0x151525,
      metalness: 0.2,
      roughness: 0.8,
    });
    const ground = new THREE.Mesh(groundGeometry, groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -1;
    ground.receiveShadow = true;
    scene.add(ground);

    // Glowing ring - gold instead of purple
    const ringGeometry = new THREE.RingGeometry(2.2, 2.4, 64);
    const ringMaterial = new THREE.MeshBasicMaterial({
      color: 0xd4a574,
      transparent: true,
      opacity: 0.4,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeometry, ringMaterial);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = -0.99;
    ringRef.current = ring;
    scene.add(ring);

    // Inner glow ring
    const innerRingGeometry = new THREE.RingGeometry(2.0, 2.15, 64);
    const innerRingMaterial = new THREE.MeshBasicMaterial({
      color: 0xf59e0b,
      transparent: true,
      opacity: 0.2,
      side: THREE.DoubleSide,
    });
    const innerRing = new THREE.Mesh(innerRingGeometry, innerRingMaterial);
    innerRing.rotation.x = -Math.PI / 2;
    innerRing.position.y = -0.98;
    scene.add(innerRing);

    // Background particles
    const particles = createParticleSystem(scene);
    particlesRef.current = particles;
    scene.add(particles);

    // Create initial dice
    createDice(selectedDice);

    // Animation loop
    const animate = () => {
      animationRef.current = requestAnimationFrame(animate);

      // Animate particles
      if (particlesRef.current) {
        particlesRef.current.rotation.y += 0.0008;
        const positions = particlesRef.current.geometry.attributes.position.array;
        for (let i = 0; i < positions.length; i += 3) {
          positions[i + 1] += Math.sin(Date.now() * 0.0008 + i) * 0.001;
        }
        particlesRef.current.geometry.attributes.position.needsUpdate = true;
      }

      // Animate burst particles
      burstParticlesRef.current = burstParticlesRef.current.filter((burst) => {
        burst.userData.life -= 0.018;
        if (burst.userData.life <= 0) {
          scene.remove(burst);
          burst.geometry.dispose();
          burst.material.dispose();
          return false;
        }

        burst.material.opacity = burst.userData.life;
        const positions = burst.geometry.attributes.position.array;
        const velocities = burst.userData.velocities;

        for (let i = 0; i < positions.length / 3; i++) {
          positions[i * 3] += velocities[i].x;
          positions[i * 3 + 1] += velocities[i].y;
          positions[i * 3 + 2] += velocities[i].z;
          velocities[i].y -= 0.008; // Gravity
        }
        burst.geometry.attributes.position.needsUpdate = true;
        return true;
      });

      // Animate dice rolling
      if (rollStateRef.current.isRolling && diceRef.current) {
        const elapsed = Date.now() - rollStateRef.current.startTime;
        const progress = Math.min(elapsed / rollStateRef.current.duration, 1);

        // Easing function for smooth deceleration
        const easeOut = 1 - Math.pow(1 - progress, 4);

        // Rotation animation with decreasing speed
        const dice = diceRef.current;
        const rotSpeed = (1 - easeOut) * 12 + 0.05;

        dice.rotation.x += rotSpeed * 0.1;
        dice.rotation.y += rotSpeed * 0.08;
        dice.rotation.z += rotSpeed * 0.05;

        // Bounce animation - higher and more dramatic
        const bounceHeight = Math.sin(progress * Math.PI * 3.5) * (1 - progress) * 1.8;
        dice.position.y = Math.max(0, bounceHeight);

        // Scale pulse during roll
        const scalePulse = 1 + Math.sin(progress * Math.PI * 5) * (1 - progress) * 0.08;
        dice.scale.setScalar(scalePulse);

        // Update display number during roll (fast cycling)
        if (progress < 0.85) {
          const config = DICE_CONFIGS[selectedDice];
          const cycleNumber = Math.floor(Math.random() * config.faces) + 1;
          if (cycleNumber !== rollStateRef.current.currentDisplayNumber) {
            rollStateRef.current.currentDisplayNumber = cycleNumber;
            setDisplayNumber(cycleNumber);
          }
        } else {
          // Lock to final number
          setDisplayNumber(rollStateRef.current.targetResult);
        }

        // Finish rolling
        if (progress >= 1) {
          rollStateRef.current.isRolling = false;
          dice.position.y = 0;
          dice.scale.setScalar(1);

          const finalResult = rollStateRef.current.targetResult;
          const maxValue = DICE_CONFIGS[selectedDice]?.faces || 20;
          const isCritical = finalResult === maxValue;
          const isFail = finalResult === 1;

          // Create burst effect
          const burst = createBurstParticles(dice.position.clone(), scene, isCritical, isFail);
          burstParticlesRef.current.push(burst);

          setIsRolling(false);
          setResult(finalResult);
          setDisplayNumber(finalResult);

          if (onRollComplete) {
            onRollComplete({
              diceType: selectedDice,
              result: finalResult,
              maxValue,
              isCritical,
              isFail,
            });
          }
        }
      } else if (diceRef.current && !rollStateRef.current.isRolling) {
        // Idle animation - gentle floating
        diceRef.current.rotation.y += 0.004;
        diceRef.current.position.y = Math.sin(Date.now() * 0.0015) * 0.08;
      }

      // Animate ring glow
      if (ringRef.current) {
        const pulseIntensity = rollStateRef.current.isRolling ? 0.6 : 0.4;
        const pulseSpeed = rollStateRef.current.isRolling ? 0.008 : 0.003;
        ringRef.current.material.opacity = pulseIntensity * 0.5 + Math.sin(Date.now() * pulseSpeed) * 0.2;
      }

      renderer.render(scene, camera);
    };

    animate();

    // Handle resize
    const handleResize = () => {
      const width = container.clientWidth;
      const newHeight = compact ? Math.min(height, 250) : height;
      camera.aspect = width / newHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(width, newHeight);
    };

    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationRef.current);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [compact, height]);

  // Create dice mesh
  const createDice = useCallback((type) => {
    if (!sceneRef.current) return;

    // Remove existing dice
    if (diceRef.current) {
      sceneRef.current.remove(diceRef.current);
      diceRef.current.geometry.dispose();
      if (Array.isArray(diceRef.current.material)) {
        diceRef.current.material.forEach((m) => m.dispose());
      } else {
        diceRef.current.material.dispose();
      }
    }

    const geometry = createDiceGeometry(type);
    const config = DICE_CONFIGS[type];

    // Create materials with high-res textures for each face
    let materials;
    if (type === 'd6') {
      // Box has 6 faces
      materials = [];
      for (let i = 1; i <= 6; i++) {
        const texture = createDiceTexture(i, type);
        materials.push(
          new THREE.MeshStandardMaterial({
            map: texture,
            metalness: 0.15,
            roughness: 0.35,
            emissive: 0x3d2a10,
            emissiveIntensity: 0.1,
            transparent: true,
            opacity: 0.92,
          })
        );
      }
    } else {
      // Other dice use a single material showing max value
      const texture = createDiceTexture(config?.faces || 20, type);
      materials = new THREE.MeshStandardMaterial({
        map: texture,
        metalness: 0.15,
        roughness: 0.35,
        emissive: 0x3d2a10,
        emissiveIntensity: 0.1,
        transparent: true,
        opacity: 0.92,
      });
    }

    const dice = new THREE.Mesh(geometry, materials);
    dice.castShadow = true;
    dice.receiveShadow = true;
    diceRef.current = dice;
    sceneRef.current.add(dice);
  }, []);

  // Update dice when type changes
  useEffect(() => {
    createDice(selectedDice);
    setResult(null);
    setDisplayNumber(null);
  }, [selectedDice, createDice]);

  // Roll the dice
  const rollDice = useCallback(() => {
    if (rollStateRef.current.isRolling) return;

    const config = DICE_CONFIGS[selectedDice];
    const maxValue = config?.faces || 20;
    const targetResult = Math.floor(Math.random() * maxValue) + 1;

    setIsRolling(true);
    setResult(null);
    setDisplayNumber(null);

    rollStateRef.current = {
      isRolling: true,
      startTime: Date.now(),
      duration: 2200,
      targetResult,
      currentDisplayNumber: 1,
    };
  }, [selectedDice]);

  // Auto-roll on mount if enabled
  useEffect(() => {
    if (autoRoll) {
      setTimeout(rollDice, 500);
    }
  }, [autoRoll, rollDice]);

  const maxValue = DICE_CONFIGS[selectedDice]?.faces || 20;
  const isCritical = result === maxValue;
  const isFail = result === 1;

  return (
    <div className="dice-roller-3d" data-compact={compact}>
      {/* 3D Canvas Container */}
      <div
        ref={containerRef}
        className="dice-canvas-container"
        style={{ height: compact ? Math.min(height, 250) : height }}
      />

      {/* Rolling Number Display Overlay */}
      {(isRolling || result !== null) && (
        <div className={`dice-number-overlay ${isRolling ? 'rolling' : 'final'} ${isCritical ? 'critical' : ''} ${isFail ? 'fail' : ''}`}>
          <span className="dice-number">{displayNumber || result}</span>
          {!isRolling && result !== null && (
            <span className="dice-result-label">
              {isCritical && 'CRITICAL!'}
              {isFail && 'CRITICAL FAIL!'}
            </span>
          )}
        </div>
      )}

      {/* Controls */}
      {showControls && (
        <div className="dice-controls">
          {/* Dice Type Selector */}
          <div className="dice-type-selector">
            {Object.keys(DICE_CONFIGS).map((type) => (
              <button
                key={type}
                className={`dice-type-btn ${selectedDice === type ? 'active' : ''}`}
                onClick={() => setSelectedDice(type)}
                disabled={isRolling}
              >
                {type.toUpperCase()}
              </button>
            ))}
          </div>

          {/* Roll Button */}
          <button
            className="roll-button-3d"
            onClick={rollDice}
            disabled={isRolling}
          >
            {isRolling ? 'Rolling...' : `Roll ${selectedDice.toUpperCase()}`}
          </button>
        </div>
      )}

      <style>{`
        .dice-roller-3d {
          display: flex;
          flex-direction: column;
          gap: 16px;
          padding: 16px;
          background: linear-gradient(135deg, #1a1a2e 0%, #0f0f1a 100%);
          border-radius: 12px;
          border: 1px solid rgba(212, 165, 116, 0.25);
          box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
          position: relative;
        }

        .dice-roller-3d[data-compact="true"] {
          padding: 12px;
          gap: 12px;
        }

        .dice-canvas-container {
          width: 100%;
          border-radius: 8px;
          overflow: hidden;
          position: relative;
          background: radial-gradient(ellipse at center, #1a1a2e 0%, #0a0a1a 100%);
          border: 1px solid rgba(212, 165, 116, 0.15);
        }

        .dice-number-overlay {
          position: absolute;
          top: 16px;
          left: 50%;
          transform: translateX(-50%);
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          z-index: 10;
          pointer-events: none;
        }

        .dice-number {
          font-size: 48px;
          font-weight: bold;
          font-family: 'Cinzel', 'Georgia', serif;
          color: #ffffff;
          text-shadow:
            0 0 20px rgba(245, 158, 11, 0.6),
            0 2px 4px rgba(0, 0, 0, 0.8);
          transition: all 0.15s ease;
        }

        .dice-number-overlay.rolling .dice-number {
          font-size: 36px;
          opacity: 0.8;
          animation: numberPulse 0.15s ease infinite;
        }

        .dice-number-overlay.final .dice-number {
          font-size: 64px;
          animation: numberReveal 0.4s ease-out;
        }

        .dice-number-overlay.critical .dice-number {
          color: #ffd700;
          text-shadow:
            0 0 30px rgba(255, 215, 0, 0.8),
            0 0 60px rgba(255, 215, 0, 0.4),
            0 2px 4px rgba(0, 0, 0, 0.8);
        }

        .dice-number-overlay.fail .dice-number {
          color: #ef4444;
          text-shadow:
            0 0 30px rgba(239, 68, 68, 0.8),
            0 2px 4px rgba(0, 0, 0, 0.8);
        }

        .dice-result-label {
          font-size: 14px;
          font-weight: bold;
          text-transform: uppercase;
          letter-spacing: 3px;
          animation: labelFade 0.5s ease-out;
        }

        .dice-number-overlay.critical .dice-result-label {
          color: #ffd700;
          text-shadow: 0 0 10px rgba(255, 215, 0, 0.6);
        }

        .dice-number-overlay.fail .dice-result-label {
          color: #ef4444;
          text-shadow: 0 0 10px rgba(239, 68, 68, 0.6);
        }

        @keyframes numberPulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.1); }
        }

        @keyframes numberReveal {
          0% { transform: scale(1.5); opacity: 0; }
          100% { transform: scale(1); opacity: 1; }
        }

        @keyframes labelFade {
          0% { opacity: 0; transform: translateY(-10px); }
          100% { opacity: 1; transform: translateY(0); }
        }

        .dice-controls {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .dice-type-selector {
          display: flex;
          gap: 6px;
          justify-content: center;
          flex-wrap: wrap;
        }

        .dice-type-btn {
          padding: 8px 14px;
          border: 1px solid rgba(212, 165, 116, 0.3);
          background: rgba(26, 26, 46, 0.8);
          color: #e0e0e0;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s ease;
          font-weight: 600;
          font-size: 13px;
        }

        .dice-type-btn:hover:not(:disabled) {
          background: rgba(212, 165, 116, 0.15);
          border-color: rgba(212, 165, 116, 0.5);
          color: #ffffff;
          transform: translateY(-1px);
        }

        .dice-type-btn.active {
          background: linear-gradient(135deg, rgba(212, 165, 116, 0.3), rgba(180, 130, 70, 0.3));
          border-color: #d4a574;
          color: #ffffff;
          box-shadow: 0 0 12px rgba(212, 165, 116, 0.3);
        }

        .dice-type-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .roll-button-3d {
          padding: 14px 28px;
          font-size: 16px;
          font-weight: bold;
          color: #1a1a2e;
          background: linear-gradient(135deg, #f59e0b 0%, #d4a574 100%);
          border: none;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.3s ease;
          text-transform: uppercase;
          letter-spacing: 2px;
          box-shadow: 0 4px 16px rgba(245, 158, 11, 0.3);
        }

        .roll-button-3d:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 6px 24px rgba(245, 158, 11, 0.4);
          background: linear-gradient(135deg, #fbbf24 0%, #e0b080 100%);
        }

        .roll-button-3d:active:not(:disabled) {
          transform: translateY(0);
        }

        .roll-button-3d:disabled {
          opacity: 0.7;
          cursor: not-allowed;
          background: linear-gradient(135deg, #8b8b8b 0%, #6b6b6b 100%);
        }

        .dice-roller-3d[data-compact="true"] .dice-type-btn {
          padding: 6px 10px;
          font-size: 11px;
        }

        .dice-roller-3d[data-compact="true"] .roll-button-3d {
          padding: 10px 20px;
          font-size: 14px;
        }

        .dice-roller-3d[data-compact="true"] .dice-number-overlay .dice-number {
          font-size: 32px;
        }

        .dice-roller-3d[data-compact="true"] .dice-number-overlay.final .dice-number {
          font-size: 48px;
        }
      `}</style>
    </div>
  );
});

DiceRoller3D.displayName = 'DiceRoller3D';

export { DICE_CONFIGS, COLORS };
export default DiceRoller3D;
