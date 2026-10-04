// «Учитель» для симулятора: знает физику и для каждой видимой платформы считает,
// успеет ли персонаж до неё долететь. Выбирает самую высокую достижимую с запасом
// и рулит к ней с упреждением (учитывает, что после отпускания клавиши персонаж
// ещё немного скользит). Нейросеть учится повторять его решения (imitate.js),
// видя только то же, что видит в настоящей игре.
const sim = require('./sim.js');
const { W, H, G, MAXVX, PW } = sim.CONST;

const wdx = (a, b) => { let d = b - a; if (d > W / 2) d -= W; else if (d < -W / 2) d += W; return d; };
const TOL = PW / 2 + 13 - 6;   // насколько центр персонажа может не попасть в центр платформы

// Время (в тиках), когда ноги, двигаясь вниз, пересекут уровень y; null — не долетаем
function landTime(feet, vy, y) {
  const a = G / 2, b = vy, c = feet - y;
  const disc = b * b - 4 * a * c;
  if (disc < 0) return null;
  const t = (-b + Math.sqrt(disc)) / (2 * a);
  return t > 0 ? t : null;
}

// Сколько по горизонтали можно пролететь за t тиков, разгоняясь к цели
function reach(vx, dir, t) {
  let v = vx, d = 0;
  for (let k = 0; k < t; k++) { v += (dir * MAXVX - v) * 0.25; d += v * dir; }
  return d;
}

function teacher(w) {
  const p = w.p, feet = p.y + 20;
  let best = null, up = null;
  for (const pl of w.plats) {
    if (pl.broken || pl.y > w.cam + H) continue;
    if (pl.y < feet - 1 && p.vy > 0) continue;              // выше ног при падении — уже не достать
    if (landTime(feet, p.vy, pl.y - 12) === null) continue;  // в высшей точке нужен запас по высоте
    const t = landTime(feet, p.vy, pl.y);
    if (t === null || t < 2) continue;
    const d = wdx(p.x, pl.x + PW / 2), need = Math.max(0, Math.abs(d) - TOL);
    const margin = reach(p.vx, Math.sign(d) || 1, Math.floor(t)) - need;
    const score = margin >= 8 ? -pl.y : -1e6 + margin;      // выше — лучше, если долетаем с запасом
    if (!best || score > best.score) best = { pl, d, t, score, margin };
    if (pl.y < w.base.y - 1 && (!up || margin > up.margin)) up = { pl, d, t, margin };
  }
  // Если надёжно долетаем только обратно на свою платформу, оставаться бессмысленно:
  // пробуем ближайшую по шансам платформу выше
  if (best && best.pl === w.base && up && up.margin > -25) best = up;
  let move = 0;
  if (best) {
    // куда снесёт, если отпустить клавишу сейчас: скорость гаснет на 25% за тик → ещё ~3·vx
    const after = best.d - 3 * p.vx;
    if (Math.abs(after) > PW / 2 - 10) move = after > 0 ? 1 : -1;
  }
  const enemy = w.enemies.some(e => !e.dead && e.y > w.cam && e.y < w.cam + H);
  return [move, enemy && w.cool <= 0];
}

module.exports = { teacher };

if (require.main === module) {
  // Проверка: как учитель играет сам, с той же частотой решений, что и настоящий бот
  const { World } = sim;
  let tot = 0; const causes = {};
  for (let s = 1; s <= 20; s++) {
    const w = new World(s * 7717);
    let mv = 0, th = false;
    while (w.alive) { if (w.t % sim.CONST.DECIDE_EVERY === 0) [mv, th] = teacher(w); w.step(mv, th); }
    tot += w.maxH; causes[w.cause] = (causes[w.cause] || 0) + 1;
  }
  console.log('учитель: средняя высота', Math.round(tot / 20), JSON.stringify(causes));
}
