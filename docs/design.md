# GitHub 热门项目中文浏览器 — 设计文档

## 概述

一个 Docker 部署的本地应用，自动抓取 GitHub 热门项目，通过大模型翻译为中文并总结 README，以精美卡片式界面展示，方便每日浏览发现优质项目。

## 目标用户

本地个人使用，关注 AI 方向为主，同时涵盖实用工具、开发工具等领域。

## 架构

```
Docker Compose
└── github-trending-viewer (单容器)
    ├── 后端 (Python FastAPI)
    │   ├── 定时任务：抓取 GitHub 数据
    │   ├── 翻译服务：调用 DeepSeek V3.2
    │   ├── REST API：为前端提供数据
    │   └── SQLite 数据库
    └── 前端 (静态文件，FastAPI 托管)
        └── HTML + CSS + JS 精美卡片界面
```

桌面快捷方式 → 无边框 Chrome/Edge 窗口 → localhost:8088

## 模块设计

### 1. 数据抓取模块

**数据来源：**

| 来源 | 说明 | 频率 |
|------|------|------|
| GitHub Trending | 每日/每周/每月热榜 | 每天 1 次 |
| GitHub Search API | 按关键词搜索项目 | 每天 1 次 |
| GitHub Topics | 预设话题下的热门项目 | 每天 1 次 |
| 自定义关键词 | 用户自行添加的关注词 | 每天 1 次 |

**预设板块及话题：**

- **AI（默认）**：artificial-intelligence, machine-learning, deep-learning, llm, large-language-model, gpt, agent, nlp, computer-vision, stable-diffusion
- **实用工具**：tool, productivity, utility, automation, self-hosted
- **开发工具**：developer-tools, devops, cli, framework, library

**抓取内容（每个项目）：**

- 仓库全名（owner/repo）
- 英文描述
- Star 总数
- 今日/本周/本月新增 Star（来自 Trending）
- 主要编程语言
- 话题标签（topics）
- README 内容（截取前 3000 字符，避免 token 浪费）
- 最近更新时间
- 仓库 URL

**排序综合评分（用于发现好用但不一定火的项目）：**

- Star 总数权重 30%
- 近期 Star 增长速度 30%
- 最近更新活跃度 20%
- 项目质量信号（有 README、有 topics、issue 活跃）20%

### 2. 大模型翻译模块

**API 配置：**

- API Endpoint: `https://models.sjtu.edu.cn/api/v1/chat/completions`（完整端点地址，代码中直接使用，不拼接路径）
- Model: `deepseek-chat`（DeepSeek V3.2 常规模式）
- 格式: OpenAI 兼容
- 请求频率：≤30 次/分钟（学校共享资源，留足余量）

**翻译任务：**

1. **项目描述翻译**：英文 description → 中文简介（1-2 句）
2. **README 摘要**：英文 README → 中文摘要（3-5 句，涵盖核心功能、使用场景、亮点）

**Prompt 设计：**

```
你是一个技术项目翻译助手。请将以下 GitHub 项目信息翻译为中文。

项目名：{repo_name}
项目描述：{description}
README 内容：{readme_content}

请返回 JSON 格式：
{
  "description_zh": "中文简介（1-2句）",
  "readme_summary_zh": "README 中文摘要（3-5句，涵盖核心功能、使用场景、亮点）"
}
```

**翻译策略：**

- 翻译结果缓存到数据库，相同项目不重复翻译
- 项目 README 有更新时才重新翻译
- 批量翻译时控制请求频率（≤30 次/分钟，给学校服务器留足余量）
- 单次更新预计翻译 30-50 个新项目，约消耗 10-15 万 token
- 设置每日 token 预算上限（15 万），超出则停止翻译，等下次更新
- 翻译失败时跳过该项目，保留英文描述，下次更新时重试

### 3. 数据存储

**SQLite 数据库，两张核心表：**

**projects 表：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| repo_full_name | TEXT UNIQUE | owner/repo |
| description | TEXT | 英文描述 |
| description_zh | TEXT | 中文简介 |
| readme_summary_zh | TEXT | README 中文摘要 |
| stars | INTEGER | Star 总数 |
| stars_gained | INTEGER | 新增 Star 数（根据 period 而定） |
| language | TEXT | 主要语言 |
| topics | TEXT | JSON 数组，话题标签 |
| category | TEXT | 板块分类 |
| repo_url | TEXT | 仓库链接 |
| score | REAL | 综合评分 |
| last_updated | TEXT | 仓库最后更新时间 |
| translated_at | TEXT | 翻译时间 |
| fetched_at | TEXT | 抓取时间 |

**keywords 表：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| keyword | TEXT UNIQUE | 关键词 |
| category | TEXT | 所属板块 |
| created_at | TEXT | 添加时间 |

### 4. 后端 API

