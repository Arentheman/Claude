// Симулятор прыгалки для предобучения сетей (тот же, что в doodle-jump-ai/index.html).
const W = 400, H = 640, G = 0.32, JUMP = -11.2, SPRING = -19, MAXVX = 6.2, PW = 58, PH = 12;
const STALL_TICKS = 720, MAX_TICKS = 36000, COOLDOWN = 20, SHOT_SPEED = 14;

function rngOf(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
// Shortest signed horizontal distance on a wrapping screen
const wdx = (a, b) => { let d = b - a; if (d > W / 2) d -= W; else if (d < -W / 2) d += W; return d; };

class World {
  constructor(seed, ai = true) {
    this.rng = rngOf(seed); this.ai = ai; this.t = 0;
    this.plats = []; this.enemies = []; this.shots = [];
    this.startY = H - 40; this.topY = H - 40; this.lastEnemyY = H - 40;
    this.plats.push(this.mk(W / 2 - PW / 2, H - 40, 'n', 0));
    this.base = this.plats[0];
    this.p = { x: W / 2, y: H - 60, vx: 0, vy: JUMP, face: 1 };
    this.cam = 0; this.maxH = 0; this.kills = 0; this.throws = 0; this.stall = 0; this.cool = 0; this.throwT = -99;
    this.alive = true; this.cause = ''; this.lastMove = 0; this.lastThrow = false;
    this.gen();
  }
  mk(x, y, type, diff) {
    const r = this.rng;
    const pl = { x, y, cx: x, type, amp: 0, spd: 0, ph: 0, broken: false, spring: false, sx: 0, fall: 0 };
    if (type === 'm') {
      pl.amp = Math.min(30 + r() * (60 + 80 * diff), (W - PW) / 2 - 2);
      pl.cx = pl.amp + r() * (W - PW - 2 * pl.amp);
      pl.spd = 0.015 + r() * 0.025 * (1 + diff);
      pl.ph = r() * 6.283;
      pl.x = pl.cx + pl.amp * Math.sin(pl.ph);
    }
    return pl;
  }
  gen() {
    const r = this.rng;
    while (this.topY > this.cam - 400) {
      const h = this.startY - this.topY, diff = Math.min(1, h / 25000);
      const gap = 28 + r() * (40 + 105 * diff);
      this.topY -= gap;
      const isM = r() < 0.08 + 0.32 * diff && h > 800;
      const pl = this.mk(r() * (W - PW), this.topY, isM ? 'm' : 'n', diff);
      if (!isM && r() < 0.07) { pl.spring = true; pl.sx = 6 + r() * (PW - 26); }
      this.plats.push(pl);
      if (r() < 0.12 + 0.25 * diff) {
        this.plats.push(this.mk(r() * (W - PW), this.topY + gap * 0.5, 'b', diff));
      }
      if (h > 1500 && this.lastEnemyY - this.topY > 650 && r() < 0.08 + 0.12 * diff) {
        const amp = r() * 60;
        this.enemies.push({
          cx: 40 + amp + r() * (W - 80 - 2 * amp), y: this.topY - 70, amp,
          spd: 0.01 + r() * 0.03, ph: r() * 6.283, x: 0, by: this.topY - 70, dead: false, fall: 0,
        });
        this.lastEnemyY = this.topY;
      }
    }
  }
  // move: -1 (A), 0, 1 (D); throwing: bool; tx/ty: world-space target (human click)
  step(move, throwing, tx, ty) {
    if (!this.alive) return;
    const p = this.p; this.t++; this.cool--;
    this.lastMove = move; this.lastThrow = false;
    for (const pl of this.plats) {
      if (pl.type === 'm') pl.x = pl.cx + pl.amp * Math.sin(this.t * pl.spd + pl.ph);
      if (pl.broken) { pl.fall += 0.5; pl.y += pl.fall; }
    }
    for (const e of this.enemies) {
      e.x = e.cx + e.amp * Math.sin(this.t * e.spd + e.ph);
      if (e.dead) { e.fall += 0.6; e.y += e.fall; } else e.y = e.by + 5 * Math.sin(this.t * 0.06 + e.ph);
    }
    p.vx += (move * MAXVX - p.vx) * 0.25;
    if (move) p.face = move;
    p.x = (p.x + p.vx + W) % W;
    const oy = p.y;
    p.vy += G; p.y += p.vy;
    if (p.vy > 0) {
      for (const pl of this.plats) {
        if (pl.broken) continue;
        if (oy + 20 <= pl.y && p.y + 20 >= pl.y && p.x + 13 > pl.x && p.x - 13 < pl.x + PW) {
          if (pl.type === 'b') { pl.broken = true; continue; }
          const onSpring = pl.spring && p.x + 10 > pl.x + pl.sx && p.x - 10 < pl.x + pl.sx + 16;
          p.vy = onSpring ? SPRING : JUMP; p.y = pl.y - 20; pl.hit = this.t; this.base = pl;
          break;
        }
      }
    }
    for (const e of this.enemies) {
      if (e.dead) continue;
      if (Math.abs(wdx(p.x, e.x)) < 30 && Math.abs(p.y - e.y) < 36) {
        if (p.vy > 0 && oy + 20 <= e.y - 6) { e.dead = true; this.kills++; p.vy = JUMP; }
        else { this.die('монстр'); return; }
      }
    }
    if (throwing && this.cool <= 0) {
      let target = null;
      if (tx !== undefined) target = { x: tx, y: ty };
      else {
        let bd = Infinity;
        for (const e of this.enemies) {
          if (e.dead || e.y < this.cam - 20 || e.y > this.cam + H) continue;
          const d = Math.hypot(wdx(p.x, e.x), e.y - p.y);
          if (d < bd) { bd = d; target = { x: p.x + wdx(p.x, e.x), y: e.y }; }
        }
        if (!target) target = { x: p.x, y: p.y - 100 };
      }
      const dx = target.x - p.x, dy = target.y - (p.y - 16), d = Math.hypot(dx, dy) || 1;
      this.shots.push({ x: p.x, y: p.y - 16, vx: dx / d * SHOT_SPEED, vy: dy / d * SHOT_SPEED, a: 0 });
      this.cool = COOLDOWN; this.throws++; this.lastThrow = true; this.throwT = this.t;
    }
    for (const s of this.shots) {
      s.x += s.vx; s.y += s.vy; s.a += 0.45;
      for (const e of this.enemies) {
        if (!e.dead && Math.abs(wdx(s.x, e.x)) < 26 && Math.abs(s.y - e.y) < 26) { e.dead = true; this.kills++; s.done = true; break; }
      }
      if (s.y < this.cam - 40 || s.y > this.cam + H + 40) s.done = true;
      s.x = (s.x + W) % W;
    }
    this.shots = this.shots.filter(s => !s.done);
    if (p.y < this.cam + H * 0.42) this.cam = p.y - H * 0.42;
    const h = this.startY - p.y;
    if (h > this.maxH + 0.5) { this.maxH = h; this.stall = 0; } else this.stall++;
    if (p.y - this.cam > H + 30) { this.die('упал'); return; }
    if (this.ai && this.stall > STALL_TICKS) { this.die('застрял'); return; }
    if (this.ai && this.t > MAX_TICKS) { this.die('время вышло'); return; }
    const cut = this.cam + H + 80;
    if (this.plats.length > 60 || this.t % 30 === 0) {
      this.plats = this.plats.filter(pl => pl.y < cut);
      this.enemies = this.enemies.filter(e => e.y < cut);
    }
    this.gen();
  }
  die(cause) { this.alive = false; this.cause = cause; }
  // Network inputs: what the doodler "sees".
  // Platforms are measured from the one it last bounced on, so "the next step up" is always slot 0.
  sense() {
    const p = this.p, feet = p.y + 20, inp = [p.vx / MAXVX, p.vy / 15];
    const put = (pl) => {
      if (!pl) { inp.push(0, 0, 0, 0); return; }
      const vel = pl.type === 'm' ? pl.amp * pl.spd * Math.cos(this.t * pl.spd + pl.ph) : 0;
      inp.push(wdx(p.x, pl.x + PW / 2) / (W / 2), (pl.y - feet) / 300, vel / 3, 1);
    };
    const base = this.base;
    const next = [];
    for (const pl of this.plats) if (!pl.broken && pl.type !== 'b' && pl.y < base.y - 1 && pl.y < this.cam + H - 10) next.push(pl);
    next.sort((a, b) => b.y - a.y);
    for (let i = 0; i < 3; i++) put(next[i]);
    let be = null, bd = Infinity;
    for (const e of this.enemies) {
      if (e.dead || e.y < this.cam - 20 || e.y > this.cam + H) continue;
      const d = Math.hypot(wdx(p.x, e.x), e.y - p.y);
      if (d < bd) { bd = d; be = e; }
    }
    if (be) inp.push(wdx(p.x, be.x) / (W / 2), (be.y - p.y) / 300, 1); else inp.push(0, 0, 0);
    inp.push(this.cool <= 0 ? 1 : 0, 1);
    return inp;
  }
  fitness() { return this.maxH + this.kills * 250 - this.throws * 3; }
}

// ===== Neural net: 19 inputs -> 12 tanh -> 2 outputs (steer, throw) =====
const NI = 19, NH = 12, NO = 2;
const O_B1 = NI * NH, O_W2 = O_B1 + NH, O_B2 = O_W2 + NH * NO, NG = O_B2 + NO;
function think(g, inp, hid, out) {
  for (let j = 0; j < NH; j++) {
    let s = g[O_B1 + j];
    for (let i = 0; i < NI; i++) s += g[j * NI + i] * inp[i];
    hid[j] = Math.tanh(s);
  }
  for (let k = 0; k < NO; k++) {
    let s = g[O_B2 + k];
    for (let j = 0; j < NH; j++) s += g[O_W2 + k * NH + j] * hid[j];
    out[k] = Math.tanh(s);
  }
}

let R = rngOf((Date.now() ^ 0x9e3779b9) >>> 0);
const gauss = () => { const u = R() || 1e-9, v = R(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(6.283185 * v); };
function randomGenome() { const g = new Float32Array(NG); for (let i = 0; i < NG; i++) g[i] = gauss() * 0.6; return g; }

// Inputs that flip sign when the world is mirrored left<->right
const DEADZONE = 0.05;
const MIRROR = [0, 2, 4, 6, 8, 10, 12, 14];
class Agent {
  constructor(genome, seed) {
    this.g = genome; this.w = new World(seed);
    this.hid = new Float32Array(NH); this.out = new Float32Array(NO);
    this.hidM = new Float32Array(NH); this.outM = new Float32Array(NO);
    this.inp = null; this.steer = 0;
  }
  // The net looks at the scene and at its mirror image. Steering is the difference of the two,
  // so it is left/right symmetric by construction and only has to learn *which way* is good.
  tick() {
    const w = this.w; if (!w.alive) return;
    const inp = this.inp = w.sense();
    const mir = inp.slice(); for (const i of MIRROR) mir[i] = -mir[i];
    think(this.g, inp, this.hid, this.out);
    think(this.g, mir, this.hidM, this.outM);
    const s = this.steer = this.out[0] - this.outM[0];
    w.step(s < -DEADZONE ? -1 : s > DEADZONE ? 1 : 0, this.out[1] + this.outM[1] > 0);
  }
}

const ROUNDS = 3, ELITE = 10, MUT_RATE = 0.2, MUT_SIGMA = 0.3;
const pack = g => Array.from(g, v => Math.round(v * 1e4) / 1e4);
class Population {
  constructor(size = 60, saved = null) {
    this.size = size; this.gen = 1; this.history = []; this.bestFit = -Infinity; this.best = null;
    this.bestH = 0; this.bestKills = 0;
    this.genomes = [];
    if (saved && saved.ng === NG) {
      this.gen = saved.gen; this.history = saved.history || []; this.bestFit = saved.bestFit; this.bestH = saved.bestH || 0;
      this.bestKills = saved.bestKills || 0;
      this.best = saved.best ? Float32Array.from(saved.best) : null;
      for (const g of saved.genomes) this.genomes.push(Float32Array.from(g));
    }
    while (this.genomes.length < size) this.genomes.push(randomGenome());
    this.begin();
  }
  begin() {
    this.round = 0; this.score = new Float64Array(this.size); this.heights = new Float64Array(this.size);
    this.kills = new Float64Array(this.size);
    this.beginRound();
  }
  // Each genome plays ROUNDS different levels; its fitness is the average, so luck matters less
  beginRound() {
    this.seed = (R() * 4294967296) >>> 0;
    this.agents = this.genomes.map(g => new Agent(g, this.seed));
  }
  aliveCount() { let n = 0; for (const a of this.agents) if (a.w.alive) n++; return n; }
  tick() {
    let any = false;
    for (const a of this.agents) if (a.w.alive) { a.tick(); any = true; }
    if (!any) {
      this.agents.forEach((a, i) => { this.score[i] += a.w.fitness(); this.heights[i] += a.w.maxH; this.kills[i] += a.w.kills; });
      if (++this.round < ROUNDS) { this.beginRound(); return false; }
      this.evolve(); return true;
    }
    return false;
  }
  evolve() {
    const scored = this.genomes.map((g, i) => ({ g, f: this.score[i] / ROUNDS, h: this.heights[i] / ROUNDS, k: this.kills[i] / ROUNDS }))
      .sort((a, b) => b.f - a.f);
    const avg = scored.reduce((s, x) => s + x.h, 0) / scored.length;
    this.history.push({ gen: this.gen, best: scored[0].h, avg, kills: scored[0].k });
    if (this.history.length > 400) this.history.shift();
    if (scored[0].f > this.bestFit) {
      this.bestFit = scored[0].f; this.best = scored[0].g.slice(); this.bestH = scored[0].h; this.bestKills = scored[0].k;
    }
    // Truncation selection: the top ELITE survive unchanged, children are mutated copies of the top 2×ELITE
    const next = [];
    for (let i = 0; i < ELITE; i++) next.push(scored[i].g);
    while (next.length < this.size) {
      const c = scored[(R() * ELITE * 2) | 0].g.slice();
      for (let i = 0; i < NG; i++) {
        if (R() < MUT_RATE) c[i] += gauss() * MUT_SIGMA;
      }
      next.push(c);
    }
    this.genomes = next; this.gen++;
    this.begin();
  }
  serialize() {
    return {
      gen: this.gen, history: this.history, bestFit: this.bestFit, bestH: this.bestH, bestKills: this.bestKills,
      best: this.best ? pack(this.best) : null, genomes: this.genomes.map(pack), ng: NG,
    };
  }
}
if (typeof module !== 'undefined') module.exports = { Population, World, Agent, randomGenome, think, NI, NH, NO, NG, O_W2, O_B1, O_B2 };
