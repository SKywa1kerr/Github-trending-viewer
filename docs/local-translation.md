# 免费、本地运行的中文翻译

本项目的“翻译”同时生成中文简介和 README 要点。因此推荐用 **Ollama + Qwen3 8B**：本地完成翻译和摘要，不依赖第三方 AI 网关的额度、排队、限流或模型下线。模型文件下载一次后保存在电脑上；推理没有 API 费用，仍占用显存、内存与电力。GitHub 项目抓取和 README 下载仍需要联网。

本次检测的设备为 RTX 5070 Ti Laptop GPU，显存约 12GB。`qwen3:8b` 的 Q4_K_M 模型文件约 5.2GB，适合作为起点；运行时还需要上下文和计算缓存，模型文件大小不等于总显存占用。应用将本地翻译限制为单并发、4096 上下文，关闭思考输出。实际速度和译文质量需要安装模型后实测。

## 方案比较

| 方案 | 翻译 | README 摘要 | 日常外部服务依赖 | 成本与取舍 |
| --- | --- | --- | --- | --- |
| Ollama + 本地 Qwen | 支持 | 支持 | 无需外部 AI | 无 API 费；需本机算力，最适合本项目 |
| Argos Translate | 支持，需安装英中语言包 | 不提供生成式摘要 | 无需外部翻译服务 | 开源，可在 CPU 使用；技术术语与长文本需检查质量 |
| 自托管 LibreTranslate | 支持，底层使用 Argos | 不提供生成式摘要 | 无需外部翻译服务 | 服务由自己维护；公共网站并不等于永久免费接口 |
| 浏览器内置翻译 | 依浏览器、语言与设备支持 | 不直接生成本项目所需摘要 | 各浏览器实现不同 | 不适合作为后端持久中文缓存的统一来源 |

## 当前使用：Windows Ollama + 直接运行（无需 Docker）

本机已安装 Windows 版 Ollama 和 `qwen3:8b`（权重来自 ModelScope 的 Qwen3-8B Q4_K_M，套用官方对话模板）。双击 `launch.vbs` 或运行 `start-local.ps1` 即可：脚本读取 `.env`，默认使用本地翻译，必要时自行启动 Ollama 服务，并在 `http://127.0.0.1:8098` 打开应用。`start-local.ps1 -Stop` 停止，`-Logs` 查看日志。不要与 Docker 版同时运行。

## 备选：沿用 Docker，一次部署本地翻译

需要 Docker Desktop 使用 WSL2 Linux 容器，并能使用 NVIDIA GPU。原应用仍用 `docker-compose.yml`；额外文件仅在命令中显式指定时启用。

在项目目录运行：

```powershell
# 先启动模型服务，不提前启动翻译队列。
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d ollama

# 首次需要下载约 5.2GB 模型。此后保存在命名卷，不必重复下载。
docker compose -f docker-compose.yml -f docker-compose.ollama.yml exec ollama ollama pull qwen3:8b

# 启动应用。覆盖文件会自动选择本地翻译，无需 API_KEY。
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d --build
```

访问 `http://127.0.0.1:8098`，在“设置 → 中文翻译”确认显示 `Ollama · 本地翻译 / 已就绪`。已有译文不会因切换提供方而全部重译；待翻译的项目会使用本地模型。之前失败的任务可点击“重试失败翻译”。

后续启动继续使用这两个 Compose 文件。单独运行 `start.ps1` 或只使用基础 Compose 文件会回到基础配置。模型服务不向宿主机暴露端口，只供同一 Compose 网络内的应用访问；设置 `OLLAMA_NO_CLOUD=1` 关闭云端能力。

停止服务使用相同的两个文件加 `down`；**不要加 `-v`**，否则会删除模型卷，需要重新下载。要恢复原远程翻译，使用基础 Compose 启动应用即可。

## 已安装 Windows Ollama 的替代接法

下载并安装 [Ollama](https://ollama.com/download/windows)，运行：

```powershell
ollama pull qwen3:8b
```

如果 Python 应用直接运行在 Windows，启动进程前设置环境变量：

```powershell
$env:TRANSLATION_PROVIDER = 'ollama'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_MODEL = 'qwen3:8b'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8098
```

直接运行 Python 不会自动加载 `.env`。如果应用在 Docker，需把上述三项写入 `.env`，其中地址改为 `http://host.docker.internal:11434`，然后重建应用容器；Windows Ollama 还必须监听容器可达的地址。Ollama 默认只监听回环地址，若改 `OLLAMA_HOST` 为 `0.0.0.0:11434`，应通过防火墙限定访问。为避免这一额外配置，优先使用上面的独立 Compose 模型服务。

## 已实现的可靠性措施

- 本地请求使用原生 `/api/chat` 与 JSON schema，输出仍进入现有数据库与阅读器。
- 本地调用不携带远程 API 密钥，也不继承系统 HTTP 代理；不会自动切回外部服务。
- 本地调用绕过远程 Token 预算和请求频率限制，单并发减少显存压力。
- 生成截断、空结果、模型缺失、连接失败会进入重试，不覆盖已有中文内容。
- 源内容签名未变时复用已有译文；数据库记录实际使用的 `ollama` 和本地模型名。
- 健康检查只查询已安装模型列表，不会因为打开设置而生成文本或加载模型。

**范围：这次只让“翻译与摘要”独立。项目问答、AI 推荐仍使用原有远程模型配置。** 缺少远程密钥时，设置会说明这些功能未配置，同时单独报告本地翻译是否就绪。

本次验证覆盖模拟 HTTP 响应、队列重试、缓存保留、模型探测和设置展示。当前电脑尚未安装 Ollama，也未下载模型，因此不能把接口测试结果当作真实模型的速度或质量验收。

## 官方参考

- [Ollama 原生聊天 API](https://docs.ollama.com/api/chat)：JSON schema、关闭思考与生成参数。
- [Qwen3 8B 模型](https://ollama.com/library/qwen3:8b)：模型尺寸、量化规格和 Apache 2.0 许可证。
- [Ollama FAQ](https://docs.ollama.com/faq)：本地运行、上下文、网络监听与关闭云功能。
- [Argos Translate](https://github.com/argosopentech/argos-translate)：离线翻译与语言包。
