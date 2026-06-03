# UI Polish And Maintainability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing GitHub Trending Viewer cleaner across desktop/mobile while reducing frontend state/rendering risk.

**Architecture:** Keep the current FastAPI + static frontend architecture and vanilla ES modules. Add small testable frontend helpers, use them from `app.js`, then polish CSS around existing DOM classes instead of replacing the app layout. Keep backend route shapes stable and only align response fields where UI rendering needs consistency.

**Tech Stack:** FastAPI, SQLite, vanilla JavaScript ES modules, CSS, Node test runner via plain `node`, pytest.

---

## File Structure

- Modify `static/js/app.js`: extract small exported helpers for mode state, empty-state labels, translation summary text, and project-card metadata HTML; use those helpers in current rendering paths.
- Modify `static/css/style.css`: improve header/status hierarchy, filters, project card layout, README behavior, modal/mobile sizing, and empty/error states.
- Modify `static/index.html`: only small copy/class hooks if needed; no structural rewrite.
- Modify `app/routers/favorites.py`: include translation status fields so favorite cards render consistently with normal project cards.
- Modify `tests/test_api.py`: add favorite API regression coverage for translation status fields.
- Create or modify `tests/test_frontend_helpers.mjs`: test exported frontend helpers without a browser DOM.
- Keep `static/js/sanitize.mjs` as the HTML/text safety boundary.

## Task 1: Add Focused Regression Tests

**Files:**
- Modify: `tests/test_api.py`
- Create: `tests/test_frontend_helpers.mjs`

- [ ] **Step 1: Add favorite API field regression test**

Append this test to `tests/test_api.py`:

```python
def test_favorites_api_returns_translation_state_fields(client):
    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status, translation_attempts) "
        "VALUES (?, ?, ?, ?)",
        ("favorite/repo", "https://github.com/favorite/repo", "failed", 3),
    )
    project_id = conn.execute(
        "SELECT id FROM projects WHERE repo_full_name = ?",
        ("favorite/repo",),
    ).fetchone()["id"]
    conn.execute("INSERT INTO favorites (project_id) VALUES (?)", (project_id,))
    conn.commit()
    conn.close()

    resp = client.get("/api/favorites")
    assert resp.status_code == 200

    item = resp.json()["items"][0]
    assert item["translation_status"] == "failed"
    assert item["translation_attempts"] == 3
```

- [ ] **Step 2: Create frontend helper tests**

Create `tests/test_frontend_helpers.mjs`:

```javascript
import assert from 'node:assert/strict';

import {
  buildModeState,
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
```

- [ ] **Step 3: Run tests to verify expected failures**

Run:

```powershell
python -m pytest tests/test_api.py::test_favorites_api_returns_translation_state_fields -q
node tests/test_frontend_helpers.mjs
```

Expected:
- pytest fails because favorites items do not include `translation_status` and `translation_attempts`.
- node fails because `app.js` does not export the helper functions yet, or because importing `app.js` touches `document` during module load.

- [ ] **Step 4: Commit tests**

Run:

```powershell
git add tests/test_api.py tests/test_frontend_helpers.mjs
git commit -m "test: cover ui helper and favorites metadata behavior"
```

## Task 2: Add Testable Frontend Helpers And API Consistency

**Files:**
- Modify: `static/js/app.js`
- Modify: `app/routers/favorites.py`
- Test: `tests/test_api.py`
- Test: `tests/test_frontend_helpers.mjs`

- [ ] **Step 1: Export small helpers from `static/js/app.js`**

Add these functions near the utilities section in `static/js/app.js` and keep `formatStars`, `formatCount`, and `translationStatusLabel` available to them:

