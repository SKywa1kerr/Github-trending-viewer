import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('../static/css/style.css', import.meta.url), 'utf8');

const mobileMatch = css.match(/@media\s*\(max-width:\s*640px\)\s*\{[\s\S]*\n\}/);
assert.ok(mobileMatch, 'mobile media query should exist');

const mobileCss = mobileMatch[0];

assert.match(
  css,
  /^\.card-repo a\s*\{[^}]*font-size:\s*26px;/m,
  'project titles should remain prominent on the unframed reading canvas'
);

assert.match(
  css,
  /^\[data-view="list"\] \.card-repo a\s*\{[^}]*font-size:\s*24px;/m,
  'the compact list should preserve the project title hierarchy'
);

assert.match(
  css,
  /^\.card-description\s*\{[^}]*font-size:\s*16px;[^}]*-webkit-line-clamp:\s*4;/m,
  'card descriptions should be readable at 16px and allow four lines'
);

assert.match(
  css,
  /^\[data-view="list"\] \.card-description\s*\{[^}]*-webkit-line-clamp:\s*3;/m,
  'list descriptions should allow one more line without losing their compact layout'
);

assert.match(
  mobileCss,
  /\.card-repo a\s*\{[^}]*font-size:\s*22px;/,
  'mobile titles should remain prominent without using the full desktop size'
);

assert.match(
  mobileCss,
  /\.card-description\s*\{[^}]*-webkit-line-clamp:\s*4;/,
  'mobile cards should also reveal four description lines'
);

assert.match(
  mobileCss,
  /\.project-list\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
  'mobile project cards should use a single column that can shrink with the viewport'
);

assert.match(
  mobileCss,
  /\.filters\s*\{[^}]*flex-wrap:\s*wrap/,
  'mobile filters should wrap instead of forcing horizontal page overflow'
);

