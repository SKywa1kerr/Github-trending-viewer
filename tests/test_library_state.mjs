import assert from 'node:assert/strict';
import {
  buildModeState, createRequestGate, filterProjectItems,
  parseProjectDate, streamChatText, timeAgo,
} from '../static/js/library.mjs';

// A late response cannot replace the result from a newer category/search request.
{
  const gate = createRequestGate();
  let resolveOld, resolveNew, visible;
  const old = gate.start();
  const pendingOld = new Promise(resolve => { resolveOld = resolve; })
    .then(value => { if (old.isCurrent()) visible = value; });
  const current = gate.start();
  const pendingNew = new Promise(resolve => { resolveNew = resolve; })
    .then(value => { if (current.isCurrent()) visible = value; });
  assert.equal(old.signal.aborted, true);
  resolveNew('tools/current');
  await pendingNew;
  resolveOld('ai/stale');
  await pendingOld;
  assert.equal(visible, 'tools/current');
  gate.cancel();
  assert.equal(current.isCurrent(), false);
  assert.equal(current.signal.aborted, true);
}

assert.equal(buildModeState('all').category, 'all');
assert.equal(buildModeState('favorites').favoritesMode, true);
assert.equal(buildModeState('recommend').githubSearch, false);

// Cached recommendations use the same literal search and filters as the library.
{
  const projects = [
    { repo_full_name: 'a/one', language: 'Python', stars: 3000, topics: ['observability'] },
    { repo_full_name: 'b/two', language: 'Rust', stars: 5000, topics: ['observability'] },
    { repo_full_name: 'c/three', language: 'Python', stars: 100, readme_summary_zh: '日报汇总，100% 本地运行' },
  ];
  assert.deepEqual(filterProjectItems(projects, { query: 'observability', language: 'Python', minStars: 1000 }).map(p => p.repo_full_name), ['a/one']);
  assert.deepEqual(filterProjectItems(projects, { query: '日报汇总' }).map(p => p.repo_full_name), ['c/three']);
  assert.deepEqual(filterProjectItems(projects, { query: '100%' }).map(p => p.repo_full_name), ['c/three']);
  assert.deepEqual(filterProjectItems(projects, { sort: 'stars' }).map(p => p.stars), [5000, 3000, 100]);
  assert.equal(projects[0].repo_full_name, 'a/one', 'sorting must not mutate the cached recommendation order');
}

assert.equal(parseProjectDate('2026-09-09 09:26:52').toISOString(), '2026-09-09T09:26:52.000Z');
assert.equal(parseProjectDate('2026-09-09T17:26:52+08:00').toISOString(), '2026-09-09T09:26:52.000Z');
assert.equal(parseProjectDate('invalid'), null);
assert.equal(timeAgo('2026-09-09 09:26:52', Date.parse('2026-09-09T10:26:52Z')), '1 小时前');

function byteStream(text, chunkSize = 1) {
  const bytes = new TextEncoder().encode(text);
  return new ReadableStream({ start(controller) {
    for (let i = 0; i < bytes.length; i += chunkSize) controller.enqueue(bytes.slice(i, i + chunkSize));
    controller.close();
  } });
}

// Splitting every byte exercises both partial JSON frames and multibyte Chinese text.
for (const size of [1, 2, 7, 1000]) {
  const stream = byteStream('data: {"content":"你好，"}\r\n\r\ndata: {"content":"世界🌍"}\n\ndata: [DONE]\n\n', size);
  let text = '';
  for await (const part of streamChatText(stream)) text += part;
  assert.equal(text, '你好，世界🌍');
}

{
  let text = '';
  for await (const part of streamChatText(byteStream('data: {"content":"尾帧"}'))) text += part;
  assert.equal(text, '尾帧');
}

await assert.rejects(async () => {
  for await (const part of streamChatText(byteStream('data: {"error":"unavailable"}\n\n'))) void part;
}, /unavailable/);

console.log('Library state, filtering, UTC dates and fragmented chat streams passed.');
