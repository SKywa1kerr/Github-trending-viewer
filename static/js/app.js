import { escapeHtml, formatChatText, safeExternalUrl } from './sanitize.mjs?v=75';
import { hasDiscoverySpotlight, hydrateProjectAvatars, normalizeProjectCategory, renderProjectCardContents } from './cards.mjs?v=75';
import { renderProjectReading } from './reader.mjs?v=75';
import { bindMotionFeedback, showDialogMotion, closeDialogMotion, showNavigationMotion } from './motion.mjs?v=75';
import {
    categoryNames, icon, formatStars, buildModeState, buildResultContext,
    formatTranslationSummary, renderSparkline, timeAgo, readmeHighlights,
    parseProjectDate, filterProjectItems, createRequestGate, streamChatText,
    readViewState, buildViewSearch,
} from './library.mjs?v=75';

export {
    buildModeState, buildResultContext, emptyStateMessage, formatTranslationSummary,
    renderProjectMeta, buildSparklinePoints, sparklineTrend, renderSparkline,
} from './library.mjs?v=75';

function preference(key, fallback, allowed) {
    try {
        const value = localStorage.getItem(key);
        return allowed.includes(value) ? value : fallback;
    } catch { return fallback; }
}

function savePreference(key, value) {
    try { localStorage.setItem(key, value); } catch { /* Storage may be disabled. */ }
}

const state = {
    ...buildModeState('all'),
    language: '', sort: 'score', query: '', minStars: 0, pageSize: 20,
    total: 0, loading: false, items: [], status: null, health: null,
    favoriteIds: new Set(), languages: [], remoteQuery: '', remoteItems: null,
    recommendations: null, recommendationMessage: '', hadError: false,
    view: preference('project-view', 'grid', ['grid', 'list']),
    theme: preference('theme', 'dark', ['system', 'light', 'dark']),
    accent: preference('accent', 'indigo', ['vermilion', 'indigo', 'teal', 'amber', 'rose']),
};
const requests = createRequestGate();
const expandedProjects = new Set();
const sparklineCache = new Map();
const chat = { repo: '', history: [], controller: null, generation: 0 };
const reader = { project: null, size: preference('reader-size', 'standard', ['standard', 'large']) };
let searchTimer;
let statusBusy = false;
let pollingTimer;
let emptyAction = () => {};
const $ = id => document.getElementById(id);

async function api(path, options = {}) {
    const response = await fetch('/api' + path, {
        ...options,
        headers: { 'Content-Type': 'application/json', ...options.headers },
    });
    if (!response.ok) {
        const error = new Error('Request failed: ' + response.status);
        error.status = response.status;
        throw error;
    }
    return response.json();
}

async function init() {
    applyTheme();
    applyView();
    $('dateline').textContent = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
    bindEvents();
    applyViewFromAddress();
    updateModeUI();
    $('loading-screen').classList.add('hidden');
    $('main-content').classList.remove('hidden');
    bindMotionFeedback();
    if (/Mac|iPhone|iPad/.test(navigator.platform)) $('search-shortcut').textContent = '⌘ K';
    await Promise.allSettled([loadProjects(), checkStatus(), checkHealth(), loadNavigation(), loadLanguages()]);
    pollingTimer = setInterval(() => { if (!document.hidden) checkStatus(); }, 5000);
    window.addEventListener('pagehide', () => {
        clearInterval(pollingTimer);
        requests.cancel();
        chat.controller?.abort();
    }, { once: true });
}

// The address is the source of truth on load and on back/forward; every list load writes it back.
function applyViewFromAddress() {
    const view = readViewState(location.search);
    Object.assign(state, buildModeState(view.category), {
        githubSearch: view.githubSearch, query: view.query, language: view.language,
        minStars: view.minStars, sort: view.sort, items: [], total: 0,
    });
    $('search-input').value = view.query;
}

function syncAddress(push = false) {
    const search = buildViewSearch({ ...state, category: currentCategory() });
    if (search === location.search) return;
    try { history[push ? 'pushState' : 'replaceState'](null, '', location.pathname + search); } catch { /* History may be unavailable. */ }
}

function currentCategory() {
    return state.favoritesMode ? 'favorites' : state.recommendMode ? 'recommend' : state.category;
}

function updateModeUI() {
    const category = currentCategory();
    const title = state.githubSearch ? 'GitHub 搜索' : categoryNames[category];
    const descriptions = {
        all: '值得读、值得用的开源项目。',
        ai: '探索模型、智能体与机器学习工具。',
        tools: '让日常工作更轻松的开源工具。',
        devtools: '框架、命令行与开发基础设施。',
        other: '发现更多领域的热门项目。',
        favorites: '值得继续探索的项目，都在这里。',
        recommend: '根据你的收藏，发现可能喜欢的项目。',
    };
    $('page-title').textContent = title;
    $('workspace-location-label').textContent = title;
    // Each phrase wraps as a unit, so the large headline never breaks in the middle of one.
    const subtitle = state.githubSearch ? '搜索 GitHub 上的公开项目。' : descriptions[category];
    $('page-subtitle').replaceChildren(...(subtitle.match(/[^、，。]+[、，。]?/g) || [subtitle]).map(phrase => {
        const part = document.createElement('span');
        part.className = 'phrase';
        part.textContent = phrase;
        return part;
    }));
    document.title = title + ' · GitHub Trending';
    const discovery = !state.favoritesMode && !state.recommendMode && !state.githubSearch;
    $('category-navigation').classList.toggle('hidden', !discovery);
    $('category-group').classList.toggle('hidden', !discovery);
    document.querySelectorAll('.tab[data-category]').forEach(tab => {
        const active = !state.githubSearch && tab.dataset.category === category;
        tab.classList.toggle('active', active);
        if (active) tab.setAttribute('aria-current', 'page');
        else tab.removeAttribute('aria-current');
    });
    document.querySelectorAll('[data-source]').forEach(button => {
        const local = button.dataset.source === 'local';
        button.setAttribute('aria-pressed', String(local !== state.githubSearch));
        if (local) button.textContent = state.favoritesMode ? '收藏' : state.recommendMode ? '推荐' : '项目库';
    });
    $('search-input').placeholder = state.githubSearch
        ? '搜索 GitHub，例如 topic:llm language:Python'
        : state.favoritesMode ? '搜索收藏的项目、介绍或标签'
        : state.recommendMode ? '搜索推荐的项目'
        : '搜索项目、中文介绍或标签';
    const favoriteOption = $('filter-sort').querySelector('[value="favorited"]');
    favoriteOption.hidden = !state.favoritesMode || state.githubSearch;
    favoriteOption.disabled = favoriteOption.hidden;
    if (state.sort === 'favorited' && favoriteOption.hidden) state.sort = 'score';
    const newestOption = $('filter-sort').querySelector('[value="newest"]');
    newestOption.disabled = state.githubSearch;
    if (state.githubSearch && state.sort === 'newest') state.sort = 'score';
    $('filter-language').value = state.language;
    $('filter-sort').value = state.sort;
    $('filter-stars').value = String(state.minStars);
    $('btn-shuffle-rec').classList.toggle('hidden', !state.recommendMode || state.githubSearch);
    updateCompositionFocus();
    updateFilterUI();
}