assert.match(
  mobileCss,
  /\.card-repo\s+a\s*\{[\s\S]*?overflow-wrap:\s*anywhere\s*;/,
  'mobile repository names should wrap instead of widening project cards'
);

assert.match(css, /^\.workspace\s*\{[^}]*margin:\s*0 auto;/m, 'the canvas should be centered, without a sidebar offset');
assert.doesNotMatch(css, /--sidebar-width|\.sidebar\s*\{/, 'obsolete fixed sidebar styling should be removed');
assert.match(css, /^\.project-card\s*\{[^}]*border:\s*0;/m, 'ordinary project stories should not be enclosed in repeated boxes');
assert.match(css, /^\.card-description\s*\{[^}]*min-height:\s*0;/m, 'short descriptions should not leave fixed-height blank areas');
assert.match(css, /\.project-list\[data-view="grid"\] \.is-featured\s*\{[^}]*grid-column:\s*1 \/ -1;/, 'the discovery spotlight should span the reading canvas');
assert.match(css, /\.project-highlights\s*\{\s*display:\s*none;/, 'spotlight notes should not appear in ordinary or compact cards');
assert.match(css, /@media\s*\(max-width:\s*880px\)[\s\S]*?\.project-list\[data-view="grid"\] \.is-featured\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/, 'spotlight columns should stack on smaller screens');
assert.match(mobileCss, /\.site-header\.is-open \.mode-nav\s*\{[^}]*display:\s*flex;/, 'mobile navigation should open within the header');
assert.match(mobileCss, /\[data-view="list"\] \.project-card\s*\{[^}]*flex-direction:\s*column;/, 'mobile compact rows should stack instead of squeezing two columns');
assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/, 'reduced-motion preferences should still be respected');
assert.match(css, /^\.project-list\s*\{[^}]*repeat\(auto-fill,\s*minmax\(min\(100%,\s*420px\),\s*1fr\)\)/m, 'project columns should adapt to their available width instead of squeezing two narrow stories');
assert.match(css, /^\.card-description\s*\{[^}]*max-width:\s*80ch;/m, 'descriptions should keep a comfortable reading measure');

function rule(selector) {
  const start = css.indexOf(selector + ' {');
  assert.notEqual(start, -1, 'Missing CSS rule: ' + selector);
  return css.slice(start + selector.length + 2, css.indexOf('}', start));
}

function colorToken(declarations, name) {
  const value = declarations.match(new RegExp('--' + name + ':\\s*(#[a-f0-9]{6});', 'i'));
  assert.ok(value, 'Missing color token: ' + name);
  return value[1];
}

function luminance(hex) {
  return hex.match(/[a-f\d]{2}/gi).map(value => parseInt(value, 16) / 255)
    .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
    .reduce((sum, value, i) => sum + value * [.2126, .7152, .0722][i], 0);
}

function contrast(ink, background) {
  const a = luminance(ink), b = luminance(background);
  return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
}

const categories = ['ai', 'tools', 'devtools', 'other'];
for (const [theme, selector] of [['light', ':root'], ['dark', '[data-theme="dark"]']]) {
  const declarations = rule(selector);
  const inks = new Set();
  for (const category of categories) {
    const ink = colorToken(declarations, 'category-' + category);
    const soft = colorToken(declarations, 'category-' + category + '-soft');
    inks.add(ink);
    for (const background of [soft, colorToken(declarations, 'bg'), colorToken(declarations, 'surface')]) {
      assert.ok(contrast(ink, background) >= 4.5, theme + ' ' + category + ' labels must meet 4.5:1 contrast');
    }
    for (const textColor of ['text', 'description', 'secondary']) {
      assert.ok(contrast(colorToken(declarations, textColor), soft) >= 4.5,
        theme + ' ' + category + ' spotlight ' + textColor + ' must remain readable');
    }
    const accentRules = [declarations, ...['teal', 'amber', 'rose'].map(accent =>
      rule((theme === 'dark' ? selector : '') + '[data-accent="' + accent + '"]'))];
    for (const accent of accentRules) {
      assert.ok(contrast(colorToken(accent, 'accent-hover'), soft) >= 4.5,
        theme + ' action text must remain readable on the ' + category + ' spotlight');
    }
  }
  assert.equal(inks.size, 4, theme + ' categories should have four distinct ink colors');
}

for (const category of categories) {
  const declarations = rule(':is(.project-card, .category-tab)[data-category="' + category + '"]');
  assert.ok(declarations.includes('--category-color: var(--category-' + category + ')'));
  assert.ok(declarations.includes('--category-soft: var(--category-' + category + '-soft)'));
  assert.doesNotMatch(declarations, /--accent:/, 'category colors must not replace the action accent');
}
assert.match(rule('.category-tab.active'), /color: var\(--category-color\)/);
assert.match(rule('.category-tab::after'), /background: var\(--category-color\)/);
assert.match(rule('.category-tab:not([data-category="all"])::before'), /background: var\(--category-color\)/);
assert.match(rule('.repo-category'), /color: var\(--category-color\)/);
assert.match(rule('.project-list[data-view="grid"] .is-featured'), /background: color-mix\(in srgb, var\(--category-soft\) var\(--spotlight-tint\), var\(--surface\)\)/);
assert.match(rule('.project-list[data-view="grid"] .is-featured'), /--muted: var\(--secondary\)/);
assert.match(rule('.project-list[data-view="grid"] .is-featured .project-highlights'), /background: var\(--spotlight-panel-bg\)/);
assert.match(rule('.project-highlights h3'), /color: var\(--spotlight-panel-heading\)/);
assert.match(rule('.project-highlights li::marker'), /color: var\(--spotlight-panel-text\)/);
assert.match(rule('.project-card:hover'), /background: var\(--category-hover\)/);
assert.match(rule('.button-primary'), /background: var\(--accent\)/);
assert.match(rule('.btn-favorite.favorited'), /color: var\(--accent\)/);
assert.match(rule('.search-form:focus-within'), /border-color: var\(--accent\)/);

assert.match(rule('.project-mark'), /position: relative;[^}]*width: 50px; height: 50px;/);
assert.match(rule('.project-mark'), /overflow: hidden;[^}]*border-radius: var\(--mark-radius\)/);
assert.match(rule('.project-avatar'), /position: absolute;[^}]*object-fit: cover; opacity: 0;/);
assert.match(rule('.project-avatar'), /border-radius: calc\(var\(--mark-radius\) - 3px\)/);
assert.match(rule('.project-mark.has-avatar .project-avatar'), /opacity: 1/);
assert.match(rule('.project-mark.has-avatar .project-monogram'), /visibility: hidden/);
assert.match(rule('.repo-byline'), /flex-wrap: wrap/, 'category labels should wrap below long owner names');
for (const [, declarations] of css.matchAll(/(?:^|\n)\s*[^\n{]*\.project-mark\s*\{([^}]+)\}/g)) {
  assert.match(declarations, /--mark-radius:/, 'each avatar size must keep its inset corner radius in sync');
}

