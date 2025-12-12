import React, { useRef, useEffect, useState, useCallback } from 'react';
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
      // D10 approximation using dodecahedron scaled
      return new THREE.DodecahedronGeometry(config.radius * 0.9);
    case 'd12':
      return new THREE.DodecahedronGeometry(config.radius);
    case 'd20':
      return new THREE.IcosahedronGeometry(config.radius);
    default:
      return new THREE.BoxGeometry(1, 1, 1);
  }
}

// Create number textures for dice faces
function createDiceTexture(number, diceType) {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');

  // Background gradient
  const gradient = ctx.createRadialGradient(64, 64, 0, 64, 64, 90);
  gradient.addColorStop(0, '#2a1a4a');
  gradient.addColorStop(1, '#1a0a2e');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 128, 128);

  // Add subtle texture/noise
  ctx.fillStyle = 'rgba(255, 255, 255, 0.03)';
  for (let i = 0; i < 50; i++) {
    ctx.beginPath();
    ctx.arc(Math.random() * 128, Math.random() * 128, Math.random() * 2, 0, Math.PI * 2);
    ctx.fill();
  }

  // Number text with glow effect
  ctx.shadowColor = '#ff00ff';
  ctx.shadowBlur = 15;
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 64px "Segoe UI", Arial, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  // Draw multiple times for glow effect
  for (let i = 0; i < 3; i++) {
    ctx.fillText(number.toString(), 64, 64);
  }

  // Final sharp text
  ctx.shadowBlur = 0;
  ctx.fillStyle = '#ffffff';
  ctx.fillText(number.toString(), 64, 64);

  return new THREE.CanvasTexture(canvas);
}

