import { escapeHtml, formatChatText, formatReadmeHtml, safeExternalUrl } from './sanitize.mjs';

// ========== State ==========
const state = {
    category: 'ai',
    language: '',
    sort: 'score',
    query: '',
    page: 1,
    pageSize: 20,
    total: 0,
    loading: false,
    favoritesMode: false,
    recommendMode: false,
    githubSearch: false,
    theme: typeof localStorage !== 'undefined' ? (localStorage.getItem('theme') || 'light') : 'light',
    accent: typeof localStorage !== 'undefined' ? (localStorage.getItem('accent') || 'indigo') : 'indigo',
    statusSignature: ''
};

// ========== API Helper ==========
async function api(path, options = {}) {
    const resp = await fetch(`/api${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

// ========== Init ==========
async function init() {
    applyTheme();
    updateTabIndicator();
    await checkStatus();
    await checkHealth();
    await loadLanguages();
    await loadProjects();
    setupEventListeners();
    startStatusPolling();
}

async function checkStatus() {
    try {
        const status = await api('/status');
        const loading = document.getElementById('loading-screen');
        const main = document.getElementById('main-content');
        if (status.total_projects === 0 && status.is_refreshing) {
            loading.classList.remove('hidden');
            main.classList.add('hidden');
            const poll = setInterval(async () => {
                const s = await api('/status');
                if (s.total_projects > 0 || !s.is_refreshing) {
                    clearInterval(poll);
                    loading.classList.add('hidden');
                    main.classList.remove('hidden');
                    await loadProjects();
                }
            }, 3000);
        } else {
            loading.classList.add('hidden');
            main.classList.remove('hidden');
        }
        updateStatusUI(status);
    } catch (e) {
        document.getElementById('loading-screen').classList.add('hidden');
        document.getElementById('main-content').classList.remove('hidden');
    }
}

function buildStatusSignature(status) {
    return [
        status.is_refreshing,
        status.refresh_stage,
        status.translation_pending,
        status.translation_processing,
        status.translation_retry,
        status.translation_failed,
        status.translation_done
    ].join('|');
}

function updateStatusUI(status) {
    updateProgressBar(status);
    updateTranslationSummary(status);
    updateOverviewStatus(status);
    updateRefreshFailureUI(status);
    state.statusSignature = buildStatusSignature(status);
    if (status.last_fetched) {
        document.getElementById('last-updated').textContent =
            `\u6700\u540E\u66F4\u65B0\uFF1A${timeAgo(status.last_fetched)}`;
    }
}

function updateOverviewStatus(status) {
    const total = document.getElementById('overview-total');
    const freshness = document.getElementById('overview-freshness');
    const freshnessNote = document.getElementById('overview-freshness-note');
    const translations = document.getElementById('overview-translations');
    if (!total || !freshness || !freshnessNote || !translations) return;

    total.textContent = formatCount(status.total_projects || 0);
    const age = Number(status.data_age_hours || 0);
    if (status.is_data_stale) {
        freshness.textContent = '需刷新';
        freshnessNote.textContent = age > 0 ? `缓存约 ${formatAgeHours(age)}` : '缓存过期';
    } else if (status.last_fetched) {
        freshness.textContent = '新鲜';
        freshnessNote.textContent = age > 0 ? `更新于 ${formatAgeHours(age)} 前` : '刚刚更新';
    } else {
        freshness.textContent = '待初始化';
        freshnessNote.textContent = '暂无抓取记录';
    }

    translations.textContent = `${formatCount(status.translation_pending || 0)} / ${formatCount(status.translation_done || 0)}`;
}

function updateRefreshFailureUI(status) {
    if (!status || !status.last_refresh_error) return;
    updateHealthUI({
        status: 'warning',
        problems: [`最近刷新失败：${status.last_refresh_error}`]
    });
}

function updateTranslationSummary(status) {
    const detail = document.getElementById('translation-summary-detail');
    detail.textContent = formatTranslationSummary(status);
}

function formatHealthProblem(problem) {
    if (String(problem).startsWith('Last refresh failed: ')) {
        return `最近刷新失败：${String(problem).replace('Last refresh failed: ', '')}`;
    }
    const labels = {
        'API_KEY is not configured': '未配置模型 API_KEY，翻译、推荐和项目问答不可用',
        'GITHUB_TOKEN is not configured; GitHub API rate limits will be lower': '未配置 GitHub Token，抓取时更容易触发限流',
        'Proxy is not configured': '未配置代理，GitHub 或模型接口可能无法访问',
        'Database check failed': '数据库检查失败',
        'Project data is stale': '项目数据已过期，建议刷新或检查 GitHub Token/代理'
    };
    return labels[problem] || problem;
}

function updateHealthUI(health) {
    const box = document.getElementById('health-summary');
    const detail = document.getElementById('health-summary-detail');
    if (!box || !detail) return;

    const problems = Array.isArray(health.problems) ? health.problems : [];
    if (health.status === 'ok' || problems.length === 0) {
        box.classList.add('hidden');
        detail.textContent = '';
        updateOverviewHealth('正常', '配置可用');
        return;
    }

    box.classList.remove('hidden');
    detail.textContent = problems.slice(0, 3).map(formatHealthProblem).join('  |  ');
    updateOverviewHealth('需关注', `${problems.length} 项提示`);
}

async function checkHealth() {
    try {
        const health = await api('/health');
        updateHealthUI(health);
    } catch (e) {
        updateHealthUI({
            status: 'warning',
            problems: ['无法读取系统诊断状态']
        });
    }
}

function updateOverviewHealth(label, note) {
    const health = document.getElementById('overview-health');
    const healthNote = document.getElementById('overview-health-note');
    if (!health || !healthNote) return;
    health.textContent = label;
    healthNote.textContent = note;
}

function translationStatusLabel(status) {
    const labels = {
        pending: '待翻译',
        processing: '翻译中',
        retry: '待重试',
        failed: '翻译失败',
        done: '已翻译'
    };
    return labels[status] || '未翻译';
}

function renderTranslationBadge(status) {
    if (!status) return '';
    const safeStatus = ['pending', 'processing', 'retry', 'failed', 'done'].includes(status)
        ? status
        : 'unknown';
    return `<span class="translation-badge ${safeStatus}">${escapeHtml(translationStatusLabel(status))}</span>`;
}

function buildProjectImportPayload(project) {
    return {
        repo_full_name: project.repo_full_name || '',
        description: project.description || '',
        stars: Number(project.stars || 0),
        stars_gained: Number(project.stars_gained || 0),
        language: project.language || '',
        topics: Array.isArray(project.topics) ? project.topics : [],
        repo_url: project.repo_url || '',
        last_updated: project.last_updated || '',
        category: project.category || 'other'
    };
}

function startStatusPolling() {
    setInterval(async () => {
        try {
            const status = await api('/status');
            const nextSignature = buildStatusSignature(status);
            const changed = state.statusSignature && state.statusSignature !== nextSignature;
            updateStatusUI(status);

            if (changed && !state.loading && !state.recommendMode && !state.githubSearch && state.page === 1) {
                await loadProjects();
            }
        } catch (e) {
            // ignore polling errors
        }
    }, 5000);
}

// ========== Load Languages Dropdown ==========
async function loadLanguages() {
    try {
        const langs = await api('/languages');
        const sel = document.getElementById('filter-language');
        // Keep first option, remove rest
        while (sel.options.length > 1) sel.remove(1);
        langs.forEach(lang => {
            const opt = document.createElement('option');
            opt.value = lang;
            opt.textContent = lang;
            sel.appendChild(opt);
        });
    } catch (e) { /* ignore */ }
}

// ========== Load Projects ==========
function renderSkeletons(list, count = 4) {
    for (let i = 0; i < count; i++) {
        const card = document.createElement('div');
        card.className = 'project-card skeleton-card';
        card.innerHTML =
            '<div class="sk-line sk-line-title"></div>' +
            '<div class="sk-line sk-line-desc"></div>' +
            '<div class="sk-line sk-line-desc-short"></div>' +
            '<div class="sk-line sk-line-meta"></div>';
        list.appendChild(card);
    }
}

async function loadProjects(append = false) {
    if (state.loading) return;
    state.loading = true;

    const listEl = document.getElementById('project-list');
    // Only on a cold list, so filtering or searching never flashes placeholders.
    if (!append && listEl.children.length === 0) renderSkeletons(listEl);

    try {
        let data;
        if (state.favoritesMode) {
            const params = new URLSearchParams({
                sort: state.sort,
                page: state.page,
                page_size: state.pageSize
            });
            data = await api(`/favorites?${params}`);
        } else {
            const params = new URLSearchParams({
                category: state.category,
                sort: state.sort,
                page: state.page,
                page_size: state.pageSize
            });
            if (state.language) params.set('language', state.language);
            if (state.query) params.set('q', state.query);
            data = await api(`/projects?${params}`);
        }

        state.total = data.total;
        const list = document.getElementById('project-list');
        const empty = document.getElementById('empty-state');
        const scrollHint = document.getElementById('load-more');
        updateResultContext();

        if (!append) list.innerHTML = '';

        if (data.items.length === 0 && !append) {
            empty.classList.remove('hidden');
            empty.querySelector('p').textContent = emptyStateMessage(state);
            scrollHint.classList.add('hidden');
        } else {
            empty.classList.add('hidden');
            const startIndex = list.children.length;
            const newCards = [];
            data.items.forEach((p, i) => {
                const card = renderCard(p);
                card.style.animationDelay = `${(startIndex + i) * 0.04}s`;
                list.appendChild(card);
                newCards.push(card);
            });
            hydrateSparklines(newCards);
            const shown = list.children.length;
            if (shown < state.total) {
                scrollHint.classList.remove('hidden');
            } else {
                scrollHint.classList.add('hidden');
            }
        }
    } catch (e) {
        console.error('Failed to load projects:', e);
    }
    state.loading = false;
}

// ========== Render Card ==========
function renderCard(p) {
    const card = document.createElement('div');
    card.className = 'project-card';
    card.dataset.id = p.id;

    const repoName = escapeHtml(p.repo_full_name || '');
    const repoUrl = escapeHtml(safeExternalUrl(p.repo_url || ''));
    const metaHtml = renderProjectMeta(p);
    const newBadge = p.is_new ? '<span class="badge-new">NEW</span>' : '';
    const favClass = p.is_favorited ? 'favorited' : '';
    const desc = escapeHtml(p.description_zh || p.description || '\u6682\u65E0\u63CF\u8FF0');
    const readmeSummary = formatReadme(p.readme_summary_zh || '');
    const tags = (p.topics || []).slice(0, 5);
    const tagsHtml = tags.map(t =>
        `<span class="tag" data-topic="${escapeHtml(t)}">#${escapeHtml(t)}</span>`
    ).join('');

    card.innerHTML = `
        <div class="card-header">
            <div class="card-repo">
                <a href="${repoUrl}" target="_blank" rel="noopener">${repoName}</a>
                ${newBadge}
            </div>
            <div class="card-actions">
                <button class="btn-chat" data-repo="${repoName}" title="AI \u95EE\u7B54">
                    <svg viewBox="0 0 24 24" width="14" height="14">
                        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z" fill="currentColor"/>
                    </svg>
                    <span>AI</span>
                </button>
                <button class="btn-favorite ${favClass}" data-id="${p.id}" title="\u6536\u85CF">
                    <svg viewBox="0 0 24 24" width="18" height="18">
                        <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" fill="currentColor"/>
                    </svg>
                </button>
                ${metaHtml}
            </div>
        </div>
        <div class="card-description">${desc}</div>
        ${readmeSummary ? `
            <button class="readme-toggle" type="button">
                <span class="readme-toggle-label">README \u6458\u8981</span><span class="readme-toggle-icon">\u25BC</span>
            </button>
            <div class="readme-content">
                <div class="readme-text">${readmeSummary}</div>
            </div>
        ` : ''}
        <div class="card-footer">
            <div class="card-tags">${tagsHtml}</div>
            <span class="card-time">${p.last_updated ? timeAgo(p.last_updated) : ''}</span>
        </div>
    `;

    // Chat button
    card.querySelector('.btn-chat').addEventListener('click', (e) => {
        e.stopPropagation();
        openChat(p.repo_full_name);
    });

    // Favorite toggle
    card.querySelector('.btn-favorite').addEventListener('click', (e) => {
        e.stopPropagation();
        toggleFavorite(p, card.querySelector('.btn-favorite'), card);
    });

    // Tag click
    card.querySelectorAll('.tag').forEach(tag => {
        tag.addEventListener('click', () => {
            const topic = tag.dataset.topic;
            document.getElementById('search-input').value = topic;
            state.query = topic;
            state.page = 1;
            if (state.favoritesMode) switchToCategory('ai');
            else loadProjects();
        });
    });

    const readmeToggle = card.querySelector('.readme-toggle');
    if (readmeToggle) {
        readmeToggle.addEventListener('click', () => toggleReadme(readmeToggle));
    }

    return card;
}