const signatureStyle = rule('.branch-signature');
assert.match(signatureStyle, /display: block; width: 96px; height: 25px;/);
assert.match(signatureStyle, /pointer-events: none/);
assert.doesNotMatch(signatureStyle, /animation:|transform:|position: absolute/, 'the small signature should be static and reserve its own space');
assert.match(mobileCss, /\.branch-signature\s*\{[^}]*width: 82px; height: 22px;/, 'the signature should stay small on mobile');
for (const category of categories) {
  assert.ok(rule('.branch-node-' + category).includes('fill: var(--category-' + category + ')'));
}

const spotlightStyle = rule('.project-list[data-view="grid"] .is-featured');
assert.match(spotlightStyle, /position: relative/);
assert.match(spotlightStyle, /box-shadow: inset 0 0 0 1px var\(--category-line\)/);
assert.doesNotMatch(spotlightStyle, /overflow: hidden/, 'the spotlight frame must not clip keyboard focus outlines');
const spotlightMarker = rule('.project-list[data-view="grid"] .is-featured::before');
assert.match(spotlightMarker, /position: absolute; top: 0; left: var\(--spotlight-inset\)/);
assert.match(spotlightMarker, /width: 42px; height: 3px/);
assert.match(spotlightMarker, /background: var\(--category-color\); pointer-events: none/);
assert.match(spotlightStyle, /--spotlight-inset: 40px/);
assert.match(css, /@media\s*\(max-width:\s*1100px\)[\s\S]*?\.is-featured\s*\{[^}]*--spotlight-inset: 30px;[^}]*padding: 30px;/);
assert.match(mobileCss, /\.is-featured\s*\{[^}]*--spotlight-inset: 23px;[^}]*padding: 25px 23px;/);
assert.match(rule('.project-card:has(:focus-visible)'), /background: var\(--category-hover\)/, 'keyboard navigation should have the same reading focus as hovering');
assert.match(rule(':focus-visible'), /outline: 2px solid var\(--accent\)/);
assert.match(rule('.category-tab.active:not([data-category="all"])::before'), /box-shadow: 0 0 0 4px var\(--category-soft\)/);

