// Shared three.js viewer: same lighting presets for the interactive page and for the
// headless screenshot renders, so every tool's output is judged under identical light.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

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
      this.ground = g;
      this.scene.add(g);
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(2.2, 2.35, 64),
        new THREE.MeshStandardMaterial({ color: '#8a7b62', roughness: 0.8 }),
      );
      ring.rotation.x = -Math.PI / 2;
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
    const gltf = await new GLTFLoader().loadAsync(url);
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
    this.target.set(0, h * 0.5, 0);
    this.distance = h * 2.4 + 0.6;
    this.clips = gltf.animations || [];
    this.mixer = this.clips.length ? new THREE.AnimationMixer(model) : null;
    this.setView(this.viewKey || 'three_quarter');
    return this.stats;
  }

  // Scene mode: static environment (no normalisation) + several characters.
  async loadScene({ arena, characters = [], target = [0, 1.0, 0], distance = 9, height = 0.35 }) {
    this.sceneMode = true;
    this.setPreset(this.presetName);
    if (this.ground) this.ground.visible = false;
    this.scene.children.filter((o) => o.isMesh && o.geometry?.type === 'RingGeometry').forEach((o) => (o.visible = false));
    const loader = new GLTFLoader();
    const env = (await loader.loadAsync(arena)).scene;
    env.traverse((o) => {
      if (o.isMesh) {
        o.receiveShadow = true;
        o.castShadow = !/sand|cliff/.test(o.name);
      }
    });
    this.scene.add(env);
    this.mixers = [];
    for (const c of characters) {
      const g = await loader.loadAsync(c.url);
      const m = g.scene;
      m.position.set(...c.pos);
      m.rotation.y = THREE.MathUtils.degToRad(c.yaw || 0);
      m.traverse((o) => o.isMesh && ((o.castShadow = true), (o.receiveShadow = true)));
      this.scene.add(m);
      if (g.animations.length) {
        const mx = new THREE.AnimationMixer(m);
        const clip = g.animations.find((a) => a.name === (c.clip || 'Idle')) || g.animations[0];
        mx.clipAction(clip).play();
        this.mixers.push(mx);
      }
    }
    this.target.set(...target);
    this.distance = distance;
    this.sceneHeight = height;
    this.setView(this.viewKey || 'three_quarter');
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

  setDebug(mode) {
    // 'lit' | 'albedo' | 'wire'
    if (!this.model) return;
    this.model.traverse((o) => {
      if (!o.isMesh) return;
      o.userData.orig ??= o.material;
      const m = o.userData.orig;
      if (mode === 'lit') o.material = m;
      else if (mode === 'albedo')
        o.material = new THREE.MeshBasicMaterial({ map: m.map || null, color: m.color, vertexColors: !!o.geometry.attributes.color });
      else if (mode === 'wire') o.material = new THREE.MeshBasicMaterial({ color: '#37e0c8', wireframe: true });
    });
  }

  renderOnce(dt = 0) {
    if (this.mixer) this.mixer.update(dt);
    for (const m of this.mixers || []) m.update(dt);
    const t = performance.now() / 1000;
    for (const f of this.flickers)
      f.light.intensity = f.base * (0.85 + 0.15 * Math.sin(t * 13 + f.seed) * Math.sin(t * 7.3 + f.seed * 2));
    if (this.controls) this.controls.update();
    this.renderer.render(this.scene, this.camera);
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
  return { triangles: Math.round(tris), vertices: verts, meshes, materials: mats.size, textures: texs.size, bones };
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
