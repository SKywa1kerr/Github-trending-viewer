# GitHub Trending Viewer

本地运行的 GitHub 热门项目中文浏览器。后端是 FastAPI + SQLite，前端是静态 HTML/CSS/JS，默认通过 Docker 暴露在 `http://localhost:8098`。

项目结构、已修复问题和后续建议见 [2026-09-12 项目检查与优化记录](docs/project-review-2026-09-12.md)。最新界面调整见 [2026-09-13 阅读体验与视觉优化](docs/reading-experience-2026-09-13.md)。

2026-10-29 对页面进行了整体重构，设计及验证记录见 [页面设计重构](docs/design-refactor-2026-10-29.md)。界面采用中性配色、紧凑导航和项目阅读区，字体与 GSAP 动画库随项目本地加载。阅读窗口支持真实滚动进度、字号切换、固定操作栏，并遵循系统的减少动态效果设置。

2026-10-30 使用 design-taste-frontend 与 GSAP 进一步调整看板，采用固定左侧导航和独立工作区，增加常用排序入口、收藏概况与数据快照提示。设计与验收记录见 [看板设计优化](docs/design-dashboard-2026-10-30.md)。

2026-11-24 界面改为 Apple 官网式的版式：顶部半透明导航条取代左侧栏（窄屏仍为抽屉），浅灰底配白色大圆角卡片，黑灰双色大标题、胶囊按钮和单一蓝色强调，“今日首推”为一张深色主卡片；深色主题为纯黑底配深灰卡片。界面文字使用本地分发的 Geist 可变字体与 Noto Sans SC（思源黑体），不再使用衬线字体。强调色为蓝色、橙色、青绿、琥珀、玫红五种，默认蓝色；下文较早的配色、字体与侧栏描述以此为准。

2026-11-25 体验打磨：当前分类、搜索与筛选写入地址栏，可刷新、收藏为书签或前进后退；取消收藏可撤销；阅读窗口可用按钮或 ← → 连续翻阅项目；主题在首屏绘制前生效；手机首屏更早露出项目。记录见 [体验打磨](docs/design-polish-2026-11-25.md)。

## 浏览与界面

页面采用左侧导航和独立项目工作区，使用本地分发的 Geist 字体及系统中文字体。未筛选的“发现”首页以“阅读焦点”和两个真实 README 要点作为阅读起点，其余项目以双列排版展示，平板和手机自动切换为单列。也可以切换到紧凑列表，显示方式会保存在当前浏览器中。综合推荐、增长最快、最近收录可直接切换；语言、Star 门槛与完整排序选项收纳在“筛选”面板内。

浅色模式使用中性蓝灰导航框架和白色工作区，深色模式使用中性黑灰层次。Geist 字体用于仓库名和界面文字，中文由本地系统字体补全。首页概况显示真实项目总数、已完成摘要、收藏数量与数据更新时间；重点项目将介绍和 README 要点并排呈现。

项目卡片的“阅读项目”会打开专注阅读窗口，完整展示介绍与中文摘要，支持标准／大字号、原文介绍、GitHub 链接与项目问答。字号会保存在当前浏览器中；关闭阅读窗口后保留项目库位置和键盘焦点。原有“展开摘要”仍可直接在卡片内阅读，支持标题、加粗、行内代码与列表。

左侧导航、顶部位置栏和项目排序栏在滚动时保持可用。列表视图将操作集中在右侧，展开摘要位于整行下方。平板和手机将导航收进抽屉，支持 Escape 关闭、键盘焦点管理和遮罩关闭；手机收起重点项目的重复速览，保留单列阅读和全屏阅读窗口。

分类通过清晰文字与中性选中状态区分；用户选择的强调色集中用于 Star 增长与阅读进度。项目标识优先显示 GitHub 作者或组织的公开头像，普通项目按需加载；加载期间或失败时保留本地字母标识，不影响项目浏览。

品牌采用本地 SVG 分支标识。GSAP 为导航抽屉、弹窗、筛选面板和按钮提供轻量操作反馈；减少动态效果模式下直接呈现内容。字体与动效库本地分发，用户无需连接 CDN。

本地 Docker 只读挂载 `app/` 和 `static/`，数据仍单独保存在 `data/`。修改前端后刷新页面即可看到效果；修改后端后运行 `docker compose restart github-trending`。首次安装或依赖变更仍需构建镜像；已有镜像且只更新代码时，可运行 `docker compose up -d --no-build --pull never`，无需连接镜像仓库。

- **发现**：浏览整个项目库，或进入人工智能、实用工具、开发工具等分类。
- **搜索范围**：项目库搜索支持仓库名、原文、中文简介、README 摘要和标签；切换到 GitHub 后，按 Enter 或点击搜索发起在线查询。
- **筛选与排序**：支持语言、Star 数量门槛，以及综合、Star 总数、增长、最近更新和最近收录排序。收藏页面同样支持搜索和筛选。
- **收藏与推荐**：点击书签图标收藏项目；推荐页根据收藏生成推荐理由，并支持在推荐结果中继续筛选。
- **显示与状态**：点击左侧“显示与状态”、首页数据快照或页脚数据状态打开面板，查看翻译进度、连接诊断，切换浅色、深色、跟随系统和强调色。
- **快捷操作**：`Ctrl/Cmd + K` 或 `/` 聚焦搜索；弹窗支持 Escape 关闭。项目问答支持流式回答、停止回答和 `Shift + Enter` 换行。

筛选发生变化时会取消过时的列表请求，避免快速切换分类后出现旧结果。中文输入法组词期间不会发起搜索。