function updateFilterUI() {
    $('filter-sort').value = state.sort;
    document.querySelectorAll('[data-sort]').forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.sort === state.sort));
        button.disabled = state.githubSearch && button.dataset.sort === 'newest';
    });
    $('btn-clear-search').classList.toggle('hidden', !$('search-input').value);
    $('search-shortcut').classList.toggle('hidden', Boolean($('search-input').value));
    const filters = [];
    if (state.query) filters.push(['query', '搜索：' + state.query]);
    if (state.language) filters.push(['language', state.language]);
    if (state.minStars) filters.push(['minStars', formatStars(state.minStars) + '+ Star']);
    $('btn-clear-filters').classList.toggle('hidden', !filters.length);
    const filterCount = Number(Boolean(state.language)) + Number(Boolean(state.minStars));
    $('filter-count').textContent = String(filterCount);
    $('filter-count').classList.toggle('hidden', !filterCount);
    const chips = $('active-filters');
    chips.replaceChildren();
    chips.classList.toggle('hidden', !filters.length);
    filters.forEach(([key, label]) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'filter-chip';
        button.dataset.filter = key;
        button.setAttribute('aria-label', '移除筛选 ' + label);
        button.innerHTML = '<span>' + escapeHtml(label) + '</span>' + icon('close');
        chips.append(button);
    });
}

function updateResultUI() {
    const context = buildResultContext(state);
    $('result-context-label').textContent = context.label;
    $('result-context-title').textContent = state.githubSearch
        ? (state.query ? '“' + state.query + '”' : '搜索 GitHub')
        : state.favoritesMode ? '收藏的项目'
        : state.recommendMode ? '为你精选'
        : state.query || state.language || state.minStars ? '筛选结果'
        : state.category === 'all' ? '全部项目' : categoryNames[state.category];
    $('result-context-detail').textContent = state.loading ? '正在加载…'
        : state.githubSearch && !state.query ? '输入关键词后搜索'
        : state.total.toLocaleString('zh-CN') + (state.githubSearch ? ' 个结果' : ' 个项目');
    $('result-context').dataset.tone = context.tone;
    const orderNotes = { score: '按综合评分排序', stars: '按 Star 总数排序',
        stars_gained: '按最近抓取的 Star 增长排序', updated: '按仓库更新时间排序',
        newest: '按项目库收录时间排序', favorited: '按收藏时间排序' };
    $('result-order-note').textContent = orderNotes[state.sort] || '';
    $('result-order-note').classList.toggle('hidden', state.recommendMode || state.githubSearch);
    updateFilterUI();
}

function setLoading(loading) {
    state.loading = loading;
    $('project-list').setAttribute('aria-busy', String(loading));
    $('btn-load-more').disabled = loading;
    $('btn-load-more').textContent = loading ? '正在加载…' : '加载更多';
    $('btn-shuffle-rec').disabled = loading;
    updateResultUI();
}

function renderSkeletons() {
    const lead = hasDiscoverySpotlight(state);
    $('project-list').innerHTML = Array.from({ length: lead ? 7 : 6 }, (_, index) =>
        '<div class="project-card skeleton-card' + (lead && index === 0 ? ' skeleton-lead' : '') + '" aria-hidden="true">' +
        '<div class="skeleton-head"><span class="skeleton-mark"></span><span class="skeleton-line"></span></div>' +
        '<div class="skeleton-line"></div>'.repeat(4) + '</div>').join('');
}

async function loadProjects(append = false, { force = false } = {}) {
    if (append && (state.loading || state.recommendMode || state.githubSearch || state.items.length >= state.total)) return;
    const request = requests.start();
    const snapshot = { ...state };
    const page = append ? state.page + 1 : 1;
    if (!append) syncAddress();
    setLoading(true);
    state.hadError = false;
    $('empty-state').classList.add('hidden');
    if (!append && !state.items.length) renderSkeletons();
    try {
        let data;
        if (snapshot.githubSearch) {
            if (!snapshot.query) {
                data = { items: [], total: 0, message: 'search_prompt' };
            } else {
                let items = state.remoteItems;
                if (force || !items || state.remoteQuery !== snapshot.query) {
                    const response = await api('/search/github?' + new URLSearchParams({ q: snapshot.query }), { signal: request.signal });
                    if (!request.isCurrent()) return;
                    state.remoteItems = items = response.items || [];
                    state.remoteQuery = snapshot.query;
                    updateLanguageOptions();
                }
                const filtered = filterProjectItems(items, { ...snapshot, query: '' });
                data = { items: filtered, total: filtered.length };
            }
        } else if (snapshot.recommendMode) {
            let items = state.recommendations;
            if (force || !items) {
                if (!state.items.length) $('project-list').innerHTML = '<div class="list-message"><span class="spinner"></span><span>正在根据你的收藏生成推荐</span></div>';
                const response = await api('/recommendations' + (force ? '?force=true' : ''), { signal: request.signal });
                if (!request.isCurrent()) return;
                state.recommendations = items = response.items || [];
                state.recommendationMessage = response.message || '';
            }
            const filtered = filterProjectItems(items, snapshot);
            data = { items: filtered, total: filtered.length, message: state.recommendationMessage };
        } else {
            const params = new URLSearchParams({ sort: snapshot.sort, page, page_size: snapshot.pageSize });
            if (!snapshot.favoritesMode && snapshot.category !== 'all') params.set('category', snapshot.category);
            if (snapshot.language) params.set('language', snapshot.language);
            if (snapshot.query) params.set('q', snapshot.query);
            if (snapshot.minStars) params.set('min_stars', snapshot.minStars);
            data = await api((snapshot.favoritesMode ? '/favorites?' : '/projects?') + params, { signal: request.signal });
        }
        if (!request.isCurrent()) return;
        state.page = page;
        state.total = Number(data.total || 0);
        state.items = append ? [...state.items, ...data.items] : data.items;
        renderCards(data.items, append);
        if (!state.items.length) showEmpty(data.message);
    } catch (error) {
        if (!request.isCurrent() || error.name === 'AbortError') return;
        state.hadError = true;
        if (append) {
            showToast('加载更多失败，请重试。', 'error');
        } else {
            state.items = [];
            state.total = 0;
            $('project-list').replaceChildren();
            showEmpty('error');
        }
    } finally {
        if (request.isCurrent()) {
            setLoading(false);
            updatePagination();
        }
    }
}