// ========== Favorites ==========
async function toggleFavorite(project, btn, card) {
    let projectId = Number(project.id || 0);
    const isFav = btn.classList.contains('favorited');
    try {
        if (!projectId) {
            const imported = await api('/projects/import', {
                method: 'POST',
                body: JSON.stringify(buildProjectImportPayload(project))
            });
            projectId = imported.id;
            project.id = imported.id;
            project.is_favorited = imported.is_favorited;
            card.dataset.id = String(imported.id);
            btn.dataset.id = String(imported.id);
        }

        if (isFav) {
            await api(`/favorites/${projectId}`, { method: 'DELETE' });
            btn.classList.remove('favorited');
            project.is_favorited = false;
            showToast('已取消收藏', 'info');
            // If in favorites view, remove the card with animation
            if (state.favoritesMode) {
                card.style.transition = 'opacity 0.3s, transform 0.3s';
                card.style.opacity = '0';
                card.style.transform = 'translateX(30px)';
                setTimeout(() => {
                    card.remove();
                    state.total--;
                    if (state.total === 0) {
                        document.getElementById('empty-state').classList.remove('hidden');
                    }
                }, 300);
            }
        } else {
            await api(`/favorites/${projectId}`, { method: 'POST' });
            btn.classList.add('favorited');
            project.is_favorited = true;
            showToast('已加入收藏', 'success');
            // Heart pop animation
            btn.classList.add('pop');
            setTimeout(() => btn.classList.remove('pop'), 400);
        }
    } catch (e) { /* ignore */ }
}

