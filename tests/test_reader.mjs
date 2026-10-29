import assert from 'node:assert/strict';
import { test } from 'node:test';
import { estimateReadingMinutes, renderProjectReading } from '../static/js/reader.mjs';
import { formatReadmeHtml } from '../static/js/sanitize.mjs';

test('the reader keeps complete descriptions and all summary paragraphs', () => {
    const description = '完整项目介绍。'.repeat(80);
    const summary = Array.from({ length: 12 }, (_, i) => `${i + 1}. 第 ${i + 1} 项能力。`).join('\n');
    const html = renderProjectReading({
        repo_full_name: 'team/reading-tool', category: 'devtools', description_zh: description,
        description: 'Original project description.', readme_summary_zh: summary, stars: 1500,
    });
    assert.ok(html.includes(description), 'reading must not reuse the clamped card preview');
    assert.match(html, /第 12 项能力。/);
    assert.match(html, /id="reader-title"[^>]*>reading-tool</);
    assert.match(html, /开发工具/);
    assert.match(html, /Original project description\./);
    assert.match(html, /中文摘要/);
});

test('missing translations have useful fallbacks without fabricated summaries', () => {
    const html = renderProjectReading({ repo_full_name: 'team/tool', description: 'Original only.' });
    assert.match(html, /Original only\./);
    assert.match(html, /暂时没有中文摘要/);
    assert.doesNotMatch(html, /分钟阅读|reader-original/);
    assert.match(renderProjectReading({ translation_status: 'failed' }), /暂未生成成功/);
    assert.match(renderProjectReading(), /未命名项目/);
});

test('reading estimates support Chinese, English, mixed text and empty content', () => {
    assert.equal(estimateReadingMinutes(''), 0);
    assert.equal(estimateReadingMinutes(null), 0);
    assert.equal(estimateReadingMinutes('一个简短介绍。'), 1);
    assert.equal(estimateReadingMinutes('中'.repeat(351)), 2);
    assert.equal(estimateReadingMinutes('word '.repeat(181)), 2);
    assert.equal(estimateReadingMinutes('中'.repeat(175) + 'word '.repeat(90)), 1);
});

test('README formatting exposes headings, emphasis, code and list points', () => {
    const html = formatReadmeHtml('## 快速了解\n**核心能力**与 `npm install`\n  1. 离线使用\n* 开放接口');
    assert.match(html, /<h3 class="readme-heading">快速了解<\/h3>/);
    assert.match(html, /<strong>核心能力<\/strong>/);
    assert.match(html, /<code>npm install<\/code>/);
    assert.match(html, /readme-point-num">1</);
    assert.match(html, /readme-point-num">•</);
});

test('remote text stays inert inside reader headings, facts and formatting', () => {
    const attack = '<img src=x onerror="alert(1)">';
    const html = renderProjectReading({
        repo_full_name: 'team/' + attack, description_zh: attack, description: '<script>alert(1)</script>',
        category: '__proto__', language: attack,
        readme_summary_zh: '## ' + attack + '\n**' + attack + '**\n`' + attack + '`\n- <svg onload=alert(1)>\n[x](javascript:alert(1))',
    });
    assert.doesNotMatch(html, /<(?:script|img|svg|iframe)\b|href="javascript:/);
    assert.match(html, /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
    assert.match(html, /更多领域/);
    assert.match(html, /<strong>&lt;img/);
    assert.match(html, /<code>&lt;img/);
});

test('inline code keeps literal emphasis markers instead of interpreting nested markup', () => {
    const html = formatReadmeHtml('`**literal**` and **emphasis**');
    assert.match(html, /<code>\*\*literal\*\*<\/code>/);
    assert.match(html, /<strong>emphasis<\/strong>/);
});
