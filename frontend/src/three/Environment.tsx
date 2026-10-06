import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { DUST_FRAGMENT, DUST_VERTEX, NEBULA_FRAGMENT, NEBULA_VERTEX, STARS_FRAGMENT, STARS_VERTEX } from "./shaders";
import { useScene } from "./sceneStore";

// ------------------------------------------------------------- star field

function buildLayer(count: number, rMin: number, rMax: number, size: [number, number], bright: [number, number], nearWeight: number) {
  const positions = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const brights = new Float32Array(count);
  const phases = new Float32Array(count);
  const depths = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    // Uniform directions on a spherical shell — real 3D depth
    const u = Math.random() * 2 - 1;
    const theta = Math.random() * Math.PI * 2;
    const s = Math.sqrt(1 - u * u);
    const r = rMin + Math.random() * (rMax - rMin);
    positions[i * 3] = s * Math.cos(theta) * r;
    positions[i * 3 + 1] = u * r;
    positions[i * 3 + 2] = s * Math.sin(theta) * r - 20;
    sizes[i] = size[0] + Math.random() * (size[1] - size[0]);
    brights[i] = bright[0] + Math.random() * (bright[1] - bright[0]);
    phases[i] = Math.random() * Math.PI * 2;
    depths[i] = Math.min(1, (r - rMin) / (rMax - rMin)) * nearWeight;
  }
  return { positions, sizes, brights, phases, depths, count };
}

function StarLayer(props: {
  count: number;
  rMin: number;
  rMax: number;
  size: [number, number];
  bright: [number, number];
  nearWeight: number;
  parallax: number;
  timeScale: number;
}) {
  const data = useMemo(
    () => buildLayer(props.count, props.rMin, props.rMax, props.size, props.bright, props.nearWeight),
    [props.count, props.rMin, props.rMax, props.size, props.bright, props.nearWeight],
  );
  const mat = useRef<THREE.ShaderMaterial>(null);
  const pointer = useRef({ x: 0, y: 0 });
  const { rig } = useScene();

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uSize: { value: 1 },
      uPixelRatio: { value: Math.min(window.devicePixelRatio || 1, 2) },
      uPointer: { value: new THREE.Vector2(0, 0) },
      uParallax: { value: props.parallax },
      uBoost: { value: 1 },
    }),
    [props.parallax],
  );

  useFrame((state, dt) => {
    pointer.current.x += (state.pointer.x - pointer.current.x) * (1 - Math.exp(-3 * dt));
    pointer.current.y += (state.pointer.y - pointer.current.y) * (1 - Math.exp(-3 * dt));
    const m = mat.current;
    if (!m) return;
    m.uniforms.uTime.value = state.clock.elapsedTime * props.timeScale;
    m.uniforms.uPointer.value.set(pointer.current.x, pointer.current.y);
    m.uniforms.uBoost.value += (rig.starBoost - m.uniforms.uBoost.value) * (1 - Math.exp(-1.8 * dt));
  });

  return (
    <points frustumCulled={false}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[data.positions, 3]} />
        <bufferAttribute attach="attributes-aSize" args={[data.sizes, 1]} />
        <bufferAttribute attach="attributes-aBrightness" args={[data.brights, 1]} />
        <bufferAttribute attach="attributes-aPhase" args={[data.phases, 1]} />
        <bufferAttribute attach="attributes-aDepth" args={[data.depths, 1]} />
      </bufferGeometry>
      <shaderMaterial
        ref={mat}
        vertexShader={STARS_VERTEX}
        fragmentShader={STARS_FRAGMENT}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

export function StarField({ budget, timeScale = 1 }: { budget: number; timeScale?: number }) {
  // Three real depth layers: distant pinpoints, medium twinklers, near parallax stars
  const far = Math.floor(budget * 0.6);
  const mid = Math.floor(budget * 0.3);
  const near = budget - far - mid;
  return (
    <group>
      <StarLayer count={far} rMin={60} rMax={110} size={[0.5, 1.1]} bright={[0.12, 0.35]} nearWeight={0.05} parallax={0.12} timeScale={timeScale} />
      <StarLayer count={mid} rMin={32} rMax={60} size={[0.8, 1.6]} bright={[0.3, 0.65]} nearWeight={0.4} parallax={0.5} timeScale={timeScale} />
      <StarLayer count={near} rMin={14} rMax={30} size={[1.0, 2.2]} bright={[0.4, 0.9]} nearWeight={1.0} parallax={1.0} timeScale={timeScale} />
    </group>
  );
}

// -------------------------------------------------------------- space dust

export function SpaceDust({ count, flow = 1 }: { count: number; flow?: number }) {
  const data = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    const brights = new Float32Array(count);
    const seeds = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 60;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 36;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 40 - 14;
      sizes[i] = 1.4 + Math.random() * 2.6;
      brights[i] = 0.08 + Math.random() * 0.22;
      seeds[i] = Math.random();
    }
    return { positions, sizes, brights, seeds };
  }, [count]);

  const mat = useRef<THREE.ShaderMaterial>(null);
  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uSize: { value: 1 },
      uPixelRatio: { value: Math.min(window.devicePixelRatio || 1, 2) },
      uFlow: { value: flow },
    }),
    [flow],
  );
  useFrame((state) => {
    if (mat.current) mat.current.uniforms.uTime.value = state.clock.elapsedTime;
  });

  return (
    <points frustumCulled={false}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[data.positions, 3]} />
        <bufferAttribute attach="attributes-aSize" args={[data.sizes, 1]} />
        <bufferAttribute attach="attributes-aBrightness" args={[data.brights, 1]} />
        <bufferAttribute attach="attributes-aSeed" args={[data.seeds, 1]} />
      </bufferGeometry>
      <shaderMaterial
        ref={mat}
        vertexShader={DUST_VERTEX}
        fragmentShader={DUST_FRAGMENT}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

// ----------------------------------------------------------------- nebula

export function Nebula() {
  const mat = useRef<THREE.ShaderMaterial>(null);
  const { rig } = useScene();
  const uniforms = useMemo(
    () => ({ uTime: { value: 0 }, uIntensity: { value: 0.6 } }),
    [],
  );
  useFrame((state, dt) => {
    const m = mat.current;
    if (!m) return;
    m.uniforms.uTime.value = state.clock.elapsedTime;
    m.uniforms.uIntensity.value += (rig.nebulaIntensity - m.uniforms.uIntensity.value) * (1 - Math.exp(-1.5 * dt));
  });
  return (
    <mesh scale={[1, 1, 1]} renderOrder={-10}>
      <sphereGeometry args={[220, 32, 32]} />
      <shaderMaterial
        ref={mat}
        vertexShader={NEBULA_VERTEX}
        fragmentShader={NEBULA_FRAGMENT}
        uniforms={uniforms}
        side={THREE.BackSide}
        depthWrite={false}
      />
    </mesh>
  );
}