function renderCards(items, append = false) {
    const list = $('project-list');
    if (!append) list.replaceChildren();
    const spotlight = !append && hasDiscoverySpotlight(state);
    const offset = append ? state.items.length - items.length : 0;
    const cards = items.map((project, index) => renderCard(project, spotlight && index === 0, offset + index + 1, index));
    list.append(...cards);
    hydrateSparklines(cards);
}

function renderCard(project, featured = false, rank = 0, order = 0) {
    const card = document.createElement('article');
    card.className = 'project-card';
    card.classList.toggle('is-featured', featured);
    card.classList.toggle('has-highlights', featured && readmeHighlights(project.readme_summary_zh).length > 0);
    card.dataset.repo = project.repo_full_name;
    card.dataset.id = String(project.id || 0);
    card.dataset.category = normalizeProjectCategory(project.category);
    card.setAttribute('aria-labelledby', 'project-title-' + encodeURIComponent(project.repo_full_name || ''));
    card.style.setProperty('--i', String(Math.min(order, 8)));
    card.innerHTML = renderProjectCardContents(project, {
        featured, rank, expanded: expandedProjects.has(project.repo_full_name),
    });
    hydrateProjectAvatars(card);
    return card;
}

async function hydrateSparklines(cards) {
    const slots = cards.flatMap(card => [...card.querySelectorAll('.star-trend')]);
    const missing = [...new Set(slots.map(slot => slot.dataset.projectId).filter(id => !sparklineCache.has(id)))];
    try {
        if (missing.length) {
            const history = await api('/star-history?ids=' + missing.join(',') + '&points=30');
            missing.forEach(id => sparklineCache.set(id, history[id] || []));
        }
        slots.forEach(slot => {
            if (!slot.isConnected) return;
            const svg = renderSparkline(sparklineCache.get(slot.dataset.projectId) || []);
            if (svg) slot.innerHTML = svg;
            else slot.remove();
        });
    } catch { slots.forEach(slot => slot.remove()); }
}

function updatePagination() {
    const paginated = !state.recommendMode && !state.githubSearch;
    const more = paginated && state.items.length < state.total;
    $('load-more').classList.toggle('hidden', !more);
    $('load-more-note').textContent = '已显示 ' + state.items.length + ' / ' + state.total + ' 个项目';
}

function showEmpty(reason = '') {
    const filtered = Boolean(state.query || state.language || state.minStars);
    let title = '没有找到项目', detail = '试试其他关键词，或调整筛选条件。', action = '清除筛选';
    emptyAction = clearFilters;
    if (reason === 'error') {
        title = state.githubSearch ? 'GitHub 搜索暂时不可用' : '暂时无法加载项目';
        detail = '请检查服务连接后重试。已保存的项目和收藏不会受影响。';
        action = '重新加载';
        emptyAction = () => loadProjects(false, { force: true });
    } else if (reason === 'search_prompt') {
        title = '探索整个 GitHub';
        detail = '输入项目名或关键词，也可以使用 topic:llm 等搜索条件。';
        action = '输入关键词';
        emptyAction = () => $('search-input').focus();
    } else if (state.recommendMode && !state.githubSearch && reason === 'no_favorites') {
        title = '从一个收藏开始';
        detail = '收藏感兴趣的项目，我们会根据标签和语言为你推荐。';
        action = '发现项目';
        emptyAction = () => selectCategory('all');
    } else if (state.favoritesMode && !state.githubSearch && !filtered) {
        title = '留住你的下一个灵感';
        detail = '点击项目右上角的收藏图标，即可在这里继续探索。';
        action = '发现项目';
        emptyAction = () => selectCategory('all');
    } else if (state.recommendMode && !filtered) {
        title = '还没有合适的推荐';
        detail = '试着收藏更多感兴趣的项目，让推荐更了解你。';
        action = '发现项目';
        emptyAction = () => selectCategory('all');
    } else if (!filtered && !state.githubSearch) {
        title = state.status?.is_refreshing ? '正在收录项目' : '项目库还没有内容';
        detail = state.status?.is_refreshing ? '项目抓取完成后会自动出现在这里。' : '更新项目库，开始发现热门开源项目。';
        action = '更新项目';
        emptyAction = refreshProjects;
    }
    $('empty-title').textContent = title;
    $('empty-detail').textContent = detail;
    $('empty-action').textContent = action;
    $('empty-state').classList.remove('hidden');
}

function cancelSearch() {
    clearTimeout(searchTimer);
    requests.cancel();
    setLoading(false);
}

function selectCategory(category) {
    cancelSearch();
    const fromRemote = state.githubSearch;
    Object.assign(state, buildModeState(category));
    if (fromRemote || state.recommendMode) {
        state.query = ''; state.language = ''; state.minStars = 0;
        $('search-input').value = '';
    }
    state.items = [];
    state.total = 0;
    updateModeUI();
    closeNavigation();
    syncAddress(true);
    loadProjects();
    window.scrollTo({ top: 0, behavior: 'instant' });
}

function selectSource(source) {
    cancelSearch();
    state.githubSearch = source === 'github';
    state.query = $('search-input').value.trim();
    state.items = [];
    state.total = 0;
    updateModeUI();
    syncAddress(true);
    loadProjects();
}

function clearFilters() {
    cancelSearch();
    state.query = ''; state.language = ''; state.minStars = 0;
    $('search-input').value = '';
    updateModeUI();
    loadProjects();
}

async function toggleFavorite(project, button) {
    if (button.disabled) return;
    button.disabled = true;
    try {
        let id = Number(project.id || 0);
        if (!id) {
            const imported = await api('/projects/import', {
                method: 'POST',
                body: JSON.stringify({
                    repo_full_name: project.repo_full_name, description: project.description || '',
                    stars: Number(project.stars || 0), stars_gained: Number(project.stars_gained || 0),
                    language: project.language || '', topics: project.topics || [],
                    repo_url: project.repo_url || '', last_updated: project.last_updated || '',
                    category: project.category || 'other',
                }),
            });
            Object.assign(project, imported);
            id = imported.id;
            if (imported.is_favorited) {
                state.favoriteIds.add(id);
                updateFavoriteButton(button, project);
                updateFavoriteCount();
                showToast('这个项目已在收藏中。');
                return;
            }
        }
        const wasFavorite = Boolean(project.is_favorited);
        try {
            await api('/favorites/' + id, { method: wasFavorite ? 'DELETE' : 'POST' });
        } catch (error) {
            if (wasFavorite || error.status !== 409) throw error;
        }
        project.is_favorited = !wasFavorite;
        if (project.is_favorited) state.favoriteIds.add(id);
        else state.favoriteIds.delete(id);
        state.recommendations = null;
        updateFavoriteButton(button, project);
        updateFavoriteCount();
        if (project.is_favorited) showToast('已加入收藏', 'success');
        else showToast('已取消收藏', 'success', { label: '撤销', run: () => restoreFavorite(project) });
        if (state.favoritesMode && !state.githubSearch && !project.is_favorited) await loadProjects();
    } catch {
        showToast('收藏未能保存，请重试。', 'error');
    } finally { button.disabled = false; }
}

