// Обучение с учителем: сеть учится повторять простую стратегию («лети к следующей
// платформе, промахнулся — рули на платформу под собой»). Получается хорошая стартовая
// сеть, которую дальше улучшает эволюция — в симуляторе (pretrain.js) и в настоящей игре.
//
//   node pretrain/imitate.js [куда записать]
const fs = require('fs');
const path = require('path');
const { World, NI, NH, NO, NG, O_B1, O_W2, O_B2, think } = require('./sim.js');

const MIRROR = [0, 2, 4, 6, 8, 10, 12, 14, 17];
const DEADZONE = 0.05;

// Учитель. Входы: 0 vx, 1 vy, 2-5 след. платформа, 6-9, 10-13, 14-16 платформа под ногами,
// 17-19 монстр, 20 бросок готов, 21 смещение
function teacher(i) {
  const falling = i[1] > 0;
  let dx;
  if (i[5] && !(falling && i[3] < -0.02)) dx = i[2];   // до следующей ещё можно долететь
  else if (i[16]) dx = i[14];                           // промахнулись — к платформе под ногами
  else dx = i[2];
  const move = dx > 0.02 ? 1 : dx < -0.02 ? -1 : 0;
  const thr = i[19] > 0 && i[20] > 0;
  return [move, thr];
}

let seed = 12345;
const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
const gauss = () => Math.sqrt(-2 * Math.log(rnd() || 1e-9)) * Math.cos(6.283185 * rnd());

function act(g, inp) {
  const mir = inp.slice(); for (const k of MIRROR) mir[k] = -mir[k];
  const h = new Float32Array(NH), o = new Float32Array(NO), h2 = new Float32Array(NH), o2 = new Float32Array(NO);
  think(g, inp, h, o); think(g, mir, h2, o2);
  const s = o[0] - o2[0];
  return [s < -DEADZONE ? -1 : s > DEADZONE ? 1 : 0, o[1] + o2[1] > 0];
}

// Сбор примеров (DAgger): играет то учитель, то сеть, а правильный ответ всегда даёт учитель,
// чтобы сеть видела и те положения, в которые попадает по своим ошибкам
function collect(g, nLevels, beta, maxTicks) {
  const X = [], Y = [];
  for (let l = 0; l < nLevels; l++) {
    const w = new World((rnd() * 4294967296) >>> 0);
    while (w.alive && w.t < maxTicks) {
      const inp = w.sense();
      const [tm, tt] = teacher(inp);
      X.push(inp); Y.push([tm, tt ? 1 : -1]);
      let mv = tm, th = tt;
      if (g && rnd() > beta) [mv, th] = act(g, inp);
      if (rnd() < 0.05) mv = [-1, 0, 1][(rnd() * 3) | 0];  // немного шума для разнообразия
      w.step(mv, th);
    }
  }
  return [X, Y];
}

