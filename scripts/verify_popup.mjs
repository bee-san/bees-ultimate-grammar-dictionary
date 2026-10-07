// Exercise the pinned, unmodified Yomitan Japanese transformation engine.
// Input rows come from the actual ZIP, including its POS/deinflection field.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {LanguageTransformer} from '../tests/vendor/yomitan/ext/js/language/language-transformer.js';
import {japaneseTransforms} from '../tests/vendor/yomitan/ext/js/language/ja/japanese-transforms.js';

const {rows, cases, absent = []} = JSON.parse(fs.readFileSync(0, 'utf8'));
const transformer = new LanguageTransformer();
transformer.addDescriptor(japaneseTransforms);
const byTerm = new Map();
// Like Yomitan's database, a row is found by its term and by its reading.
for (const row of rows) {
    for (const key of new Set([row.term, row.reading].filter(Boolean))) {
        if (!byTerm.has(key)) byTerm.set(key, []);
        byTerm.get(key).push(row);
    }
}
// Yomitan tries progressively shorter prefixes from the hovered position,
// then tests transformed candidates against each dictionary row's rules.
function lookup(text, hover) {
    const offset = text.indexOf(hover);
    assert(offset >= 0, `Missing cursor text: ${hover}`);
    const scanned = text.slice(offset);
    const hits = new Set();
    for (let length = scanned.length; length > 0; --length) {
        for (const candidate of transformer.transform(scanned.slice(0, length))) {
            for (const row of byTerm.get(candidate.text) ?? []) {
                const flags = transformer.getConditionFlagsFromPartsOfSpeech(row.rules.split(' '));
                if (LanguageTransformer.conditionsMatch(candidate.conditions, flags)) {
                    hits.add(row.term);
                    for (const label of row.sources) hits.add(`${row.term}\t${label}`);
                }
            }
        }
    }
    return hits;
}
for (const {text, hover, term, source} of cases) {
    assert(lookup(text, hover).has(`${term}\t${source}`), `No ${source} hit for ${term}: ${text} at ${hover}`);
}
for (const {text, hover, term} of absent) {
    assert(!lookup(text, hover).has(term), `Unexpected ${term} hit: ${text} at ${hover}`);
}
console.log(JSON.stringify({checked: cases.length + absent.length, engine: 'Yomitan 06393468bf00dfc315a3eba78b9f2c95fa1ffd10'}));
