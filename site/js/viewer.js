// Shared three.js viewer: same lighting presets for the interactive page and for the
// headless screenshot renders, so every tool's output is judged under identical light.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { OutlineEffect } from 'three/addons/effects/OutlineEffect.js';

// 3-step toon ramp (shadow / mid / lit), nearest filtering -> hard cel-shading bands
function toonRamp() {
  const data = new Uint8Array([90, 90, 90, 255, 175, 175, 175, 255, 255, 255, 255, 255]);
  const t = new THREE.DataTexture(data, 3, 1, THREE.RGBAFormat);
  t.minFilter = t.magFilter = THREE.NearestFilter;
  t.generateMipmaps = false;
  t.needsUpdate = true;
  return t;
}
const NO_OUTLINE = { visible: false };
// clips every rig shares (blender/build_character.py BASE_CLIPS); anything else is a character's signature move
export const BASE_CLIPS = ['Idle', 'Walk', 'Run', 'Jump', 'Wave', 'Hit', 'ArmsUp'];

// ink-wash ramp: ink / wash / paper bands
function inkRamp() {
  const data = new Uint8Array([60, 60, 60, 255, 150, 150, 150, 255, 255, 255, 255, 255]);
  const t = new THREE.DataTexture(data, 3, 1, THREE.RGBAFormat);
  t.minFilter = t.magFilter = THREE.NearestFilter;
  t.generateMipmaps = false;
  t.needsUpdate = true;
  return t;
}


// Artifact hosting can't serve .glb, so the published page ships each model as base64 text next to
// it (<name>.glb.b64.txt). Load the real .glb when it is served (local dev, other hosts), otherwise
// fall back to the base64 copy. Binary first so a stale .b64.txt can never shadow a fresh build.
export async function loadGLTF(url) {
  return withClipExtras(await fetchGLTF(url));
}

async function fetchGLTF(url) {
  const loader = new GLTFLoader();
  if (!url.endsWith('.glb')) return loader.loadAsync(url);
  const bin = await fetch(url).catch(() => null);
  if (bin && bin.ok) return loader.parseAsync(await bin.arrayBuffer(), '');
  const r = await fetch(url + '.b64.txt');
  if (!r.ok) throw new Error(`model not found: ${url}`);
  const s = atob((await r.text()).trim());
  const bytes = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) bytes[i] = s.charCodeAt(i);
  return loader.parseAsync(bytes.buffer, '');
}

// Per-clip metadata written by the Blender builds into animations[].extras (e.g. `hit`: seconds into a
// move where it lands, like an engine's anim notify). GLTFLoader keeps clips in glTF order but drops extras.
function withClipExtras(gltf) {
  (gltf.parser?.json.animations || []).forEach((a, k) => {
    if (gltf.animations[k]) gltf.animations[k].userData = { ...(a.extras || {}) };
  });
  return gltf;
}

// White hit flash: one uniform per stage character, mixed in after lighting, so it works the same on the
// PBR, toon and ink materials (outlines stay dark, like anime/fighting-game hit flashes).
function withFlash(mat, u) {
  if (mat.userData.flash === u) return;
  mat.userData.flash = u;
  const prev = mat.onBeforeCompile, key = mat.customProgramCacheKey() + '+flash';
  mat.onBeforeCompile = function (sh, renderer) {
    prev.call(this, sh, renderer);
    sh.uniforms.uFlash = u;
    sh.fragmentShader = 'uniform float uFlash;\n' + sh.fragmentShader.replace('#include <opaque_fragment>',
      'outgoingLight = mix(outgoingLight, vec3(1.0), uFlash);\n#include <opaque_fragment>');
  };
  mat.customProgramCacheKey = () => key;
  mat.needsUpdate = true;
}

// Sparring feel (fighting-game staples): at impact both fighters freeze for a few frames (hit-stop), the
// defender flashes white, is knocked back along the line of attack, holds, then steps back to its mark.
const SPAR = { hitstop: 0.08, flash: 0.5, flashFade: 0.22, out: 0.14, hold: 0.3, back: 0.55 };  // seconds; flash = white mix (linear)

export const PRESETS = {
  studio: {
    label: '三點打光 Studio',
    bg: ['#3a3f47', '#15171b'],
    env: 0.35,
    exposure: 1.0,
    lights: [
      { type: 'dir', color: '#fff0dc', intensity: 2.6, pos: [2.2, 3.2, 2.6], shadow: true, name: 'Key 主光' },
      { type: 'dir', color: '#cfe0ff', intensity: 0.7, pos: [-3, 1.4, 2.2], name: 'Fill 補光' },
      { type: 'dir', color: '#ffffff', intensity: 3.2, pos: [-1.2, 2.8, -3.4], name: 'Rim 輪廓光' },
      { type: 'hemi', sky: '#bcc8ff', ground: '#3b3027', intensity: 0.35 },
    ],
  },
  sunset: {
    label: '競技場黃昏 Golden hour',
    bg: ['#f2a65a', '#3b2a4a'],
    env: 0.45,
    exposure: 1.05,
    fog: ['#c9876a', 6, 22],
    lights: [
      { type: 'dir', color: '#ffb066', intensity: 3.4, pos: [-3.5, 1.6, -2.4], shadow: true, name: 'Sun 低角度夕陽（逆光）' },
      { type: 'dir', color: '#9db8ff', intensity: 0.9, pos: [2.5, 2.5, 3.0], name: 'Sky fill 天空補光' },
      { type: 'hemi', sky: '#ffd2a1', ground: '#5a3b2a', intensity: 0.6 },
    ],
  },
  night: {
    label: '夜間火把 Torchlight',
    bg: ['#1b2440', '#06080f'],
    env: 0.08,
    exposure: 1.15,
    fog: ['#0b1020', 5, 16],
    lights: [
      { type: 'dir', color: '#7f9cff', intensity: 0.7, pos: [1.5, 4, -3], name: 'Moon 月光' },
      { type: 'point', color: '#ff8a3d', intensity: 9, distance: 7, pos: [1.6, 1.5, 1.4], flicker: true, shadow: true, name: 'Torch R 火把' },
      { type: 'point', color: '#ff9a4a', intensity: 6, distance: 7, pos: [-1.8, 1.3, 1.2], flicker: true, name: 'Torch L 火把' },
      { type: 'hemi', sky: '#2a3b6a', ground: '#120c08', intensity: 0.25 },
    ],
  },
  ink: {
    label: '水墨宣紙 Ink',
    bg: ['#f1ebdd', '#d9ceb6'],
    env: 0.0,
    exposure: 1.0,
    lights: [
      { type: 'dir', color: '#ffffff', intensity: 2.4, pos: [-2.2, 3.4, 2.4], shadow: true, name: 'Key 主光（左上）' },
      { type: 'hemi', sky: '#ffffff', ground: '#bdb29c', intensity: 0.9 },
    ],
  },
  flat: {
    label: '平光（看貼圖）Flat',
    bg: ['#d9dde3', '#aeb4bd'],
    env: 1.0,
    exposure: 1.0,
    lights: [{ type: 'hemi', sky: '#ffffff', ground: '#888888', intensity: 1.2 }],
  },
};