**FastAPI 路由：**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 获取项目列表（支持分页、筛选、排序） |
| GET | `/api/projects/{id}` | 获取单个项目详情 |
| POST | `/api/refresh` | 手动触发刷新 |
| GET | `/api/status` | 获取最后更新时间、项目总数等状态 |
| GET | `/api/keywords` | 获取自定义关键词列表 |
| POST | `/api/keywords` | 添加自定义关键词 |
| DELETE | `/api/keywords/{id}` | 删除自定义关键词 |
| GET | `/api/categories` | 获取板块列表及项目数量 |

**筛选参数（`/api/projects`）：**

- `category`：板块筛选（`ai` / `tools` / `devtools` / `other`，对应前端显示名：AI / 实用工具 / 开发工具 / 其他热门）
- `language`：编程语言筛选
- `period`：抓取时间维度（`daily` / `weekly` / `monthly`，控制从哪个 Trending 页面抓取数据）
- `sort`：排序方式（`score` / `stars` / `stars_gained` / `updated`）
- `q`：搜索关键词
- `page` / `page_size`：分页

### 5. 前端界面

**设计风格：**

- 现代深色/浅色主题（支持切换）
- 圆角卡片 + 柔和阴影
- 平滑动画过渡
- 响应式布局

**页面布局：**

```
┌──────────────────────────────────────────────┐
│  GitHub 热门项目             [刷新] [主题切换] │
│  最后更新：2026-03-26 08:00                   │
├──────────────────────────────────────────────┤
│ [AI] [实用工具] [开发工具] [其他热门]           │
├──────────────────────────────────────────────┤
│ 语言: [全部]  时间: [今日]  排序: [综合]       │
│ 搜索: [___________________] [+ 添加关注词]    │
├──────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────┐ │
│ │ 12.3k (+580)                 Python      │ │
│ │ owner/repo-name                          │ │
│ │ 中文简介：这是一个xxx的项目...             │ │
│ │ ─────────────────────────────             │ │
│ │ README 摘要                  [展开/收起]   │ │
│ │ 这个项目主要用于...支持...亮点是...        │ │
│ │ ─────────────────────────────             │ │
│ │ #ai #llm #agent    更新于 2 小时前        │ │
│ └──────────────────────────────────────────┘ │
│                                              │
│ [加载更多...]                                │
└──────────────────────────────────────────────┘
```

**交互细节：**

- 卡片 hover 时轻微上浮 + 阴影增强
- README 摘要默认收起，点击展开，带平滑动画
- 点击项目名跳转 GitHub 仓库页面（新标签页打开）
- 标签可点击作为筛选条件
- 无限滚动加载更多项目
- 刷新按钮点击后显示加载状态
- 深色/浅色主题切换带过渡动画

### 6. Docker 部署

**docker-compose.yml 配置：**

```yaml
services:
  github-trending:
    build: ./github-trending-viewer
    container_name: github-trending
    ports:
      - "127.0.0.1:8088:8000"  # 仅本机访问
    volumes:
      - ./github-trending-data:/app/data
    environment:
      - API_ENDPOINT=https://models.sjtu.edu.cn/api/v1/chat/completions
      - API_KEY=${API_KEY}
      - API_MODEL=deepseek-chat
      - UPDATE_HOUR=8
      - TZ=Asia/Shanghai
    restart: unless-stopped
```

**敏感信息处理：**

- API key 通过 `.env` 文件配置，不硬编码
- `.env` 加入 `.gitignore`，Dockerfile 中不 COPY `.env`
- 提供 `.env.example` 作为模板

**首次启动：**

- 检测数据库为空时，立即触发一次抓取+翻译，无需等到 UPDATE_HOUR
- 抓取完成前，前端显示"正在初始化数据，请稍候..."加载页面

### 7. 桌面快捷方式

提供 `.vbs` 脚本：

- 检查 Docker 容器是否在运行，未运行则启动
- 等待服务就绪（轮询 `/api/status` 直到返回 200）
- 以 `--app` 模式打开 Chrome/Edge 访问 `http://localhost:8088`
- 窗口无地址栏和标签栏，看起来像独立应用

## 技术栈总结

| 层 | 技术 |
|----|------|
| 后端框架 | Python 3.11 + FastAPI |
| 数据库 | SQLite |
| 定时任务 | APScheduler |
| GitHub 数据 | httpx + BeautifulSoup (Trending) + GitHub REST API |
| 大模型调用 | httpx（OpenAI 兼容格式） |
| 前端 | HTML5 + CSS3 + Vanilla JS |
| 容器化 | Docker + Docker Compose |
| 桌面入口 | .vbs 脚本（无边框浏览器窗口） |

## 非功能需求

- API 调用频率限制在 30 次/分钟以内
- 每日 token 消耗控制在 15 万以内（超出自动停止）
- SQLite 使用 WAL 模式，避免读写冲突
- GitHub 数据抓取失败时使用缓存数据，不影响前端展示
- 页面首次加载时间 < 2 秒（数据已缓存）
- 支持 Windows 11 环境
