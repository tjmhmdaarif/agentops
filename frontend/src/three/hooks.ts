import { useEffect, useMemo, useRef, useState } from "react";

// ------------------------------------------------------------- quality

export type Quality = "low" | "medium" | "high";

export interface QualityProfile {
  globeParticles: number;
  starParticles: number;
  dustParticles: number;
  pixelRatio: number;
  bloomLike: boolean;
}

const PROFILES: Record<Quality, QualityProfile> = {
  low: { globeParticles: 6000, starParticles: 1400, dustParticles: 400, pixelRatio: 1, bloomLike: false },
  medium: { globeParticles: 14000, starParticles: 2800, dustParticles: 800, pixelRatio: 1.5, bloomLike: true },
  high: { globeParticles: 26000, starParticles: 4500, dustParticles: 1400, pixelRatio: 2, bloomLike: true },
};

export function useQuality(override?: Quality | "auto"): QualityProfile {
  return useMemo(() => {
    let q: Quality = "high";
    if (override && override !== "auto") {
      q = override;
    } else {
      const ua = navigator.userAgent;
      const mobile = /Mobi|Android|iPhone|iPad/i.test(ua);
      const smallScreen = Math.min(window.innerWidth, window.innerHeight) < 760;
      const dpr = window.devicePixelRatio || 1;
      if (mobile || smallScreen) q = "low";
      else if (dpr < 1.5 || window.innerWidth < 1440) q = "medium";
    }
    const profile = { ...PROFILES[q] };
    profile.pixelRatio = Math.min(profile.pixelRatio, window.devicePixelRatio || 1);
    return profile;
  }, [override]);
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

export function useWebGLAvailable(): boolean {
  return useMemo(() => {
    try {
      const canvas = document.createElement("canvas");
      return !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
    } catch {
      return false;
    }
  }, []);
}

// ------------------------------------------------- globe drag + inertia

export interface GlobePhysics {
  rotX: number;
  rotY: number;
  velX: number;
  velY: number;
  dragging: boolean;
  hover: number;      // eased 0..1
  ripple: number;     // click ripple time, -1 = inactive
}

/** Real pointer physics: drag → angular velocity; release → inertia with
 * frame-rate-independent damping; auto-rotation blends back in. */
export function useGlobePhysics(opts: {
  autoRotateSpeed: number;
  dragSensitivity: number;
  reducedMotion: boolean;
  interactive: boolean;
  getAutoSpeed?: () => number;
}) {
  const phys = useRef<GlobePhysics>({
    rotX: 0.18,
    rotY: 0,
    velX: 0,
    velY: 0,
    dragging: false,
    hover: 0,
    ripple: -1,
  });
  const pointer = useRef<{ id: number; x: number; y: number } | null>(null);
  const hoverTarget = useRef(0);

  useEffect(() => {
    if (!opts.interactive) return;
    const el = document.getElementById("space-canvas-wrap");
    if (!el) return;

    const down = (e: PointerEvent) => {
      pointer.current = { id: e.pointerId, x: e.clientX, y: e.clientY };
      phys.current.dragging = true;
      phys.current.velX = 0;
      phys.current.velY = 0;
      el.setPointerCapture(e.pointerId);
    };
    const move = (e: PointerEvent) => {
      hoverTarget.current = 1;
      if (!pointer.current || pointer.current.id !== e.pointerId) return;
      const dx = e.clientX - pointer.current.x;
      const dy = e.clientY - pointer.current.y;
      pointer.current = { id: e.pointerId, x: e.clientX, y: e.clientY };
      phys.current.rotY += dx * opts.dragSensitivity;
      phys.current.rotX += dy * opts.dragSensitivity;
      phys.current.velY = dx * opts.dragSensitivity * 60; // per-second velocity
      phys.current.velX = dy * opts.dragSensitivity * 60;
      // clamp vertical rotation ±60°
      const limit = (60 * Math.PI) / 180;
      phys.current.rotX = Math.max(-limit, Math.min(limit, phys.current.rotX));
    };
    const up = (e: PointerEvent) => {
      if (pointer.current?.id !== e.pointerId) return;
      pointer.current = null;
      phys.current.dragging = false;
      hoverTarget.current = 0;
    };
    const click = () => {
      if (!opts.reducedMotion) phys.current.ripple = 0;
    };

    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
    el.addEventListener("pointerleave", up);
    el.addEventListener("click", click);
    return () => {
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
      el.removeEventListener("pointerleave", up);
      el.removeEventListener("click", click);
    };
  }, [opts.interactive, opts.dragSensitivity, opts.reducedMotion]);

  /** Called once per frame from inside the Canvas. */
  const step = (dt: number) => {
    const p = phys.current;
    if (!p.dragging) {
      p.rotY += p.velY * dt;
      p.rotX += p.velX * dt;
      const limit = (60 * Math.PI) / 180;
      p.rotX = Math.max(-limit, Math.min(limit, p.rotX));
      // exponential friction, frame-rate independent
      const damping = Math.exp(-2.6 * dt);
      p.velX *= damping;
      p.velY *= damping;
      // blend back to calm autonomous rotation
      const auto = opts.reducedMotion ? 0 : (opts.getAutoSpeed?.() ?? opts.autoRotateSpeed);
      const blend = 1 - Math.exp(-0.7 * dt);
      p.velY += (auto - p.velY) * blend;
      p.velX += (0 - p.velX) * blend;
    }
    p.hover += (hoverTarget.current - p.hover) * (1 - Math.exp(-6 * dt));
    if (p.ripple >= 0) {
      p.ripple += dt;
      if (p.ripple > 1.6) p.ripple = -1;
    }
  };

  return { phys, step };
}

// -------------------------------------------------- scene state machine

export type SceneState =
  | "BOOT"
  | "GLOBE_ACTIVE"
  | "LOGIN_TRANSITION"
  | "LOGIN"
  | "AUTHENTICATED"
  | "SPACE_BACKGROUND";

export interface TransitionTargets {
  dissolve: number;       // 0 intact → 1 fully dissolved
  globeX: number;         // world-space x offset
  globeScale: number;
  starBoost: number;      // star brightness multiplier
  nebulaIntensity: number;
  camZ: number;
  camDrift: number;       // amplitude of idle camera drift
  globeAutoRotate: number;
}

export const STATE_TARGETS: Record<SceneState, TransitionTargets> = {
  BOOT:              { dissolve: 0, globeX: 0,     globeScale: 0.001, starBoost: 0.5, nebulaIntensity: 0.5, camZ: 8.2, camDrift: 0.04, globeAutoRotate: 0.02 },
  GLOBE_ACTIVE:      { dissolve: 0, globeX: 0,     globeScale: 1,     starBoost: 0.8, nebulaIntensity: 0.8, camZ: 8.2, camDrift: 0.06, globeAutoRotate: 0.08 },
  LOGIN_TRANSITION:  { dissolve: 0.65, globeX: -2.6, globeScale: 0.82, starBoost: 1.15, nebulaIntensity: 1.0, camZ: 8.6, camDrift: 0.05, globeAutoRotate: 0.03 },
  LOGIN:             { dissolve: 0.65, globeX: -2.6, globeScale: 0.82, starBoost: 1.15, nebulaIntensity: 1.0, camZ: 8.6, camDrift: 0.05, globeAutoRotate: 0.03 },
  AUTHENTICATED:     { dissolve: 0.92, globeX: -1.4, globeScale: 0.6, starBoost: 1.0, nebulaIntensity: 1.0, camZ: 9.2, camDrift: 0.03, globeAutoRotate: 0.015 },
  SPACE_BACKGROUND:  { dissolve: 0.92, globeX: -1.4, globeScale: 0.6, starBoost: 1.0, nebulaIntensity: 1.0, camZ: 9.2, camDrift: 0.03, globeAutoRotate: 0.015 },
};

/** Mutable, per-frame eased transition values — never in React state. */
export interface SceneRig extends TransitionTargets {
  state: SceneState;
  enteredAt: number;
}
