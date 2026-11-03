// Run: node --test src/lib/format.test.cjs (from dashboard).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const source = fs.readFileSync(`${__dirname}/format.ts`, 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const loaded = { exports: {} };
new Function('exports', compiled)(loaded.exports);
const { fmtCount, fmtNum, fmtUsd, fmtSec } = loaded.exports;

test('compact counts and unit promotion', () => {
  for (const [input, expected] of [
    [0, '0'], [1, '1'], [999, '999'], [999.99, '999.99'],
    [1000, '1K'], [1200, '1.2K'], [12500, '12.5K'],
    [999949, '999.9K'], [999950, '1M'], [1000000, '1M'],
    [1200000, '1.2M'], [999950000, '1B'], [1200000000, '1.2B'],
    [-999, '-999'], [-12500, '-12.5K'], [-999950, '-1M'],
    [null, '-'], [undefined, '-'],
  ]) assert.equal(fmtCount(input), expected, String(input));
});

test('count formatting never emits 1000K or 1000M near boundaries', () => {
  for (const boundary of [1000000, 1000000000]) {
    for (let offset = -100; offset <= 100; offset++) {
      assert.doesNotMatch(fmtCount(boundary + offset), /1000[KM]/);
    }
  }
});

test('exact number, money and duration formatters remain unchanged', () => {
  assert.equal(fmtNum(12500), '12,500');
  assert.equal(fmtUsd(12500), '$12500.00');
  assert.equal(fmtSec(12500), '208:20');
});
