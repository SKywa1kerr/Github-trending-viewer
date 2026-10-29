import { escapeHtml } from './sanitize.mjs';

export const categoryNames = {
    all: '发现', ai: '人工智能', tools: '实用工具', devtools: '开发工具',
    other: '其他热门', favorites: '我的收藏', recommend: '为你推荐',
};

export function icon(name, extraClass = '') {
    return `<svg class="icon ${extraClass}" aria-hidden="true"><use href="#icon-${name}"/></svg>`;
}

export function formatStars(value) {
    const n = Number(value) || 0;
    return n >= 1000 ? `${(n / 1000).toFixed(1).replace(/\.0$/, '')}k` : String(n);
}

// Use existing translated context for short taglines; never generate or persist new copy.
export function buildProjectDescription(project = {}) {
    const description = String(project.description_zh || '').trim()
        || String(project.description || '').trim();
    if (description.length >= 120) return description;

    const overview = readmeHighlights(project.readme_summary_zh).join(' ');
    return (overview.length > description.length ? overview : description)
        || '这个项目暂时没有提供简介。';
}

export function readmeHighlights(value, limit = 2) {
    return String(value || '').split(/\r?\n/)
        .map(line => line.trim())
        .filter(line => line && !/^#{1,6}\s/.test(line))
        .slice(0, limit)
        .map(line => line.replace(/^(?:[-*•·]\s+|\d+[.)）、]\s*)/u, '')
            .replace(/\*\*([^*]+)\*\*/g, '$1').replace(/`([^`]+)`/g, '$1'))
        .filter(Boolean);
}

export function buildModeState(category) {
    return {
        category: ['all', 'ai', 'tools', 'devtools', 'other'].includes(category) ? category : 'all',
        favoritesMode: category === 'favorites',
        recommendMode: category === 'recommend',
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

export function buildResultContext({ category = 'all', language = '', query = '', total = 0,
    favoritesMode = false, recommendMode = false, githubSearch = false } = {}) {
    const count = `共 ${formatStars(total)} 个项目`;
    if (githubSearch) return { label: 'GitHub 搜索', title: query || '实时搜索', detail: `来自 GitHub 实时搜索 · ${formatStars(total)} 个结果`, tone: 'remote' };
    if (favoritesMode) return { label: '收藏', title: '已收藏项目', detail: count, tone: 'favorites' };
    if (recommendMode) return { label: '为你推荐', title: 'AI 推荐列表', detail: total ? count : '等待收藏偏好', tone: 'recommend' };
    const labels = { all: '全部项目', ai: 'AI', tools: '实用工具', devtools: '开发工具', other: '其他热门' };
    return { label: '本地筛选', title: [labels[category] || category || '全部', language, query].filter(Boolean).join(' · '), detail: count, tone: 'local' };
}

export function formatTranslationSummary(status) {
    return [
        `待翻译 ${status.translation_pending || 0}`, `翻译中 ${status.translation_processing || 0}`,
        `待重试 ${status.translation_retry || 0}`, `失败 ${status.translation_failed || 0}`,
        `已完成 ${status.translation_done || 0}`,
    ].join('  |  ');
}

export function renderProjectMeta(project) {
    const statuses = { pending: '待翻译', processing: '翻译中', retry: '待重试', failed: '翻译失败', done: '已翻译' };
    const status = Object.hasOwn(statuses, project.translation_status) ? project.translation_status : '';
    const gained = Number(project.stars_gained) > 0 ? `<span class="star-gained" title="最近抓取到的 Star 增长">+${formatStars(project.stars_gained)}</span>` : '';
    const language = project.language ? `<span class="card-language"><span class="language-dot"></span>${escapeHtml(project.language)}</span>` : '';
    const spark = Number(project.id) > 0 ? `<span class="star-trend" data-project-id="${Number(project.id)}"></span>` : '';
    const badge = status ? `<span class="translation-badge ${status}">${statuses[status]}</span>` : '';
    return `<div class="card-stats"><span class="star-count" title="${Number(project.stars || 0).toLocaleString('zh-CN')} Star">${icon('star')}${formatStars(project.stars)}</span>${spark}${gained}${language}${badge}</div>`;
}

function sparklineValues(history) {
    return (history || []).filter(h => h && typeof h === 'object' && h.stars !== null && h.stars !== undefined && h.stars !== '')
        .map(h => Number(h.stars)).filter(Number.isFinite);
}

export function buildSparklinePoints(history, width = 72, height = 22, pad = 2) {
    const values = sparklineValues(history);
    if (values.length < 2) return [];
    const min = Math.min(...values), span = Math.max(...values) - min || 1;
    return values.map((v, i) => [
        Number((pad + i * (width - pad * 2) / (values.length - 1)).toFixed(1)),
        Number((height - pad - (v - min) / span * (height - pad * 2)).toFixed(1)),
    ]);
}

export function sparklineTrend(history) {
    const values = sparklineValues(history);
    if (values.length < 2) return 'flat';
    const delta = values.at(-1) - values[0];
    return delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat';
}

export function renderSparkline(history) {
    const points = buildSparklinePoints(history);
    if (!points.length) return '';
    const values = sparklineValues(history), delta = values.at(-1) - values[0];
    const deltaText = delta === 0 ? '0' : `${delta > 0 ? '+' : '-'}${formatStars(Math.abs(delta))}`;
    const title = `最近 ${values.length} 次记录：${deltaText} star`;
    const path = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x} ${y}`).join(' ');
    const [x, y] = points.at(-1);
    return `<svg class="sparkline sparkline-${sparklineTrend(history)}" viewBox="0 0 72 22" width="72" height="22" role="img" aria-label="${escapeHtml(title)}"><title>${escapeHtml(title)}</title><path d="${path}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${x}" cy="${y}" r="1.8" fill="currentColor"/></svg>`;
}

