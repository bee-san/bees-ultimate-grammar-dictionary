// Exercise the pinned, unmodified Yomitan Japanese transformation engine.
// Input rows come from the actual ZIP, including its POS/deinflection field.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {LanguageTransformer} from '../tests/vendor/yomitan/ext/js/language/language-transformer.js';
import {japaneseTransforms} from '../tests/vendor/yomitan/ext/js/language/ja/japanese-transforms.js';

const {rows, cases} = JSON.parse(fs.readFileSync(0, 'utf8'));
const transformer = new LanguageTransformer();
transformer.addDescriptor(japaneseTransforms);
const byTerm = new Map();
for (const row of rows) {
    if (!byTerm.has(row.term)) byTerm.set(row.term, []);
    byTerm.get(row.term).push(row);
}
for (const {text, hover, term, source} of cases) {
    const offset = text.indexOf(hover);
    assert(offset >= 0, `Missing cursor text: ${hover}`);
    const scanned = text.slice(offset);
    const hits = new Set();
    // Yomitan tries progressively shorter prefixes from the hovered position,
    // then tests transformed candidates against each dictionary row's rules.
    for (let length = scanned.length; length > 0; --length) {
        for (const candidate of transformer.transform(scanned.slice(0, length))) {
            for (const row of byTerm.get(candidate.text) ?? []) {
                const flags = transformer.getConditionFlagsFromPartsOfSpeech(row.rules.split(' '));
                if (LanguageTransformer.conditionsMatch(candidate.conditions, flags)) {
                    for (const label of row.sources) hits.add(`${row.term}\t${label}`);
                }
            }
        }
    }
    assert(hits.has(`${term}\t${source}`), `No ${source} hit for ${term}: ${text} at ${hover}`);
}
console.log(JSON.stringify({checked: cases.length, engine: 'Yomitan 06393468bf00dfc315a3eba78b9f2c95fa1ffd10'}));