// Removing a favorite is one tap, so the confirmation carries its own way back.
async function restoreFavorite(project) {
    const id = Number(project.id || 0);
    try {
        try { await api('/favorites/' + id, { method: 'POST' }); }
        catch (error) { if (error.status !== 409) throw error; }
        project.is_favorited = true;
        state.favoriteIds.add(id);
        state.recommendations = null;
        updateFavoriteCount();
        if (state.favoritesMode && !state.githubSearch) { await loadProjects(); return; }
        const card = [...document.querySelectorAll('.project-card')].find(item => item.dataset.repo === project.repo_full_name);
        const button = card?.querySelector('.btn-favorite');
        if (button) updateFavoriteButton(button, project);
    } catch { showToast('未能恢复收藏，请重试。', 'error'); }
}

function updateFavoriteButton(button, project) {
    button.classList.toggle('favorited', Boolean(project.is_favorited));
    button.setAttribute('aria-pressed', String(Boolean(project.is_favorited)));
    button.title = project.is_favorited ? '取消收藏' : '收藏项目';
    button.setAttribute('aria-label', (project.is_favorited ? '取消收藏 ' : '收藏 ') + project.repo_full_name);
}

function updateFavoriteCount() {
    const count = document.querySelector('[data-count="favorites"]');
    count.textContent = String(state.favoriteIds.size);
    $('pulse-favorites').textContent = state.favoriteIds.size.toLocaleString('zh-CN');
    $('btn-pulse-favorites').setAttribute('aria-label', '查看 ' + state.favoriteIds.size + ' 个收藏的项目');
}

async function loadNavigation() {
    const results = await Promise.allSettled([api('/categories'), api('/favorites/ids')]);
    if (results[0].status === 'fulfilled') {
        let total = 0;
        results[0].value.forEach(category => {
            total += category.count;
            const count = [...document.querySelectorAll('[data-count]')].find(element => element.dataset.count === category.key);
            if (count) count.textContent = String(category.count);
        });
        document.querySelector('[data-count="all"]').textContent = String(total);
        renderComposition(results[0].value, total);
    }
    if (results[1].status === 'fulfilled') {
        state.favoriteIds = new Set(results[1].value);
        updateFavoriteCount();
    }
}

// Part-to-whole figure: the legend buttons carry names and counts, so color is never the only cue.
function renderComposition(categories, total) {
    const parts = ['ai', 'tools', 'devtools', 'other']
        .map(key => ({ key, count: Number(categories.find(category => category.key === key)?.count || 0) }))
        .filter(part => part.count > 0);
    const root = $('pulse-composition');
    if (!total || !parts.length) { root.replaceChildren(); return; }
    const share = count => Math.round(count / total * 100) + '%';
    const summary = parts.map(part => categoryNames[part.key] + ' ' + part.count + ' 个（' + share(part.count) + '）').join('，');
    root.innerHTML = '<div class="composition-bar" role="img" aria-label="' + escapeHtml('分类构成：' + summary) + '">'
        + parts.map(part => '<span data-part="' + part.key + '" style="flex-grow:' + part.count + '"></span>').join('')
        + '</div><div class="composition-legend" role="group" aria-label="按分类浏览">'
        + parts.map(part => '<button type="button" data-part="' + part.key + '" title="' + escapeHtml(categoryNames[part.key] + ' · 占 ' + share(part.count)) + '">'
            + escapeHtml(categoryNames[part.key]) + '<b>' + part.count + '</b></button>').join('') + '</div>';
    updateCompositionFocus();
}

function updateCompositionFocus(hovered = '') {
    const root = $('pulse-composition');
    const selected = state.githubSearch ? '' : currentCategory();
    const focus = hovered || (['ai', 'tools', 'devtools', 'other'].includes(selected) ? selected : '');
    if (focus) root.dataset.focus = focus; else delete root.dataset.focus;
    root.querySelectorAll('button[data-part]').forEach(button =>
        button.setAttribute('aria-pressed', String(button.dataset.part === selected)));
}

async function loadLanguages() {
    try { state.languages = await api('/languages'); updateLanguageOptions(); } catch { /* The project list has its own connection error. */ }
}

function updateLanguageOptions() {
    const select = $('filter-language');
    const languages = new Set([...state.languages, ...(state.remoteItems || []).map(project => project.language)].filter(Boolean));
    if (state.language) languages.add(state.language);
    select.replaceChildren(new Option('全部语言', ''));
    [...languages].sort().forEach(language => select.add(new Option(language, language)));
    select.value = state.language;
}

function statusSignature(status) {
    return [status.total_projects, status.translation_done, status.translation_pending, status.translation_failed, status.is_refreshing].join('|');
}

async function checkStatus() {
    if (statusBusy) return;
    statusBusy = true;
    try {
        const previous = state.status;
        const status = await api('/status');
        state.status = status;
        updateStatusUI();
        const finished = previous?.is_refreshing && !status.is_refreshing;
        if (finished) {
            sparklineCache.clear();
            await Promise.allSettled([loadNavigation(), loadLanguages(), checkHealth()]);
            if (status.last_refresh_error) showToast('更新未完成，请在状态面板查看原因。', 'error');
            else showToast('项目库已更新', 'success');
        }
        const changed = previous && statusSignature(previous) !== statusSignature(status);
        const reading = document.querySelector('dialog[open]') || $('project-list').contains(document.activeElement);
        if (changed && !reading && !state.loading && state.page === 1 && !state.githubSearch && !state.recommendMode) loadProjects();
    } catch {
        $('status-label').textContent = '连接中断';
        $('btn-status').dataset.tone = 'error';
        $('btn-status').setAttribute('aria-label', '连接中断，查看状态');
    } finally { statusBusy = false; }
}

