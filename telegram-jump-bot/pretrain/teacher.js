// «Учитель» для симулятора: знает физику и для каждой видимой платформы считает,
// успеет ли персонаж до неё долететь. Выбирает самую высокую достижимую с запасом
// и рулит к ней с упреждением (учитывает, что после отпускания клавиши персонаж
// ещё немного скользит). Нейросеть учится повторять его решения (imitate.js),
// видя только то же, что видит в настоящей игре.
const sim = require('./sim.js');
const { W, H, G, MAXVX, PW, HOLE_R } = sim.CONST;

const wdx = (a, b) => { let d = b - a; if (d > W / 2) d -= W; else if (d < -W / 2) d += W; return d; };
const TOL = PW / 2 + 13 - 6;   // насколько центр персонажа может не попасть в центр платформы

// Время (в тиках), когда ноги, двигаясь вниз, пересекут уровень y; null — не долетаем
// (физика по шагам: скорость растёт до сдвига, поэтому y(n) = y0 + n·(vy + G/2) + G·n²/2)
function landTime(feet, vy, y) {
  const a = G / 2, b = vy + G / 2, c = feet - y;
  const disc = b * b - 4 * a * c;
  if (disc < 0) return null;
  const t = (-b + Math.sqrt(disc)) / (2 * a);
  return t > 0 ? t : null;
}

// Где будет левый край платформы через t тиков (движущиеся ездят туда-обратно)
function platX(pl, t) {
  if (pl.type !== 'm') return pl.x;
  let x = pl.x, v = pl.v;
  for (let k = 0; k < t; k++) {
    x += v;
    if (x < pl.lo) { x = pl.lo; v = -v; } else if (x > pl.hi) { x = pl.hi; v = -v; }
  }
  return x;
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
    const lx = platX(pl, Math.floor(t));                     // где платформа будет, когда долетим
    // Платформа под дырой опасна: отскочишь вверх — и прямо в неё (дыра снизу не мешает).
    // Такие берём, только если других путей наверх нет
    const danger = w.holes.some(hl => Math.abs(wdx(hl.x, lx + PW / 2)) < HOLE_R + 22 && hl.y < pl.y + 20 && hl.y > pl.y - 230);
    const d = wdx(p.x, lx + PW / 2), need = Math.max(0, Math.abs(d) - TOL);
    const margin = reach(p.vx, Math.sign(d) || 1, Math.floor(t)) - need;
    const score = margin >= 8 && !danger ? -pl.y : -1e6 + margin;  // выше — лучше, если долетаем с запасом
    if (!best || score > best.score) best = { pl, d, t, score, margin };
    if (pl.y < w.base.y - 1 && (!up || margin - (danger ? 20 : 0) > up.margin)) up = { pl, d, t, margin: margin - (danger ? 20 : 0) };
  }
  // Если надёжно долетаем только обратно на свою платформу, оставаться бессмысленно:
  // пробуем ближайшую по шансам платформу выше
  // (кроме движущейся: на ней лучше подождать, пока она подвезёт к нужной платформе)
  if (best && best.pl === w.base && w.base.type !== 'm' && up && up.margin > -25) best = up;
  let move = 0;
  if (best) {
    // куда снесёт, если отпустить клавишу сейчас: скорость гаснет на 25% за тик → ещё ~3·vx
    const after = best.d - 3 * p.vx;
    if (Math.abs(after) > PW / 2 - 10) move = after > 0 ? 1 : -1;
  }
  // Чёрная дыра прямо на пути (не выше, чем долетим) — уходим от неё в сторону
  // Пока дыра на пути вверх, к ней не приближаемся, даже если цель по ту сторону
  const rise = p.vy < 0 ? p.vy * p.vy / (2 * G) : 0;
  for (const hl of w.holes) {
    const dx = wdx(p.x, hl.x), dy = hl.y - p.y;
    if (dy >= 30 || dy <= -(rise + 30)) continue;
    const away = dx > 0 ? -1 : 1;
    if (Math.abs(dx) < HOLE_R + 18) move = away;
    else if (Math.abs(dx) < HOLE_R + 45 && move === -away) move = 0;
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
