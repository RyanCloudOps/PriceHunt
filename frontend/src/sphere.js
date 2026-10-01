import * as THREE from "three";

/**
 * Esfera de red "plexus": una corteza irregular de nodos conectados, un núcleo
 * difuso, focos ámbar que laten y pulsos de datos que viajan por las aristas.
 * En modo `scanning` (refresco en curso) los pulsos se multiplican y aceleran.
 */

const RADIUS = 2;
const SHELL_NODES = 950;
const CORE_NODES = 260;
const NEIGHBOURS = 3;
const PULSES = 90;
const AMBER = new THREE.Color("#ffb547");
const INK = new THREE.Color("#161616");

function mulberry32(seed) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function glowTexture() {
  const size = 128;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d");
  const grd = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grd.addColorStop(0, "rgba(255,240,200,1)");
  grd.addColorStop(0.2, "rgba(255,190,90,0.85)");
  grd.addColorStop(0.5, "rgba(255,150,40,0.25)");
  grd.addColorStop(1, "rgba(255,140,0,0)");
  g.fillStyle = grd;
  g.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function buildNodes(rand) {
  const nodes = [];
  // Corteza: distribución de Fibonacci + ruido de baja frecuencia para un borde "rocoso"
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < SHELL_NODES; i++) {
    const y = 1 - (i / (SHELL_NODES - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = golden * i + rand() * 0.35;
    const dir = new THREE.Vector3(Math.cos(theta) * r, y, Math.sin(theta) * r).normalize();
    const lump =
      Math.sin(dir.x * 3.1 + 1.3) * Math.cos(dir.y * 2.7) * 0.09 +
      Math.sin(dir.z * 5.3 + dir.x * 2.1) * 0.05;
    const jitter = (rand() - 0.5) * 0.14;
    nodes.push(dir.multiplyScalar(RADIUS * (1 + lump + jitter)));
  }
  // Núcleo: nube interior más tenue
  for (let i = 0; i < CORE_NODES; i++) {
    const dir = new THREE.Vector3(rand() * 2 - 1, rand() * 2 - 1, rand() * 2 - 1).normalize();
    nodes.push(dir.multiplyScalar(RADIUS * 0.72 * Math.cbrt(rand())));
  }
  return nodes;
}

function buildEdges(nodes) {
  const edges = [];
  const seen = new Set();
  const adjacency = nodes.map(() => []);
  for (let i = 0; i < nodes.length; i++) {
    const best = [];
    for (let j = 0; j < nodes.length; j++) {
      if (i === j) continue;
      const d = nodes[i].distanceToSquared(nodes[j]);
      if (best.length < NEIGHBOURS) {
        best.push([d, j]);
        best.sort((a, b) => a[0] - b[0]);
      } else if (d < best[NEIGHBOURS - 1][0]) {
        best[NEIGHBOURS - 1] = [d, j];
        best.sort((a, b) => a[0] - b[0]);
      }
    }
    for (const [, j] of best) {
      const key = i < j ? `${i}-${j}` : `${j}-${i}`;
      if (seen.has(key)) continue;
      seen.add(key);
      edges.push([i, j]);
      adjacency[i].push(j);
      adjacency[j].push(i);
    }
  }
  return { edges, adjacency };
}

function segments(nodes, edges, filter) {
  const pos = [];
  for (const [a, b] of edges) {
    if (!filter(a, b)) continue;
    pos.push(nodes[a].x, nodes[a].y, nodes[a].z, nodes[b].x, nodes[b].y, nodes[b].z);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  return geo;
}

export function createSphere(canvas) {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const rand = mulberry32(20261001);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
  camera.position.set(0, 0, 7.2);

  const root = new THREE.Group(); // posición / escala por scroll
  const spin = new THREE.Group(); // rotación continua + ratón
  root.add(spin);
  scene.add(root);

  const nodes = buildNodes(rand);
  const { edges, adjacency } = buildEdges(nodes);
  const isCore = (i) => i >= SHELL_NODES;

  // Aristas de la corteza y del núcleo
  spin.add(
    new THREE.LineSegments(
      segments(nodes, edges, (a, b) => !isCore(a) && !isCore(b)),
      new THREE.LineBasicMaterial({ color: INK, transparent: true, opacity: 0.62 }),
    ),
  );
  spin.add(
    new THREE.LineSegments(
      segments(nodes, edges, (a, b) => isCore(a) || isCore(b)),
      new THREE.LineBasicMaterial({ color: INK, transparent: true, opacity: 0.16 }),
    ),
  );

  // Nodos: oscuros con algunos brillantes (como chispas en la malla)
  const nodePos = new Float32Array(nodes.length * 3);
  const nodeCol = new Float32Array(nodes.length * 3);
  const sparkle = new THREE.Color("#fff3d6");
  nodes.forEach((n, i) => {
    nodePos.set([n.x, n.y, n.z], i * 3);
    const c = rand() < 0.12 ? sparkle : INK;
    nodeCol.set([c.r, c.g, c.b], i * 3);
  });
  const nodeGeo = new THREE.BufferGeometry();
  nodeGeo.setAttribute("position", new THREE.BufferAttribute(nodePos, 3));
  nodeGeo.setAttribute("color", new THREE.BufferAttribute(nodeCol, 3));
  spin.add(
    new THREE.Points(
      nodeGeo,
      new THREE.PointsMaterial({ size: 0.035, vertexColors: true, transparent: true, opacity: 0.9 }),
    ),
  );

  // Focos ámbar: subredes que laten
  const glow = glowTexture();
  const hotspots = [];
  const hotspotCount = 5;
  for (let h = 0; h < hotspotCount; h++) {
    const center = nodes[Math.floor(rand() * (h < 3 ? SHELL_NODES : nodes.length))];
    const reach = 0.45 + rand() * 0.25;
    const near = (i) => nodes[i].distanceTo(center) < reach;
    const mat = new THREE.LineBasicMaterial({
      color: AMBER,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const lines = new THREE.LineSegments(segments(nodes, edges, (a, b) => near(a) && near(b)), mat);
    const sprite = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: glow,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        opacity: 0,
      }),
    );
    sprite.position.copy(center);
    spin.add(lines, sprite);
    hotspots.push({ mat, sprite, phase: rand() * Math.PI * 2, speed: 0.5 + rand() * 0.7 });
  }

  // Pulsos de datos que recorren la malla
  const pulsePos = new Float32Array(PULSES * 3);
  const pulseGeo = new THREE.BufferGeometry();
  pulseGeo.setAttribute("position", new THREE.BufferAttribute(pulsePos, 3));
  const pulseMat = new THREE.PointsMaterial({
    size: 0.16,
    map: glow,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    opacity: 0.9,
  });
  spin.add(new THREE.Points(pulseGeo, pulseMat));
  const pulses = Array.from({ length: PULSES }, () => {
    const from = Math.floor(rand() * nodes.length);
    const opts = adjacency[from];
    return { from, to: opts[Math.floor(rand() * opts.length)] ?? from, t: rand() };
  });

  // Órbitas finas alrededor
  for (const [radius, tilt, opacity] of [
    [RADIUS * 1.42, 0.08, 0.22],
    [RADIUS * 1.62, -0.05, 0.12],
  ]) {
    const pts = [];
    for (let i = 0; i <= 256; i++) {
      const a = (i / 256) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * radius, Math.sin(a) * radius, 0));
    }
    const ring = new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: INK, transparent: true, opacity }),
    );
    ring.rotation.x = tilt;
    root.add(ring);
  }

  // Estado de interacción
  let scanning = false;
  let scanBlend = 0;
  let scroll = 0;
  const mouse = new THREE.Vector2();
  const mouseSmooth = new THREE.Vector2();
  window.addEventListener("pointermove", (e) => {
    mouse.set((e.clientX / window.innerWidth) * 2 - 1, (e.clientY / window.innerHeight) * 2 - 1);
  });

  function layout() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", layout);
  layout();

  const clock = new THREE.Clock();
  function frame() {
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime;
    scanBlend += ((scanning ? 1 : 0) - scanBlend) * Math.min(1, dt * 3);

    const motion = reduceMotion ? 0.15 : 1;
    mouseSmooth.lerp(mouse, 0.04);
    spin.rotation.y += dt * (0.06 + scanBlend * 0.25) * motion;
    spin.rotation.x = 0.25 + mouseSmooth.y * 0.18 * motion;
    spin.rotation.z = mouseSmooth.x * -0.08 * motion;

    // En escritorio la esfera vive a la derecha del titular; al bajar se aleja y se apaga
    const wide = window.innerWidth > 900;
    // En móvil la esfera sube por encima del titular para no restarle legibilidad
    const baseX = wide ? 1.55 : 0;
    const baseY = wide ? 0 : 1.4;
    root.position.set(baseX + scroll * (wide ? 0.8 : 0), baseY + scroll * 1.4, -scroll * 2.5);
    const s = (wide ? 1 : 0.6) * (1 + Math.sin(t * 0.8) * 0.006);
    root.scale.setScalar(s);
    canvas.style.opacity = String(1 - Math.min(scroll, 1) * 0.72);

    for (const h of hotspots) {
      const beat = 0.5 + 0.5 * Math.sin(t * h.speed * (1 + scanBlend * 2) + h.phase);
      const intensity = 0.25 + beat * 0.75;
      h.mat.opacity = intensity * (0.75 + scanBlend * 0.25);
      h.sprite.material.opacity = intensity * 0.8;
      h.sprite.scale.setScalar(0.5 + beat * 0.6 + scanBlend * 0.4);
    }

    if (!reduceMotion) {
      const speed = 0.6 + scanBlend * 2.4;
      const live = Math.floor(PULSES * (0.45 + scanBlend * 0.55));
      for (let i = 0; i < PULSES; i++) {
        const p = pulses[i];
        if (i >= live) {
          pulsePos.set([0, 0, -999], i * 3);
          continue;
        }
        p.t += dt * speed * 2.2;
        if (p.t >= 1) {
          p.t -= 1;
          p.from = p.to;
          const opts = adjacency[p.from];
          p.to = opts[Math.floor(Math.random() * opts.length)] ?? p.from;
        }
        const a = nodes[p.from];
        const b = nodes[p.to];
        pulsePos.set(
          [a.x + (b.x - a.x) * p.t, a.y + (b.y - a.y) * p.t, a.z + (b.z - a.z) * p.t],
          i * 3,
        );
      }
      pulseGeo.attributes.position.needsUpdate = true;
      pulseMat.size = 0.14 + scanBlend * 0.08;
    }

    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  return {
    setScanning(value) {
      scanning = value;
    },
    setScroll(value) {
      scroll = value;
    },
  };
}