```javascript
export function buildModeState(category) {
    if (category === 'favorites') {
        return {
            category: 'ai',
            favoritesMode: true,
            recommendMode: false,
            githubSearch: false,
            page: 1,
        };
    }
    if (category === 'recommend') {
        return {
            category: 'ai',
            favoritesMode: false,
            recommendMode: true,
            githubSearch: false,
            page: 1,
        };
    }
    return {
        category,
        favoritesMode: false,
        recommendMode: false,
        githubSearch: false,
        page: 1,
    };
}

export function emptyStateMessage({ favoritesMode = false, recommendMode = false, githubSearch = false, reason = '' } = {}) {
    if (favoritesMode) return '还没有收藏的项目';
    if (recommendMode && reason === 'no_favorites') return '收藏一些项目后，AI 会为你推荐相似项目';
    if (recommendMode && reason === 'error') return '加载推荐失败，请重试';
    if (recommendMode) return '暂无推荐，试试多收藏一些项目';
    if (githubSearch && reason === 'error') return 'GitHub 搜索失败，请检查网络或稍后重试';
    if (githubSearch) return 'GitHub 没有返回匹配项目';
    return '暂无项目数据';
}

export function formatTranslationSummary(status) {
    return [
        `待翻译 ${status.translation_pending || 0}`,
        `翻译中 ${status.translation_processing || 0}`,
        `待重试 ${status.translation_retry || 0}`,
        `失败 ${status.translation_failed || 0}`,
        `已完成 ${status.translation_done || 0}`,
    ].join('  |  ');
}

export function renderProjectMeta(project) {
    const gainedHtml = project.stars_gained > 0
        ? `<span class="star-gained">+${formatStars(project.stars_gained)}</span>` : '';
    const langHtml = project.language
        ? `<span class="card-language">${escapeHtml(project.language)}</span>` : '';
    return `
        <div class="card-stats">
            <span class="star-count">⭐ ${formatStars(project.stars)}</span>
            ${gainedHtml}
            ${langHtml}
            ${renderTranslationBadge(project.translation_status)}
        </div>
    `;
}
```

- [ ] **Step 2: Guard browser-only startup in `static/js/app.js`**

Replace the unconditional startup:

```javascript
document.addEventListener('DOMContentLoaded', init);
```

with:

```javascript
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', init);
}
```

- [ ] **Step 3: Use the helpers in existing render paths**

In `updateTranslationSummary`, replace the local `parts` construction with:

```javascript
detail.textContent = formatTranslationSummary(status);
```

In `renderCard`, replace direct `gainedHtml`, `langHtml`, `translationBadge`, and `<div class="card-stats">...</div>` construction with:

```javascript
const metaHtml = renderProjectMeta(p);
```

and inside `.card-actions`:

```html
${metaHtml}
```

In category tab click handling, use:

```javascript
const nextMode = buildModeState(cat);
Object.assign(state, nextMode);
if (state.recommendMode) {
    loadRecommendations();
} else {
    loadProjects();
}
```

- [ ] **Step 4: Fix favorites API metadata fields**

In `app/routers/favorites.py`, add these fields to each favorite item:

```python
"translation_status": r["translation_status"] if "translation_status" in r.keys() else "",
"translation_attempts": r["translation_attempts"] if "translation_attempts" in r.keys() else 0,
```

Place them next to `readme_summary_zh` so favorite cards match normal project cards.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
python -m pytest tests/test_api.py::test_favorites_api_returns_translation_state_fields -q
node tests/test_frontend_helpers.mjs
node --check static/js/app.js
```

Expected: all pass.

- [ ] **Step 6: Commit helper/API changes**

Run:

```powershell
git add static/js/app.js app/routers/favorites.py tests/test_api.py tests/test_frontend_helpers.mjs
git commit -m "refactor: add frontend rendering helpers"
```

## Task 3: Polish Cards, Status Area, And Responsive Layout

**Files:**
- Modify: `static/css/style.css`
- Modify: `static/js/app.js`
- Optional modify: `static/index.html`
- Test: `tests/test_frontend_helpers.mjs`

- [ ] **Step 1: Update README default behavior**

In `renderCard`, change README content from expanded by default:

```html
<button class="readme-toggle">
    📖 README 摘要 <span>▲</span>
</button>
<div class="readme-content expanded">
```

to collapsed with a clearer action:

```html
<button class="readme-toggle" type="button">
    <span class="readme-toggle-label">README 摘要</span><span class="readme-toggle-icon">▼</span>
