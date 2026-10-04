// Предобучение в симуляторе: node pretrain/pretrain.js [поколений] [куда записать] [с каких сетей начать]
// Пишет ../pretrained.json — с этих сетей bot.py начинает учиться в настоящей игре.
const fs = require('fs');
const path = require('path');
const { Population, NG } = require('./sim.js');

const GENS = +process.argv[2] || 80;
const pop = new Population(60);
// Третий аргумент — файл с сетями, с которых продолжить (например, прошлый pretrained.json)
if (process.argv[4]) {
  const seeds = require(path.resolve(process.argv[4])).genomes;
  seeds.forEach((g, i) => { if (i < pop.genomes.length) pop.genomes[i] = Float32Array.from(g); });
  pop.begin();
}
const t0 = Date.now();
while (pop.gen <= GENS) {
  if (pop.tick()) {
    const h = pop.history[pop.history.length - 1];
    if (h.gen % 10 === 0) console.log(`поколение ${h.gen}: лучший ${Math.round(h.best)}, среднее ${Math.round(h.avg)}`);
  }
}
// После evolve() первыми идут элиты прошлого поколения — их и берём
const out = { ng: NG, gens: GENS, genomes: pop.genomes.slice(0, 12).map(g => Array.from(g, v => Math.round(v * 1e5) / 1e5)) };
const outPath = process.argv[3] || path.join(__dirname, '..', 'pretrained.json');
fs.writeFileSync(outPath, JSON.stringify(out));
console.log(`Готово за ${((Date.now() - t0) / 1000).toFixed(0)} с, записал ${outPath}`);