export const VIEWS = {
  front: 0,
  three_quarter: -35,
  side: -90,
  back: 180,
};

// ---------------------------------------------------------------------------------------------
// Spring bones (secondary motion for hair / capes / skirts), VRM-style verlet chains.
// Rig convention (blender/build_character.py): chain joints are bones named spring_<type><id>_<i>,
// each chain ends in a spring_..._end bone; type picks the preset. Sphere colliders are bones named
// col_<bone>_<radius in mm>, capsules are cap_<name>_<radius in mm> with a cap_<name>_end child; cloth tails
// are pushed out of them (legs through skirts, back through capes).
// ---------------------------------------------------------------------------------------------
const SPRING_PRESETS = {
  hair: { stiffness: 2.4, drag: 0.32, gravity: 0.5, hit: 0.015 },
  cloth: { stiffness: 1.0, drag: 0.22, gravity: 1.1, hit: 0.02 },
  skirt: { stiffness: 3.6, drag: 0.4, gravity: 0.4, hit: 0.03 },
  // thick, stiff felt (voxel witch): settles ~14 deg off vertical where `cloth` would sag to ~7 deg and lose the A-line flare
  cape: { stiffness: 3.0, drag: 0.35, gravity: 0.45, hit: 0.025 },
};
const STEP = 1 / 60;

export class SpringBones {
  constructor(root) {
    this.root = root;
    this.joints = [];
    this.colliders = [];
    root.traverse((o) => {
      if (!o.isBone) return;
      let m = o.name.match(/^col_.*_(\d+)$/);
      if (m) this.colliders.push({ bone: o, r: +m[1] / 1000, p: new THREE.Vector3() });
      m = o.name.match(/^cap_.*_(\d+)$/);
      const end = m && o.children.find((c) => c.isBone && c.name.endsWith('_end'));
      if (end) this.colliders.push({ bone: o, end, r: +m[1] / 1000, p: new THREE.Vector3(), q: new THREE.Vector3() });
      m = o.name.match(/^spring_([a-z]+)[A-Za-z0-9]*_\d+$/);
      const child = m && o.children.find((c) => c.isBone && c.name.startsWith('spring_'));
      if (child) this.joints.push({ bone: o, child, preset: SPRING_PRESETS[m[1]] || SPRING_PRESETS.cloth,
        rest: o.quaternion.clone(), axis: child.position.clone().normalize(), q: o.quaternion.clone(),
        cur: new THREE.Vector3(), prev: new THREE.Vector3() });
    });
    this.acc = 0;
    this.needsReset = true;
  }

  get active() { return this.joints.length > 0; }

  // snap every tail to the current (animated) rest pose - after loading, scaling or teleporting
  reset() {
    this.root.updateMatrixWorld(true);
    for (const j of this.joints) {
      j.bone.quaternion.copy(j.rest);
      j.q.copy(j.rest);
      j.bone.updateMatrixWorld(true);
      j.child.getWorldPosition(j.cur);
      j.prev.copy(j.cur);
    }
    this.needsReset = false;
  }

  update(dt) {
    if (!this.joints.length) return;
    if (this.needsReset) this.reset();
    this.acc = Math.min(this.acc + dt, STEP * 4);
    if (this.acc < STEP) {  // keep the last simulated pose (the mixer may have overwritten it)
      for (const j of this.joints) j.bone.quaternion.copy(j.q);
      return;
    }
    while (this.acc >= STEP) { this.acc -= STEP; this._step(STEP); }
  }

  _step(dt) {
    const head = new THREE.Vector3(), tail = new THREE.Vector3(), dir = new THREE.Vector3();
    const pq = new THREE.Quaternion(), frame = new THREE.Quaternion(), turn = new THREE.Quaternion();
    this.root.updateMatrixWorld(true);
    for (const c of this.colliders) { c.bone.getWorldPosition(c.p); c.end?.getWorldPosition(c.q); }
    const seg = new THREE.Line3(), near = new THREE.Vector3();
    for (const j of this.joints) {
      const { bone, preset } = j;
      bone.quaternion.copy(j.rest);
      bone.updateMatrixWorld(true);
      bone.getWorldPosition(head);
      const len = j.child.getWorldPosition(tail).distanceTo(head);
      bone.parent.getWorldQuaternion(pq);
      frame.copy(pq).multiply(j.rest);
      dir.copy(j.axis).applyQuaternion(frame);  // where the bone points without physics
      const next = j.cur.clone()
        .addScaledVector(tail.subVectors(j.cur, j.prev), 1 - preset.drag)
        .addScaledVector(dir, preset.stiffness * dt * len);
      next.y -= preset.gravity * dt * len;
      next.sub(head).setLength(len).add(head);
      for (const c of this.colliders) {
        if (c.end) seg.set(c.p, c.q).closestPointToPoint(next, true, near);
        else near.copy(c.p);
        const d = next.clone().sub(near);
        const r = c.r + preset.hit;
        if (d.lengthSq() < r * r) next.copy(near).addScaledVector(d.normalize(), r).sub(head).setLength(len).add(head);
      }
      j.prev.copy(j.cur);
      j.cur.copy(next);
      const to = next.clone().sub(head).applyQuaternion(frame.clone().invert()).normalize();
      turn.setFromUnitVectors(j.axis, to);
      j.q.copy(j.rest).multiply(turn);
      bone.quaternion.copy(j.q);
      bone.updateMatrixWorld(true);
    }
  }
}

