# GitHub Trending Viewer

本地运行的 GitHub 热门项目中文浏览器。后端是 FastAPI + SQLite，前端是静态 HTML/CSS/JS，默认通过 Docker 暴露在 `http://localhost:8098`。

项目结构、已修复问题和后续建议见 [2026-09-12 项目检查与优化记录](docs/project-review-2026-09-12.md)。最新界面调整见 [2026-09-13 阅读体验与视觉优化](docs/reading-experience-2026-09-13.md)。

## 浏览与界面

页面采用顶部导航、横向分类与开放式项目阅读区，使用本地系统字体。未筛选的“发现”首页以一个宽幅项目和 README 速览作为阅读起点，其余项目以轻量双列排版展示，手机自动切换为单列。也可以切换到紧凑列表，显示方式会保存在当前浏览器中；语言与 Star 条件收纳在“筛选”面板内。

浅色模式使用银灰页面底色与连续白色阅读区，搭配低饱和强调色和较轻的页头字重。重点项目通过深蓝速览面板突出真实 README 内容；分类色保留在导航、标签和项目标识中。仓库标题优先使用本地 Bahnschrift，正文增加行距，辅助文字更清晰。深色模式使用对应的深色阅读面与分类配色。

项目卡片的“阅读项目”会打开专注阅读窗口，完整展示介绍与中文摘要，支持标准／大字号、原文介绍、GitHub 链接与项目问答。字号会保存在当前浏览器中；关闭阅读窗口后保留项目库位置和键盘焦点。原有“展开摘要”仍可直接在卡片内阅读，支持标题、加粗、行内代码与列表。

桌面端分类与筛选栏在滚动时固定于导航下方，便于连续浏览；普通卡片底部操作按行对齐。手机端收起重点项目的重复速览，将阅读入口提前，阅读窗口内容独立滚动，操作按钮始终可见。

分类采用固定配色：人工智能为柔紫、实用工具为青绿、开发工具为蓝色、更多领域为琥珀，贯穿分类导航、项目标签与重点区，并适配浅色和深色主题；搜索、收藏等操作仍使用用户选择的强调色。项目标识优先显示 GitHub 作者或组织的公开头像，普通项目按需加载；加载期间或失败时保留本地字母标识，不影响项目浏览。

页头以静态代码分支线稿点缀，重点项目保留细窄分类色标和轻量边缘。装饰不加载额外资源、不参与键盘导航；按钮轻按反馈遵循系统的减少动态效果偏好。

本地 Docker 只读挂载 `app/` 和 `static/`，数据仍单独保存在 `data/`。修改前端后刷新页面即可看到效果；修改后端后运行 `docker compose restart github-trending`。首次安装或依赖变更仍需构建镜像；已有镜像且只更新代码时，可运行 `docker compose up -d --no-build --pull never`，无需连接镜像仓库。

- **发现**：浏览整个项目库，或进入人工智能、实用工具、开发工具等分类。
- **搜索范围**：项目库搜索支持仓库名、原文、中文简介、README 摘要和标签；切换到 GitHub 后，按 Enter 或点击搜索发起在线查询。
- **筛选与排序**：支持语言、Star 数量门槛，以及综合、Star 总数、增长、最近更新和最近收录排序。收藏页面同样支持搜索和筛选。
- **收藏与推荐**：点击书签图标收藏项目；推荐页根据收藏生成推荐理由，并支持在推荐结果中继续筛选。
- **显示与状态**：点击顶部设置图标或页脚数据状态打开面板，查看翻译进度、连接诊断，切换浅色、深色、跟随系统和强调色。
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

翻译、AI 推荐和项目问答都通过 `app/ai_client.py` 访问 OpenAI-compatible 接口。后续更换模型、调整代理、超时或错误处理时，优先改这个统一客户端，避免不同功能各自维护一套模型请求逻辑。

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