// Обучение: выход руля — разница ответов на сцену и её зеркало; градиент через обе ветви
function train(g, X, Y, epochs) {
  const m = new Float64Array(NG), v = new Float64Array(NG), grad = new Float64Array(NG);
  const lr = 0.01, b1 = 0.9, b2 = 0.999; let step = 0;
  const idx = X.map((_, k) => k);
  const fwd = (x) => {
    const h = new Float64Array(NH), pre = new Float64Array(NO), o = new Float64Array(NO);
    for (let j = 0; j < NH; j++) { let s = g[O_B1 + j]; for (let i = 0; i < NI; i++) s += g[j * NI + i] * x[i]; h[j] = Math.tanh(s); }
    for (let k = 0; k < NO; k++) { let s = g[O_B2 + k]; for (let j = 0; j < NH; j++) s += g[O_W2 + k * NH + j] * h[j]; o[k] = Math.tanh(s); }
    return [h, o];
  };
  const back = (x, h, dO) => {   // dO: dLoss/d(out) для обоих выходов
    for (let k = 0; k < NO; k++) {
      const dz = dO[k];  // уже умножено на (1 - o^2)
      grad[O_B2 + k] += dz;
      for (let j = 0; j < NH; j++) grad[O_W2 + k * NH + j] += dz * h[j];
    }
    for (let j = 0; j < NH; j++) {
      let dh = 0; for (let k = 0; k < NO; k++) dh += dO[k] * g[O_W2 + k * NH + j];
      const dz = dh * (1 - h[j] * h[j]);
      grad[O_B1 + j] += dz;
      for (let i = 0; i < NI; i++) grad[j * NI + i] += dz * x[i];
    }
  };
  for (let ep = 0; ep < epochs; ep++) {
    for (let k = idx.length - 1; k > 0; k--) { const r = (rnd() * (k + 1)) | 0; [idx[k], idx[r]] = [idx[r], idx[k]]; }
    let loss = 0;
    for (let b = 0; b < idx.length; b += 256) {
      grad.fill(0);
      const batch = idx.slice(b, b + 256);
      for (const n of batch) {
        const x = X[n], mir = x.slice(); for (const q of MIRROR) mir[q] = -mir[q];
        const [h, o] = fwd(x), [hm, om] = fwd(mir);
        const steer = o[0] - om[0], thr = (o[1] + om[1]) / 2;
        const es = steer - Y[n][0], et = thr - Y[n][1];
        loss += es * es + 0.3 * et * et;
        // d steer / d o = +1 (сцена), -1 (зеркало); d thr / d o = 0.5 в обеих
        back(x, h, [2 * es * (1 - o[0] * o[0]), 0.3 * et * (1 - o[1] * o[1])]);
        back(mir, hm, [-2 * es * (1 - om[0] * om[0]), 0.3 * et * (1 - om[1] * om[1])]);
      }
      step++;
      for (let q = 0; q < NG; q++) {
        const gq = grad[q] / batch.length;
        m[q] = b1 * m[q] + (1 - b1) * gq; v[q] = b2 * v[q] + (1 - b2) * gq * gq;
        g[q] -= lr * (m[q] / (1 - b1 ** step)) / (Math.sqrt(v[q] / (1 - b2 ** step)) + 1e-8);
      }
    }
    if (ep === epochs - 1) console.log(`  ошибка ${(loss / idx.length).toFixed(3)} на ${idx.length} примерах`);
  }
}

function evaluate(g, levels = 20) {
  let tot = 0; const causes = {};
  for (let s = 1; s <= levels; s++) {
    const w = new World(s * 7717);
    while (w.alive) { const [mv, th] = act(g, w.sense()); w.step(mv, th); }
    tot += w.maxH; causes[w.cause] = (causes[w.cause] || 0) + 1;
  }
  return [Math.round(tot / levels), JSON.stringify(causes)];
}

const nets = [];
for (let n = 0; n < 4; n++) {
  const g = new Float32Array(NG);
  for (let q = 0; q < NG; q++) g[q] = gauss() * 0.3;
  let [X, Y] = collect(null, 30, 1, 3000);
  for (let round = 0; round < 4; round++) {
    train(g, X, Y, 6);
    const [X2, Y2] = collect(g, 15, 0.3, 3000);
    X = X.concat(X2); Y = Y.concat(Y2);
  }
  train(g, X, Y, 8);
  const [h, c] = evaluate(g);
  console.log(`сеть ${n + 1}: средняя высота ${h}, ${c}`);
  nets.push(g);
}
const out = { ng: NG, method: 'imitation', genomes: [] };
for (let k = 0; k < 12; k++) {
  const base = nets[k % nets.length], c = Float32Array.from(base);
  if (k >= nets.length) for (let q = 0; q < NG; q++) if (rnd() < 0.1) c[q] += gauss() * 0.1;
  out.genomes.push(Array.from(c, v => Math.round(v * 1e5) / 1e5));
}
const outPath = process.argv[2] || path.join(__dirname, '..', 'pretrained.json');
fs.writeFileSync(outPath, JSON.stringify(out));
console.log('записал', outPath);
