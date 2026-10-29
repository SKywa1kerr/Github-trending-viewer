import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import {
  githubOwnerAvatarUrl, hasDiscoverySpotlight, hydrateProjectAvatars,
  normalizeProjectCategory, projectIdentity, renderProjectCardContents,
} from '../static/js/cards.mjs';

const project = {
  id: 7, repo_full_name: 'acme/OpenTools', repo_url: 'https://example.com/acme/OpenTools',
  description_zh: '一个本地优先的开发工具。',
  readme_summary_zh: '1. 支持离线使用，数据留在设备上。\n2. 提供命令行与桌面应用。\n3. 可以扩展自己的工作流。',
  topics: ['local-first', 'developer-tools'], category: 'devtools',
  stars: 18000, stars_gained: 200, language: 'TypeScript', translation_status: 'done',
  is_favorited: true, is_new: true, last_updated: '2026-09-09T12:00:00Z',
};

test('project identity keeps a stable, local monogram for the avatar fallback', () => {
  assert.deepEqual(projectIdentity('acme/OpenTools'), {owner: 'acme', name: 'OpenTools', monogram: 'OT'});
  assert.deepEqual(projectIdentity('acme/deep-live-cam'), {owner: 'acme', name: 'deep-live-cam', monogram: 'DL'});
  assert.equal(projectIdentity('acme/ECC').monogram, 'EC');
  assert.equal(projectIdentity('中文/工具集').monogram, '工具');
  assert.equal(projectIdentity().name, '未命名项目');
});

test('only the unfiltered discovery context has a spotlight', () => {
  assert.equal(hasDiscoverySpotlight(), true);
  for (const state of [
    {category: 'ai'}, {query: 'offline'}, {language: 'Python'}, {minStars: 1000},
    {sort: 'stars'}, {sort: 'updated'}, {favoritesMode: true}, {recommendMode: true}, {githubSearch: true},
  ]) assert.equal(hasDiscoverySpotlight(state), false, JSON.stringify(state));
});

test('ordinary projects retain headings, metadata and every existing action', () => {
  const html = renderProjectCardContents(project);
  assert.match(html, /<h2 id="project-title-acme%2FOpenTools">/);
  assert.match(html, /data-action="favorite" aria-pressed="true"/);
  assert.match(html, /data-action="readme" aria-expanded="false"/);
  assert.match(html, /data-action="chat"/);
  assert.match(html, /data-action="reader" aria-haspopup="dialog" aria-controls="reader-modal"/);
  assert.match(html, /data-topic="local-first"/);
  assert.match(html, /class="star-trend" data-project-id="7"/);
  assert.match(html, /18k/);
  assert.match(html, /TypeScript/);
  assert.match(html, /class="badge-new">新收录/);
  assert.doesNotMatch(html, /<aside/);
  assert.match(html, /class="repo-category">开发工具<\/span>/);
  assert.match(html, /class="project-monogram">OT<\/span>/);
  assert.match(html, /class="project-avatar"/);
});

test('featured projects show two real README highlights, keeping the full summary', () => {
  const html = renderProjectCardContents(project, {featured: true});
  assert.match(html, /class="project-highlights"/);
  const aside = html.match(/<aside[\s\S]*?<\/aside>/)[0];
  assert.equal([...aside.matchAll(/<li>/g)].length, 2);
  assert.match(aside, /支持离线使用，数据留在设备上。/);
  assert.match(aside, /提供命令行与桌面应用。/);
  assert.doesNotMatch(aside, /可以扩展自己的工作流/);
  assert.match(html, /可以扩展自己的工作流/);
});

test('missing README content leaves an honest disabled summary action', () => {
  const html = renderProjectCardContents({...project, readme_summary_zh: ''}, {featured: true, expanded: true});
  assert.doesNotMatch(html, /<aside/);
  assert.match(html, /aria-expanded="false"[^>]*disabled/);
  assert.match(html, /暂无中文摘要/);
  assert.doesNotMatch(html, /readme-content expanded/);
});

test('expanded state remains consistent with its button label and controlled region', () => {
  const html = renderProjectCardContents(project, {expanded: true});
  assert.match(html, /aria-expanded="true" aria-controls="readme-acme%2FOpenTools"/);
  assert.match(html, /class="readme-label">收起摘要/);
  assert.match(html, /id="readme-acme%2FOpenTools" class="readme-content expanded"/);
});

