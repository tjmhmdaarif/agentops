import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { LAND_POINTS } from "./landPoints";
import { ATMOS_FRAGMENT, ATMOS_VERTEX, GLOBE_FRAGMENT, GLOBE_VERTEX } from "./shaders";
import { useGlobePhysics } from "./hooks";
import { useScene } from "./sceneStore";

const RADIUS = 2.2;

export interface ParticleGlobeProps {
  particleCount?: number;
  particleColor?: string;
  particleSize?: number;
  autoRotateSpeed?: number;
  dragSensitivity?: number;
  noiseStrength?: number;
  interactive?: boolean;
  reducedMotion?: boolean;
}

/** Thousands of luminous land points forming Earth, with real drag physics
 * and a GPU dissolution driven by the scene state machine. */
export function ParticleGlobe({
  particleCount = 24000,
  particleColor = "#d9f7ff",
  particleSize = 1.35,
  autoRotateSpeed = 0.08,
  dragSensitivity = 0.005,
  noiseStrength = 1.0,
  interactive = true,
  reducedMotion = false,
}: ParticleGlobeProps) {
  const { rig } = useScene();
  const { phys, step } = useGlobePhysics({
    autoRotateSpeed,
    dragSensitivity,
    reducedMotion,
    interactive,
    getAutoSpeed: () => rig.globeAutoRotate,
  });

  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const atmosRef = useRef<THREE.ShaderMaterial>(null);
  const groupRef = useRef<THREE.Group>(null);

  const { positions, seeds, sizes, brightness, drifts, count } = useMemo(() => {
    const total = LAND_POINTS.length / 2;
    const n = Math.min(particleCount, total);
    const positions = new Float32Array(n * 3);
    const seeds = new Float32Array(n);
    const sizes = new Float32Array(n);
    const brightness = new Float32Array(n);
    const drifts = new Float32Array(n * 3);
    const rng = () => Math.random();
    for (let i = 0; i < n; i++) {
      // Even sampling across the dataset (it's pre-shuffled)
      const idx = Math.floor((i / n) * total);
      const lat = (LAND_POINTS[idx * 2] * Math.PI) / 180;
      const lon = (LAND_POINTS[idx * 2 + 1] * Math.PI) / 180;
      const r = RADIUS * (1 + (rng() - 0.5) * 0.012);
      positions[i * 3] = r * Math.cos(lat) * Math.cos(lon);
      positions[i * 3 + 1] = r * Math.sin(lat);
      positions[i * 3 + 2] = r * Math.cos(lat) * Math.sin(lon);

      seeds[i] = rng();
      sizes[i] = 0.8 + rng() * 1.5;
      // 0.3 / 0.6 / 1.0 brightness tiers — never uniform
      const b = rng();
      brightness[i] = b < 0.55 ? 0.3 + rng() * 0.2 : b < 0.9 ? 0.55 + rng() * 0.2 : 0.85 + rng() * 0.35;

      // Random unit-ish outward drift direction
      const v = new THREE.Vector3(rng() - 0.5, rng() - 0.5, rng() - 0.5).normalize();
      drifts[i * 3] = v.x;
      drifts[i * 3 + 1] = v.y;
      drifts[i * 3 + 2] = v.z;
    }
    return { positions, seeds, sizes, brightness, drifts, count: n };
  }, [particleCount]);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uDissolve: { value: 0 },
      uWaveDir: { value: new THREE.Vector3(1, 0.25, 0.2).normalize() },
      uNoiseAmp: { value: noiseStrength },
      uHover: { value: 1 },
      uSize: { value: particleSize },
      uPixelRatio: { value: Math.min(window.devicePixelRatio || 1, 2) },
      uColor: { value: new THREE.Color(particleColor) },
      uColorHot: { value: new THREE.Color("#9fd8ff") },
    }),
    [particleColor, particleSize, noiseStrength],
  );

  const atmosUniforms = useMemo(
    () => ({
      uColor: { value: new THREE.Color("#7fd4e8") },
      uIntensity: { value: 0.16 },
    }),
    [],
  );

  useFrame((state, dt) => {
    step(Math.min(dt, 0.05));
    const g = groupRef.current;
    if (g) {
      g.rotation.y = phys.current.rotY;
      g.rotation.x = phys.current.rotX;
      // Scene rig drives position/scale (globe shifts aside for login, etc.)
      g.position.x += (rig.globeX - g.position.x) * (1 - Math.exp(-2.2 * dt));
      const s = g.scale.x + (rig.globeScale - g.scale.x) * (1 - Math.exp(-2.2 * dt));
      g.scale.setScalar(Math.max(s, 0.0001));
    }
    const m = materialRef.current;
    if (m) {
      m.uniforms.uTime.value = state.clock.elapsedTime;
      // ease dissolve toward rig target
      m.uniforms.uDissolve.value += (rig.dissolve - m.uniforms.uDissolve.value) * (1 - Math.exp(-1.6 * dt));
      m.uniforms.uHover.value = 1 + phys.current.hover * 0.08;
      // click ripple: brief global swell of noise amplitude
      const ripple = phys.current.ripple;
      m.uniforms.uNoiseAmp.value =
        noiseStrength * (ripple >= 0 ? 1 + Math.sin((ripple / 1.6) * Math.PI) * 0.9 : 1);
    }
    const a = atmosRef.current;
    if (a) {
      const dissolveNow = m ? (m.uniforms.uDissolve.value as number) : 0;
      a.uniforms.uIntensity.value = 0.16 * (1 - dissolveNow) + 0.03;
    }
  });

  return (
    <group ref={groupRef}>
      <points frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
          <bufferAttribute attach="attributes-aSeed" args={[seeds, 1]} />
          <bufferAttribute attach="attributes-aSize" args={[sizes, 1]} />
          <bufferAttribute attach="attributes-aBrightness" args={[brightness, 1]} />
          <bufferAttribute attach="attributes-aDrift" args={[drifts, 3]} />
        </bufferGeometry>
        <shaderMaterial
          ref={materialRef}
          vertexShader={GLOBE_VERTEX}
          fragmentShader={GLOBE_FRAGMENT}
          uniforms={uniforms}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
      {/* Barely-there stylized atmospheric shell */}
      <mesh scale={[1.06, 1.06, 1.06]}>
        <sphereGeometry args={[RADIUS, 48, 48]} />
        <shaderMaterial
          ref={atmosRef}
          vertexShader={ATMOS_VERTEX}
          fragmentShader={ATMOS_FRAGMENT}
          uniforms={atmosUniforms}
          transparent
          depthWrite={false}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
    </group>
  );
}