function updateStatusUI() {
    const status = state.status;
    if (!status) return;
    $('overview-total').textContent = Number(status.total_projects || 0).toLocaleString('zh-CN');
    $('overview-freshness').textContent = status.is_data_stale ? '需更新' : status.last_fetched ? '已更新' : '待初始化';
    $('overview-translations').textContent = Number(status.translation_done || 0).toLocaleString('zh-CN');
    $('pulse-projects').textContent = $('overview-total').textContent;
    $('pulse-translations').textContent = $('overview-translations').textContent;
    const coverage = status.total_projects > 0
        ? Math.min(100, Math.max(0, Math.round((status.translation_done || 0) / status.total_projects * 100))) : 0;
    $('pulse-coverage').textContent = status.total_projects > 0 ? coverage + '%' : '';
    $('pulse-translation-fill').style.width = coverage + '%';
    const date = parseProjectDate(status.last_fetched);
    $('last-updated').textContent = date ? '更新于 ' + timeAgo(status.last_fetched) : '等待首次更新';
    // The same figure-and-unit shape as the other three: "11" + "小时前更新".
    const age = date ? timeAgo(status.last_fetched) : '';
    const [, figure, unit] = age.match(/^(\d+)\s*(.+)$/) || [];
    $('pulse-freshness').textContent = figure || age || '—';
    $('pulse-freshness-unit').textContent = figure ? unit + '更新' : age ? '更新' : '等待首次更新';
    $('btn-pulse-status').title = date ? '更新于 ' + date.toLocaleString('zh-CN', { hour12: false }) : '';
    $('pulse-status-label').textContent = status.is_refreshing ? '项目库更新中' : status.is_data_stale ? '数据较旧 · 建议更新' : '数据快照';
    $('btn-pulse-status').dataset.tone = status.is_refreshing ? 'working' : status.is_data_stale ? 'warning' : 'ok';
    $('overview-freshness-note').textContent = date ? '上次更新：' + date.toLocaleString('zh-CN', { hour12: false }) : '尚未抓取项目。';
    $('translation-summary-detail').textContent = formatTranslationSummary(status);
    $('btn-retry-failed').disabled = !((status.translation_retry || 0) + (status.translation_failed || 0));
    $('refresh-progress').classList.toggle('hidden', !status.is_refreshing);
    $('progress-stage').textContent = { scraping: '正在更新项目', scoring: '正在计算排序' }[status.refresh_stage] || '准备更新';
    $('progress-detail').textContent = status.refresh_detail || '';
    const progress = status.translate_total ? Math.round(status.translate_done / status.translate_total * 100) : 8;
    $('progress-fill').style.width = Math.min(100, Math.max(8, progress)) + '%';
    $('btn-refresh').disabled = status.is_refreshing;
    $('btn-refresh').classList.toggle('refreshing', status.is_refreshing);
    let label = '已更新', tone = 'ok';
    if (status.is_refreshing) { label = '更新中'; tone = 'working'; }
    else if (status.translation_processing || status.translation_pending) { label = '翻译中'; tone = 'working'; }
    else if (status.last_refresh_error || status.is_data_stale || state.health?.status === 'warning') { label = '需要检查'; tone = 'warning'; }
    else if (!status.last_fetched) { label = '待初始化'; tone = 'warning'; }
    $('status-label').textContent = label;
    $('btn-status').dataset.tone = tone;
    $('btn-status').setAttribute('aria-label', label + '，查看更新与翻译状态');
}

function healthProblem(problem) {
    const labels = {
        'API_KEY is not configured': '模型密钥尚未配置，翻译与问答暂不可用。',
        'Remote AI features are not configured': '远程问答与 AI 推荐未配置；本地翻译不受影响。',
        'GITHUB_TOKEN is not configured; GitHub API rate limits will be lower': '未配置 GitHub Token，抓取时更容易受到频率限制。',
        'Proxy is not configured': '未设置代理，请确认可以直接访问 GitHub 与模型服务。',
        'Database check failed': '项目库连接失败。',
        'Project data is stale': '项目数据较旧，建议更新项目库。',
    };
    if (problem.startsWith('Last refresh failed: ')) return '上次更新失败：' + problem.slice(21);
    if (problem.startsWith("Model '")) return '配置的模型当前不可用，请检查模型名称。';
    return labels[problem] || problem;
}

async function checkHealth() {
    $('btn-refresh-health').disabled = true;
    try {
        const health = await api('/health');
        state.health = health;
        const translation = health.checks?.translation;
        $('translation-engine-name').textContent = translation?.local ? 'Ollama · 本地翻译' : '远程模型翻译';
        $('translation-engine-detail').textContent = translation
            ? [translation.model, translation.detail].filter(Boolean).join(' · ') : '当前服务尚未返回翻译方式';
        $('translation-engine-state').textContent = translation ? (translation.ok ? '已就绪' : '待检查') : '';
        $('translation-engine-state').dataset.tone = translation?.ok ? 'ok' : 'warning';
        const problems = Array.isArray(health.problems) ? health.problems : [];
        $('overview-health').textContent = problems.length ? '有 ' + problems.length + ' 项需要检查' : '连接正常';
        $('health-summary').classList.toggle('hidden', !problems.length);
        $('health-summary-detail').textContent = problems.map(healthProblem).join('\n');
        $('overview-health-note').textContent = health.checks?.model_api_key?.model ? '当前模型：' + health.checks.model_api_key.model : '';
        updateStatusUI();
    } catch {
        state.health = { status: 'warning' };
        $('overview-health').textContent = '无法连接到服务';
        $('overview-health-note').textContent = '请确认应用服务正在运行，再重新检查。';
        $('translation-engine-name').textContent = '翻译状态暂不可用';
        $('translation-engine-detail').textContent = '连接恢复后重新检查。';
        $('translation-engine-state').textContent = '';
        updateStatusUI();
    } finally { $('btn-refresh-health').disabled = false; }
}

async function refreshProjects() {
    if ($('btn-refresh').disabled) return;
    $('btn-refresh').disabled = true;
    try {
        await api('/refresh', { method: 'POST' });
        showToast('已开始更新项目库');
        await checkStatus();
    } catch {
        $('btn-refresh').disabled = false;
        showToast('未能开始更新，请检查服务连接。', 'error');
    }
}

async function retryTranslations() {
    $('btn-retry-failed').disabled = true;
    try {
        await api('/translations/retry-failed', { method: 'POST' });
        showToast('已加入翻译重试队列');
        await checkStatus();
    } catch {
        $('btn-retry-failed').disabled = false;
        showToast('未能开始重试，请稍后再试。', 'error');
    }
}

