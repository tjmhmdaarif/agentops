/** GLSL for the particle globe, star field, atmosphere and nebula.
 * All animation is GPU-side: the CPU only moves a handful of uniforms.
 */

// ---------------------------------------------------------------- globe

export const GLOBE_VERTEX = /* glsl */ `
  attribute float aSeed;        // 0..1 per-particle random
  attribute float aSize;        // base point size
  attribute float aBrightness;  // base brightness
  attribute vec3  aDrift;       // random outward drift direction (unit-ish)

  uniform float uTime;
  uniform float uDissolve;      // 0 = intact globe, 1 = fully dissolved
  uniform vec3  uWaveDir;       // directional dissolution wave axis
  uniform float uNoiseAmp;      // procedural motion strength
  uniform float uHover;         // brightness boost near pointer
  uniform float uSize;          // global size multiplier
  uniform float uPixelRatio;

  varying float vBrightness;
  varying float vLocal;         // per-particle dissolution progress

  // Cheap, smooth pseudo-noise (GPU-friendly, no textures)
  vec3 pnoise(vec3 p, float t) {
    return vec3(
      sin(p.y * 1.7 + t) + sin(p.z * 2.3 + t * 1.3),
      sin(p.z * 1.9 + t * 0.8) + sin(p.x * 2.1 + t),
      sin(p.x * 1.5 + t * 1.1) + sin(p.y * 2.7 + t * 0.7)
    ) * 0.5;
  }

  void main() {
    // Directional wave coordinate (0 at one side, 1 at the other) + random stagger
    float waveCoord = dot(normalize(position), uWaveDir) * 0.5 + 0.5;
    float delay = aSeed * 0.25 + waveCoord * 0.35;
    float local = smoothstep(delay, delay + 0.65, uDissolve);
    vLocal = local;

    // Intact-globe breathing shimmer (subtle, alive)
    float breathe = sin(uTime * 0.9 + aSeed * 6.2831) * 0.004;
    vec3 pos = position * (1.0 + breathe * (1.0 - local));

    // Stage 1: instability jitter as the wave approaches
    float unstable = smoothstep(delay - 0.15, delay, uDissolve) * (1.0 - local);
    pos += pnoise(position * 3.0, uTime * 1.4 + aSeed * 10.0) * 0.02 * unstable * uNoiseAmp;

    // Stage 2+3: detach, outward + curl-ish fluid drift, orbital sideways swirl
    vec3 curlish = pnoise(position * 1.4 + aDrift * 2.0, uTime * 0.35 + aSeed * 6.2831);
    vec3 outward = aDrift * (0.6 + aSeed * 2.4);
    vec3 swirl = normalize(cross(position, vec3(0.0, 1.0, 0.15))) * (0.5 + aSeed);
    vec3 travel = outward * 1.6 + curlish * 1.1 * uNoiseAmp + swirl * 0.7;
    pos += travel * local;

    vec4 mv = modelViewMatrix * vec4(pos, 1.0);

    // Perspective-aware size; particles shrink as they dissolve into dust
    float size = aSize * uSize * (1.0 - local * 0.75);
    gl_PointSize = size * uPixelRatio * (26.0 / -mv.z);

    // Brightness: varied base, brighter mid-dissolve, fading to ambient star level
    float fade = mix(1.0, 0.16, local);
    vBrightness = aBrightness * fade * uHover * (1.0 + unstable * 0.5);

    gl_Position = projectionMatrix * mv;
  }
`;

export const GLOBE_FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  uniform vec3 uColorHot;   // brief color during dissolution
  varying float vBrightness;
  varying float vLocal;

  void main() {
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    if (d > 0.5) discard;
    // Soft round sprite
    float alpha = smoothstep(0.5, 0.08, d);
    vec3 color = mix(uColor, uColorHot, vLocal * 0.6);
    gl_FragColor = vec4(color * vBrightness, alpha * vBrightness);
  }
`;

// ------------------------------------------------------------ atmosphere

export const ATMOS_VERTEX = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vView = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;

export const ATMOS_FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  uniform float uIntensity;
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    // Fresnel rim — barely-there stylized shell
    float rim = pow(1.0 - abs(dot(vNormal, vView)), 3.2);
    gl_FragColor = vec4(uColor, rim * uIntensity);
  }
`;

// ---------------------------------------------------------------- stars

