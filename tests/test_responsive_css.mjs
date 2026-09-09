import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('../static/css/style.css', import.meta.url), 'utf8');

const mobileMatch = css.match(/@media\s*\(max-width:\s*640px\)\s*\{[\s\S]*\n\}/);
assert.ok(mobileMatch, 'mobile media query should exist');

const mobileCss = mobileMatch[0];

assert.match(
  mobileCss,
  /\.header\s*\{[\s\S]*?margin:\s*0\s+-16px\s+24px\s*;/,
  'mobile header negative margin should match .main-content horizontal padding'
);

assert.match(
  mobileCss,
  /\.category-tabs\s*\{[\s\S]*?min-width:\s*0\s*;/,
  'mobile horizontal tab scroller should not force the page wider than its container'
);

assert.match(
  mobileCss,
  /\.card-repo\s+a\s*\{[\s\S]*?overflow-wrap:\s*anywhere\s*;/,
  'mobile repository names should wrap instead of widening project cards'
);