function applyTheme() {
    const dark = state.theme === 'dark' || (state.theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    document.documentElement.dataset.accent = state.accent;
    document.querySelectorAll('meta[name="theme-color"]').forEach(meta => { meta.content = dark ? '#000000' : '#f5f5f7'; });
    $('theme-select').value = state.theme;
    document.querySelectorAll('[data-accent]').forEach(button => {
        if (button.tagName === 'BUTTON') button.setAttribute('aria-pressed', String(button.dataset.accent === state.accent));
    });
}

function applyView() {
    $('project-list').dataset.view = state.view;
    document.querySelectorAll('[data-view]').forEach(button => {
        if (button.tagName === 'BUTTON') button.setAttribute('aria-pressed', String(button.dataset.view === state.view));
    });
}

function openDialog(id) {
    const dialog = $(id);
    if (!dialog.open) {
        dialog.showModal();
        document.body.classList.add('has-dialog');
        showDialogMotion(dialog);
    }
}

function closeDialog(dialog) { closeDialogMotion(dialog); }

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
}

function closeNavigation() {
    const wasOpen = $('site-header').classList.contains('is-open');
    $('site-header').classList.remove('is-open');
    $('site-header').removeAttribute('aria-modal');
    $('site-header').removeAttribute('role');
    document.body.classList.remove('has-navigation');
    $('navigation-scrim').hidden = true;
    document.querySelector('.workspace').inert = false;
    document.querySelector('.workspace-topbar').inert = false;
    $('btn-menu').setAttribute('aria-expanded', 'false');
    $('btn-menu').setAttribute('aria-label', '展开导航');
    if (wasOpen && $('btn-menu').getClientRects().length) $('btn-menu').focus();
}

function showToast(message, type = 'info', action = null) {
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.innerHTML = icon(type === 'success' ? 'check' : 'info') + '<span>' + escapeHtml(message) + '</span>';
    const dismiss = () => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 200); };
    if (action) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'toast-action';
        button.textContent = action.label;
        button.addEventListener('click', () => { dismiss(); action.run(); }, { once: true });
        toast.append(button);
    }
    const root = document.querySelector('dialog[open]') || $('toast-root');
    if (root.tagName === 'DIALOG') {
        toast.classList.add('dialog-toast');
        root.append(toast);
    } else root.append(toast);
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(dismiss, action ? 6000 : 2800);
}

async function loadKeywords() {
    const list = $('keyword-list');
    list.textContent = '正在读取关注关键词…';
    try {
        const keywords = await api('/keywords');
        list.replaceChildren();
        if (!keywords.length) {
            list.innerHTML = '<p class="keyword-empty">还没有关注的关键词</p>';
            return;
        }
        keywords.forEach(keyword => {
            const item = document.createElement('div');
            item.className = 'keyword-item';
            item.innerHTML = '<span>' + escapeHtml(keyword.keyword) + '<small>' + escapeHtml(categoryNames[keyword.category] || '其他热门') + '</small></span>';
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'icon-button';
            button.setAttribute('aria-label', '删除关键词 ' + keyword.keyword);
            button.innerHTML = icon('close');
            button.addEventListener('click', async () => {
                button.disabled = true;
                try { await api('/keywords/' + keyword.id, { method: 'DELETE' }); await loadKeywords(); }
                catch { button.disabled = false; showToast('删除失败，请重试。', 'error'); }
            });
            item.append(button);
            list.append(item);
        });
    } catch { list.textContent = '无法读取关键词，请关闭后重试。'; }
}

async function saveKeyword(event) {
    event.preventDefault();
    const keyword = $('keyword-input').value.trim();
    if (!keyword) return;
    $('btn-save-keyword').disabled = true;
    $('keyword-error').classList.add('hidden');
    try {
        await api('/keywords', { method: 'POST', body: JSON.stringify({ keyword, category: $('keyword-category').value }) });
        $('keyword-input').value = '';
        await loadKeywords();
        showToast('已添加关注，下次更新时生效。', 'success');
    } catch (error) {
        $('keyword-error').textContent = error.status === 409 ? '已经关注过这个关键词。' : '添加失败，请检查连接后重试。';
        $('keyword-error').classList.remove('hidden');
    } finally { $('btn-save-keyword').disabled = false; }
}

function openChat(project) {
    chat.controller?.abort();
    chat.generation++;
    chat.controller = null;
    chat.repo = project.repo_full_name;
    chat.history = [];
    $('chat-repo-name').textContent = chat.repo;
    $('chat-input').value = '';
    setChatBusy(false);
    $('chat-messages').innerHTML = '<div class="chat-welcome">' + icon('sparkles') +
        '<h3>进一步了解这个项目</h3><p>基于项目介绍和 README，帮你判断它是否适合你。</p><div class="chat-suggestions">' +
        ['适合什么场景使用？', '核心优势是什么？', '如何快速上手？', '有哪些局限性？'].map(question =>
            '<button class="chat-suggestion" type="button" data-question="' + question + '">' + question + '</button>').join('') +
        '</div></div>';
    openDialog('chat-modal');
    $('chat-input').focus();
}

function openReader(project) {
    reader.project = project;
    $('reader-repo').textContent = project.repo_full_name;
    $('reader-content').innerHTML = renderProjectReading(project);
    $('reader-github').href = safeExternalUrl(project.repo_url);
    applyReaderSize();
    openDialog('reader-modal');
    $('reader-scroll').scrollTop = 0;
    updateReaderProgress();
    updateReaderNavigation();
    $('reader-content').querySelector('h2').focus({ preventScroll: true });
}

function canLoadMore() {
    return !state.recommendMode && !state.githubSearch && state.items.length < state.total;
}

function updateReaderNavigation() {
    const index = state.items.indexOf(reader.project);
    $('reader-prev').disabled = index <= 0;
    $('reader-next').disabled = index < 0 || (index >= state.items.length - 1 && !canLoadMore());
}

// Read through the list without leaving the reader; the next page loads when the list runs out.
async function stepReader(delta) {
    const index = state.items.indexOf(reader.project);
    if (index < 0) return;
    const control = document.activeElement === $('reader-prev') || document.activeElement === $('reader-next')
        ? (delta > 0 ? $('reader-next') : $('reader-prev')) : null;
    if (delta > 0 && index === state.items.length - 1 && canLoadMore()) {
        $('reader-next').disabled = true;
        await loadProjects(true);
        if (!$('reader-modal').open) return;
    }
    const project = state.items[index + delta];
    if (!project) { updateReaderNavigation(); return; }
    openReader(project);
    if (control && !control.disabled) control.focus();
}