</button>
<div class="readme-content">
```

Update `toggleReadme` to use `.readme-toggle-icon`:

```javascript
function toggleReadme(btn) {
    const content = btn.nextElementSibling;
    const arrow = btn.querySelector('.readme-toggle-icon');
    content.classList.toggle('expanded');
    arrow.textContent = content.classList.contains('expanded') ? '▲' : '▼';
}
```

- [ ] **Step 2: Add CSS for clearer card hierarchy**

In `static/css/style.css`, adjust these blocks:

```css
.project-card {
    padding: 18px 20px;
}

.card-header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
}

.card-actions {
    display: grid;
    grid-template-columns: auto auto;
    align-items: center;
    justify-items: end;
}

.card-stats {
    grid-column: 1 / -1;
    justify-content: flex-end;
    max-width: 360px;
    flex-wrap: wrap;
}

.card-description {
    max-width: 820px;
}
```

Keep existing colors and transitions.

- [ ] **Step 3: Add CSS for compact status and filters**

Add or adjust:

```css
.overview-card {
    min-height: 86px;
}

.translation-summary,
.health-summary {
    min-width: 0;
}

.translation-summary-detail,
#translation-summary-detail,
#health-summary-detail {
    overflow-wrap: anywhere;
}

.filters {
    align-items: stretch;
}

.filter-group select,
.filter-group input,
.btn {
    min-height: 38px;
}
```

- [ ] **Step 4: Strengthen mobile layout**

Inside the existing `@media (max-width: 640px)` block, add:

```css
.header-right {
    width: 100%;
    justify-content: space-between;
}

.header .btn {
    flex: 1;
    justify-content: center;
}

.card-header {
    grid-template-columns: 1fr;
}

.card-actions {
    width: 100%;
    grid-template-columns: auto auto 1fr;
    justify-items: start;
}

.card-stats {
    grid-column: 1 / -1;
    justify-content: flex-start;
    max-width: 100%;
}

.chat-modal-content {
    width: calc(100% - 20px);
    height: min(78vh, 620px);
}

.modal-content {
    padding: 22px;
}
```

- [ ] **Step 5: Run syntax and helper tests**

Run:

```powershell
node --check static/js/app.js
node tests/test_frontend_helpers.mjs
```

Expected: both pass.

- [ ] **Step 6: Commit UI polish**

Run:

```powershell
git add static/css/style.css static/js/app.js static/index.html tests/test_frontend_helpers.mjs
git commit -m "style: polish project cards and responsive layout"
```

## Task 4: Verification And Final Commit Hygiene

**Files:**
- Modify only if tests reveal a defect in touched files.

- [ ] **Step 1: Run Python test suite**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend tests and syntax checks**

Run:

```powershell
node tests/test_frontend_security.mjs
node tests/test_frontend_helpers.mjs
node --check static/js/app.js
```

Expected: all commands pass.

- [ ] **Step 3: Start local app for browser verification**

If Docker is available and configured, run:

```powershell
docker compose up -d
```

Then open `http://localhost:8098` and verify:
- desktop layout has no overlapping header/status/filter/card content
- mobile width around 390 px has no horizontal overflow
- category switch still loads projects
- favorites tab still renders translation badges
- README toggle expands/collapses
- theme toggle works
- chat modal opens and closes

If Docker or configuration is unavailable, skip browser verification and record the exact reason.

- [ ] **Step 4: Inspect staged and unstaged changes**

Run:

```powershell
git status --short
git diff --stat
git diff --cached --stat
```

Expected:
- Only intended files are staged for each commit.
- Existing unrelated dirty files remain untouched or unstaged.

- [ ] **Step 5: Final implementation commit if needed**

If any fixes were made during verification, commit only those touched files:

```powershell
git add <specific-files>
git commit -m "fix: stabilize ui polish regressions"
```

## Self-Review

- Spec coverage: UI hierarchy, responsive behavior, cards, modals, empty/error states, frontend helper structure, API consistency, and verification are covered by Tasks 1-4.
- Placeholder scan: no incomplete placeholder phrases or unspecified implementation steps are present.
- Type consistency: helper names are consistent across tests and implementation steps: `buildModeState`, `emptyStateMessage`, `formatTranslationSummary`, and `renderProjectMeta`.
