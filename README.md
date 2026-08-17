# 万径

万径是一套面向个性化学习场景的 AI 学习平台。它以课程、项目和学习资料为基础，通过文档理解、语义检索、多智能体协作和学习状态建模，为学习者生成对话辅导、笔记、测验、闪卡、思维导图、学习路径与综合资源包。


## 核心功能

- 课程与项目空间：组织课程、项目、书籍、学习资料和项目成员数据。
- 文档学习：上传、解析和检索学习材料，围绕文档进行问答与内容生成。
- AI 学习助手：支持上下文对话、引用来源、图片附件和流式响应。
- 学习资源生成：生成笔记、测验、闪卡、思维导图、学习计划及综合资源包。
- 个性化学习闭环：维护学习者画像、知识状态、知识图谱、学习路径、练习记录和干预结果。
- 多智能体编排：通过 Agent、Skill 和内部工具协同完成复杂学习任务，并记录运行事件和用量。
- 异步任务处理：使用 Redis 与 ARQ Worker 执行耗时生成任务，支持进度查询和流式状态更新。
- 编程练习：通过隔离的 Piston 服务运行和评测 Python、C++ 代码。
- 扩展能力：提供 PDF OCR、手写识别、文档翻译、语音输入、图片生成、联网搜索和数字人接口。
- 管理与运营：提供用户、课程、套餐、额度、订单、Agent 运行和审计管理能力。

部分 AI 与第三方能力需要在 `.env` 中配置相应服务凭据；未配置时不影响基础服务启动，但对应功能不可用。

## 技术架构

- 前端：React 19、TypeScript、Vite、TanStack Router、TanStack Query、Tailwind CSS。
- API：FastAPI、Pydantic、SQLAlchemy、Alembic。
- AI：LangChain、OpenAI 兼容接口、向量检索、多智能体编排。
- 数据：PostgreSQL、pgvector、本地文件存储。
- 异步任务：Redis、ARQ、独立 Worker。
- 代码执行：Piston 隔离运行服务。
- 部署：Docker Compose；生产环境可结合 Caddy 提供统一入口。

本地 `docker-compose.yaml` 会启动以下后端服务：

| 服务 | 用途 |
| --- | --- |
| `api` | 万径后端 API，端口 `8000` |
| `worker` | 异步生成任务 Worker |
| `migrate` | 启动时自动执行数据库迁移 |
| `db` | PostgreSQL 与 pgvector，本机端口 `5433` |
| `redis` | 任务队列与状态存储 |
| `piston` | Python、C++ 代码运行服务 |

前端默认使用本机 Node.js 启动，访问端口为 `3000`。

## 快速启动

### 环境要求

- Windows 10/11（使用一键启动脚本时）
- Docker Desktop，并启用 Docker Compose
- Node.js 20.19 或更高版本（也支持 22.12 及以上版本）
- npm
- 首次构建和安装依赖时需要网络连接

如果需要不依赖 Docker 运行后端或执行开发工具，还需要 Python 3.12 和 `uv`。

### 1. 创建环境配置

在项目根目录复制示例配置：

```powershell
Copy-Item .env.example .env
```

至少需要为 `AUTH_JWT_SECRET` 设置一个长度不低于 32 个字符的随机值：

```env
AUTH_JWT_SECRET=replace-with-a-random-string-of-at-least-32-characters
AUTH_ALLOW_REGISTRATION=true
ALLOW_DEV_AUTH_BYPASS=false
```

如需使用 AI 对话、语义检索和第三方能力，请继续在 `.env` 中填写对应配置。不要将真实 `.env` 或任何密钥提交到 Git。

### 2. Windows 一键启动

双击项目根目录的 `启动万径.bat`，脚本会：

1. 检查 Docker Desktop、Docker Compose 和 npm；
2. 构建并启动数据库、Redis、迁移、Worker、Piston 和 API；
3. 首次运行时安装前端依赖；
4. 在新的命令行窗口启动前端开发服务器。

启动完成后访问：

- 万径前端：<http://localhost:3000>
- 后端 API 与交互式文档：<http://localhost:8000>
- OpenAPI 描述：<http://localhost:8000/openapi.json>

### 3. 手动启动

启动后端服务：

```bash
docker compose up -d --build
```

启动前端：

```bash
cd src/edu-web
npm ci
npm start
```

查看服务状态和日志：

```bash
docker compose ps
docker compose logs -f api worker
```

停止服务：

```bash
docker compose down
```

数据库存储在 Docker 卷中，上传文件和本地资源默认保存在 `.localdata/`。普通的 `docker compose down` 不会删除数据库卷；不要在演示前删除 `.localdata/`。

## 主要配置

完整配置及注释请查看 `.env.example`。常用配置包括：

| 配置 | 说明 |
| --- | --- |
| `AUTH_JWT_SECRET` | JWT 签名密钥，本地启动必填 |
| `AUTH_ADMIN_USERNAMES` | 管理员用户名列表 |
| `LLM_MODEL`、`LLM_API_KEY`、`LLM_BASE_URL` | 对话与内容生成模型 |
| `EMBEDDING_MODEL`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL` | 文档向量化与语义检索 |
| `XFYUN_*` | 讯飞 PPT、OCR、语音、翻译和图片能力 |
| `VITE_AVATAR_*` | 讯飞数字人前端配置 |
| `BAIDU_SEARCH_*` | 百度联网搜索能力 |
| `CODE_EXECUTION_*` | Piston 代码执行配置 |
| `BILLING_*` | 演示套餐、订单与人工收款配置 |
| `VITE_SERVER_URL` | 前端访问后端的地址，默认 `http://localhost:8000` |

## 项目结构

```text
.
├─ src/
│  ├─ edu-web/          React 前端
│  ├─ edu-api/          FastAPI 接口层
│  ├─ edu-worker/       ARQ 异步任务 Worker
│  └─ shared/
│     ├─ ai/            Agent、Skill、提示词与 AI 工具
│     ├─ core/          核心业务服务
│     ├─ db/            数据模型与 Alembic 迁移
│     └─ queue/         队列协议与任务服务
├─ tests/               后端、Agent 与业务测试
├─ scripts/             初始化、部署、备份与演示数据脚本
├─ tools/               开发工具与 Piston 运行时配置
├─ deploy/              Caddy 和生产部署配置
├─ docker-compose.yaml  本地开发与演示编排
└─ 启动万径.bat         Windows 一键启动脚本
```

## 开发与验证

后端测试：

```bash
uv run --all-packages --with pytest pytest
```

前端检查：

```bash
cd src/edu-web
npm test
npm run type-check
npm run lint
npm run build
```

数据库迁移由 Compose 的 `migrate` 服务在启动时自动执行。手动执行迁移时，可在正确配置 `DATABASE_URL` 后运行：

```bash
uv run alembic upgrade head
```

## 数据与安全说明

- `.env` 包含模型、第三方服务和认证密钥，只能保存在本机或安全的密钥管理系统中。
- `.localdata/` 可能包含上传文件和演示数据，不应提交到公共仓库。
- 生产环境必须关闭 `ALLOW_DEV_AUTH_BYPASS`，使用随机强 `AUTH_JWT_SECRET`，并限制数据库、Redis 和 Piston 的网络访问。
- 收款二维码属于敏感业务素材；提交公开源码时应使用演示占位图，不要上传个人真实收款码。

## License

本项目使用 [MIT License](LICENSE)。第三方 SDK、模型服务及外部 API 仍分别受其自身许可协议和使用条款约束。
