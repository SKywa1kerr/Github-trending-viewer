# GitHub Trending Viewer

本地运行的 GitHub 热门项目中文浏览器。后端是 FastAPI + SQLite，前端是静态 HTML/CSS/JS，默认通过 Docker 暴露在 `http://localhost:8098`。

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

## 常用命令

```powershell
docker compose up -d --build
docker compose logs -f github-trending
docker compose down
```

## 敏感文件

`.env`、`.env.*`、数据库和 `data/` 已被 `.gitignore` 与 `.dockerignore` 排除。不要把真实 API key 写入 `.env.example`、README 或代码。
