import { escapeHtml, formatReadmeHtml } from './sanitize.mjs?v=42';
import { categoryNames, formatStars, timeAgo } from './library.mjs?v=40';
import { normalizeProjectCategory, projectIdentity } from './cards.mjs?v=42';

export function estimateReadingMinutes(value) {
    const text = String(value || '').trim();
    if (!text) return 0;
    const han = text.match(/\p{Script=Han}/gu) || [];
    const words = text.replace(/\p{Script=Han}/gu, ' ').match(/[\p{L}\p{N}]+/gu) || [];
    return Math.max(1, Math.ceil(han.length / 350 + words.length / 180));
}

// The reader uses the complete saved text, independent of card preview clamping.
export function renderProjectReading(project = {}) {
    const { owner, name } = projectIdentity(project.repo_full_name);
    const category = normalizeProjectCategory(project.category);
    const categoryLabel = category === 'other' ? '更多领域' : categoryNames[category];
    const description = String(project.description_zh || '').trim() || String(project.description || '').trim();
    const summary = String(project.readme_summary_zh || '').trim();
    const original = String(project.description || '').trim();
    const updated = timeAgo(project.last_updated);
    const minutes = estimateReadingMinutes(description + '\n' + summary);
    const facts = [owner, categoryLabel, formatStars(project.stars) + ' Star', project.language, updated ? '更新于 ' + updated : ''].filter(Boolean);
    const emptySummary = project.translation_status === 'failed'
        ? '中文摘要暂未生成成功，可以在 GitHub 查看项目文档。'
        : '这个项目暂时没有中文摘要，可以在 GitHub 查看项目文档。';
    return '<header class="reader-introduction">'
        + '<h2 id="reader-title" tabindex="-1">' + escapeHtml(name) + '</h2>'
        + '<ul class="reader-facts">' + facts.map(fact => '<li>' + escapeHtml(fact) + '</li>').join('') + '</ul>'
        + (description ? '<p class="reader-description">' + escapeHtml(description) + '</p>' : '')
        + '</header><section class="reader-summary" aria-labelledby="reader-summary-title">'
        + '<div class="reader-section-heading"><h3 id="reader-summary-title">中文摘要</h3>'
        + (summary && minutes ? '<span>约 ' + minutes + ' 分钟阅读</span>' : '') + '</div>'
        + '<div class="reader-prose">' + (summary ? formatReadmeHtml(summary) : '<p class="reader-empty">' + emptySummary + '</p>') + '</div>'
        + '</section>'
        + (original && original !== description ? '<details class="reader-original"><summary>查看原文介绍</summary><p>' + escapeHtml(original) + '</p></details>' : '');
}
