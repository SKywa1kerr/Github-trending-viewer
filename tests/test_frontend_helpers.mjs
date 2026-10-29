import assert from 'node:assert/strict';

import {
  buildModeState,
  buildResultContext,
  buildSparklinePoints,
  emptyStateMessage,
  formatTranslationSummary,
  renderProjectMeta,
  renderSparkline,
  sparklineTrend,
} from '../static/js/app.js';

assert.deepEqual(buildModeState('favorites'), {
  category: 'all',
  favoritesMode: true,
  recommendMode: false,
  githubSearch: false,
  page: 1,
});

assert.deepEqual(buildModeState('recommend'), {
  category: 'all',
  favoritesMode: false,
  recommendMode: true,
  githubSearch: false,
  page: 1,
});

assert.deepEqual(buildModeState('devtools'), {
  category: 'devtools',
  favoritesMode: false,
  recommendMode: false,
  githubSearch: false,
  page: 1,
});

assert.equal(emptyStateMessage({ favoritesMode: true }), '还没有收藏的项目');
assert.equal(
  emptyStateMessage({ recommendMode: true, reason: 'no_favorites' }),
  '收藏一些项目后，AI 会为你推荐相似项目'
);
assert.equal(
  emptyStateMessage({ githubSearch: true, reason: 'error' }),
  'GitHub 搜索失败，请检查网络或稍后重试'
);
assert.equal(emptyStateMessage({}), '暂无项目数据');

assert.deepEqual(
  buildResultContext({
    category: 'ai',
    language: 'Python',
    query: 'agent',
    total: 42,
  }),
  {
    label: '本地筛选',
    title: 'AI · Python · agent',
    detail: '共 42 个项目',
    tone: 'local',
  }
);

assert.deepEqual(
  buildResultContext({
    githubSearch: true,
    query: 'vector database',
    total: 12,
  }),
  {
    label: 'GitHub 搜索',
    title: 'vector database',
    detail: '来自 GitHub 实时搜索 · 12 个结果',
    tone: 'remote',
  }
);

assert.deepEqual(
  buildResultContext({
    favoritesMode: true,
    total: 3,
  }),
  {
    label: '收藏',
    title: '已收藏项目',
    detail: '共 3 个项目',
    tone: 'favorites',
  }
);

assert.deepEqual(
  buildResultContext({
    recommendMode: true,
    total: 0,
  }),
  {
    label: '为你推荐',
    title: 'AI 推荐列表',
    detail: '等待收藏偏好',
    tone: 'recommend',
  }
);

assert.equal(
  formatTranslationSummary({
    translation_pending: 2,
    translation_processing: 1,
    translation_retry: 3,
    translation_failed: 4,
    translation_done: 20,
  }),
  '待翻译 2  |  翻译中 1  |  待重试 3  |  失败 4  |  已完成 20'
);

assert.match(
  renderProjectMeta({
    stars: 12345,
    stars_gained: 80,
    language: 'TypeScript',
    translation_status: 'done',
  }),
  /12\.3k/
);
assert.match(
  renderProjectMeta({
    stars: 12345,
    stars_gained: 80,
    language: 'TypeScript',
    translation_status: 'done',
  }),
  /TypeScript/
);
assert.match(
  renderProjectMeta({
    stars: 12345,
    stars_gained: 80,
    language: 'TypeScript',
    translation_status: 'done',
  }),
  /已翻译/
);

// Sparkline slot only exists for persisted projects (GitHub search results have id 0)
assert.match(
  renderProjectMeta({ id: 7, stars: 1, stars_gained: 0, language: '', translation_status: '' }),
  /class="star-trend" data-project-id="7"/
);
assert.doesNotMatch(
  renderProjectMeta({ id: 0, stars: 1, stars_gained: 0, language: '', translation_status: '' }),
  /star-trend/
);

// ---- sparkline geometry ----
assert.deepEqual(buildSparklinePoints([]), []);
assert.deepEqual(buildSparklinePoints([{ date: '2026-09-01', stars: 5 }]), []);
assert.deepEqual(
  buildSparklinePoints([{ stars: 0 }, { stars: 10 }, { stars: 5 }], 20, 10, 0),
  [[0, 10], [10, 0], [20, 5]]
);
// flat series must not divide by zero and should draw a mid line
assert.deepEqual(
  buildSparklinePoints([{ stars: 3 }, { stars: 3 }], 10, 10, 0),
  [[0, 10], [10, 10]]
);
// non-numeric entries are skipped
assert.deepEqual(
  buildSparklinePoints([{ stars: 'x' }, { stars: 1 }, null, { stars: 2 }], 10, 10, 0),
  [[0, 10], [10, 0]]
);

assert.equal(sparklineTrend([]), 'flat');
assert.equal(sparklineTrend([{ stars: 1 }, { stars: 1 }]), 'flat');
assert.equal(sparklineTrend([{ stars: 1 }, { stars: 9 }]), 'up');
assert.equal(sparklineTrend([{ stars: 9 }, { stars: 1 }]), 'down');

assert.equal(renderSparkline([{ stars: 1 }]), '');
{
  const svg = renderSparkline([
    { date: '2026-09-01', stars: 1000 },
    { date: '2026-09-02', stars: 1500 },
    { date: '2026-09-03', stars: 2300 },
  ]);
  assert.match(svg, /^<svg class="sparkline sparkline-up"/);
  assert.match(svg, /<title>最近 3 次记录：\+1\.3k star<\/title>/);
  assert.match(svg, /<path d="M2 20 L36 [\d.]+ L70 2"/);
  assert.match(svg, /<circle cx="70" cy="2"/);
}
{
  const svg = renderSparkline([{ stars: 50 }, { stars: 40 }]);
  assert.match(svg, /sparkline-down/);
  assert.match(svg, /<title>最近 2 次记录：-10 star<\/title>/);
}
// title text is escaped, so hostile data cannot break out of the SVG
{
  const svg = renderSparkline([{ stars: 1 }, { stars: 2 }]);
  assert.doesNotMatch(svg, /<script/);
}