## 快速启动

1. 首次启动会自动创建本地 `.env`。也可以手动复制配置模板：

   ```powershell
   Copy-Item .env.example .env
   ```

2. 编辑 `.env`，至少填入：

   ```env
   API_KEY=your-api-key
   ```

   如果你的 Windows 代理端口是 `7897`，默认配置已经适配 Docker：

   ```env
   APP_HTTP_PROXY=http://host.docker.internal:7897
   APP_HTTPS_PROXY=http://host.docker.internal:7897
   ```

   默认访问端口是 `8098`，如需修改：

   ```env
   APP_HOST_PORT=8098
   ```

   数据超过 72 小时未更新时，页面会显示诊断提示。可调整：

   ```env
   DATA_STALE_HOURS=72
   ```

3. 启动：

   ```powershell
   .\start.ps1 -Build
   ```

后续普通启动可以直接运行：

   ```powershell
   .\start.ps1
   ```

也可以双击 `launch.vbs`，它会在后台调用 `start.ps1` 并打开 Edge app 窗口。

## 诊断和日志

```powershell
.\start.ps1 -Doctor
.\start.ps1 -Logs
.\doctor.ps1
```

`doctor.ps1` 会检查 Docker、Compose 配置、`.env`、本地代理端口、应用状态接口和健康检查接口。它不会输出 `.env` 中的密钥值。

## 翻译速度

希望翻译不再依赖外部 AI 服务，可使用新增的 **Ollama 本地翻译**。支持本地生成中文简介与 README 摘要，不需要 API key，不走远程代理、限流和 Token 预算；旧译文继续保存在 SQLite 中。项目提供可选的 `docker-compose.ollama.yml`，安装步骤、硬件取舍和 Argos 对比见 [本地翻译指南](docs/local-translation.md)。当前默认仍为已有远程配置，启用本地模式需要先安装并下载模型。

翻译速度主要受模型接口响应时间、服务端限流、README 输入长度影响。默认参数偏向稳定，不会把临时限流快速刷成失败：

```env
TRANSLATION_CONCURRENCY=2
TRANSLATION_BATCH_SIZE=8
TRANSLATION_README_CHARS=1600
TRANSLATION_MAX_OUTPUT_TOKENS=700
TRANSLATION_REQUEST_INTERVAL_SECONDS=6.0
MAX_REQUESTS_PER_MINUTE=10
MAX_DAILY_TOKENS=1000000
```

默认会把模型请求间隔控制在至少 `6` 秒，避免触发共享接口的 `429 Too Many Requests`。如果长时间没有 429，可以把 `TRANSLATION_REQUEST_INTERVAL_SECONDS` 逐步调到 `5`、`4`；如果 429 增多，优先调大这个值，而不是提高并发。

## 模型调用

远程翻译、AI 推荐和项目问答通过 `app/ai_client.py` 访问 OpenAI-compatible 接口。本地翻译由 `app/translation_provider.py` 直接访问 Ollama 原生接口，与远程模型配置独立；启用本地翻译不会自动改变问答和推荐的提供方。

当前默认模型是交大"致远一号"网关上的 Qwen（`qwen3.8-27b`）。相关配置：

```env
API_ENDPOINT=https://models.sjtu.edu.cn/api/v1/chat/completions
API_MODEL=qwen
AI_JSON_MODE=1
AI_MODEL_CHECK=1
```

- `API_MODEL` 建议填网关别名 `qwen`，而不是带版本的 `qwen3.8-27b`。带版本的部署名经常处于冷却状态并返回 `429 No deployments available`，别名会自动路由到可用部署。
- `AI_JSON_MODE=1` 时，翻译和推荐请求会附带 `response_format=json_object`，输出更稳定也更快。接口若不支持会自动退回普通请求。
- `AI_MODEL_CHECK=1` 时，`/api/health` 会调用网关的 `/models` 确认 `API_MODEL` 仍然存在，模型下线后页面的"系统诊断"会直接提示。结果缓存 10 分钟。
- 客户端会自动剥离思考模型可能输出的 `<think>` 段落，并忽略 `reasoning_content` 字段，切换到推理模型也不需要改解析逻辑。

查看网关当前可用模型：

```powershell
Invoke-RestMethod -Uri "https://models.sjtu.edu.cn/api/v1/models" -Headers @{ Authorization = "Bearer $env:API_KEY" } | Select-Object -ExpandProperty data | Select-Object id
```

## Star 趋势

每次抓取都会把当天的 star 数写入 `star_history` 表。卡片上的星数旁会显示最近 30 次记录的迷你趋势线，绿色上升、红色下降、灰色持平；不足两条记录时不显示。数据通过 `GET /api/star-history?ids=1,2,3&points=30` 批量读取。

## 本地测试

```powershell
python -m pytest -q
node tests/test_frontend_security.mjs
node tests/test_frontend_helpers.mjs
node tests/test_responsive_css.mjs
node tests/test_library_state.mjs
node tests/test_project_description.mjs
node tests/test_card_presentation.mjs
node tests/test_reader.mjs
node --check static/js/app.js
node --check static/js/library.mjs
node --check static/js/cards.mjs
node --check static/js/reader.mjs
```

## 常用命令

```powershell
docker compose up -d --build
docker compose logs -f github-trending
docker compose down
```

## 敏感文件

`.env`、`.env.*`、数据库和 `data/` 已被 `.gitignore` 与 `.dockerignore` 排除。不要把真实 API key 写入 `.env.example`、README 或代码。