export const STARS_VERTEX = /* glsl */ `
  attribute float aSize;
  attribute float aBrightness;
  attribute float aPhase;    // twinkle phase
  attribute float aDepth;    // 0 far → 1 near (pointer parallax weight)
  uniform float uTime;
  uniform float uSize;
  uniform float uPixelRatio;
  uniform vec2  uPointer;    // -1..1 pointer
  uniform float uParallax;
  uniform float uBoost;      // global brightness boost during transition
  varying float vBrightness;

  void main() {
    vec3 pos = position;
    pos.xy += uPointer * uParallax * aDepth * vec2(-1.0, 1.0) * 6.0;
    vec4 mv = modelViewMatrix * vec4(pos, 1.0);
    float twinkle = 0.72 + 0.28 * sin(uTime * (0.4 + aPhase) + aPhase * 17.0);
    vBrightness = aBrightness * twinkle * uBoost;
    gl_PointSize = aSize * uSize * uPixelRatio * (42.0 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`;

export const STARS_FRAGMENT = /* glsl */ `
  varying float vBrightness;
  void main() {
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    if (d > 0.5) discard;
    float alpha = smoothstep(0.5, 0.05, d);
    gl_FragColor = vec4(vec3(0.82, 0.92, 1.0) * vBrightness, alpha * vBrightness);
  }
`;

// ------------------------------------------------------------- space dust

export const DUST_VERTEX = /* glsl */ `
  attribute float aSize;
  attribute float aBrightness;
  attribute float aSeed;
  uniform float uTime;
  uniform float uSize;
  uniform float uPixelRatio;
  uniform float uFlow;       // drift speed scale (0 for reduced motion)
  varying float vBrightness;

  vec3 curlish(vec3 p, float t) {
    return vec3(
      sin(p.y * 0.9 + t) - cos(p.z * 1.1 + t * 0.7),
      sin(p.z * 1.0 + t * 0.9) - cos(p.x * 0.8 + t),
      sin(p.x * 1.2 + t * 0.8) - cos(p.y * 1.0 + t * 1.1)
    );
  }

  void main() {
    // Slow curl-field drift — fluid, never visibly looping
    vec3 pos = position + curlish(position * 0.35, uTime * 0.05 * uFlow + aSeed * 3.0) * 14.0;
    vec4 mv = modelViewMatrix * vec4(pos, 1.0);
    vBrightness = aBrightness * (0.55 + 0.45 * sin(uTime * 0.3 * uFlow + aSeed * 9.0));
    gl_PointSize = aSize * uSize * uPixelRatio * (30.0 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`;

export const DUST_FRAGMENT = /* glsl */ `
  varying float vBrightness;
  void main() {
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    if (d > 0.5) discard;
    float alpha = smoothstep(0.5, 0.0, d);
    gl_FragColor = vec4(vec3(0.55, 0.72, 0.85) * vBrightness, alpha * vBrightness * 0.5);
  }
`;

// ---------------------------------------------------------------- nebula

export const NEBULA_VERTEX = /* glsl */ `
  varying vec3 vDir;
  void main() {
    vDir = normalize(position);
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
  }
`;

export const NEBULA_FRAGMENT = /* glsl */ `
  uniform float uTime;
  uniform float uIntensity;
  varying vec3 vDir;

  // Compact value-noise fbm — procedural, no textures, intentionally very dark
  float hash(vec3 p) {
    p = fract(p * 0.3183099 + 0.1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
  }
  float noise(vec3 x) {
    vec3 i = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
      mix(mix(hash(i), hash(i + vec3(1,0,0)), f.x), mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
      mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x), mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y),
      f.z
    );
  }
  float fbm(vec3 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
      v += a * noise(p);
      p *= 2.1;
      a *= 0.5;
    }
    return v;
  }

  void main() {
    float n = fbm(vDir * 3.0 + vec3(uTime * 0.004, 0.0, uTime * 0.003));
    n = pow(max(n - 0.45, 0.0) * 1.8, 2.0);
    vec3 deep = vec3(0.008, 0.012, 0.040);   // #02030A-ish
    vec3 mid  = vec3(0.023, 0.063, 0.094);   // #061018-ish
    vec3 color = mix(deep, mid, n) * uIntensity;
    gl_FragColor = vec4(color, 1.0);
  }
`;
