import { escapeHtml, formatReadmeHtml, safeExternalUrl } from './sanitize.mjs?v=42';
import { buildProjectDescription, categoryNames, icon, readmeHighlights, renderProjectMeta, timeAgo } from './library.mjs?v=40';

const failedAvatarUrls = new Set();

export function normalizeProjectCategory(category) {
    return ['ai', 'tools', 'devtools', 'other'].includes(category) ? category : 'other';
}

// GitHub avatars identify the owner or organization, not the repository itself.
export function githubOwnerAvatarUrl(owner) {
    if (typeof owner !== 'string' || !owner || owner.length > 39
        || /[^a-z0-9-]/i.test(owner) || owner.startsWith('-') || owner.endsWith('-') || owner.includes('--')) return '';
    return 'https://github.com/' + owner.toLowerCase() + '.png?size=128';
}

export function hydrateProjectAvatars(root) {
    root.querySelectorAll('.project-avatar[data-avatar-src]').forEach(avatar => {
        const url = avatar.dataset.avatarSrc;
        const mark = avatar.parentElement;
        delete avatar.dataset.avatarSrc;
        if (failedAvatarUrls.has(url)) {
            avatar.remove();
            return;
        }
        const cleanup = () => {
            avatar.removeEventListener('load', onLoad);
            avatar.removeEventListener('error', onError);
        };
        const onError = () => {
            cleanup();
            failedAvatarUrls.add(url);
            mark.classList.remove('has-avatar');
            avatar.remove();
        };
        const onLoad = () => {
            if (!avatar.naturalWidth) return onError();
            cleanup();
            failedAvatarUrls.delete(url);
            mark.classList.add('has-avatar');
        };
        avatar.addEventListener('load', onLoad, { once: true });
        avatar.addEventListener('error', onError, { once: true });
        // Set the source after handlers are ready, and skip failed URLs on later renders.
        avatar.src = url;
        if (avatar.complete) avatar.naturalWidth ? onLoad() : onError();
    });
}

export function projectIdentity(fullName = '') {
    const value = String(fullName);
    const slash = value.indexOf('/');
    const owner = slash < 0 ? '' : value.slice(0, slash);
    const name = (slash < 0 ? value : value.slice(slash + 1)) || '未命名项目';
    const words = name.replace(/([a-z])([A-Z])/g, '$1 $2').split(/[^\p{L}\p{N}]+/u).filter(Boolean);
    const monogram = (words.length > 1
        ? words.slice(0, 2).map(word => Array.from(word)[0]).join('')
        : Array.from(words[0] || 'GH').slice(0, 2).join('')).toUpperCase();
    return { owner, name, monogram };
}

// A single reading focus on unfiltered discovery; search and saved views keep their ordering.
export function hasDiscoverySpotlight({ category = 'all', query = '', language = '', minStars = 0,
    sort = 'score', favoritesMode = false, recommendMode = false, githubSearch = false } = {}) {
    return category === 'all' && !query && !language && !Number(minStars) && sort === 'score'
        && !favoritesMode && !recommendMode && !githubSearch;
}

