// Предобучение в симуляторе: node pretrain/pretrain.js [поколений]
// Пишет ../pretrained.json — с этих сетей bot.py начинает учиться в настоящей игре.
const fs = require('fs');
const path = require('path');
const { Population, NG } = require('./sim.js');

const GENS = +process.argv[2] || 80;
const pop = new Population(60);
const t0 = Date.now();
while (pop.gen <= GENS) {
  if (pop.tick()) {
    const h = pop.history[pop.history.length - 1];
    if (h.gen % 10 === 0) console.log(`поколение ${h.gen}: лучший ${Math.round(h.best)}, среднее ${Math.round(h.avg)}`);
  }
}
// После evolve() первыми идут элиты прошлого поколения — их и берём
const out = { ng: NG, gens: GENS, genomes: pop.genomes.slice(0, 12).map(g => Array.from(g, v => Math.round(v * 1e5) / 1e5)) };
fs.writeFileSync(path.join(__dirname, '..', 'pretrained.json'), JSON.stringify(out));
console.log(`Готово за ${((Date.now() - t0) / 1000).toFixed(0)} с, записал pretrained.json`);