// ---------------------------------------------------------------------------------------------
// Anime face shadows (SDF-style, procedural). Meshes exported with a _FACEMASK attribute get head-space
// shading in toon mode: the light's angle around the head moves one clean shadow boundary across the
// face (curved toward the far side at brow and chin), instead of normal-based blotches.
// ---------------------------------------------------------------------------------------------
export function makeFaceRig(root) {
  let mesh = null, head = null;
  root.traverse((o) => {
    if (o.isSkinnedMesh && o.geometry.attributes._facemask) mesh = o;
    if (o.isBone && o.name === 'head') head = o;
  });
  if (!mesh || !head) return null;
  root.updateMatrixWorld(true);  // called at load: bones are still in their rest pose
  const pos = mesh.geometry.attributes.position, mask = mesh.geometry.attributes._facemask;
  const pts = [], v = new THREE.Vector3(), c = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    if (mask.getX(i) < 0.5) continue;
    pts.push(v.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld).clone());
    c.add(pts[pts.length - 1]);
  }
  c.divideScalar(pts.length);
  const F = new THREE.Vector3(0, 0, 1).applyQuaternion(mesh.getWorldQuaternion(new THREE.Quaternion()));  // glTF front = +Z
  const U = new THREE.Vector3(0, 1, 0), R = new THREE.Vector3().crossVectors(U, F).normalize();
  let sx = 1e-3, sy = 1e-3;
  for (const p of pts) { sx = Math.max(sx, Math.abs(p.clone().sub(c).dot(R))); sy = Math.max(sy, Math.abs(p.clone().sub(c).dot(U))); }
  const inv = head.getWorldQuaternion(new THREE.Quaternion()).invert();
  const V3 = () => new THREE.Vector3();
  return {
    head, centre: c.clone().applyMatrix4(head.matrixWorld.clone().invert()),
    F: F.applyQuaternion(inv), R: R.applyQuaternion(inv), U: U.clone().applyQuaternion(inv),
    uniforms: { uFaceCentre: { value: V3() }, uFaceF: { value: V3() }, uFaceR: { value: V3() }, uFaceU: { value: V3() },
      uFaceSize: { value: new THREE.Vector2(sx, sy) }, uFaceLight: { value: new THREE.Vector3(0, 1, 1).normalize() } },
  };
}

function updateFaceRig(rig, lightDir) {
  const u = rig.uniforms, q = rig.head.getWorldQuaternion(new THREE.Quaternion());
  u.uFaceCentre.value.copy(rig.centre).applyMatrix4(rig.head.matrixWorld);
  u.uFaceF.value.copy(rig.F).applyQuaternion(q);
  u.uFaceR.value.copy(rig.R).applyQuaternion(q);
  u.uFaceU.value.copy(rig.U).applyQuaternion(q);
  u.uFaceLight.value.copy(lightDir);
}

const FACE_VERT = `
  #ifdef FACE_SDF
    vFaceMask = _facemask;
    vFaceWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;
  #endif`;
const FACE_FRAG = `
  #ifdef FACE_SDF
  if (vFaceMask > 0.5) {
    vec3 L = normalize(uFaceLight), F = normalize(uFaceF), R = normalize(uFaceR), U = normalize(uFaceU);
    vec3 Lh = L - U * dot(L, U);
    float phi = atan(dot(Lh, R), dot(Lh, F));                 // 0 = light in front of the face
    vec3 p = vFaceWorld - uFaceCentre;
    float x = dot(p, R) / uFaceSize.x, y = dot(p, U) / uFaceSize.y;
    float farSide = -sign(phi) * x;                            // 1 at the cheek turned away from the light
    float edge = cos(phi) * 1.1 + 0.22 * y * y - 0.08 * y;     // boundary bends round brow and chin
    float lit = length(Lh) < 0.05 ? step(0.0, dot(L, F)) : smoothstep(-0.05, 0.05, edge - farSide);
    vec3 nW = normalize(F * 0.35 + mix(-L, L, lit));          // synthetic normal -> exactly lit / shadow band
    normal = normalize((viewMatrix * vec4(nW, 0.0)).xyz);
  }
  #endif`;

// stride per clip cycle in leg lengths (from blender/build_character.py walk_keys / run_keys swings)
const LOCO = { Walk: 1.75, Run: 2.48 };

// hip -> knee -> ankle length of a glTF character (bone names lose their dots in three.js)
function legLength(root) {
  const b = {};
  root.traverse((o) => { if (o.isBone && /^(thighL|shinL|footL)$/.test(o.name)) b[o.name] = o; });
  root.updateMatrixWorld(true);
  if (!b.thighL || !b.shinL || !b.footL) return 0.8;
  const p = (o) => o.getWorldPosition(new THREE.Vector3());
  return p(b.thighL).distanceTo(p(b.shinL)) + p(b.shinL).distanceTo(p(b.footL));
}