function switchToCategory(cat) {
    state.favoritesMode = false;
    state.recommendMode = false;
    state.category = cat;
    state.page = 1;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab[data-category="${cat}"]`).classList.add('active');
    updateTabIndicator();
    loadProjects();
}

// ========== Tab Indicator ==========
const TAB_TINTS = {
    favorites: 'var(--danger-soft)',
    recommend: 'var(--star-bg)'
};

function updateTabIndicator() {
    const indicator = document.getElementById('tab-indicator');
    const active = document.querySelector('.tab.active');
    if (!indicator || !active) return;
    indicator.style.width = `${active.offsetWidth}px`;
    indicator.style.transform = `translateX(${active.offsetLeft}px)`;
    indicator.style.setProperty('--indicator-bg', TAB_TINTS[active.dataset.category] || 'var(--bg-card)');
    indicator.classList.add('ready');
}

// ========== Recommendations ==========
async function loadRecommendations(force = false) {
    const list = document.getElementById('project-list');
    const empty = document.getElementById('empty-state');
    const loadMore = document.getElementById('load-more');
    loadMore.classList.add('hidden');
    list.innerHTML = '<div class="rec-loading">AI \u6B63\u5728\u5206\u6790\u4F60\u7684\u6536\u85CF\u504F\u597D\uFF0C\u751F\u6210\u63A8\u8350...</div>';
    empty.classList.add('hidden');
    state.total = 0;
    updateResultContext();

    try {
        const url = force ? '/recommendations?force=true' : '/recommendations';
        const data = await api(url);
        list.innerHTML = '';
        state.total = Array.isArray(data.items) ? data.items.length : 0;
        updateResultContext();

        if (data.message === 'no_favorites') {
            empty.classList.remove('hidden');
            empty.querySelector('p').textContent = emptyStateMessage({ recommendMode: true, reason: 'no_favorites' });
            return;
        }
        if (data.items.length === 0) {
            empty.classList.remove('hidden');
            empty.querySelector('p').textContent = emptyStateMessage({ recommendMode: true });
            return;
        }

        // Add "换一批" button at top
        const toolbar = document.createElement('div');
        toolbar.className = 'rec-toolbar';
        toolbar.innerHTML = `<button class="btn btn-shuffle" id="btn-shuffle-rec">
            <svg viewBox="0 0 24 24" width="16" height="16"><path d="M17.65 6.35A7.96 7.96 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" fill="currentColor"/></svg>
            \u6362\u4E00\u6279
        </button>`;
        list.appendChild(toolbar);

        toolbar.querySelector('#btn-shuffle-rec').addEventListener('click', () => {
            loadRecommendations(true);
        });

        const recCards = [];
        data.items.forEach((p, i) => {
            const card = renderCard(p);
            if (p.recommendation_reason) {
                const badge = document.createElement('div');
                badge.className = 'rec-reason';
                badge.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" style="vertical-align:-2px;margin-right:4px;flex-shrink:0"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="currentColor"/></svg>';
                badge.append(document.createTextNode(p.recommendation_reason));
                const desc = card.querySelector('.card-description');
                if (desc) desc.after(badge);
            }
            card.style.animationDelay = `${i * 0.04}s`;
            list.appendChild(card);
            recCards.push(card);
        });
        hydrateSparklines(recCards);
    } catch (e) {
        list.innerHTML = '';
        empty.classList.remove('hidden');
        empty.querySelector('p').textContent = emptyStateMessage({ recommendMode: true, reason: 'error' });
        updateResultContext();
    }
}

// ========== Format README ==========
function formatReadme(text) {
    return formatReadmeHtml(text);
}

// ========== Utilities ==========
function formatStars(n) {
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return String(n);
}

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

export function buildResultContext({
    category = 'ai',
    language = '',
    query = '',
    total = 0,
    favoritesMode = false,
    recommendMode = false,
    githubSearch = false,
} = {}) {
    const countText = `共 ${formatCount(total)} 个项目`;
    if (githubSearch) {
        return {
            label: 'GitHub 搜索',
            title: query || '实时搜索',
            detail: `来自 GitHub 实时搜索 · ${formatCount(total)} 个结果`,
            tone: 'remote',
        };
    }
    if (favoritesMode) {
        return {
            label: '收藏',
            title: '已收藏项目',
            detail: countText,
            tone: 'favorites',
        };
    }
    if (recommendMode) {
        return {
            label: '为你推荐',
            title: 'AI 推荐列表',
            detail: total > 0 ? countText : '等待收藏偏好',
            tone: 'recommend',
        };
    }

    const categoryLabels = {
        ai: 'AI',
        tools: '实用工具',
        devtools: '开发工具',
        other: '其他热门',
    };
    const parts = [categoryLabels[category] || category || '全部'];
    if (language) parts.push(language);
    if (query) parts.push(query);
    return {
        label: '本地筛选',
        title: parts.join(' · '),
        detail: countText,
        tone: 'local',
    };
}

function updateResultContext(overrides = {}) {
    const box = document.getElementById('result-context');
    const label = document.getElementById('result-context-label');
    const title = document.getElementById('result-context-title');
    const detail = document.getElementById('result-context-detail');
    if (!box || !label || !title || !detail) return;

    const context = buildResultContext({ ...state, ...overrides });
    box.className = `result-context result-context-${context.tone}`;
    label.textContent = context.label;
    title.textContent = context.title;
    detail.textContent = context.detail;
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
    const sparkSlot = project.id
        ? `<span class="star-trend" data-project-id="${Number(project.id)}" aria-hidden="true"></span>` : '';
    return `
        <div class="card-stats">
            <span class="star-count">⭐ ${formatStars(project.stars)}</span>
            ${sparkSlot}
            ${gainedHtml}
            ${langHtml}
            ${renderTranslationBadge(project.translation_status)}
        </div>
    `;
}

// ========== Star Trend Sparklines ==========
const SPARK_WIDTH = 72;
const SPARK_HEIGHT = 22;
const SPARK_PAD = 2;

function sparklineValues(history) {
    return (history || [])
        .filter((h) => h && typeof h === 'object' && h.stars !== null && h.stars !== undefined && h.stars !== '')
        .map((h) => Number(h.stars))
        .filter((v) => Number.isFinite(v));
}

export function buildSparklinePoints(history, width = SPARK_WIDTH, height = SPARK_HEIGHT, pad = SPARK_PAD) {
    const values = sparklineValues(history);
    if (values.length < 2) return [];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const stepX = (width - pad * 2) / (values.length - 1);
    return values.map((v, i) => {
        const x = pad + i * stepX;
        const y = height - pad - ((v - min) / span) * (height - pad * 2);
        return [Number(x.toFixed(1)), Number(y.toFixed(1))];
    });
}

export function sparklineTrend(history) {
    const values = sparklineValues(history);
    if (values.length < 2) return 'flat';
    const first = values[0];
    const last = values[values.length - 1];
    const delta = last - first;
    if (delta === 0) return 'flat';
    return delta > 0 ? 'up' : 'down';
}

export function renderSparkline(history) {
    const points = buildSparklinePoints(history);
    if (!points.length) return '';
    const values = sparklineValues(history);
    const trend = sparklineTrend(history);
    const path = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x} ${y}`).join(' ');
    const [lastX, lastY] = points[points.length - 1];
    const delta = values[values.length - 1] - values[0];
    const deltaText = delta === 0 ? '0' : `${delta > 0 ? '+' : '-'}${formatStars(Math.abs(delta))}`;
    const title = `最近 ${values.length} 次记录：${deltaText} star`;
    return `<svg class="sparkline sparkline-${trend}" viewBox="0 0 ${SPARK_WIDTH} ${SPARK_HEIGHT}" width="${SPARK_WIDTH}" height="${SPARK_HEIGHT}" role="img">`
        + `<title>${escapeHtml(title)}</title>`
        + `<path d="${path}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>`
        + `<circle cx="${lastX}" cy="${lastY}" r="1.8" fill="currentColor"/>`
        + `</svg>`;
}

