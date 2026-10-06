# Space Scene — Cinematic Particle Globe System

The pre/post-login visual environment: an interactive particle Earth that
dissolves into a permanent deep-space background. Built with three.js +
React Three Fiber, custom GLSL, zero video/image tricks.

## Architecture

```
App.tsx
└── <SceneProvider>                    // sceneStore.tsx — explicit state machine
    ├── <SpaceScene/>  (lazy chunk)    // Canvas + controller + WebGL fallback
    │   ├── SceneController            // eases rig → targets, camera parallax/drift
    │   ├── BootSequencer              // BOOT → GLOBE_ACTIVE
    │   ├── <Nebula/>                  // procedural fbm shell, BackSide sphere
    │   ├── <StarField/>               // 3 real depth layers (far/mid/near shells)
    │   ├── <SpaceDust/>               // curl-field drifting dust
    │   └── <ParticleGlobe/>           // land points + atmosphere + drag physics
    └── <AuthProvider>
        └── <EntryOverlay/>            // boot status, ENTER SYSTEM, LoginPanel
        └── <App/>                     // dashboard floats over SPACE_BACKGROUND
```

## State machine

`BOOT → GLOBE_ACTIVE → LOGIN_TRANSITION → LOGIN → AUTHENTICATED → SPACE_BACKGROUND`

Each state declares targets (`STATE_TARGETS` in `hooks.ts`): dissolve, globe
position/scale, star boost, nebula intensity, camera Z/drift, auto-rotate speed.
A mutable **rig** is eased toward those targets every frame inside the Canvas —
React never re-renders per frame.

## Particle generation

`tools/generate_landmask.py` samples a jittered 0.6° lat/lon grid against real
Natural Earth 110m polygons (ray-casting, holes respected) → 59,685 candidates →
30,000 land-only points in `src/three/landPoints.ts`. At runtime the globe
converts lat/lon → sphere (x = r·cosφ·cosλ, y = r·sinφ, z = r·cosφ·sinλ) with
per-particle attributes: `aSeed, aSize, aBrightness (0.3/0.6/1.0 tiers), aDrift`.

## Globe physics

`useGlobePhysics` — pointer drag maps to angular velocity (pointer capture,
mouse/touch/pen); release applies exponential, frame-rate-independent friction
(`vel *= exp(-2.6·dt)`); velocity blends back to calm auto-rotation
(`blend = 1-exp(-0.7·dt)`); vertical rotation clamped to ±60°; hover adds a
+8% brightness; click fires a 1.6s local ripple via noise-amplitude swell.

## Dissolution shader

GPU-side, directional wave + per-particle stagger:

```
waveCoord  = dot(normalize(position), uWaveDir) * 0.5 + 0.5
delay      = aSeed * 0.25 + waveCoord * 0.35
local      = smoothstep(delay, delay + 0.65, uDissolve)
pos       += (outward * 1.6 + pnoise() * 1.1 + swirl * 0.7) * local
```

Three visible stages: instability jitter (wave approaches) → detach with
outward+curl+orbital forces → shrink/dim to 16% brightness and join the ambient
star field. Color lerps toward a cooler tint mid-flight.

## Space environment

- **Stars**: 3 shells (60–110, 32–60, 14–30 world units), twinkle by phase,
  near layer carries pointer parallax weight.
- **Dust**: curl-ish field `pnoise(position*0.35, t)` — slow, fluid, never loops.
- **Nebula**: value-noise fbm on an inverted 220-unit sphere, palette limited to
  #02030A…#061018. Visible only if you look carefully.
- **Camera**: FOV 52, damped pointer parallax (0.22) + two incommensurate idle
  drift frequencies.

## Performance strategy

All motion is GPU-side (uniforms only from CPU); typed Float32Arrays; additive
blending instead of bloom post-processing; quality profiles
(low 6k / medium 14k / high 26k globe particles) auto-selected from device +
DPR + screen size; pixelRatio capped; `frustumCulled={false}` avoided per-point
overdraw only where needed; three.js is a **separate lazy chunk** (app shell
stays 230 kB gzip). Measured: **59 FPS, 27 MB heap** on desktop Chrome.

## Mobile & accessibility

Mobile/small screens → low profile automatically; drag works via pointer events;
login panel centers. `prefers-reduced-motion` → no inertia, no drift, static
calm field. Login is plain HTML (labels, autocomplete, focus rings) — never
inside WebGL. Canvas is `aria-hidden`, keyboard flows straight to the form.
WebGL unavailable → static CSS star gradient, app fully functional.

## Customization API

```tsx
<SpaceScene quality="auto" interactive />
<ParticleGlobe
  particleCount={24000}
  particleColor="#d9f7ff"
  particleSize={1.35}
  autoRotateSpeed={0.08}
  dragSensitivity={0.005}
  noiseStrength={1.0}
  interactive
  reducedMotion={false}
/>
```

State targets live in `STATE_TARGETS` (hooks.ts) — tune the cinematic without
touching components. Branding strings are in `EntryOverlay.tsx` and the login
panel; credentials/auth are unchanged (`/api/auth/*`).