function applyReaderSize() {
    $('reader-modal').dataset.readingSize = reader.size;
    $('reader-size').querySelectorAll('button').forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.readerSize === reader.size));
    });
    requestAnimationFrame(updateReaderProgress);
}

function updateReaderProgress() {
    const region = $('reader-scroll');
    const travel = region.scrollHeight - region.clientHeight;
    const progress = travel > 0 ? Math.min(1, Math.max(0, region.scrollTop / travel)) : 1;
    $('reader-progress-fill').style.transform = 'scaleX(' + progress + ')';
    $('reader-progress-label').textContent = '阅读进度 ' + Math.round(progress * 100) + '%';
}

function setChatBusy(busy) {
    $('chat-input').disabled = busy;
    $('btn-send-chat').disabled = busy;
    $('btn-send-chat').classList.toggle('hidden', busy);
    $('btn-stop-chat').classList.toggle('hidden', !busy);
}

async function sendChat(message) {
    const text = (message || '').trim();
    if (!text || chat.controller) return;
    const generation = chat.generation;
    const controller = new AbortController();
    chat.controller = controller;
    setChatBusy(true);
    const messages = $('chat-messages');
    messages.querySelector('.chat-welcome')?.remove();
    const user = document.createElement('div');
    user.className = 'chat-msg chat-msg-user';
    user.textContent = text;
    const answer = document.createElement('div');
    answer.className = 'chat-msg chat-msg-ai';
    answer.innerHTML = '<span class="chat-typing">正在阅读项目信息…</span>';
    messages.append(user, answer);
    messages.scrollTop = messages.scrollHeight;
    $('chat-input').value = '';
    let reply = '';
    let completed = false;
    try {
        const response = await fetch('/api/chat', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repo_full_name: chat.repo, message: text, history: chat.history }),
            signal: controller.signal,
        });
        if (!response.ok) throw new Error('Chat request failed');
        for await (const part of streamChatText(response.body)) {
            if (generation !== chat.generation) return;
            reply += part;
            answer.innerHTML = formatChatText(reply);
            messages.scrollTop = messages.scrollHeight;
        }
        if (!reply.trim()) throw new Error('The model returned no content');
        completed = true;
    } catch (error) {
        if (generation !== chat.generation) return;
        const stopped = error.name === 'AbortError';
        if (stopped && reply) completed = true;
        const note = stopped ? '已停止回答。' : '回答未能完成，请检查模型连接后重试。';
        answer.innerHTML = formatChatText(reply) + (reply ? '<br><br>' : '') + '<span class="' + (stopped ? 'muted' : 'chat-error') + '">' + note + '</span>';
    } finally {
        if (generation === chat.generation) {
            if (completed) chat.history.push({ role: 'user', content: text }, { role: 'assistant', content: reply });
            chat.history = chat.history.slice(-6);
            chat.controller = null;
            setChatBusy(false);
            if ($('chat-modal').open) $('chat-input').focus();
        }
    }
}