async function hydrateSparklines(cards) {
    const slots = [];
    cards.forEach((card) => {
        const slot = card.querySelector('.star-trend[data-project-id]');
        if (slot && !slot.dataset.loaded) slots.push(slot);
    });
    if (!slots.length) return;
    const ids = [...new Set(slots.map((s) => s.dataset.projectId))].filter((id) => Number(id) > 0);
    if (!ids.length) return;
    try {
        const history = await api(`/star-history?ids=${ids.join(',')}&points=30`);
        slots.forEach((slot) => {
            slot.dataset.loaded = '1';
            const series = history[slot.dataset.projectId];
            const svg = renderSparkline(series || []);
            if (svg) {
                slot.innerHTML = svg;
                slot.classList.add('has-data');
            } else {
                slot.remove();
            }
        });
    } catch (e) {
        slots.forEach((slot) => slot.remove());
    }
}

function formatCount(n) {
    const value = Number(n || 0);
    if (value >= 1000) return (value / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return String(value);
}

function formatAgeHours(hours) {
    const value = Number(hours || 0);
    if (value < 1) return '不足 1 小时';
    if (value < 24) return `${Math.round(value)} 小时`;
    return `${Math.round(value / 24)} 天`;
}

function timeAgo(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return '\u521A\u521A';
    if (diff < 3600) return Math.floor(diff / 60) + ' \u5206\u949F\u524D';
    if (diff < 86400) return Math.floor(diff / 3600) + ' \u5C0F\u65F6\u524D';
    if (diff < 2592000) return Math.floor(diff / 86400) + ' \u5929\u524D';
    if (diff < 31536000) return Math.floor(diff / 2592000) + ' \u4E2A\u6708\u524D';
    return Math.floor(diff / 31536000) + ' \u5E74\u524D';
}

// ========== Event Listeners ==========
function setupEventListeners() {
    // Category tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const cat = tab.dataset.category;
            const nextMode = buildModeState(cat);
            Object.assign(state, nextMode);
            updateTabIndicator();
            if (state.recommendMode) loadRecommendations();
            else loadProjects();
        });
    });
    window.addEventListener('resize', updateTabIndicator);

    // Language filter
    document.getElementById('filter-language').addEventListener('change', (e) => {
        state.language = e.target.value;
        state.page = 1;
        loadProjects();
    });

    // Sort filter
    document.getElementById('filter-sort').addEventListener('change', (e) => {
        state.sort = e.target.value;
        state.page = 1;
        loadProjects();
    });

    // Search with debounce
    let searchTimer;
    const searchInput = document.getElementById('search-input');
    const btnSearchGithub = document.getElementById('btn-search-github');

    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.query = e.target.value.trim();
            state.page = 1;
            state.githubSearch = false;
            if (state.favoritesMode) switchToCategory('ai');
            else loadProjects();
        }, 300);
    });

    // Search GitHub button
    btnSearchGithub.addEventListener('click', async () => {
        const q = searchInput.value.trim();
        if (!q) return;
        btnSearchGithub.disabled = true;
        btnSearchGithub.textContent = '搜索中...';
        try {
            const data = await api(`/search/github?q=${encodeURIComponent(q)}`);
            state.githubSearch = true;
            state.query = q;
            state.total = data.total;
            const list = document.getElementById('project-list');
            const empty = document.getElementById('empty-state');
            const loadMore = document.getElementById('load-more');
            list.innerHTML = '';
            data.items.forEach((p, i) => {
                const card = renderCard(p);
                card.style.animationDelay = `${i * 0.04}s`;
                list.appendChild(card);
            });
            loadMore.classList.add('hidden');
            updateResultContext();
            if (data.items.length === 0) {
                empty.classList.remove('hidden');
                empty.querySelector('p').textContent = emptyStateMessage({ githubSearch: true });
            } else {
                empty.classList.add('hidden');
            }
        } catch (e) {
            console.error('GitHub search failed:', e);
            state.githubSearch = true;
            state.query = q;
            state.total = 0;
            document.getElementById('project-list').innerHTML = '';
            document.getElementById('load-more').classList.add('hidden');
            const empty = document.getElementById('empty-state');
            empty.classList.remove('hidden');
            empty.querySelector('p').textContent = emptyStateMessage({ githubSearch: true, reason: 'error' });
            updateResultContext();
        }
        btnSearchGithub.disabled = false;
        btnSearchGithub.textContent = '搜索 GitHub';
    });

    // Enter key in search triggers GitHub search if local results are empty
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            btnSearchGithub.click();
        }
    });

    // Refresh button
    document.getElementById('btn-refresh').addEventListener('click', onRefresh);
    document.getElementById('btn-retry-failed').addEventListener('click', retryFailedTranslations);
    document.getElementById('btn-refresh-health').addEventListener('click', checkHealth);

    // Theme toggle
    document.getElementById('btn-theme').addEventListener('click', toggleTheme);
    document.getElementById('accent-picker').addEventListener('click', (e) => {
        const dot = e.target.closest('.accent-dot');
        if (dot) setAccent(dot.dataset.accent);
    });

    // Infinite scroll
    let scrollTimer;
    window.addEventListener('scroll', () => {
        clearTimeout(scrollTimer);
        scrollTimer = setTimeout(() => {
            if (state.loading || state.recommendMode || state.githubSearch) return;
            const list = document.getElementById('project-list');
            if (!list.children.length) return;
            const shown = list.children.length;
            if (shown >= state.total) return;
            const bottomY = list.getBoundingClientRect().bottom;
            if (bottomY - window.innerHeight < 300) {
                state.page++;
                loadProjects(true);
            }
        }, 100);
    });

    // Keyword modal
    document.getElementById('btn-add-keyword').addEventListener('click', showKeywordModal);
    document.getElementById('btn-save-keyword').addEventListener('click', saveKeyword);
    document.getElementById('btn-cancel-keyword').addEventListener('click', () => {
        document.getElementById('keyword-modal').classList.add('hidden');
    });

    // Back to top
    const backTopBtn = document.getElementById('btn-back-top');
    backTopBtn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    window.addEventListener('scroll', () => {
        if (window.scrollY > 400) {
            backTopBtn.classList.add('visible');
        } else {
            backTopBtn.classList.remove('visible');
        }
    });

    // Close modal on backdrop click
    document.getElementById('keyword-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
            e.currentTarget.classList.add('hidden');
        }
    });

    // Chat modal
    document.getElementById('btn-close-chat').addEventListener('click', () => {
        document.getElementById('chat-modal').classList.add('hidden');
    });
    document.getElementById('chat-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
            e.currentTarget.classList.add('hidden');
        }
    });
    document.getElementById('btn-send-chat').addEventListener('click', () => {
        sendChat(document.getElementById('chat-input').value);
    });
    document.getElementById('chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChat(e.target.value);
        }
    });
}