export class Viewer {
  constructor(canvas, { preserveDrawingBuffer = false, controls = true, ground = true } = {}) {
    this.canvas = canvas;
    const r = (this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer }));
    r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.toneMapping = THREE.ACESFilmicToneMapping;
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFSoftShadowMap;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(30, 1, 0.05, 100);
    this.pmrem = new THREE.PMREMGenerator(r);
    this.envTex = this.pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environment = this.envTex;
    this.lightGroup = new THREE.Group();
    this.scene.add(this.lightGroup);
    this.clock = new THREE.Clock();
    this.mixer = null;
    this.clips = [];
    this.model = null;
    this.target = new THREE.Vector3(0, 0.9, 0);
    this.viewAngle = VIEWS.three_quarter;
    this.distance = 5;

    if (ground) {
      const g = new THREE.Mesh(
        new THREE.CircleGeometry(2.2, 64),
        new THREE.MeshStandardMaterial({ color: '#6b6258', roughness: 0.92, metalness: 0 }),
      );
      g.rotation.x = -Math.PI / 2;
      g.receiveShadow = true;
      g.material.userData.outlineParameters = NO_OUTLINE;
      this.ground = g;
      this.scene.add(g);
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(2.2, 2.35, 64),
        new THREE.MeshStandardMaterial({ color: '#8a7b62', roughness: 0.8 }),
      );
      ring.rotation.x = -Math.PI / 2;
      ring.material.userData.outlineParameters = NO_OUTLINE;
      ring.position.y = 0.001;
      this.scene.add(ring);
    }
    if (controls) {
      this.controls = new OrbitControls(this.camera, canvas);
      this.controls.enableDamping = true;
      this.controls.target.copy(this.target);
    }
    this.setPreset('studio');
    this._loop = this._loop.bind(this);
    this.resize();
  }

  resize() {
    const w = this.canvas.clientWidth || this.canvas.width;
    const h = this.canvas.clientHeight || this.canvas.height;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  setPreset(name) {
    const p = PRESETS[name];
    this.presetName = name;
    this.lightGroup.clear();
    this.flickers = [];
    const [top, bottom] = p.bg;
    this.scene.background = gradientTexture(top, bottom);
    const fs = this.sceneMode ? 3 : 1; // arena is ~10x bigger than the portrait set
    this.scene.fog = p.fog ? new THREE.Fog(p.fog[0], p.fog[1] * fs, p.fog[2] * fs) : null;
    this.scene.environmentIntensity = p.env;
    this.renderer.toneMappingExposure = p.exposure;
    for (const L of p.lights) {
      let light;
      if (L.type === 'dir') {
        light = new THREE.DirectionalLight(L.color, L.intensity);
        light.position.set(...L.pos);
        light.target.position.set(0, 0.9, 0);
        this.lightGroup.add(light.target);
      } else if (L.type === 'point') {
        light = new THREE.PointLight(L.color, L.intensity, L.distance, 1.6);
        light.position.set(...L.pos);
        const flame = new THREE.Mesh(new THREE.SphereGeometry(0.06, 12, 8), new THREE.MeshBasicMaterial({ color: L.color }));
        flame.position.copy(light.position);
        this.lightGroup.add(flame);
        if (L.flicker) this.flickers.push({ light, base: L.intensity, seed: Math.random() * 10 });
      } else if (L.type === 'hemi') {
        light = new THREE.HemisphereLight(L.sky, L.ground, L.intensity);
      }
      if (L.shadow) {
        light.castShadow = true;
        light.shadow.mapSize.set(2048, 2048);
        light.shadow.bias = -0.0004;
        light.shadow.normalBias = 0.02;
        if (light.shadow.camera.isOrthographicCamera) {
          const s = this.sceneMode ? 11 : 2.5;
          if (this.sceneMode) light.position.multiplyScalar(4);
          Object.assign(light.shadow.camera, { left: -s, right: s, top: this.sceneMode ? s : 3, bottom: this.sceneMode ? -s : -1, near: 0.1, far: this.sceneMode ? 60 : 15 });
          light.shadow.camera.updateProjectionMatrix();
        }
      }
      this.lightGroup.add(light);
    }
    if (this.sceneMode && name === 'night') {
      // swap the portrait torches for the arena's four braziers (Blender (x,y,z) -> glTF (x,z,-y))
      this.lightGroup.children.filter((o) => o.isPointLight || (o.isMesh && o.material.isMeshBasicMaterial)).forEach((o) => this.lightGroup.remove(o));
      this.flickers = [];
      for (let k = 0; k < 4; k++) {
        const a = (Math.PI / 2) * k + Math.PI / 4;
        const light = new THREE.PointLight('#ff8a3d', 22, 14, 1.6);
        light.position.set(6.2 * Math.cos(a), 1.6, -6.2 * Math.sin(a));
        if (k < 2) {
          light.castShadow = true;
          light.shadow.mapSize.set(1024, 1024);
          light.shadow.bias = -0.002;
        }
        this.lightGroup.add(light);
        this.flickers.push({ light, base: 22, seed: k * 3.1 });
      }
    }
  }

  async load(url, { targetHeight = null, faceYaw = 0 } = {}) {
    if (this.model) {
      this.scene.remove(this.model);
      this.model.traverse((o) => o.geometry && o.geometry.dispose());
    }
    const gltf = await loadGLTF(url);
    const root = new THREE.Group();
    const model = gltf.scene;
    model.rotation.y = THREE.MathUtils.degToRad(faceYaw);
    root.add(model);
    model.traverse((o) => {
      if (o.isMesh) {
        o.castShadow = true;
        o.receiveShadow = true;
        if (o.material && o.material.map) o.material.map.anisotropy = 8;
      }
    });
    // normalise: feet on the ground, centred, optional uniform height
    root.updateMatrixWorld(true);
    let box = new THREE.Box3().setFromObject(root);
    const size = box.getSize(new THREE.Vector3());
    if (targetHeight) root.scale.setScalar(targetHeight / size.y);
    root.updateMatrixWorld(true);
    box = new THREE.Box3().setFromObject(root);
    const c = box.getCenter(new THREE.Vector3());
    root.position.set(-c.x, -box.min.y, -c.z);
    this.scene.add(root);
    this.model = root;
    this.gltf = gltf;
    this.stats = meshStats(root);

    const h = box.max.y - box.min.y;
    this.modelHeight = h;
    this.target.set(0, h * 0.5, 0);
    this.distance = h * 2.4 + 0.6;
    this.clips = gltf.animations || [];
    this.mixer = this.clips.length ? new THREE.AnimationMixer(model) : null;
    this.springs = new SpringBones(root);
    this.faceRigs = [];
    this._addFaceRig(root);
    this._applyMaterials();
    this.setView(this.viewKey || 'three_quarter');
    return this.stats;
  }

  // Scene mode: static environment (no normalisation) + several characters.
  async loadScene({ arena, characters = [], target = [0, 1.0, 0], distance = 9, height = 0.35 }) {
    this.sceneMode = true;
    this.setPreset(this.presetName);
    if (this.ground) this.ground.visible = false;
    this.scene.children.filter((o) => o.isMesh && o.geometry?.type === 'RingGeometry').forEach((o) => (o.visible = false));
    const env = (await loadGLTF(arena)).scene;
    env.traverse((o) => {
      if (o.isMesh) {
        o.material.userData.outlineParameters = NO_OUTLINE;
        o.receiveShadow = true;
        o.castShadow = !/sand|cliff/.test(o.name);
      }
    });
    this.scene.add(env);
    await this.loadCast(characters);
    this.target.set(...target);
    this.distance = distance;
    this.sceneHeight = height;
    this.setView(this.viewKey || 'three_quarter');
  }

  // Replace the characters standing in the scene (arena stage); shading applies to them too.
  async loadCast(characters) {
    for (const c of this.cast || []) this.scene.remove(c);
    this.cast = [];
    this.mixers = [];  // one slot per cast member (null when it has no animation)
    this.castClips = [];
    this.castActions = [];
    this.castSprings = [];
    this.castHome = [];
    this.castLeg = [];
    this.castFlash = [];
    this.impacts = [];
    this.loco = null;
    this.faceRigs = (this.faceRigs || []).filter((r) => this.model && r.root === this.model);
    const loaded = await Promise.all(characters.map((c) => loadGLTF(c.url)));
    loaded.forEach((g, i) => {
      const c = characters[i];
      const m = g.scene;
      m.position.set(...c.pos);
      m.rotation.y = THREE.MathUtils.degToRad(c.yaw || 0);
      const flash = { value: 0 };
      m.traverse((o) => o.isMesh && ((o.castShadow = true), (o.receiveShadow = true), (o.userData.flash = flash)));
      this.castFlash.push(flash);
      this.scene.add(m);
      this.cast.push(m);
      this.castClips.push(g.animations);
      this.castSprings.push(new SpringBones(m));
      this._addFaceRig(m);
      this.mixers.push(g.animations.length ? new THREE.AnimationMixer(m) : null);
      this.castActions.push(null);
      this.castHome.push({ pos: m.position.clone(), yaw: m.rotation.y });
      this.castLeg.push(legLength(m));
    });
    this.playCastClip(this.castClip || 'Idle', 0);
    this._applyMaterials();
  }

  // Every cast member plays the same clip (cross-faded); 'signature' = each character's own move.
  // Members without that clip fall back to Idle.
  playCastClip(name, fade = 0.3) {
    this.castClip = name;
    this._clearImpacts();
    if (name === 'spar') return this._startSpar();
    this.spar = null;
    (this.cast || []).forEach((m, i) => {
      const mx = this.mixers[i], clips = this.castClips[i];
      if (!mx || !clips.length) return;
      const pick = name === 'signature'
        ? clips.find((c) => !BASE_CLIPS.includes(c.name))
        : clips.find((c) => c.name === name);
      const next = mx.clipAction(pick || clips.find((c) => c.name === 'Idle') || clips[0]);
      const prev = this.castActions[i];
      if (next === prev) return;
      next.reset().setLoop(THREE.LoopRepeat, Infinity).setEffectiveWeight(1).setEffectiveTimeScale(1).play();
      if (prev && fade > 0) next.crossFadeFrom(prev, fade, false);
      else if (prev) prev.stop();
      this.castActions[i] = next;
    });
    this._startLoco(LOCO[name] ? name : null);
  }

  // Walk / Run on the stage move the cast round a circle in the arena instead of treading in place.
  // Every member shares one angular speed (no overtaking); each one's clip is time-scaled so the feet
  // match its own stride (short chibi legs pedal faster). Other clips walk everyone back to their marks.
  _startLoco(name) {
    const n = this.cast?.length || 0;
    const from = this.cast.map((m) => ({ pos: m.position.clone(), yaw: m.rotation.y }));
    if (!name || !n) {
      this.loco = this.loco && { ...this.loco, leaving: true, t: 0, from };
      return;
    }
    const speeds = this.cast.map((m, i) => {
      const clip = this.castActions[i]?.getClip();
      return clip ? (LOCO[name] * this.castLeg[i]) / clip.duration : 0;
    }).filter((v) => v > 0).sort((a, b) => a - b);
    const v = speeds.length ? speeds[Math.floor(speeds.length / 2)] : 1;  // median natural speed
    const R = THREE.MathUtils.clamp(0.25 * n + 1.0, 1.4, 2.2);  // stays inside the stage camera's frame
    const order = this.castHome.map((h, i) => [Math.atan2(h.pos.z, h.pos.x), i]).sort((a, b) => a[0] - b[0]);
    const theta = [];
    order.forEach(([, i], k) => { theta[i] = Math.PI / 2 + (2 * Math.PI * k) / n; });
    this.loco = { name, v, R, omega: v / R, theta, t: 0, from, leaving: false };
    this.cast.forEach((m, i) => {
      const a = this.castActions[i];
      const clip = a?.getClip();
      if (a && clip) a.setEffectiveTimeScale(THREE.MathUtils.clamp(v / ((LOCO[name] * this.castLeg[i]) / clip.duration), 0.5, 2.5));
    });
  }

  // play one clip on cast member i (cross-faded); once = play through and hold the last pose
  _castPlay(i, name, once = false, fade = 0.2) {
    const mx = this.mixers[i], clips = this.castClips[i];
    if (!mx || !clips.length) return null;
    const clip = (name === 'signature' ? clips.find((c) => !BASE_CLIPS.includes(c.name)) : clips.find((c) => c.name === name))
      || clips.find((c) => c.name === 'Idle') || clips[0];
    const next = mx.clipAction(clip), prev = this.castActions[i];
    next.reset().setLoop(once ? THREE.LoopOnce : THREE.LoopRepeat, Infinity).setEffectiveTimeScale(1).setEffectiveWeight(1);
    next.clampWhenFinished = once;
    next.play();
    if (prev && prev !== next) next.crossFadeFrom(prev, fade, false);
    this.castActions[i] = next;
    return clip;
  }

  // Sparring: neighbours pair up face to face; the attacker plays its signature move and the partner
  // reacts with Hit when it lands (the clip's `hit` time from the build, else 45% in), then they swap roles.
  _startSpar() {
    const n = this.cast?.length || 0;
    // pair similar sizes (leg length) -> in the style line-up each style's two characters face off
    const order = this.castLeg.map((l, i) => [l, i]).sort((a, b) => b[0] - a[0]).map(([, i]) => i);
    const from = this.cast.map((m) => ({ pos: m.position.clone(), yaw: m.rotation.y }));
    const targets = this.castHome.map((h) => ({ pos: h.pos.clone(), yaw: h.yaw }));
    const pairs = Math.floor(n / 2);
    const homeZ = this.castHome.reduce((z, h) => z + h.pos.z, 0) / Math.max(1, n);
    this.spar = [];
    for (let p = 0; p < pairs; p++) {
      const a = order[2 * p], b = order[2 * p + 1];
      // one pair: centre stage; several: a two-column grid, big pairs at the back, small ones in front
      const row = Math.floor(p / 2), rows = Math.ceil(pairs / 2);
      const c = pairs === 1 ? new THREE.Vector3(0, this.castHome[a].pos.y, homeZ)
        : new THREE.Vector3(p % 2 ? 1.55 : -1.55, this.castHome[a].pos.y, -0.9 + (rows > 1 ? (1.6 * row) / (rows - 1) : 0));
      const d = 0.9 * (this.castLeg[a] + this.castLeg[b]) + 0.35;  // reach grows with body size
      targets[a] = { pos: c.clone().add(new THREE.Vector3(-d / 2, 0, 0)), yaw: Math.PI / 2 };
      targets[b] = { pos: c.clone().add(new THREE.Vector3(d / 2, 0, 0)), yaw: -Math.PI / 2 };
      this.spar.push({ pair: [a, b], attacker: p % 2, t: -0.6 - 0.35 * p, phase: 'wait' });
    }
    this.cast.forEach((m, i) => this._castPlay(i, 'Idle'));
    this.loco = { targets, t: 0, from, leaving: false };
  }

  _updateSpar(dt) {
    for (const s of this.spar || []) {
      s.t += dt;
      const atk = s.pair[s.attacker], def = s.pair[1 - s.attacker];
      const move = this.castActions[atk];  // action time, not wall time: hit-stop pauses it
      if (s.phase === 'wait' && s.t >= 0) {
        s.clip = this._castPlay(atk, 'signature', true);
        this._castPlay(def, 'Idle');
        s.phase = 'attack';
      } else if (s.phase === 'attack' && s.clip && move.time >= (s.clip.userData?.hit ?? 0.45 * s.clip.duration)) {
        this._castPlay(def, 'Hit', true, 0.08);
        this._impact(atk, def);
        s.phase = 'recover';
      } else if (s.phase === 'recover' && move.time >= s.clip.duration - 1e-4) {
        s.t = 0;
        s.phase = 'rest';
      } else if (s.phase === 'rest' && s.t >= 0.5) {
        this._castPlay(atk, 'Idle');
        this._castPlay(def, 'Idle');
        s.attacker = 1 - s.attacker;
        s.t = -0.5;
        s.phase = 'wait';
      }
    }
    this._updateImpacts(dt);
  }

  _impact(atk, def) {
    const a = this.cast[atk].position, d = this.cast[def].position;
    const dir = new THREE.Vector3(d.x - a.x, 0, d.z - a.z).normalize();
    this.impacts = this.impacts.filter((k) => k.atk !== atk && k.def !== def);
    this.impacts.push({ atk, def, t: 0, dir, dist: 0.1 + 0.18 * this.castLeg[def] });  // bigger bodies slide further
  }

  // runs after _updateLoco has placed everyone on their marks: offsets the knocked-back defender,
  // drives its flash and freezes both fighters' animation during the hit-stop
  _updateImpacts(dt) {
    if (!this.impacts) return;  // single-model viewers have no stage cast
    const frozen = new Set();
    for (const k of this.impacts) {
      k.t += dt;
      const S = SPAR, t = k.t - S.hitstop;
      if (t < 0) frozen.add(k.atk).add(k.def);
      const push = t < 0 ? 0 : t < S.out ? 1 - (1 - t / S.out) ** 3
        : 1 - THREE.MathUtils.smoothstep(t, S.out + S.hold, S.out + S.hold + S.back);
      this.cast[k.def].position.addScaledVector(k.dir, k.dist * push);
      this.castFlash[k.def].value = S.flash * Math.max(0, 1 - k.t / S.flashFade) ** 2;  // pops on the impact frame, fades at once
    }
    this.impacts = this.impacts.filter((k) => k.t < SPAR.hitstop + SPAR.out + SPAR.hold + SPAR.back);
    (this.mixers || []).forEach((mx, i) => mx && (mx.timeScale = frozen.has(i) ? 0 : 1));
  }

  _clearImpacts() {
    this.impacts = [];
    (this.castFlash || []).forEach((f) => (f.value = 0));
    (this.mixers || []).forEach((mx) => mx && (mx.timeScale = 1));
  }

  _updateLoco(dt) {
    const L = this.loco;
    if (!L) return;
    L.t += dt;
    const blend = THREE.MathUtils.smoothstep(L.t, 0, 0.8);
    this.cast.forEach((m, i) => {
      let pos, yaw;
      if (L.leaving) {
        pos = this.castHome[i].pos; yaw = this.castHome[i].yaw;
      } else if (L.targets) {
        ({ pos, yaw } = L.targets[i]);
      } else {
        const th = L.theta[i] + L.omega * L.t;
        pos = new THREE.Vector3(L.R * Math.cos(th), this.castHome[i].pos.y, L.R * Math.sin(th));
        yaw = Math.atan2(-Math.sin(th), Math.cos(th));  // face along the counter-clockwise tangent
      }
      m.position.lerpVectors(L.from[i].pos, pos, blend);
      const d = Math.atan2(Math.sin(yaw - L.from[i].yaw), Math.cos(yaw - L.from[i].yaw));
      m.rotation.y = L.from[i].yaw + d * blend;
    });
    if (L.leaving && blend >= 1) this.loco = null;
  }

  playClip(name) {
    if (!this.mixer) return;
    this.mixer.stopAllAction();
    const clip = this.clips.find((c) => c.name === name);
    if (clip) this.mixer.clipAction(clip).play();
  }

  setView(key) {
    this.viewKey = key;
    const a = THREE.MathUtils.degToRad(VIEWS[key] ?? 0);
    this.camera.position.set(
      Math.sin(a) * this.distance,
      this.target.y + this.distance * (this.sceneHeight ?? 0.12),
      Math.cos(a) * this.distance,
    );
    this.camera.lookAt(this.target);
    if (this.controls) {
      this.controls.target.copy(this.target);
      this.controls.update();
    }
  }

  // 'pbr' (default) | 'toon': cel shading (toon ramp + inverted-hull outlines) for anime characters
  setShading(mode) {
    this.shading = mode;
    if (mode === 'toon' || mode === 'ink') {
      const ink = mode === 'ink';
      this.outline = new OutlineEffect(this.renderer, ink
        ? { defaultThickness: 0.0065, defaultColor: [0.05, 0.05, 0.06] }
        : { defaultThickness: 0.0035, defaultColor: [0.12, 0.08, 0.1] });
      this.renderer.toneMapping = ink ? THREE.NoToneMapping : THREE.NeutralToneMapping;
    } else {
      this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    }
    if (this.ground) {  // paper ground for ink, stone otherwise
      this.ground.material.color.set(mode === 'ink' ? '#e4d9c3' : '#6b6258');
    }
    this._applyMaterials();
  }

  _toonFor(m, mesh) {
    this.ramp ??= toonRamp();
    const rig = mesh?.userData.faceRig;
    const t = new THREE.MeshToonMaterial({
      map: m.map || null, color: m.color ? m.color.clone() : new THREE.Color(1, 1, 1),
      emissive: m.emissive ? m.emissive.clone() : new THREE.Color(0, 0, 0), emissiveMap: m.emissiveMap || null,
      emissiveIntensity: m.emissiveIntensity ?? 1, gradientMap: this.ramp, vertexColors: m.vertexColors,
    });
    // anime rim light: fresnel term added after lighting so dark clothes keep a readable silhouette
    t.onBeforeCompile = (sh) => {
      sh.fragmentShader = sh.fragmentShader.replace('#include <opaque_fragment>', `
        float rimF = pow(1.0 - clamp(dot(normalize(normal), normalize(vViewPosition)), 0.0, 1.0), 4.0);
        outgoingLight += vec3(0.55, 0.6, 0.7) * smoothstep(0.35, 0.6, rimF) * 0.45 * (1.0 - FACE_MASK);
        #include <opaque_fragment>`);
      if (!rig) {
        sh.fragmentShader = '#define FACE_MASK 0.0\n' + sh.fragmentShader;
        return;
      }
      Object.assign(sh.uniforms, rig.uniforms);
      sh.vertexShader = '#define FACE_SDF\nattribute float _facemask;\nvarying float vFaceMask;\nvarying vec3 vFaceWorld;\n'
        + sh.vertexShader.replace('#include <project_vertex>', '#include <project_vertex>' + FACE_VERT);
      sh.fragmentShader = '#define FACE_SDF\n#define FACE_MASK step(0.5, vFaceMask)\nvarying float vFaceMask;\nvarying vec3 vFaceWorld;\n'
        + 'uniform vec3 uFaceCentre, uFaceF, uFaceR, uFaceU, uFaceLight;\nuniform vec2 uFaceSize;\n'
        + sh.fragmentShader.replace('#include <normal_fragment_maps>', '#include <normal_fragment_maps>' + FACE_FRAG)
          // anime faces take no cast shadows (hair bangs would smear the clean SDF boundary)
          .replace('#include <lights_fragment_begin>',
            THREE.ShaderChunk.lights_fragment_begin.replaceAll('&& receiveShadow )', '&& receiveShadow && vFaceMask < 0.5 )'));
    };
    t.customProgramCacheKey = () => (rig ? 'toon-face' : 'toon');
    return t;
  }

  // ink-wash: luminance -> ink tones, red accents kept, paper grain, toon bands
  _inkFor(m) {
    this.inkRampTex ??= inkRamp();
    const t = new THREE.MeshToonMaterial({
      map: m.map || null, color: m.color ? m.color.clone() : new THREE.Color(1, 1, 1),
      gradientMap: this.inkRampTex, vertexColors: m.vertexColors,
      emissive: m.emissive ? m.emissive.clone().multiplyScalar(0.25) : new THREE.Color(0, 0, 0), emissiveMap: m.emissiveMap || null,
    });
    t.onBeforeCompile = (sh) => {
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <map_fragment>', `#include <map_fragment>
          float lum = dot(diffuseColor.rgb, vec3(0.299, 0.587, 0.114));
          float redness = smoothstep(0.25, 0.4, diffuseColor.r - max(diffuseColor.g, diffuseColor.b));  // only true reds
          vec3 inkTone = mix(vec3(0.07, 0.07, 0.08), vec3(0.97, 0.95, 0.9), smoothstep(0.015, 0.6, lum));
          diffuseColor.rgb = mix(inkTone, vec3(0.72, 0.14, 0.11), redness);`)
        .replace('#include <opaque_fragment>', `
          float g = fract(sin(dot(floor(gl_FragCoord.xy * 0.75), vec2(12.9898, 78.233))) * 43758.5453);
          outgoingLight *= 0.9 + 0.1 * g;               // paper grain / dry brush
          outgoingLight = mix(outgoingLight, vec3(0.93, 0.9, 0.84), 0.06);
          #include <opaque_fragment>`);
    };
    return t;
  }

  _applyMaterials() {
    for (const root of [this.model, ...(this.cast || [])].filter(Boolean)) root.traverse((o) => {
      if (!o.isMesh) return;
      o.userData.orig ??= o.material;
      const m = o.userData.orig;
      const mode = this.debugMode || 'lit';
      if (mode === 'albedo')
        o.material = new THREE.MeshBasicMaterial({ map: m.map || null, color: m.color, vertexColors: !!o.geometry.attributes.color });
      else if (mode === 'wire') o.material = new THREE.MeshBasicMaterial({ color: '#37e0c8', wireframe: true });
      else if (this.shading === 'toon') o.material = (o.userData.toon ??= this._toonFor(m, o));
      else if (this.shading === 'ink') o.material = (o.userData.ink ??= this._inkFor(m));
      else o.material = m;
      if (mode !== 'lit') o.material.userData.outlineParameters = NO_OUTLINE;
      if (o.userData.flash) withFlash(o.material, o.userData.flash);
    });
  }

  setDebug(mode) {
    this.debugMode = mode;
    return this._applyMaterials();
  }

  renderOnce(dt = 0) {
    this.advance(dt);
    if (this.faceRigs?.length && this.shading === 'toon') {
      const L = this._keyLightDir();
      for (const r of this.faceRigs) updateFaceRig(r, L);
    }
    const t = performance.now() / 1000;
    // procedural blink for models exported with a 'Blink' morph target
    const blinkPhase = (t % 3.6) / 3.6;
    const blink = blinkPhase > 0.955 ? Math.sin(((blinkPhase - 0.955) / 0.045) * Math.PI) : 0;
    for (const root of [this.model, ...(this.cast || [])]) root?.traverse((o) => {
      const i = o.morphTargetDictionary?.Blink;
      if (i !== undefined) o.morphTargetInfluences[i] = blink;
    });
    for (const f of this.flickers)
      f.light.intensity = f.base * (0.85 + 0.15 * Math.sin(t * 13 + f.seed) * Math.sin(t * 7.3 + f.seed * 2));
    if (this.controls) this.controls.update();
    if ((this.shading === 'toon' || this.shading === 'ink') && this.outline) this.outline.render(this.scene, this.camera);
    else this.renderer.render(this.scene, this.camera);
  }

  _addFaceRig(root) {
    const rig = makeFaceRig(root);
    if (!rig) return;
    rig.root = root;
    root.traverse((o) => { if (o.isSkinnedMesh && o.geometry.attributes._facemask) o.userData.faceRig = rig; });
    this.faceRigs.push(rig);
  }

  // direction towards the key light for face shading: the shadow-casting directional light
  // (rim lights can be brighter than the key, so intensity alone picks the wrong one)
  _keyLightDir() {
    let best = null;
    const score = (l) => (l.castShadow ? 100 : 0) + l.intensity;
    this.lightGroup.traverse((l) => { if (l.isDirectionalLight && (!best || score(l) > score(best))) best = l; });
    const d = new THREE.Vector3(0.3, 1, 1);
    if (best) d.copy(best.getWorldPosition(new THREE.Vector3())).sub(best.target.getWorldPosition(new THREE.Vector3()));
    return d.normalize();
  }

  // animation + secondary motion without drawing (headless renders step to a clip time this way)
  advance(dt) {
    this._updateLoco(dt);
    this._updateSpar(dt);
    if (this.mixer) this.mixer.update(dt);
    for (const m of this.mixers || []) m?.update(dt);
    this.springs?.update(dt);
    for (const sp of this.castSprings || []) sp.update(dt);
  }

  // jump to `t` seconds into the current clip, simulating springs at 60 Hz on the way
  seek(t) {
    this.springs?.reset();
    for (const sp of this.castSprings || []) sp.reset();
    for (let k = 0, n = Math.round(t / STEP); k < n; k++) this.advance(STEP);
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.clock.getDelta();
    requestAnimationFrame(this._loop);
  }

  stop() {
    this.running = false;
  }

  _loop() {
    if (!this.running) return;
    this.renderOnce(this.clock.getDelta());
    requestAnimationFrame(this._loop);
  }
}

