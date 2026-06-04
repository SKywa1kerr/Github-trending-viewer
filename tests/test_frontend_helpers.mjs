import assert from 'node:assert/strict';

import {
  buildModeState,
  buildResultContext,
  emptyStateMessage,
  formatTranslationSummary,
  renderProjectMeta,
} from '../static/js/app.js';

assert.deepEqual(buildModeState('favorites'), {
  category: 'ai',
  favoritesMode: true,
  recommendMode: false,
  githubSearch: false,
  page: 1,
});

assert.deepEqual(buildModeState('recommend'), {
  category: 'ai',
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