for (const selector of [':root', '[data-theme="dark"]']) {
  assert.match(rule(selector), /--control-shadow:/);
  assert.match(rule(selector), /--surface-rim:/);
}
assert.match(rule('.search-form'), /border: 1px solid var\(--border\)/);
assert.match(rule('.search-form'), /box-shadow: inset 0 1px 0 var\(--surface-rim\), var\(--control-shadow\)/);
assert.match(rule(':is(.button, .icon-button, .utility-button):active:not(:disabled)'), /transform: translateY\(1px\)/);
const reducedMotionCss = css.slice(css.indexOf('@media (prefers-reduced-motion: reduce)'));
assert.match(reducedMotionCss, /:is\(\.button, \.icon-button, \.utility-button\):active:not\(:disabled\)\s*\{\s*transform: none;/, 'reduced-motion users should not get the press displacement');

// Light mode separates the page canvas from a single, uninterrupted reading surface.
const lightPalette = rule(':root');
const darkPalette = rule('[data-theme="dark"]');
const lightCanvas = colorToken(lightPalette, 'bg');
const lightSurface = colorToken(lightPalette, 'surface');
assert.ok(luminance(lightCanvas) > .87 && luminance(lightCanvas) < .97, 'the light canvas should remain a near-white neutral');
assert.ok(luminance(lightSurface) - luminance(lightCanvas) >= .03, 'the white reading surface should be distinct from the canvas');
assert.match(lightPalette, /--reading-bg: var\(--surface\)/);
assert.match(darkPalette, /--reading-bg: transparent;[\s\S]*--reading-edge: transparent;[\s\S]*--reading-shadow: none;/);
assert.match(rule('.results-section'), /position: relative; isolation: isolate/);
assert.doesNotMatch(rule('.results-section'), /overflow: hidden|padding:/, 'the surface must not clip filters or narrow the existing reading columns');
const readingSurface = rule('.results-section::before');
assert.match(readingSurface, /position: absolute; z-index: -1;/);
assert.match(readingSurface, /background: var\(--reading-bg\)/);
assert.match(readingSurface, /pointer-events: none/);
assert.match(readingSurface, /inset: -4px -24px -24px/);
assert.match(css, /@media\s*\(max-width:\s*1100px\)[\s\S]*?\.results-section::before\s*\{[^}]*inset: -4px -20px -24px/);
assert.match(css, /@media\s*\(max-width:\s*880px\)[\s\S]*?\.results-section::before\s*\{[^}]*inset: -4px -16px -24px/);
assert.match(mobileCss, /\.results-section::before\s*\{[^}]*inset: -4px -12px -20px/, 'the mobile surface must stay inside the 20px workspace gutter');

assert.match(lightPalette, /--spotlight-tint: 44%/);
assert.match(darkPalette, /--spotlight-tint: 100%/);
assert.match(lightPalette, /--story-surface: var\(--surface\)/);
assert.match(darkPalette, /--story-surface: var\(--bg\)/);
assert.match(lightPalette, /--category-line-strength: 16%/);
assert.match(darkPalette, /--category-line-strength: 22%/);
for (const palette of [lightPalette, darkPalette]) {
  for (const token of ['spotlight-panel-text', 'spotlight-panel-heading']) {
    assert.ok(contrast(colorToken(palette, token), colorToken(palette, 'spotlight-panel-bg')) >= 4.5,
      'spotlight notes must remain readable in both themes');
  }
}

function mixColor(first, second, weight) {
  const a = first.match(/[a-f\d]{2}/gi).map(value => parseInt(value, 16));
  const b = second.match(/[a-f\d]{2}/gi).map(value => parseInt(value, 16));
  return '#' + a.map((value, i) => Math.round(value * weight + b[i] * (1 - weight)).toString(16).padStart(2, '0')).join('');
}
for (const textColor of ['text', 'description', 'secondary', 'muted']) {
  for (const background of [lightCanvas, lightSurface, colorToken(lightPalette, 'well'),
    ...categories.flatMap(category => {
      const soft = colorToken(lightPalette, 'category-' + category + '-soft');
      return [soft, mixColor(soft, lightSurface, .44)];
    })]) {
    assert.ok(contrast(colorToken(lightPalette, textColor), background) >= 4.5,
      textColor + ' must remain readable on every light-mode reading surface');
  }
}
for (const accent of ['indigo', 'teal', 'amber', 'rose']) {
  const palette = accent === 'indigo' ? lightPalette : rule('[data-accent="' + accent + '"]');
  const ink = colorToken(palette, 'accent');
  const swatch = rule(accent === 'indigo' ? '.accent-picker button' : '.accent-picker button[data-accent="' + accent + '"]');
  assert.ok(swatch.includes('background: ' + ink), 'the ' + accent + ' swatch should preview its actual light-mode accent');
  assert.ok(contrast(ink, '#ffffff') >= 4.5, 'the ' + accent + ' primary action and brand mark must support white text');
  assert.ok(contrast(ink, colorToken(palette, 'accent-soft')) >= 4.5, 'the ' + accent + ' text must remain readable on its soft tint');
}
assert.match(rule('.brand-mark'), /background: var\(--brand-bg\); color: var\(--brand-color\)/);
assert.match(rule('.mode-nav'), /background: var\(--nav-bg\)/);
assert.match(rule('.mode-tab.active'), /color: var\(--nav-active-color\)/);
assert.match(rule('.search-form'), /background: var\(--search-bg\)/);
assert.match(lightPalette, /--brand-bg: var\(--accent\)/);
assert.match(darkPalette, /--brand-bg: var\(--text\);[\s\S]*--brand-color: var\(--bg\)/);
assert.match(lightPalette, /--nav-active-color: var\(--accent\)/);
assert.match(darkPalette, /--nav-active-color: var\(--text\)/);
assert.match(lightPalette, /--search-bg: var\(--surface\)/);
assert.match(darkPalette, /--search-bg: var\(--well\)/);
assert.match(rule('.page-header h1'), /font-weight: var\(--display-weight\)/);
assert.match(lightPalette, /--display-weight: 500/);
assert.match(darkPalette, /--display-weight: 600/);
for (const [name, expected] of Object.entries({bg: '#181a1e', surface: '#22252b', text: '#f1f3f7', accent: '#93baff',
  'category-ai': '#baa7f5', 'category-tools': '#87ceb6', 'category-devtools': '#99bfff', 'category-other': '#e9b780'})) {
  assert.equal(colorToken(darkPalette, name), expected, 'this light-mode refresh must preserve dark-mode ' + name);
}