// SQLite timestamps are UTC but omit the timezone. ISO GitHub timestamps already carry one.
export function parseProjectDate(value) {
    if (!value) return null;
    let normalized = String(value).trim().replace(' ', 'T');
    if (/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?$/.test(normalized)) normalized += 'Z';
    const date = new Date(normalized);
    return Number.isNaN(date.getTime()) ? null : date;
}

export function timeAgo(value, now = Date.now()) {
    const date = parseProjectDate(value);
    if (!date) return '';
    const seconds = Math.max(0, (now - date.getTime()) / 1000);
    if (seconds < 60) return '刚刚';
    if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`;
    if (seconds < 2592000) return `${Math.floor(seconds / 86400)} 天前`;
    if (seconds < 31536000) return `${Math.floor(seconds / 2592000)} 个月前`;
    return `${Math.floor(seconds / 31536000)} 年前`;
}

export function filterProjectItems(items, { language = '', query = '', minStars = 0, sort = 'score' } = {}) {
    const needle = query.trim().toLowerCase();
    const filtered = items.filter(project => {
        if (language && project.language !== language) return false;
        if (Number(project.stars || 0) < minStars) return false;
        const haystack = [project.repo_full_name, project.description, project.description_zh,
            project.readme_summary_zh, ...(project.topics || [])].join(' ').toLowerCase();
        return !needle || haystack.includes(needle);
    });
    if (sort === 'score') return filtered;
    const field = { stars: 'stars', stars_gained: 'stars_gained', updated: 'last_updated', newest: 'first_seen_at' }[sort];
    if (!field) return filtered;
    return filtered.sort((a, b) => {
        const values = [a[field], b[field]].map(value => field.includes('_at') || field === 'last_updated'
            ? (parseProjectDate(value)?.getTime() || 0) : Number(value || 0));
        return values[1] - values[0];
    });
}

// Cancellation saves work; the generation check also rejects responses from non-cancellable work.
export function createRequestGate() {
    let generation = 0;
    let controller;
    return {
        start() {
            controller?.abort();
            controller = new AbortController();
            const current = ++generation;
            return { signal: controller.signal, isCurrent: () => generation === current };
        },
        cancel() { controller?.abort(); generation++; },
    };
}

// Both UTF-8 characters and SSE frames can span arbitrary network chunks.
export async function* streamChatText(body) {
    if (!body) throw new Error('Empty response stream');
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    try {
        while (true) {
            const { value, done } = await reader.read();
            buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
            const frames = buffer.split(/\r?\n\r?\n/);
            buffer = frames.pop();
            if (done && buffer.trim()) { frames.push(buffer); buffer = ''; }
            for (const frame of frames) {
                const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:'))
                    .map(line => line.slice(5).trimStart()).join('\n').trim();
                if (!data) continue;
                if (data === '[DONE]') return;
                const parsed = JSON.parse(data);
                if (parsed.error) throw new Error(String(parsed.error));
                if (typeof parsed.content === 'string') yield parsed.content;
            }
            if (done) break;
        }
    } finally { reader.releaseLock(); }
}