// ========== Theme ==========
function applyTheme() {
    document.documentElement.setAttribute('data-theme', state.theme);
    document.documentElement.setAttribute('data-accent', state.accent);
    document.querySelectorAll('.accent-dot').forEach((dot) => {
        dot.setAttribute('aria-pressed', dot.dataset.accent === state.accent ? 'true' : 'false');
    });
}

function toggleTheme() {
    state.theme = state.theme === 'light' ? 'dark' : 'light';
    localStorage.setItem('theme', state.theme);
    const root = document.documentElement;
    root.classList.add('theme-anim');
    applyTheme();
    setTimeout(() => root.classList.remove('theme-anim'), 480);
}

function setAccent(accent) {
    if (!accent || accent === state.accent) return;
    state.accent = accent;
    localStorage.setItem('accent', accent);
    applyTheme();
}

// ========== Toast ==========
let _toastRoot = null;
function showToast(message, type = 'info') {
    if (!_toastRoot) _toastRoot = document.getElementById('toast-root');
    if (!_toastRoot) return;
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = message;
    _toastRoot.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => {
        el.classList.remove('show');
        setTimeout(() => el.remove(), 320);
    }, 2400);
}

// ========== Refresh ==========
function updateProgressBar(s) {
    const bar = document.getElementById('refresh-progress');
    const stage = document.getElementById('progress-stage');
    const detail = document.getElementById('progress-detail');
    const fill = document.getElementById('progress-fill');

    if (!s.is_refreshing) {
        bar.classList.add('hidden');
        return;
    }

    bar.classList.remove('hidden');
    const stageNames = {
        scraping: '\u6293\u53D6\u9879\u76EE\u4E2D...',
        translating: '\u7FFB\u8BD1\u4E2D...',
        scoring: '\u8BA1\u7B97\u8BC4\u5206...'
    };
    stage.textContent = stageNames[s.refresh_stage] || '\u51C6\u5907\u4E2D...';

    detail.textContent = s.refresh_detail || '';

    if (s.translate_total > 0) {
        const pct = Math.round((s.translate_done / s.translate_total) * 100);
        fill.style.width = Math.max(pct, 5) + '%';
        if (s.refresh_stage === 'translating') {
            detail.textContent = `${s.translate_done} / ${s.translate_total} (${pct}%)`;
        }
    } else if (s.refresh_stage === 'scoring') {
        fill.style.width = '95%';
    } else {
        fill.style.width = '10%';
    }
}