// Create a glowing particle system
function createParticleSystem(scene) {
  const particleCount = 100;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(particleCount * 3);
  const colors = new Float32Array(particleCount * 3);
  const sizes = new Float32Array(particleCount);

  for (let i = 0; i < particleCount; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 10;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 10;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 10;

    // Purple/magenta colors
    colors[i * 3] = 0.5 + Math.random() * 0.5;
    colors[i * 3 + 1] = 0.1 + Math.random() * 0.3;
    colors[i * 3 + 2] = 0.8 + Math.random() * 0.2;

    sizes[i] = Math.random() * 3 + 1;
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

  const material = new THREE.PointsMaterial({
    size: 0.1,
    vertexColors: true,
    transparent: true,
    opacity: 0.6,
    blending: THREE.AdditiveBlending,
  });

  return new THREE.Points(geometry, material);
}

// Create burst particles for roll completion
function createBurstParticles(position, scene) {
  const particleCount = 50;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(particleCount * 3);
  const velocities = [];
  const colors = new Float32Array(particleCount * 3);

  for (let i = 0; i < particleCount; i++) {
    positions[i * 3] = position.x;
    positions[i * 3 + 1] = position.y;
    positions[i * 3 + 2] = position.z;

    // Random velocities
    velocities.push({
      x: (Math.random() - 0.5) * 0.3,
      y: Math.random() * 0.2 + 0.1,
      z: (Math.random() - 0.5) * 0.3,
    });

    // Gold/yellow colors for success
    colors[i * 3] = 1;
    colors[i * 3 + 1] = 0.8 + Math.random() * 0.2;
    colors[i * 3 + 2] = 0.2;
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 0.15,
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
const DiceRoller3D = ({ onRollComplete, diceType = 'd20', autoRoll = false }) => {
  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef = useRef(null);
  const diceRef = useRef(null);
  const animationRef = useRef(null);
  const particlesRef = useRef(null);
  const burstParticlesRef = useRef([]);

  const [isRolling, setIsRolling] = useState(false);
  const [result, setResult] = useState(null);
  const [selectedDice, setSelectedDice] = useState(diceType);

  // Rolling animation state
  const rollStateRef = useRef({
    isRolling: false,
    startTime: 0,
    duration: 2500,
    initialRotation: { x: 0, y: 0, z: 0 },
    targetRotation: { x: 0, y: 0, z: 0 },
    bouncePhase: 0,
    targetResult: 1,
  });

  // Initialize Three.js scene
  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a1a);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
    camera.position.set(0, 2, 4);
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
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x404060, 0.5);
    scene.add(ambientLight);

    // Main spotlight
    const spotlight = new THREE.SpotLight(0xffffff, 2);
    spotlight.position.set(5, 10, 5);
    spotlight.castShadow = true;
    spotlight.shadow.mapSize.width = 1024;
    spotlight.shadow.mapSize.height = 1024;
    spotlight.angle = Math.PI / 4;
    spotlight.penumbra = 0.3;
    scene.add(spotlight);

    // Colored accent lights
    const purpleLight = new THREE.PointLight(0x9900ff, 1, 20);
    purpleLight.position.set(-3, 3, 2);
    scene.add(purpleLight);

    const blueLight = new THREE.PointLight(0x0066ff, 1, 20);
    blueLight.position.set(3, 3, -2);
    scene.add(blueLight);

    // Ground plane with glow effect
    const groundGeometry = new THREE.CircleGeometry(5, 64);
    const groundMaterial = new THREE.MeshStandardMaterial({
      color: 0x1a1a2e,
      metalness: 0.3,
      roughness: 0.7,
    });
    const ground = new THREE.Mesh(groundGeometry, groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -1;
    ground.receiveShadow = true;
    scene.add(ground);

    // Glowing ring
    const ringGeometry = new THREE.RingGeometry(2.5, 2.7, 64);
    const ringMaterial = new THREE.MeshBasicMaterial({
      color: 0x9900ff,
      transparent: true,
      opacity: 0.5,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeometry, ringMaterial);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = -0.99;
    scene.add(ring);

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
        particlesRef.current.rotation.y += 0.001;
        const positions = particlesRef.current.geometry.attributes.position.array;
        for (let i = 0; i < positions.length; i += 3) {
          positions[i + 1] += Math.sin(Date.now() * 0.001 + i) * 0.002;
        }
        particlesRef.current.geometry.attributes.position.needsUpdate = true;
      }

      // Animate burst particles
      burstParticlesRef.current = burstParticlesRef.current.filter((burst) => {
        burst.userData.life -= 0.02;
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
          velocities[i].y -= 0.01; // Gravity
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

        // Rotation animation
        const dice = diceRef.current;
        const rotSpeed = (1 - easeOut) * 15 + 0.1;

        dice.rotation.x += rotSpeed * 0.1;
        dice.rotation.y += rotSpeed * 0.08;
        dice.rotation.z += rotSpeed * 0.06;

        // Bounce animation
        const bounceHeight = Math.sin(progress * Math.PI * 4) * (1 - progress) * 1.5;
        dice.position.y = bounceHeight;

        // Scale pulse
        const scalePulse = 1 + Math.sin(progress * Math.PI * 6) * (1 - progress) * 0.1;
        dice.scale.setScalar(scalePulse);

        // Finish rolling
        if (progress >= 1) {
          rollStateRef.current.isRolling = false;
          dice.position.y = 0;
          dice.scale.setScalar(1);

          // Create burst effect
          const burst = createBurstParticles(dice.position.clone(), scene);
          burstParticlesRef.current.push(burst);

          setIsRolling(false);
          setResult(rollStateRef.current.targetResult);

          if (onRollComplete) {
            onRollComplete({
              diceType: selectedDice,
              result: rollStateRef.current.targetResult,
              maxValue: DICE_CONFIGS[selectedDice]?.faces || 20,
            });
          }
        }
      } else if (diceRef.current && !rollStateRef.current.isRolling) {
        // Idle animation - gentle floating
        diceRef.current.rotation.y += 0.005;
        diceRef.current.position.y = Math.sin(Date.now() * 0.002) * 0.1;
      }

      // Animate ring glow
      ring.material.opacity = 0.3 + Math.sin(Date.now() * 0.003) * 0.2;

      renderer.render(scene, camera);
    };

    animate();

    // Handle resize
    const handleResize = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationRef.current);
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, []);

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

    // Create materials with textures for each face
    let materials;
    if (type === 'd6') {
      // Box has 6 faces
      materials = [];
      for (let i = 1; i <= 6; i++) {
        const texture = createDiceTexture(i, type);
        materials.push(
          new THREE.MeshStandardMaterial({
            map: texture,
            metalness: 0.3,
            roughness: 0.4,
            emissive: 0x220033,
            emissiveIntensity: 0.2,
          })
        );
      }
    } else {
      // Other dice use a single material
      const texture = createDiceTexture(config?.faces || 20, type);
      materials = new THREE.MeshStandardMaterial({
        map: texture,
        metalness: 0.3,
        roughness: 0.4,
        emissive: 0x220033,
        emissiveIntensity: 0.2,
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
  }, [selectedDice, createDice]);

  // Roll the dice
  const rollDice = useCallback(() => {
    if (rollStateRef.current.isRolling) return;

    const config = DICE_CONFIGS[selectedDice];
    const maxValue = config?.faces || 20;
    const targetResult = Math.floor(Math.random() * maxValue) + 1;

    setIsRolling(true);
    setResult(null);

    rollStateRef.current = {
      isRolling: true,
      startTime: Date.now(),
      duration: 2500,
      targetResult,
    };
  }, [selectedDice]);

  // Auto-roll on mount if enabled
  useEffect(() => {
    if (autoRoll) {
      setTimeout(rollDice, 500);
    }
  }, [autoRoll, rollDice]);

  return (
    <div className="dice-roller-3d">
      {/* 3D Canvas Container */}
      <div
        ref={containerRef}
        className="dice-canvas-container"
        style={{
          width: '100%',
          height: '400px',
          borderRadius: '12px',
          overflow: 'hidden',
          position: 'relative',
        }}
      />

      {/* Result Display */}
      {result !== null && (
        <div className="dice-result-display">
          <span className="dice-result-number">{result}</span>
          <span className="dice-result-label">
            {result === DICE_CONFIGS[selectedDice]?.faces ? 'Critical!' : ''}
            {result === 1 ? 'Critical Fail!' : ''}
          </span>
        </div>
      )}

      {/* Controls */}
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
          {isRolling ? (
            <>
              <span className="rolling-icon">🎲</span>
              Rolling...
            </>
          ) : (
            <>
              <span className="roll-icon">🎲</span>
              Roll {selectedDice.toUpperCase()}
            </>
          )}
        </button>
      </div>

      <style>{`
        .dice-roller-3d {
          display: flex;
          flex-direction: column;
          gap: 16px;
          padding: 20px;
          background: linear-gradient(135deg, #1a1a2e 0%, #0f0f1a 100%);
          border-radius: 16px;
          border: 1px solid rgba(153, 0, 255, 0.3);
          box-shadow: 0 0 40px rgba(153, 0, 255, 0.2);
        }

        .dice-canvas-container {
          background: radial-gradient(ellipse at center, #1a1a2e 0%, #0a0a1a 100%);
          border: 1px solid rgba(153, 0, 255, 0.2);
        }

        .dice-result-display {
          text-align: center;
          padding: 16px;
          background: rgba(153, 0, 255, 0.1);
          border-radius: 12px;
          border: 1px solid rgba(153, 0, 255, 0.3);
        }

        .dice-result-number {
          font-size: 64px;
          font-weight: bold;
          color: #ffffff;
          text-shadow: 0 0 20px rgba(153, 0, 255, 0.8);
          display: block;
        }

        .dice-result-label {
          font-size: 18px;
          color: #ff9900;
          text-transform: uppercase;
          letter-spacing: 2px;
        }

        .dice-controls {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .dice-type-selector {
          display: flex;
          gap: 8px;
          justify-content: center;
          flex-wrap: wrap;
        }

        .dice-type-btn {
          padding: 8px 16px;
          border: 1px solid rgba(153, 0, 255, 0.4);
          background: rgba(26, 26, 46, 0.8);
          color: #ffffff;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s ease;
          font-weight: bold;
        }

        .dice-type-btn:hover:not(:disabled) {
          background: rgba(153, 0, 255, 0.3);
          border-color: rgba(153, 0, 255, 0.6);
          transform: translateY(-2px);
        }

        .dice-type-btn.active {
          background: linear-gradient(135deg, rgba(153, 0, 255, 0.5), rgba(100, 0, 200, 0.5));
          border-color: #9900ff;
          box-shadow: 0 0 15px rgba(153, 0, 255, 0.5);
        }

        .dice-type-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .roll-button-3d {
          padding: 16px 32px;
          font-size: 20px;
          font-weight: bold;
          color: #ffffff;
          background: linear-gradient(135deg, #9900ff 0%, #6600cc 100%);
          border: none;
          border-radius: 12px;
          cursor: pointer;
          transition: all 0.3s ease;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          text-transform: uppercase;
          letter-spacing: 2px;
          box-shadow: 0 4px 20px rgba(153, 0, 255, 0.4);
        }

        .roll-button-3d:hover:not(:disabled) {
          transform: translateY(-3px);
          box-shadow: 0 6px 30px rgba(153, 0, 255, 0.6);
          background: linear-gradient(135deg, #aa22ff 0%, #7722dd 100%);
        }

        .roll-button-3d:active:not(:disabled) {
          transform: translateY(-1px);
        }

        .roll-button-3d:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }

        .rolling-icon {
          animation: spin 0.5s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .roll-icon {
          font-size: 24px;
        }
      `}</style>
    </div>
  );
};

export default DiceRoller3D;
