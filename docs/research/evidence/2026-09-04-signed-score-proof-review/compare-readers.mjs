// Offline only: load two source strings in memory; never invoke the handler.
import { readFileSync } from 'node:fs';
const input = JSON.parse(readFileSync(0, 'utf8'));
const exports = '\nexport { validateV2Proof, precloseContractValid, precloseScore };\n';
async function reader(source) {
  return import('data:text/javascript;base64,' + Buffer.from(source + exports).toString('base64'));
}
const baseline = await reader(input.baseline_source);
const proposed = await reader(input.proposed_source);
const results = {};
for (const [name, row] of Object.entries(input.rows)) {
  results[name] = {
    baseline: baseline.validateV2Proof(row) !== null,
    proposed: proposed.validateV2Proof(row) !== null,
  };
}
const nonfinite = {};
for (const [name, value] of [['nan', NaN], ['positive_infinity', Infinity], ['negative_infinity', -Infinity]]) {
  const row = structuredClone(input.rows.negative);
  row.evaluation_proof.preclose.score = value;
  nonfinite[name] = {baseline: baseline.validateV2Proof(row) !== null, proposed: proposed.validateV2Proof(row) !== null};
}
process.stdout.write(JSON.stringify({results, nonfinite}));