async function onRefresh() {
    const btn = document.getElementById('btn-refresh');
    btn.classList.add('refreshing');
    btn.disabled = true;
    try {
        await api('/refresh', { method: 'POST' });
        showToast('已开始刷新数据', 'info');
        const poll = setInterval(async () => {
            const s = await api('/status');
            updateStatusUI(s);
            if (!s.is_refreshing) {
                clearInterval(poll);
                btn.classList.remove('refreshing');
                btn.disabled = false;
                state.page = 1;
                await loadLanguages();
                await loadProjects();
            }
        }, 1000);
    } catch (e) {
        btn.classList.remove('refreshing');
        btn.disabled = false;
    }
}

async function retryFailedTranslations() {
    const btn = document.getElementById('btn-retry-failed');
    btn.disabled = true;
    try {
        await api('/translations/retry-failed', { method: 'POST' });
        showToast('已加入重试队列', 'info');
        const status = await api('/status');
        updateStatusUI(status);
        if (!state.recommendMode && !state.githubSearch && state.page === 1) {
            await loadProjects();
        }
    } catch (e) {
        console.error('Failed to retry translations:', e);
    }
    btn.disabled = false;
}

// ========== README Toggle ==========
function toggleReadme(btn) {
    const content = btn.nextElementSibling;
    const arrow = btn.querySelector('.readme-toggle-icon');
    content.classList.toggle('expanded');
    arrow.textContent = content.classList.contains('expanded') ? '\u25B2' : '\u25BC';
}