test('remote project strings cannot become markup, handlers, classes or unsafe links', () => {
  const hostile = {
    ...project, repo_full_name: 'acme/<script>alert(1)</script>', repo_url: 'javascript:alert(1)',
    description_zh: '<img src=x onerror="alert(1)">', topics: ['" onclick="alert(1)'],
    readme_summary_zh: '<script>alert(1)</script>\n<img src=x>',
    recommendation_reason: '<iframe src=javascript:alert(1)>', category: '" onmouseover="alert(1)',
  };
  for (const featured of [false, true]) {
    const html = renderProjectCardContents(hostile, {featured});
    const avatars = [...html.matchAll(/<img\b[^>]*>/g)].map(match => match[0]);
    assert.equal(avatars.length, 1, 'only the generated owner avatar may be an image');
    assert.match(avatars[0], /^<img class="project-avatar" data-avatar-src="https:\/\/github\.com\/acme\.png\?size=128"/);
    assert.doesNotMatch(avatars[0], /\son\w+=|\ssrcset=|\ssrc=/);
    assert.doesNotMatch(html.replace(avatars[0], ''), /<script|<img|<iframe|href="javascript:|onclick="alert|onmouseover="alert/);
    assert.match(html, /href="#"/);
    assert.match(html, /data-tone="other"/);
    assert.match(html, /&lt;script&gt;/);
    assert.match(html, /rel="noopener noreferrer"/);
  }
});

test('category colors and visible labels only use known project categories', () => {
  const labels = { ai: '人工智能', tools: '实用工具', devtools: '开发工具', other: '更多领域' };
  for (const [category, label] of Object.entries(labels)) {
    assert.equal(normalizeProjectCategory(category), category);
    const html = renderProjectCardContents({...project, category});
    assert.ok(html.includes('data-tone="' + category + '"'));
    assert.ok(html.includes('class="repo-category">' + label + '</span>'));
  }
  for (const category of [undefined, null, '', 'all', 'favorites', 'AI', '__proto__', 'constructor', {}, ['ai']]) {
    assert.equal(normalizeProjectCategory(category), 'other');
    assert.match(renderProjectCardContents({...project, category}), /class="repo-category">更多领域<\/span>/);
  }
});

test('avatar URLs accept only valid owner names on a fixed HTTPS host', () => {
  for (const owner of ['a', 'ACME', 'open-source', 'a'.repeat(39)]) {
    const url = new URL(githubOwnerAvatarUrl(owner));
    assert.equal(url.origin, 'https://github.com');
    assert.equal(url.pathname, '/' + owner.toLowerCase() + '.png');
    assert.equal(url.search, '?size=128');
    assert.equal(url.username, '');
    assert.equal(url.password, '');
  }
  for (const owner of [undefined, null, 5, {}, '', '-acme', 'acme-', 'ac--me', 'a'.repeat(40),
    '中文', 'ac_me', ' acme', 'acme ', 'acme\n', 'acme\t', 'acme/repo', 'acme?x=1', 'acme#x',
    'evil.example', 'acme@evil.example', 'acme%2f..', '\\evil', '"><img src=x>']) {
    assert.equal(githubOwnerAvatarUrl(owner), '', JSON.stringify(owner));
  }
});

test('avatars are decorative, fixed-size and lazy outside the spotlight', () => {
  for (const featured of [false, true]) {
    const html = renderProjectCardContents(project, {featured});
    const avatar = html.match(/<img\b[^>]*>/)[0];
    assert.match(html, /class="project-mark"[^>]*aria-hidden="true"/);
    assert.match(avatar, /alt="" width="50" height="50"/);
    assert.ok(avatar.includes('loading="' + (featured ? 'eager' : 'lazy') + '"'));
    assert.match(avatar, /decoding="async" referrerpolicy="no-referrer"/);
    assert.doesNotMatch(avatar, /\ssrc=|\son\w+=|example\.com/);
    assert.match(avatar, /data-avatar-src="https:\/\/github\.com\/acme\.png\?size=128"/);
  }
  for (const repo_full_name of ['OpenTools', '中文/工具集', 'evil.example/Repo', 'acme\n/Repo']) {
    const html = renderProjectCardContents({...project, repo_full_name});
    assert.doesNotMatch(html, /<img\b/);
    assert.match(html, /class="project-monogram"/);
  }
});

// A small image double exercises load/error races without a browser or network requests.
function avatarFixture(owner, {cachedWidth, synchronousLoad = false} = {}) {
  const listeners = new Map();
  const classes = new Set();
  const requests = [];
  const avatar = {
    dataset: {avatarSrc: githubOwnerAvatarUrl(owner)},
    parentElement: {classList: {add: value => classes.add(value), remove: value => classes.delete(value)}},
    removed: false, complete: false, naturalWidth: 0,
    addEventListener: (type, listener) => listeners.set(type, listener),
    removeEventListener(type, listener) { if (listeners.get(type) === listener) listeners.delete(type); },
    remove() { this.removed = true; },
    set src(value) {
      requests.push(value);
      this.complete = cachedWidth !== undefined;
      this.naturalWidth = cachedWidth || 0;
      if (synchronousLoad) {
        this.complete = true;
        this.naturalWidth = 128;
        listeners.get('load')?.();
      }
    },
  };
  const root = {querySelectorAll(selector) {
    assert.equal(selector, '.project-avatar[data-avatar-src]');
    return avatar.removed || !Object.hasOwn(avatar.dataset, 'avatarSrc') ? [] : [avatar];
  }};
  return {root, avatar, classes, requests, listeners, emit(type, width = 0) {
    avatar.complete = true;
    avatar.naturalWidth = width;
    listeners.get(type)?.();
  }};
}

test('pending avatars keep their fallback, hydrate once and reveal only after loading', () => {
  const fixture = avatarFixture('test-pending');
  hydrateProjectAvatars(fixture.root);
  hydrateProjectAvatars(fixture.root);
  assert.equal(fixture.requests.length, 1);
  assert.equal(fixture.classes.has('has-avatar'), false);
  assert.equal(fixture.avatar.removed, false);
  fixture.emit('load', 128);
  assert.equal(fixture.classes.has('has-avatar'), true);
  assert.equal(fixture.listeners.size, 0);
});

test('cached and synchronously loaded avatars do not miss their load event', () => {
  for (const [owner, options] of [
    ['test-cached', {cachedWidth: 128}], ['test-synchronous', {synchronousLoad: true}],
  ]) {
    const fixture = avatarFixture(owner, options);
    hydrateProjectAvatars(fixture.root);
    assert.equal(fixture.classes.has('has-avatar'), true);
    assert.equal(fixture.avatar.removed, false);
    assert.equal(fixture.listeners.size, 0);
  }
});

test('failed avatars are removed and do not request the same owner again this session', () => {
  const fixture = avatarFixture('test-failed');
  hydrateProjectAvatars(fixture.root);
  fixture.emit('error');
  assert.equal(fixture.classes.has('has-avatar'), false);
  assert.equal(fixture.avatar.removed, true);
  assert.equal(fixture.listeners.size, 0);
  const repeat = avatarFixture('TEST-FAILED');
  hydrateProjectAvatars(repeat.root);
  assert.equal(repeat.requests.length, 0);
  assert.equal(repeat.avatar.removed, true);
  assert.equal(repeat.classes.has('has-avatar'), false);
});

test('cached broken images and empty decoded images leave the monogram visible', () => {
  const cached = avatarFixture('test-broken-cache', {cachedWidth: 0});
  hydrateProjectAvatars(cached.root);
  const empty = avatarFixture('test-empty-image');
  hydrateProjectAvatars(empty.root);
  empty.emit('load', 0);
  for (const fixture of [cached, empty]) {
    assert.equal(fixture.avatar.removed, true);
    assert.equal(fixture.classes.has('has-avatar'), false);
    assert.equal(fixture.listeners.size, 0);
  }
});

test('cards receive their normalized category and avatar hydration in the application', () => {
  const script = readFileSync(new URL('../static/js/app.js', import.meta.url), 'utf8');
  assert.match(script, /card\.dataset\.category = normalizeProjectCategory\(project\.category\)/);
  assert.match(script, /card\.innerHTML = renderProjectCardContents\([\s\S]*?hydrateProjectAvatars\(card\);\s*return card;/);
});

test('the restructured shell has unique IDs and every literal script target', () => {
  const html = readFileSync(new URL('../static/index.html', import.meta.url), 'utf8');
  const script = readFileSync(new URL('../static/js/app.js', import.meta.url), 'utf8');
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  const known = new Set(ids);
  assert.equal(known.size, ids.length, 'HTML IDs must be unique');
  for (const [, id] of script.matchAll(/\$\('([^']+)'\)/g)) assert.ok(known.has(id), 'Missing #' + id);
  for (const id of ['site-header', 'navigation', 'category-navigation', 'filter-panel', 'filter-count']) assert.ok(known.has(id));
  assert.match(html, /<details id="filter-panel"/);
  assert.match(html, /aria-controls="navigation"/);
  assert.doesNotMatch(script, /querySelector\('\.sidebar'\)/);
  assert.doesNotMatch(html, /class="sidebar"|fonts\.googleapis/);
  for (const name of ['bookmark', 'sparkles', 'chevron', 'star']) assert.ok(known.has('icon-' + name));
});

test('the shell identifies the product with an inert local branch mark', () => {
  const html = readFileSync(new URL('../static/index.html', import.meta.url), 'utf8');
  const signatures = html.match(/<svg class="brand-mark"[\s\S]*?<\/svg>/g) || [];
  assert.equal(signatures.length, 1);
  const signature = signatures[0];
  assert.match(signature, /aria-hidden="true"/);
  assert.doesNotMatch(signature, /<script|<image|<foreignObject|<animate|<text|\b(?:href|src|tabindex|onclick)=/i);
  assert.match(html, /GitHub 开源项目库/);
  assert.match(html, /class="brand" aria-label="GitHub Trending 首页"/);
});

test('local code mounts are read-only while the existing data mount is preserved', () => {
  const compose = readFileSync(new URL('../docker-compose.yml', import.meta.url), 'utf8');
  assert.match(compose, /- \.\/app:\/app\/app:ro/);
  assert.match(compose, /- \.\/static:\/app\/static:ro/);
  assert.match(compose, /- \.\/data:\/app\/data\r?\n/);
  assert.doesNotMatch(compose, /privileged:|network_mode:\s*host|docker\.sock/);
});