export function renderProjectCardContents(project, { featured = false, expanded = false } = {}) {
    const fullName = String(project.repo_full_name || '');
    const { owner, name, monogram } = projectIdentity(fullName);
    const summary = formatReadmeHtml(project.readme_summary_zh || '');
    const isExpanded = Boolean(summary && expanded);
    const readmeId = 'readme-' + encodeURIComponent(fullName);
    const titleId = 'project-title-' + encodeURIComponent(fullName);
    const tone = normalizeProjectCategory(project.category);
    const categoryLabel = tone === 'other' ? '更多领域' : categoryNames[tone];
    const avatarUrl = githubOwnerAvatarUrl(owner);
    const description = featured
        ? String(project.description_zh || '').trim() || buildProjectDescription(project)
        : buildProjectDescription(project);
    const highlights = featured ? readmeHighlights(project.readme_summary_zh) : [];
    const updated = timeAgo(project.last_updated);
    const tags = (project.topics || []).slice(0, 3).map(topic =>
        '<button type="button" class="tag" data-topic="' + escapeHtml(topic) + '" title="筛选标签 ' + escapeHtml(topic) + '">' + escapeHtml(topic) + '</button>').join('');
    const readmeLabel = summary ? '展开摘要' : project.translation_status === 'failed' ? '摘要生成失败' : '暂无中文摘要';
    const url = escapeHtml(safeExternalUrl(project.repo_url));
    return [
        '<div class="project-story">',
        '<div class="card-header"><div class="project-identity">',
        '<span class="project-mark" data-tone="' + tone + '" aria-hidden="true"><span class="project-monogram">' + escapeHtml(monogram) + '</span>',
        avatarUrl ? '<img class="project-avatar" data-avatar-src="' + escapeHtml(avatarUrl) + '" alt="" width="50" height="50" loading="' + (featured ? 'eager' : 'lazy') + '" decoding="async" referrerpolicy="no-referrer">' : '',
        '</span>',
        '<div class="card-repo"><h2 id="' + escapeHtml(titleId) + '"><a href="' + url + '" target="_blank" rel="noopener noreferrer" aria-label="在 GitHub 查看 ' + escapeHtml(fullName) + '">' + escapeHtml(name) + '</a></h2>',
        '<div class="repo-byline"><span class="repo-owner">' + escapeHtml(owner || '开源项目') + '</span>',
        '<span class="repo-category">' + escapeHtml(categoryLabel) + '</span>',
        project.is_new ? '<span class="badge-new">新收录</span>' : '',
        '</div></div></div><div class="card-actions">',
        '<button type="button" class="icon-button btn-favorite' + (project.is_favorited ? ' favorited' : '') + '" data-action="favorite" aria-pressed="' + Boolean(project.is_favorited) + '" title="' + (project.is_favorited ? '取消收藏' : '收藏项目') + '" aria-label="' + (project.is_favorited ? '取消收藏 ' : '收藏 ') + escapeHtml(fullName) + '">' + icon('bookmark') + '</button></div></div>',
        '<p class="card-description" title="' + escapeHtml(description) + '">' + escapeHtml(description) + '</p>',
        renderProjectMeta(project),
        '<div class="card-tags">' + tags + '</div>',
        project.recommendation_reason ? '<div class="rec-reason">' + icon('sparkles') + '<span>' + escapeHtml(project.recommendation_reason) + '</span></div>' : '',
        '</div>',
        highlights.length ? '<aside class="project-highlights" aria-label="' + escapeHtml(name) + ' 项目速览"><h3>项目速览</h3><ul>' + highlights.map(point => '<li>' + escapeHtml(point) + '</li>').join('') + '</ul></aside>' : '',
        '<div class="card-footer"><div class="card-footer-actions">',
        '<button class="card-read" type="button" data-action="reader" aria-haspopup="dialog" aria-controls="reader-modal" aria-label="阅读 ' + escapeHtml(fullName) + '">' + icon('book') + '<span>阅读项目</span></button>',
        '<button class="readme-toggle" type="button" data-action="readme" aria-expanded="' + isExpanded + '" aria-controls="' + escapeHtml(readmeId) + '"' + (summary ? '' : ' disabled') + '><span class="readme-label">' + (isExpanded ? '收起摘要' : readmeLabel) + '</span>' + (summary ? icon('chevron') : '') + '</button>',
        '<button type="button" class="card-chat" data-action="chat" aria-label="向 AI 了解 ' + escapeHtml(fullName) + '">' + icon('sparkles') + '<span>问 AI</span></button>',
        '</div><span class="card-time">' + (updated ? '更新于 ' + updated : '') + '</span></div>',
        '<div id="' + escapeHtml(readmeId) + '" class="readme-content' + (isExpanded ? ' expanded' : '') + '"><div class="readme-text">' + summary + '</div></div>',
    ].join('');
}