export function meshStats(root) {
  let tris = 0, verts = 0, meshes = 0, bones = 0;
  const mats = new Set(), texs = new Set();
  root.traverse((o) => {
    if (o.isMesh) {
      meshes++;
      const g = o.geometry;
      verts += g.attributes.position.count;
      tris += (g.index ? g.index.count : g.attributes.position.count) / 3;
      const ms = Array.isArray(o.material) ? o.material : [o.material];
      ms.forEach((m) => {
        mats.add(m.uuid);
        ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'emissiveMap', 'aoMap'].forEach((k) => m[k] && texs.add(m[k].uuid));
      });
      if (o.isSkinnedMesh) bones = Math.max(bones, o.skeleton.bones.length);
    }
  });
  let physics = 0;  // spring chains + colliders (see SpringBones), counted apart from the 19-bone body rig
  root.traverse((o) => { if (o.isBone && /^(spring|col|cap)_/.test(o.name)) physics++; });
  return { triangles: Math.round(tris), vertices: verts, meshes, materials: mats.size, textures: texs.size,
    bones: bones && Math.max(0, bones - physics), physicsBones: physics };
}

function gradientTexture(top, bottom) {
  const c = document.createElement('canvas');
  c.width = 2;
  c.height = 256;
  const g = c.getContext('2d');
  const grd = g.createLinearGradient(0, 0, 0, 256);
  grd.addColorStop(0, top);
  grd.addColorStop(1, bottom);
  g.fillStyle = grd;
  g.fillRect(0, 0, 2, 256);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
