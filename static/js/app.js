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
    theme: localStorage.getItem('theme') || 'light'
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
    await checkStatus();
    await loadLanguages();
    await loadProjects();
    setupEventListeners();
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
        if (status.last_fetched) {
            document.getElementById('last-updated').textContent =
                `最后更新：${timeAgo(status.last_fetched)}`;
        }
    } catch (e) {
        document.getElementById('loading-screen').classList.add('hidden');
        document.getElementById('main-content').classList.remove('hidden');
    }
}

// ========== Load Languages Dropdown ==========
async function loadLanguages() {
    try {
        const langs = await api('/languages');
        const sel = document.getElementById('filter-language');
        langs.forEach(lang => {
            const opt = document.createElement('option');
            opt.value = lang;
            opt.textContent = lang;
            sel.appendChild(opt);
        });
    } catch (e) { /* ignore */ }
}

// ========== Load Projects ==========
async function loadProjects(append = false) {
    if (state.loading) return;
    state.loading = true;

    const params = new URLSearchParams({
        category: state.category,
        sort: state.sort,
        page: state.page,
        page_size: state.pageSize
    });
    if (state.language) params.set('language', state.language);
    if (state.query) params.set('q', state.query);

    try {
        const data = await api(`/projects?${params}`);
        state.total = data.total;
        const list = document.getElementById('project-list');
        const empty = document.getElementById('empty-state');
        const loadMore = document.getElementById('load-more');

        if (!append) list.innerHTML = '';

        if (data.items.length === 0 && !append) {
            empty.classList.remove('hidden');
            loadMore.classList.add('hidden');
        } else {
            empty.classList.add('hidden');
            data.items.forEach(p => list.appendChild(renderCard(p)));
            const shown = list.children.length;
            if (shown < state.total) {
                loadMore.classList.remove('hidden');
            } else {
                loadMore.classList.add('hidden');
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

    const gainedHtml = p.stars_gained > 0
        ? `<span class="star-gained">+${formatStars(p.stars_gained)}</span>` : '';
    const langHtml = p.language
        ? `<span class="card-language">${p.language}</span>` : '';
    const desc = p.description_zh || p.description || '暂无描述';
    const readmeSummary = p.readme_summary_zh || '';
    const tags = (p.topics || []).slice(0, 5);
    const tagsHtml = tags.map(t =>
        `<span class="tag" data-topic="${t}">#${t}</span>`
    ).join('');

    card.innerHTML = `
        <div class="card-header">
            <div class="card-repo">
                <a href="${p.repo_url}" target="_blank" rel="noopener">${p.repo_full_name}</a>
            </div>
            <div class="card-stats">
                <span class="star-count">\u2B50 ${formatStars(p.stars)}</span>
                ${gainedHtml}
                ${langHtml}
            </div>
        </div>
        <div class="card-description">${desc}</div>
        ${readmeSummary ? `
            <button class="readme-toggle" onclick="toggleReadme(this)">
                \uD83D\uDCD6 README 摘要 <span>\u25BC</span>
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

    card.querySelectorAll('.tag').forEach(tag => {
        tag.addEventListener('click', () => {
            const topic = tag.dataset.topic;
            document.getElementById('search-input').value = topic;
            state.query = topic;
            state.page = 1;
            loadProjects();
        });
    });

    return card;
}

// ========== Utilities ==========
function formatStars(n) {
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return String(n);
}

function timeAgo(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return '刚刚';
    if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前';
    if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前';
    if (diff < 2592000) return Math.floor(diff / 86400) + ' 天前';
    if (diff < 31536000) return Math.floor(diff / 2592000) + ' 个月前';
    return Math.floor(diff / 31536000) + ' 年前';
}

// ========== Event Listeners ==========
function setupEventListeners() {
    // Category tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelector('.tab.active').classList.remove('active');
            tab.classList.add('active');
            state.category = tab.dataset.category;
            state.page = 1;
            loadProjects();
        });
    });

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
    document.getElementById('search-input').addEventListener('input', (e) => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.query = e.target.value.trim();
            state.page = 1;
            loadProjects();
        }, 300);
    });

    // Refresh button
    document.getElementById('btn-refresh').addEventListener('click', onRefresh);

    // Theme toggle
    document.getElementById('btn-theme').addEventListener('click', toggleTheme);

    // Load more
    document.getElementById('btn-load-more').addEventListener('click', () => {
        state.page++;
        loadProjects(true);
    });

    // Keyword modal
    document.getElementById('btn-add-keyword').addEventListener('click', showKeywordModal);
    document.getElementById('btn-save-keyword').addEventListener('click', saveKeyword);
    document.getElementById('btn-cancel-keyword').addEventListener('click', () => {
        document.getElementById('keyword-modal').classList.add('hidden');
    });

    // Close modal on backdrop click
    document.getElementById('keyword-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
            e.currentTarget.classList.add('hidden');
        }
    });
}

// ========== Theme ==========
function applyTheme() {
    document.documentElement.setAttribute('data-theme', state.theme);
}

function toggleTheme() {
    state.theme = state.theme === 'light' ? 'dark' : 'light';
    localStorage.setItem('theme', state.theme);
    applyTheme();
}

// ========== Refresh ==========
async function onRefresh() {
    const btn = document.getElementById('btn-refresh');
    btn.classList.add('refreshing');
    btn.disabled = true;
    try {
        await api('/refresh', { method: 'POST' });
        const poll = setInterval(async () => {
            const s = await api('/status');
            if (!s.is_refreshing) {
                clearInterval(poll);
                btn.classList.remove('refreshing');
                btn.disabled = false;
                document.getElementById('last-updated').textContent =
                    `最后更新：${timeAgo(s.last_fetched)}`;
                state.page = 1;
                await loadLanguages();
                await loadProjects();
            }
        }, 5000);
    } catch (e) {
        btn.classList.remove('refreshing');
        btn.disabled = false;
    }
}

// ========== README Toggle ==========
function toggleReadme(btn) {
    const content = btn.nextElementSibling;
    const arrow = btn.querySelector('span');
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
        list.innerHTML = keywords.map(kw => `
            <div class="keyword-item">
                <span>${kw.keyword} (${kw.category})</span>
                <button class="keyword-delete" onclick="deleteKeyword(${kw.id})">\u2715</button>
            </div>
        `).join('');
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
        alert('添加失败，关键词可能已存在');
    }
}

async function deleteKeyword(id) {
    try {
        await api(`/keywords/${id}`, { method: 'DELETE' });
        await loadKeywords();
    } catch (e) { /* ignore */ }
}

// ========== Start ==========
document.addEventListener('DOMContentLoaded', init);