// ========== Keyword Modal ==========
async function showKeywordModal() {
    document.getElementById('keyword-modal').classList.remove('hidden');
    document.getElementById('keyword-input').value = '';
    await loadKeywords();
}

async function loadKeywords() {
    try {
        const keywords = await api('/keywords');
        const list = document.getElementById('keyword-list');
        list.innerHTML = '';
        keywords.forEach((kw) => {
            const item = document.createElement('div');
            item.className = 'keyword-item';

            const label = document.createElement('span');
            label.textContent = `${kw.keyword} (${kw.category})`;

            const button = document.createElement('button');
            button.className = 'keyword-delete';
            button.type = 'button';
            button.textContent = '\u2715';
            button.addEventListener('click', () => deleteKeyword(kw.id));

            item.appendChild(label);
            item.appendChild(button);
            list.appendChild(item);
        });
    } catch (e) { /* ignore */ }
}

async function saveKeyword() {
    const keyword = document.getElementById('keyword-input').value.trim();
    const category = document.getElementById('keyword-category').value;
    if (!keyword) return;
    try {
        await api('/keywords', {
            method: 'POST',
            body: JSON.stringify({ keyword, category })
        });
        document.getElementById('keyword-input').value = '';
        await loadKeywords();
    } catch (e) {
        alert('\u6DFB\u52A0\u5931\u8D25\uFF0C\u5173\u952E\u8BCD\u53EF\u80FD\u5DF2\u5B58\u5728');
    }
}

