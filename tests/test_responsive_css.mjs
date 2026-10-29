import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('../static/css/style.css', import.meta.url), 'utf8');
const root = css.match(/:root\s*\{([^}]+)\}/)[1];
const dark = css.match(/\[data-theme="dark"\]\s*\{([^}]+)\}/)[1];
function tokens(body) {
    return Object.fromEntries([...body.matchAll(/--([\w-]+):\s*(#[a-f\d]{6});/gi)].map(([, key, value]) => [key, value]));
}
function luminance(hex) {
    return hex.match(/[a-f\d]{2}/gi).map(value => parseInt(value, 16) / 255)
        .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
        .reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
}
function contrast(a, b) {
    const x = luminance(a), y = luminance(b);
    return (Math.max(x, y) + .05) / (Math.min(x, y) + .05);
}
// Check actual palette relationships, independently of exact colors and geometry.
for (const [theme, palette] of [['light', tokens(root)], ['dark', tokens(dark)]]) {
    for (const ink of ['text', 'description', 'secondary', 'faint']) {
        for (const ground of ['bg', 'surface', 'raised', 'active']) {
            assert.ok(contrast(palette[ink], palette[ground]) >= 4.5, `${theme}: ${ink} on ${ground} must be legible`);
        }
    }
    for (const ink of ['signal', 'negative', 'warning']) {
        assert.ok(contrast(palette[ink], palette.surface) >= 4.5, `${theme}: ${ink} carries readable information`);
    }
    assert.ok(contrast(palette.text, palette.surface) >= 7, `${theme}: primary controls must have strong contrast`);
}
for (const name of ['teal', 'amber', 'rose']) {
    for (const [theme, selector, base] of [
        ['light', `[data-accent="${name}"]`, tokens(root)],
        ['dark', `[data-theme="dark"][data-accent="${name}"]`, tokens(dark)],
    ]) {
        const start = css.indexOf(selector + ' {');
        const palette = tokens(css.slice(start, css.indexOf('}', start)));
        assert.ok(contrast(palette.signal, base.surface) >= 4.5, `${theme}: ${name} signal must be readable`);
    }
}
assert.match(css, /:focus-visible\s*\{[^}]*outline:\s*2px/, 'keyboard users retain a visible focus indicator');
assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/, 'motion preference has a CSS fallback');
assert.match(css, /overscroll-behavior:\s*contain/, 'reader scrolling must stay within its region');
console.log('Both themes, all accent choices, keyboard focus and reader scrolling checks passed.');
