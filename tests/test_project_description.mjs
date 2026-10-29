import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildProjectDescription } from '../static/js/library.mjs';
import { escapeHtml } from '../static/js/sanitize.mjs';

test('short introductions use two existing summary points for more context', () => {
  assert.equal(buildProjectDescription({
    description_zh: '开放数据平台。',
    readme_summary_zh: '整合公共与私有数据源，帮助分析师开展研究。\n支持将数据接入 AI 助手与研究仪表盘。\n提供多种安装方式。',
  }), '整合公共与私有数据源，帮助分析师开展研究。 支持将数据接入 AI 助手与研究仪表盘。');
});

test('an already detailed description is kept intact', () => {
  const description = '这是一段已经足够详细的项目介绍。'.repeat(10);
  assert.equal(buildProjectDescription({
    description_zh: description,
    readme_summary_zh: '更长的摘要内容。'.repeat(30),
  }), description);
});

test('a shorter summary does not replace a more informative description', () => {
  assert.equal(buildProjectDescription({
    description_zh: '面向分析师、量化交易员和 AI 代理的开放数据平台。',
    readme_summary_zh: '开放数据。',
  }), '面向分析师、量化交易员和 AI 代理的开放数据平台。');
});

test('summary previews skip headings and remove list and emphasis markers', () => {
  assert.equal(buildProjectDescription({
    readme_summary_zh: '## 项目简介\r\n\r\n1. **本地优先**，数据留在设备上。\r\n2）支持 `CLI` 与桌面应用。\r\n3. 第三条仍可在完整摘要里阅读。',
  }), '本地优先，数据留在设备上。 支持 CLI 与桌面应用。');
  assert.equal(buildProjectDescription({readme_summary_zh: '- 支持离线使用。\n• 无需注册。'}), '支持离线使用。 无需注册。');
});

test('missing and blank translations fall back without inventing content', () => {
  assert.equal(buildProjectDescription({description_zh: '  ', description: ' An offline tool. '}), 'An offline tool.');
  assert.equal(buildProjectDescription({readme_summary_zh: '一个支持离线使用的工具。'}), '一个支持离线使用的工具。');
  assert.equal(buildProjectDescription({description: '  ', readme_summary_zh: '\n'}), '这个项目暂时没有提供简介。');
  assert.equal(buildProjectDescription(), '这个项目暂时没有提供简介。');
});

test('summary text remains plain text and is escaped at the rendering boundary', () => {
  const description = buildProjectDescription({readme_summary_zh: '<img src=x onerror="alert(1)">\n用于测试文本转义。'});
  assert.match(escapeHtml(description), /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
  assert.doesNotMatch(escapeHtml(description), /<img/);
});