function bindEvents() {
    document.querySelectorAll('.tab[data-category]').forEach(tab => tab.addEventListener('click', () => selectCategory(tab.dataset.category)));
    document.querySelectorAll('[data-source]').forEach(button => button.addEventListener('click', () => selectSource(button.dataset.source)));
    $('search-input').addEventListener('input', event => {
        if (event.isComposing) return;
        clearTimeout(searchTimer);
        $('btn-clear-search').classList.toggle('hidden', !$('search-input').value);
        $('search-shortcut').classList.toggle('hidden', Boolean($('search-input').value));
        if (state.githubSearch) return;
        requests.cancel();
        setLoading(false);
        state.query = $('search-input').value.trim();
        updateFilterUI();
        searchTimer = setTimeout(() => loadProjects(), 300);
    });
    $('search-form').addEventListener('submit', event => {
        event.preventDefault();
        clearTimeout(searchTimer);
        state.query = $('search-input').value.trim();
        loadProjects(false, { force: state.githubSearch });
    });
    $('btn-clear-search').addEventListener('click', () => {
        cancelSearch();
        state.query = '';
        $('search-input').value = '';
        loadProjects();
        $('search-input').focus();
    });
    [['filter-language', 'language'], ['filter-sort', 'sort'], ['filter-stars', 'minStars']].forEach(([id, key]) => {
        $(id).addEventListener('change', event => {
            const value = event.target.value;
            cancelSearch();
            state[key] = key === 'minStars' ? Number(value) : value;
            loadProjects();
        });
    });
    document.querySelectorAll('[data-sort]').forEach(button => button.addEventListener('click', () => {
        cancelSearch();
        state.sort = button.dataset.sort;
        loadProjects();
    }));
    $('btn-pulse-favorites').addEventListener('click', () => selectCategory('favorites'));
    const composition = $('pulse-composition');
    composition.addEventListener('click', event => {
        const button = event.target.closest('button[data-part]');
        if (button) selectCategory(button.dataset.part === currentCategory() ? 'all' : button.dataset.part);
    });
    for (const [enter, leave] of [['pointerover', 'pointerleave'], ['focusin', 'focusout']]) {
        composition.addEventListener(enter, event => updateCompositionFocus(event.target.closest('[data-part]')?.dataset.part));
        composition.addEventListener(leave, () => updateCompositionFocus());
    }
    $('btn-clear-filters').addEventListener('click', clearFilters);
    $('active-filters').addEventListener('click', event => {
        const button = event.target.closest('[data-filter]');
        if (!button) return;
        cancelSearch();
        const key = button.dataset.filter;
        state[key] = key === 'minStars' ? 0 : '';
        if (key === 'query') $('search-input').value = '';
        updateModeUI();
        loadProjects();
    });
    document.querySelectorAll('button[data-view]').forEach(button => button.addEventListener('click', () => {
        state.view = button.dataset.view;
        savePreference('project-view', state.view);
        applyView();
    }));
    $('project-list').addEventListener('click', event => {
        const button = event.target.closest('button');
        const card = button?.closest('.project-card');
        if (!card) return;
        const project = state.items.find(item => item.repo_full_name === card.dataset.repo);
        if (!project) return;
        if (button.dataset.action === 'reader') openReader(project);
        if (button.dataset.action === 'chat') openChat(project);
        if (button.dataset.action === 'favorite') toggleFavorite(project, button);
        if (button.dataset.action === 'readme') {
            const expanded = button.getAttribute('aria-expanded') !== 'true';
            button.setAttribute('aria-expanded', String(expanded));
            button.querySelector('.readme-label').textContent = expanded ? '收起摘要' : '展开摘要';
            card.querySelector('.readme-content').classList.toggle('expanded', expanded);
            if (expanded) expandedProjects.add(project.repo_full_name);
            else expandedProjects.delete(project.repo_full_name);
        }
        if (button.dataset.topic) {
            cancelSearch();
            state.query = button.dataset.topic;
            $('search-input').value = state.query;
            loadProjects();
            $('search-input').focus();
            scrollToTop();
        }
    });
    $('btn-load-more').addEventListener('click', () => loadProjects(true));
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver(entries => {
            if (entries.some(entry => entry.isIntersecting) && !state.hadError) loadProjects(true);
        }, { rootMargin: '180px' });
        observer.observe($('load-more'));
    }
    $('empty-action').addEventListener('click', () => emptyAction());
    $('btn-shuffle-rec').addEventListener('click', () => loadProjects(false, { force: true }));
    $('btn-refresh').addEventListener('click', refreshProjects);
    $('btn-retry-failed').addEventListener('click', retryTranslations);
    $('btn-refresh-health').addEventListener('click', checkHealth);
    ['btn-settings', 'btn-status', 'btn-pulse-status'].forEach(id => $(id).addEventListener('click', () => {
        openDialog('settings-modal'); checkHealth(); closeNavigation();
    }));
    $('btn-add-keyword').addEventListener('click', () => {
        $('keyword-error').classList.add('hidden');
        openDialog('keyword-modal'); loadKeywords(); closeNavigation();
    });
    $('keyword-form').addEventListener('submit', saveKeyword);
    $('theme-select').addEventListener('change', event => {
        state.theme = event.target.value; savePreference('theme', state.theme); applyTheme();
    });
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (state.theme === 'system') applyTheme(); });
    $('accent-picker').addEventListener('click', event => {
        const button = event.target.closest('button[data-accent]');
        if (!button) return;
        state.accent = button.dataset.accent; savePreference('accent', state.accent); applyTheme();
    });
    $('btn-menu').addEventListener('click', () => {
        if ($('site-header').classList.contains('is-open')) { closeNavigation(); return; }
        $('site-header').classList.add('is-open');
        $('site-header').setAttribute('role', 'dialog');
        $('site-header').setAttribute('aria-modal', 'true');
        document.body.classList.add('has-navigation');
        $('navigation-scrim').hidden = false;
        document.querySelector('.workspace').inert = true;
        document.querySelector('.workspace-topbar').inert = true;
        $('btn-menu').setAttribute('aria-expanded', 'true');
        $('btn-menu').setAttribute('aria-label', '收起导航');
        showNavigationMotion($('site-header').querySelector('.header-inner'));
        $('btn-close-navigation').focus();
    });
    $('btn-close-navigation').addEventListener('click', closeNavigation);
    $('navigation-scrim').addEventListener('click', closeNavigation);
    window.matchMedia('(min-width: 1101px)').addEventListener('change', event => { if (event.matches) closeNavigation(); });
    document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => closeDialog($(button.dataset.close))));
    document.querySelectorAll('dialog').forEach(dialog => {
        dialog.addEventListener('cancel', event => { event.preventDefault(); closeDialog(dialog); });
        dialog.addEventListener('close', () => {
            if (!document.querySelector('dialog[open]')) document.body.classList.remove('has-dialog');
        });
        dialog.addEventListener('click', event => {
        const bounds = dialog.getBoundingClientRect();
        if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) closeDialog(dialog);
        });
    });
    $('chat-modal').addEventListener('close', () => { chat.generation++; chat.controller?.abort(); chat.controller = null; });
    $('reader-modal').addEventListener('close', () => { reader.project = null; });
    let readerFrame = 0;
    const scheduleReaderProgress = () => {
        if (readerFrame) return;
        readerFrame = requestAnimationFrame(() => { readerFrame = 0; updateReaderProgress(); });
    };
    $('reader-scroll').addEventListener('scroll', scheduleReaderProgress, { passive: true });
    window.addEventListener('resize', scheduleReaderProgress);
    $('reader-size').addEventListener('click', event => {
        const button = event.target.closest('button[data-reader-size]');
        if (!button) return;
        reader.size = button.dataset.readerSize;
        savePreference('reader-size', reader.size);
        applyReaderSize();
    });
    $('reader-prev').addEventListener('click', () => stepReader(-1));
    $('reader-next').addEventListener('click', () => stepReader(1));
    $('reader-modal').addEventListener('keydown', event => {
        if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
        if (event.key === 'ArrowLeft' && !$('reader-prev').disabled) { event.preventDefault(); stepReader(-1); }
        if (event.key === 'ArrowRight' && !$('reader-next').disabled) { event.preventDefault(); stepReader(1); }
    });
    window.addEventListener('popstate', () => {
        cancelSearch();
        applyViewFromAddress();
        updateModeUI();
        loadProjects();
    });
    $('reader-chat').addEventListener('click', () => { if (reader.project) openChat(reader.project); });
    $('chat-form').addEventListener('submit', event => { event.preventDefault(); sendChat($('chat-input').value); });
    $('chat-input').addEventListener('keydown', event => {
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
            event.preventDefault(); sendChat(event.target.value);
        }
    });
    $('chat-messages').addEventListener('click', event => {
        const button = event.target.closest('[data-question]');
        if (button) sendChat(button.dataset.question);
    });
    $('btn-stop-chat').addEventListener('click', () => chat.controller?.abort());
    document.addEventListener('click', event => {
        const filters = $('filter-panel');
        if (filters.open && !filters.contains(event.target)) filters.open = false;
    });
    document.addEventListener('keydown', event => {
        if (document.querySelector('dialog[open]')) return;
        if ($('site-header').classList.contains('is-open')) {
            if (event.key === 'Escape') { event.preventDefault(); closeNavigation(); return; }
            if (event.key === 'Tab') {
                const controls = [...$('site-header').querySelectorAll('a[href], button:not(:disabled)')].filter(element => element.getClientRects().length);
                const first = controls[0], last = controls.at(-1);
                if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
                else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
            }
            return;
        }
        if (event.key === 'Escape' && $('filter-panel').open) {
            $('filter-panel').open = false;
            $('filter-panel').querySelector('summary').focus();
            return;
        }
        const editing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName) || document.activeElement?.isContentEditable;
        if ((event.key.toLowerCase() === 'k' && (event.ctrlKey || event.metaKey)) || (event.key === '/' && !editing)) {
            event.preventDefault(); $('search-input').focus(); $('search-input').select();
        }
        if (event.key === 'Escape' && document.activeElement === $('search-input')) $('btn-clear-search').click();
    });
    $('btn-back-top').addEventListener('click', scrollToTop);
    window.addEventListener('scroll', () => $('btn-back-top').classList.toggle('visible', window.scrollY > 600), { passive: true });
}

if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', init);
