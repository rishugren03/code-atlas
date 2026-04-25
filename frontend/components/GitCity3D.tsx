"use client";

import { useRef, useState, useMemo, useEffect } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Play, Pause, ChevronLeft, ChevronRight, RotateCcw, Users, GitCommit, Activity, Zap } from "lucide-react";
import { format, parseISO } from "date-fns";
import styles from "./GitCity3D.module.css";

export interface CityCommit {
  commit_hash: string;
  author_name: string;
  author_email: string;
  committed_at: string;
  message: string;
  additions: number;
  deletions: number;
  files_changed: number;
}

// ─── Color system ─────────────────────────────────────────────────────────────

const PALETTE = [
  "#7c3aed", "#06b6d4", "#f43f5e", "#10b981", "#f59e0b",
  "#8b5cf6", "#14b8a6", "#ec4899", "#22c55e", "#ef4444",
  "#6366f1", "#0ea5e9", "#84cc16", "#fb923c", "#a855f7",
];

function emailToColor(email: string): string {
  let h = 5381;
  for (let i = 0; i < email.length; i++) h = ((h << 5) + h + email.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

// ─── Layout ───────────────────────────────────────────────────────────────────

function spiralPos(i: number): [number, number, number] {
  if (i === 0) return [0, 0, 0];
  const phi = Math.PI * (3 - Math.sqrt(5));
  const r = Math.sqrt(i) * 2.4;
  return [r * Math.cos(i * phi), 0, r * Math.sin(i * phi)];
}

function buildingHeight(c: CityCommit): number {
  const total = (c.additions ?? 0) + (c.deletions ?? 0);
  return Math.max(0.3, Math.min(Math.log(total + 2) * 1.6, 14));
}

function getContributorRank(count: number): { label: string; color: string } {
  if (count >= 100) return { label: "LEGEND", color: "#f59e0b" };
  if (count >= 50)  return { label: "ARCHITECT", color: "#a855f7" };
  if (count >= 20)  return { label: "SENIOR", color: "#06b6d4" };
  if (count >= 5)   return { label: "DEV", color: "#10b981" };
  return { label: "ROOKIE", color: "#6a6a80" };
}

// ─── Three.js scene state ─────────────────────────────────────────────────────

interface FlashRing {
  mesh: THREE.Mesh;
  life: number;
}

interface SceneState {
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  controls: OrbitControls;
  meshes: THREE.Mesh[];
  heights: number[];
  targetScales: number[];
  currentScales: number[];
  raycaster: THREE.Raycaster;
  animId: number;
  flashRings: FlashRing[];
  newBuildingQueue: number[];
}

// ─── Main component ───────────────────────────────────────────────────────────

interface GitCity3DProps {
  commits: CityCommit[];
  repoName: string;
}

export default function GitCity3D({ commits, repoName }: GitCity3DProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<SceneState | null>(null);
  const commitsRef = useRef(commits);
  commitsRef.current = commits;
  const prevVisibleRef = useRef(commits.length);
  const bannerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [visibleCount, setVisibleCount] = useState(commits.length);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(5);
  const [hovered, setHovered] = useState<CityCommit | null>(null);
  const [selected, setSelected] = useState<CityCommit | null>(null);
  const [autoRotate, setAutoRotate] = useState(false);
  const [unlockBanner, setUnlockBanner] = useState<string | null>(null);

  // ─── Derived state ──────────────────────────────────────────────────────────

  const contributors = useMemo(() => {
    const map = new Map<string, { name: string; color: string; count: number }>();
    for (const c of commits) {
      const key = c.author_email || c.author_name;
      const entry = map.get(key);
      if (entry) entry.count++;
      else map.set(key, { name: c.author_name, color: emailToColor(key), count: 1 });
    }
    return Array.from(map.values()).sort((a, b) => b.count - a.count).slice(0, 7);
  }, [commits]);

  const cityScore = useMemo(() => {
    return commits.slice(0, visibleCount).reduce((sum, c) => sum + (c.additions ?? 0) + (c.deletions ?? 0), 0);
  }, [commits, visibleCount]);

  const currentCommit = commits[Math.min(visibleCount - 1, commits.length - 1)];
  const progress = commits.length > 0 ? (visibleCount / commits.length) * 100 : 0;

  // ─── Build Three.js scene once per commits array ─────────────────────────────

  useEffect(() => {
    if (!mountRef.current || commits.length === 0) return;
    const mount = mountRef.current;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.setClearColor(0x05050f);
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x05050f, 60, 220);

    const camera = new THREE.PerspectiveCamera(55, mount.clientWidth / mount.clientHeight, 0.1, 1000);
    camera.position.set(0, 45, 65);
    camera.lookAt(0, 0, 0);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 5;
    controls.maxDistance = (Math.sqrt(commits.length) * 2.4 + 12) * 4;
    controls.maxPolarAngle = Math.PI / 2.05;

    scene.add(new THREE.AmbientLight(0xffffff, 0.22));
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.6);
    dirLight.position.set(35, 50, 30);
    scene.add(dirLight);
    const pl1 = new THREE.PointLight(0x7c3aed, 1.0, 90, 2);
    pl1.position.set(0, 20, 0);
    scene.add(pl1);
    const pl2 = new THREE.PointLight(0x06b6d4, 0.7, 70, 2);
    pl2.position.set(25, 3, -25);
    scene.add(pl2);

    // Stars
    const starPositions = new Float32Array(5000 * 3);
    for (let i = 0; i < 5000; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 150 + Math.random() * 80;
      starPositions[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
      starPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      starPositions[i * 3 + 2] = r * Math.cos(phi);
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.4, sizeAttenuation: true, transparent: true, opacity: 0.7 })));

    // Ground
    const cityRadius = Math.sqrt(commits.length) * 2.4 + 12;
    const ground = new THREE.Mesh(
      new THREE.CircleGeometry(cityRadius + 25, 64),
      new THREE.MeshStandardMaterial({ color: 0x090912, roughness: 1 })
    );
    ground.rotation.x = -Math.PI / 2;
    scene.add(ground);

    const grid = new THREE.GridHelper((cityRadius + 10) * 2, Math.ceil((cityRadius + 10) * 2 / 5), 0x191932, 0x111128);
    grid.position.y = 0.01;
    scene.add(grid);

    // Buildings
    const sharedGeo = new THREE.BoxGeometry(0.78, 1, 0.78);
    const meshes: THREE.Mesh[] = [];
    const heights: number[] = [];
    const targetScales = new Array(commits.length).fill(1);
    const currentScales = new Array(commits.length).fill(1);

    commits.forEach((commit, i) => {
      const h = buildingHeight(commit);
      const colorStr = emailToColor(commit.author_email || commit.author_name);
      const color = new THREE.Color(colorStr);
      const mat = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.18,
        roughness: 0.35,
        metalness: 0.3,
      });
      const mesh = new THREE.Mesh(sharedGeo, mat);
      const [x, , z] = spiralPos(i);
      mesh.position.set(x, h / 2, z);
      mesh.scale.y = h;
      mesh.userData = { idx: i };
      scene.add(mesh);
      meshes.push(mesh);
      heights.push(h);
    });

    // Raycaster
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let hoveredIdx = -1;

    const onMouseMove = (e: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(meshes);
      if (hits.length > 0) {
        const idx = (hits[0].object as THREE.Mesh).userData.idx as number;
        if (idx !== hoveredIdx) {
          hoveredIdx = idx;
          setHovered(commitsRef.current[idx] ?? null);
          renderer.domElement.style.cursor = "pointer";
        }
      } else {
        if (hoveredIdx !== -1) {
          hoveredIdx = -1;
          setHovered(null);
          renderer.domElement.style.cursor = "default";
        }
      }
    };

    const onClick = (e: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(meshes);
      if (hits.length > 0) {
        const idx = (hits[0].object as THREE.Mesh).userData.idx as number;
        const commit = commitsRef.current[idx];
        setSelected(prev => prev?.commit_hash === commit?.commit_hash ? null : commit ?? null);
      } else {
        setSelected(null);
      }
    };

    renderer.domElement.addEventListener("mousemove", onMouseMove);
    renderer.domElement.addEventListener("click", onClick);

    const onResize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    const flashRings: FlashRing[] = [];
    const state: SceneState = {
      renderer, scene, camera, controls, meshes, heights,
      targetScales, currentScales, raycaster, animId: -1,
      flashRings, newBuildingQueue: [],
    };
    sceneRef.current = state;

    let lastT = 0;
    const animate = (t: number) => {
      state.animId = requestAnimationFrame(animate);
      const dt = Math.min((t - lastT) / 1000, 0.1);
      lastT = t;

      // Spawn flash ring for each newly revealed building
      while (state.newBuildingQueue.length > 0) {
        const idx = state.newBuildingQueue.shift()!;
        const mesh = state.meshes[idx];
        if (!mesh) continue;
        const mat = mesh.material as THREE.MeshStandardMaterial;
        const ringGeo = new THREE.RingGeometry(0.5, 1.0, 32);
        const ringMat = new THREE.MeshBasicMaterial({
          color: mat.color,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.85,
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.rotation.x = -Math.PI / 2;
        ring.position.set(mesh.position.x, 0.05, mesh.position.z);
        state.scene.add(ring);
        state.flashRings.push({ mesh: ring, life: 1.0 });
      }

      // Animate flash rings — expand outward and fade
      for (let i = state.flashRings.length - 1; i >= 0; i--) {
        const fr = state.flashRings[i];
        fr.life -= dt * 1.8;
        if (fr.life <= 0) {
          state.scene.remove(fr.mesh);
          fr.mesh.geometry.dispose();
          (fr.mesh.material as THREE.MeshBasicMaterial).dispose();
          state.flashRings.splice(i, 1);
        } else {
          const scale = 1 + (1 - fr.life) * 5;
          fr.mesh.scale.set(scale, scale, scale);
          (fr.mesh.material as THREE.MeshBasicMaterial).opacity = fr.life * 0.7;
        }
      }

      // Animate building heights
      for (let i = 0; i < state.meshes.length; i++) {
        state.currentScales[i] += (state.targetScales[i] - state.currentScales[i]) * Math.min(dt * 9, 1);
        const s = state.currentScales[i];
        const h = state.heights[i];
        state.meshes[i].scale.y = s * h;
        state.meshes[i].position.y = (h * s) / 2;
      }

      state.controls.update();
      renderer.render(scene, camera);
    };
    state.animId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(state.animId);
      renderer.domElement.removeEventListener("mousemove", onMouseMove);
      renderer.domElement.removeEventListener("click", onClick);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      renderer.dispose();
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement);
      sceneRef.current = null;
    };
  }, [commits]);

  // ─── Sync visibleCount → building scales + flash rings ───────────────────────

  useEffect(() => {
    const s = sceneRef.current;
    if (!s) return;
    const prev = prevVisibleRef.current;
    for (let i = 0; i < s.targetScales.length; i++) {
      s.targetScales[i] = i < visibleCount ? 1 : 0;
      // Only queue the newest building to avoid ring spam when scrubbing
      if (i >= prev && i < visibleCount && i === visibleCount - 1) {
        s.newBuildingQueue.push(i);
      }
    }
    prevVisibleRef.current = visibleCount;
  }, [visibleCount]);

  // ─── Sync autoRotate ─────────────────────────────────────────────────────────

  useEffect(() => {
    const s = sceneRef.current;
    if (!s) return;
    s.controls.autoRotate = autoRotate;
    s.controls.autoRotateSpeed = 0.4;
  }, [autoRotate]);

  // ─── Sync selected highlight ─────────────────────────────────────────────────

  useEffect(() => {
    const s = sceneRef.current;
    if (!s) return;
    s.meshes.forEach((mesh, i) => {
      const mat = mesh.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = selected?.commit_hash === commits[i]?.commit_hash ? 0.9 : 0.18;
    });
  }, [selected, commits]);

  // ─── Playback timer ──────────────────────────────────────────────────────────

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (!isPlaying) return;
    if (visibleCount >= commits.length) { setIsPlaying(false); return; }

    const delay = Math.max(30, 400 / speed);
    intervalRef.current = setInterval(() => {
      setVisibleCount(prev => {
        if (prev >= commits.length) { setIsPlaying(false); clearInterval(intervalRef.current!); return prev; }
        const newCommit = commitsRef.current[prev];
        if (newCommit) {
          setUnlockBanner(`${newCommit.author_name}: ${newCommit.message.split("\n")[0].slice(0, 55)}`);
          if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current);
          bannerTimerRef.current = setTimeout(() => setUnlockBanner(null), 2200);
        }
        return prev + 1;
      });
    }, delay);

    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [isPlaying, speed, commits.length, visibleCount]);

  // ─── UI handlers ─────────────────────────────────────────────────────────────

  const handleReset = () => {
    setIsPlaying(false);
    setSelected(null);
    prevVisibleRef.current = 0;
    setVisibleCount(1);
  };

  const cycleSpeed = () => setSpeed(s => s === 1 ? 5 : s === 5 ? 20 : 1);

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setIsPlaying(false);
    const newVal = +e.target.value;
    prevVisibleRef.current = newVal - 1;
    setVisibleCount(newVal);
  };

  const handlePlayToggle = () => {
    if (visibleCount >= commits.length) {
      prevVisibleRef.current = 0;
      setVisibleCount(1);
      setIsPlaying(true);
    } else {
      setIsPlaying(p => !p);
    }
  };

  if (commits.length === 0) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyIcon}>🏙️</div>
        <p>No commits loaded yet.</p>
      </div>
    );
  }

  return (
    <div className={styles.wrapper}>
      {/* Three.js canvas */}
      <div ref={mountRef} className={styles.canvas} />

      {/* Top HUD */}
      <div className={styles.hudTop}>
        <div className={styles.cityTitle}>
          <span className={styles.cityGlyph}>🏙️</span>
          <div>
            <div className={styles.cityName}>{repoName}</div>
            <div className={styles.citySubtitle}>Git City · {commits.length.toLocaleString()} commits</div>
          </div>
        </div>
        <div className={styles.statsRow}>
          <span className={styles.stat}><GitCommit size={13} />{visibleCount.toLocaleString()} / {commits.length.toLocaleString()}</span>
          <span className={styles.stat}><Users size={13} />{contributors.length} devs</span>
          {currentCommit?.committed_at && (
            <span className={styles.stat}><Activity size={13} />{format(parseISO(currentCommit.committed_at), "MMM d, yyyy")}</span>
          )}
        </div>
        {/* City Score */}
        <div className={styles.scoreBox}>
          <Zap size={13} className={styles.scoreIcon} />
          <span className={styles.scoreLabel}>CITY SCORE</span>
          <span className={styles.scoreValue}>{cityScore.toLocaleString()}</span>
        </div>
      </div>

      {/* Contributor legend with rank badges */}
      <div className={styles.legend}>
        <div className={styles.legendTitle}>Contributors</div>
        {contributors.map(c => {
          const rank = getContributorRank(c.count);
          return (
            <div key={c.name} className={styles.legendRow}>
              <span className={styles.legendDot} style={{ background: c.color }} />
              <span className={styles.legendName}>{c.name}</span>
              <span className={styles.rankBadge} style={{ color: rank.color, borderColor: `${rank.color}55` }}>
                {rank.label}
              </span>
              <span className={styles.legendCount}>{c.count}</span>
            </div>
          );
        })}
      </div>

      {/* Unlock banner — shown during playback */}
      {unlockBanner && (
        <div className={styles.unlockBanner}>
          <span className={styles.unlockIcon}>⚡</span>
          <span className={styles.unlockText}>{unlockBanner}</span>
        </div>
      )}

      {/* Hover tooltip */}
      {hovered && !selected && (
        <div className={styles.tooltip}>
          <div className={styles.ttHash}>{hovered.commit_hash.slice(0, 7)}</div>
          <div className={styles.ttAuthor}>{hovered.author_name}</div>
          <div className={styles.ttMsg}>{hovered.message.split("\n")[0].slice(0, 72)}</div>
          <div className={styles.ttMeta}>
            <span className={styles.ttAdded}>+{hovered.additions}</span>
            <span className={styles.ttDeleted}>-{hovered.deletions}</span>
            <span className={styles.ttFiles}>{hovered.files_changed} files</span>
          </div>
        </div>
      )}

      {/* Selected commit panel */}
      {selected && (
        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <code className={styles.panelHash}>{selected.commit_hash.slice(0, 7)}</code>
            <button className={styles.panelClose} onClick={() => setSelected(null)}>✕</button>
          </div>
          <div className={styles.panelAuthor}>
            <span className={styles.panelDot} style={{ background: emailToColor(selected.author_email || selected.author_name) }} />
            {selected.author_name}
          </div>
          {selected.committed_at && (
            <div className={styles.panelDate}>{format(parseISO(selected.committed_at), "PPpp")}</div>
          )}
          <div className={styles.panelMsg}>{selected.message.split("\n")[0]}</div>
          <div className={styles.panelStats}>
            <span className={styles.panelAdded}>+{selected.additions}</span>
            <span className={styles.panelDeleted}>-{selected.deletions}</span>
            <span className={styles.panelFiles}>{selected.files_changed} files</span>
          </div>
        </div>
      )}

      {/* Bottom controls */}
      <div className={styles.controls}>
        {/* Milestone checkpoints */}
        <div className={styles.milestoneRow}>
          {[25, 50, 75, 100].map(pct => {
            const reached = Math.round(progress) >= pct;
            return (
              <div key={pct} className={`${styles.milestoneChip} ${reached ? styles.milestoneReached : ""}`}>
                <span className={styles.milestoneCheck}>{reached ? "✓" : "○"}</span>
                {pct}%
              </div>
            );
          })}
        </div>
        <div className={styles.ctrlBar}>
          <button className={styles.ctrlBtn} onClick={handleReset} title="Reset to beginning">
            <RotateCcw size={15} />
          </button>
          <button className={styles.ctrlBtn} onClick={() => { prevVisibleRef.current = visibleCount - 2; setVisibleCount(v => Math.max(1, v - 1)); }} disabled={visibleCount <= 1}>
            <ChevronLeft size={17} />
          </button>
          <button className={`${styles.ctrlBtn} ${styles.playBtn}`} onClick={handlePlayToggle}>
            {isPlaying ? <Pause size={19} /> : <Play size={19} />}
          </button>
          <button className={styles.ctrlBtn} onClick={() => { setVisibleCount(v => Math.min(commits.length, v + 1)); }} disabled={visibleCount >= commits.length}>
            <ChevronRight size={17} />
          </button>
          <button className={`${styles.ctrlBtn} ${styles.speedTag}`} onClick={cycleSpeed} title="Cycle playback speed">
            {speed}×
          </button>
          <button
            className={`${styles.ctrlBtn} ${autoRotate ? styles.ctrlActive : ""}`}
            onClick={() => setAutoRotate(r => !r)}
            title="Auto-rotate camera"
          >
            ↻
          </button>
          <input
            type="range"
            min={1}
            max={commits.length}
            value={visibleCount}
            onChange={handleSliderChange}
            className={styles.slider}
          />
          <span className={styles.pct}>{Math.round(progress)}%</span>
        </div>
      </div>
    </div>
  );
}
