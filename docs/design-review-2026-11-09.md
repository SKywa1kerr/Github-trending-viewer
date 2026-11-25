# 2026-11-09 页面与本地翻译改进

沿用已有 FastAPI、原生 JavaScript 和 Framed sheet 设计方向，seed `1188424797`，保留 Geist 与分支品牌标识，无重抽。基于工作区现有未提交的改动继续优化，没有重置旧工作。界面回答的首要问题仍是“哪个项目值得继续读？”

## 本次视觉调整

- 标题从 22px 提高到 28px，手机保持 24px；项目名从 18px 提高到 20px，阅读焦点为 26px。
- 桌面内容边距从 24px 改为 32px，卡片间距为 20px。1440px 下宽度闭合：216px 导航 + 1216px 工作区 + 8px 外边距；工作区内部 2 + 64 + 565 + 20 + 565 = 1216。
- 库概况成为一个完整区域，翻译覆盖率从实际总量计算。空库不显示伪造百分比，进度为 0。
- 阅读焦点使用浅蓝灰表面，深色模式使用中性灰；左右两列更平衡，README 要点不再用“为什么值得读”暗示人工评审。
- 调整卡片标题、正文行距、操作栏与头像间距。阅读仍为主要动作，搜索使用描边次级按钮。
- 回到顶部从页面右下角移至顶部工具栏，消除手机滚动时覆盖卡片操作的情况。
- 设置新增中文翻译方式、模型与状态，说明已有译文保存在本地。

产品面孔来自蓝灰框架、分支标识和仓库身份；特色元素是实际项目的阅读焦点及其 README 要点。数据来自已有数据库副本：357 个项目、357 篇译文、2 个收藏。无虚构项目、统计、译文或新素材。外部头像保留已有首字母降级。

## 视觉复核

ROUND 1

Seen in one second: 中文开源项目库，推荐项目及其用途先被看到。

Idea (one sentence): 将仓库的中文简介与 README 要点变成首页的阅读入口。

Live thing: 搜索、筛选、收藏和完整阅读器。

Layout words by section: shell=浅色框架 / overview=并列数据 / spotlight=双栏阅读 / projects=双列卡片 / phone=单列阅读。

Scores: design 7.8 · usability 8.2 · creativity 7.2 · content 8.0 → overall 7.9（主观设计自评）。

Caps applied: 应用界面规则，不套用营销页面的图片数量或动画下限。

Top three problems (most visible first), each with the screenshot it shows in and the fix:

1. 手机长页的回顶浮钮覆盖“问 AI”（首轮 mobile-page-02）：改到顶部工具栏。
2. 搜索和阅读都为黑色主按钮（首轮 desktop-light）：恢复搜索描边，保留阅读的主动作权重。
3. 长摘要让页面滚动较长（tablet-page-01）：保留浏览/紧凑列表切换，不截断完整阅读器内容。此项为内容密度取舍，未删除项目。

ROUND 2

Seen in one second: 先看推荐项目，再浏览项目库，翻译覆盖率可直接辨识。

Idea (one sentence): 仓库内容决定首页重点，颜色集中在阅读焦点与真实数据。

Live thing: 同上，所有既有交互通过真实浏览器检查。

Layout words by section: 与第一轮一致，回顶动作归入工具栏。

Scores: design 8.0 · usability 8.7 · creativity 7.2 · content 8.0 → overall 8.1（主观设计自评）。

Caps applied: 无应用规则违例。

Remaining limitations: 部分头像依赖 GitHub 网络；较长的中文摘要仍会增加浏览高度，可使用紧凑列表；现有数据最后抓取于 2026-10-05，界面明确显示需更新。

## 验证证据

| 检查 | 结果 |
| --- | --- |
| Python 全量测试 | 118 passed |
| 前端测试 | 34 passed |
| 真实浏览器验收 | 6 组通过，覆盖浅深色各 1440/768/390px |
| 设计检查器，修改前 | 0 FAIL / 0 WARN |
| 设计检查器，最终版本 | 0 FAIL / 0 WARN |
| 源码设计检查 | 0 FAIL / 4 WARN |
| JavaScript 语法、git diff --check | 通过 |
| 可选 Ollama Compose 配置 | config --quiet 通过 |

保留的四个源码提示：两处阴影仅用于浮动筛选和 dialog；分类小标签用于导航分组；六个破折号代表未加载的数值。没有关闭检查器规则。

已查看最终检查器列出的全部九张截图，以及浅深色首屏、手机设置、阅读器和列表摘要。截图及报告位于 `.taste-skill/review-20261109/after/`，浏览器交互截图位于 `.taste-skill/review-20261109/final/`，数据证据位于 `.taste-skill/review-20261109/browser-qa.json`。

测试使用 `http://127.0.0.1:8099` 和独立数据库副本，未启动后台抓取/翻译。沙箱内专项浏览器脚本发生 CDP 初始化超时；获批在沙箱外运行后，两轮六组交互全部通过。应用按既有方式直接提供静态资源，无前端打包步骤。

## 本地翻译范围

增加 Ollama 原生提供方、结构化输出、单并发、独立超时、安装模型探测，绕过远程代理/频率/Token 预算。连接失败、截断与空输出进入重试并保留已有译文。模型来源与名称写入数据库；源内容签名一致时复用缓存。

没有下载模型、切换 `.env` 或启用模型服务。当前 Docker 服务未运行。测试使用模拟 HTTP；真实模型的译文质量、速度和 GPU 部署仍需安装后验证。项目问答与 AI 推荐仍为远程功能。

启用方法和免费离线方案比较见 [本地翻译指南](local-translation.md)。
