import assert from 'node:assert/strict';

import {
  escapeHtml,
  formatChatText,
  formatReadmeHtml,
  safeExternalUrl,
} from '../static/js/sanitize.mjs';

assert.equal(
  escapeHtml('<img src=x onerror="alert(1)">'),
  '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'
);

{
  const html = formatChatText('hello <b>world</b>\n`code`');

  assert.match(html, /hello &lt;b&gt;world&lt;\/b&gt;<br><code>code<\/code>/);
  assert.doesNotMatch(html, /<b>world<\/b>/);
}

{
  const html = formatReadmeHtml('1. ship it\n- <script>alert(1)</script>');

  assert.match(html, /readme-point-num">1</);
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>/);
}

assert.equal(safeExternalUrl('https://github.com/openai/openai-python'), 'https://github.com/openai/openai-python');
assert.equal(safeExternalUrl('javascript:alert(1)'), '#');
assert.equal(safeExternalUrl('data:text/html,boom'), '#');