async function deleteKeyword(id) {
    try {
        await api(`/keywords/${id}`, { method: 'DELETE' });
        await loadKeywords();
    } catch (e) { /* ignore */ }
}

// ========== AI Chat ==========
let chatHistory = [];
let chatRepo = '';

function openChat(repoName) {
    chatRepo = repoName;
    chatHistory = [];
    document.getElementById('chat-repo-name').textContent = repoName;
    document.getElementById('chat-messages').innerHTML = `
        <div class="chat-welcome">
            <p>你可以问我关于这个项目的任何问题，比如：</p>
            <div class="chat-suggestions">
                <button class="chat-suggestion" data-q="这个项目适合什么场景使用？">适合什么场景？</button>
                <button class="chat-suggestion" data-q="这个项目的核心优势是什么？和同类项目相比如何？">核心优势是什么？</button>
                <button class="chat-suggestion" data-q="如何快速上手这个项目？需要什么前置条件？">如何快速上手？</button>
                <button class="chat-suggestion" data-q="这个项目有什么局限性或注意事项？">有什么局限性？</button>
            </div>
        </div>`;
    document.getElementById('chat-modal').classList.remove('hidden');
    document.getElementById('chat-input').focus();

    // Bind suggestion buttons
    document.querySelectorAll('.chat-suggestion').forEach(btn => {
        btn.addEventListener('click', () => sendChat(btn.dataset.q));
    });
}

async function sendChat(message) {
    if (!message || !message.trim()) return;
    const msg = message.trim();
    const messagesEl = document.getElementById('chat-messages');
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('btn-send-chat');

    // Remove welcome if present
    const welcome = messagesEl.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    // Add user message
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-msg chat-msg-user';
    userDiv.textContent = msg;
    messagesEl.appendChild(userDiv);

    // Add AI message placeholder
    const aiDiv = document.createElement('div');
    aiDiv.className = 'chat-msg chat-msg-ai';
    aiDiv.innerHTML = '<span class="chat-typing">思考中...</span>';
    messagesEl.appendChild(aiDiv);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    input.value = '';
    input.disabled = true;
    sendBtn.disabled = true;

    try {
        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                repo_full_name: chatRepo,
                message: msg,
                history: chatHistory
            })
        });

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let aiText = '';
        aiDiv.innerHTML = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6).trim();
                    if (data === '[DONE]') break;
                    try {
                        const parsed = JSON.parse(data);
                        if (parsed.content) {
                            aiText += parsed.content;
                            aiDiv.innerHTML = formatChatText(aiText);
                            messagesEl.scrollTop = messagesEl.scrollHeight;
                        }
                    } catch (e) {}
                }
            }
        }

        chatHistory.push({ role: 'user', content: msg });
        chatHistory.push({ role: 'assistant', content: aiText });
    } catch (e) {
        aiDiv.innerHTML = '<span style="color:#ef4444">请求失败，请重试</span>';
    }

    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
}

// ========== Start ==========
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', init);
}
