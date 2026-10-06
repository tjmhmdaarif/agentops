import { Suspense, useEffect } from "react";
import * as THREE from "three";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Nebula, SpaceDust, StarField } from "./Environment";
import { ParticleGlobe } from "./ParticleGlobe";
import { STATE_TARGETS, useQuality, useReducedMotion, useWebGLAvailable, type Quality } from "./hooks";
import { useScene, useSceneState } from "./sceneStore";

export interface SpaceSceneProps {
  mode?: "intro" | "login" | "authenticated" | "background";
  quality?: Quality | "auto";
  interactive?: boolean;
}

/** Eases the mutable rig toward the active state's targets and drives the
 * camera: pointer parallax (damped) + slow non-repeating idle drift. */
function SceneController({ reducedMotion }: { reducedMotion: boolean }) {
  const { rig } = useScene();
  const { camera } = useThree();
  useFrame((state, dt) => {
    const targets = STATE_TARGETS[rig.state];
    const k = 1 - Math.exp(-1.8 * dt);
    rig.dissolve += (targets.dissolve - rig.dissolve) * k;
    rig.globeX += (targets.globeX - rig.globeX) * k;
    rig.globeScale += (targets.globeScale - rig.globeScale) * k;
    rig.starBoost += (targets.starBoost - rig.starBoost) * k;
    rig.nebulaIntensity += (targets.nebulaIntensity - rig.nebulaIntensity) * k;
    rig.camZ += (targets.camZ - rig.camZ) * k;
    rig.camDrift += (targets.camDrift - rig.camDrift) * k;

    const t = state.clock.elapsedTime;
    const drift = reducedMotion ? 0 : rig.camDrift;
    // Two incommensurate frequencies — motion never visibly loops
    const idleX = Math.sin(t * 0.11) * drift + Math.sin(t * 0.043 + 1.7) * drift * 0.6;
    const idleY = Math.cos(t * 0.089) * drift * 0.7 + Math.sin(t * 0.031) * drift * 0.4;
    const parallax = reducedMotion ? 0 : 0.22;
    camera.position.x += (idleX - state.pointer.x * parallax - camera.position.x) * (1 - Math.exp(-2.5 * dt));
    camera.position.y += (idleY + state.pointer.y * parallax * 0.7 - camera.position.y) * (1 - Math.exp(-2.5 * dt));
    camera.position.z += (rig.camZ - camera.position.z) * (1 - Math.exp(-2.5 * dt));
    camera.lookAt(0, 0, 0);
  });
  return null;
}

/** Boot choreography: BOOT → GLOBE_ACTIVE once the globe has formed. */
function BootSequencer() {
  const { transitionTo } = useScene();
  const state = useSceneState();
  useEffect(() => {
    if (state !== "BOOT") return;
    const t = window.setTimeout(() => transitionTo("GLOBE_ACTIVE"), 1400);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);
  return null;
}

function StaticFallback() {
  // WebGL unavailable: a calm static star gradient. App remains fully usable.
  return (
    <div
      className="fixed inset-0 -z-10"
      style={{
        background:
          "radial-gradient(1200px 700px at 30% 20%, rgba(56,120,160,0.10), transparent 60%)," +
          "radial-gradient(2px 2px at 20% 30%, rgba(255,255,255,0.5), transparent 100%)," +
          "radial-gradient(1.5px 1.5px at 70% 60%, rgba(255,255,255,0.4), transparent 100%)," +
          "radial-gradient(1px 1px at 45% 80%, rgba(255,255,255,0.35), transparent 100%)," +
          "radial-gradient(1.8px 1.8px at 85% 25%, rgba(255,255,255,0.45), transparent 100%)," +
          "#05070c",
      }}
      aria-hidden
    />
  );
}

export default function SpaceScene({ quality = "auto", interactive = true }: SpaceSceneProps) {
  const profile = useQuality(quality);
  const reducedMotion = useReducedMotion();
  const webgl = useWebGLAvailable();
  if (!webgl) return <StaticFallback />;

  return (
    <div id="space-canvas-wrap" className="fixed inset-0 -z-10" aria-hidden={!interactive}>
      <Canvas
        dpr={profile.pixelRatio}
        camera={{ fov: 52, near: 0.1, far: 1200, position: [0, 0, 8.2] }}
        gl={{
          antialias: true,
          alpha: false,
          powerPreference: "high-performance",
        }}
        onCreated={({ gl }) => gl.setClearColor(new THREE.Color("#04060b"))}
        frameloop="always"
      >
        <Suspense fallback={null}>
          <SceneController reducedMotion={reducedMotion} />
          <BootSequencer />
          <Nebula />
          <StarField budget={profile.starParticles} timeScale={reducedMotion ? 0 : 1} />
          <SpaceDust count={profile.dustParticles} flow={reducedMotion ? 0 : 1} />
          <ParticleGlobe
            particleCount={profile.globeParticles}
            particleColor="#d9f7ff"
            particleSize={1.35}
            autoRotateSpeed={0.08}
            dragSensitivity={0.005}
            noiseStrength={1.0}
            interactive={interactive && !reducedMotion}
            reducedMotion={reducedMotion}
          />
        </Suspense>
      </Canvas>
    </div>
  );
}
