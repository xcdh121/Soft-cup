# 使用公网 IP 进行生产环境部署

[English](PRODUCTION_DEPLOYMENT.md)

此部署方案仅通过 80 端口公开前端反向代理。API、PostgreSQL、Redis 和 Piston 仅能在 Compose 网络内部访问。部署时不要求已有域名：可以先使用服务器公网 IP 完成部署，之后再添加 DNS 和 TLS，无需重新构建单页应用（SPA）。

## 1. 准备主机

使用装有 Docker Engine 和 Docker Compose 插件的 Ubuntu 22.04/24.04。对于 2 核、4 GB 内存的主机，请在构建镜像前创建 2–4 GB 的交换空间。按以下方式配置云防火墙或安全组：

- TCP 22：尽可能仅允许受信任的管理员 IP 访问。
- TCP 80：允许公网访问。
- TCP 443：保留给域名可用后的 HTTPS。
- 不要开放 2000、5432/5433、6379 或 8000 端口。

将仓库克隆或复制到服务器，然后在仓库根目录下进行后续操作。

## 2. 创建生产环境密钥

```bash
sh scripts/init-production-env.sh
nano .env.production
```

初始化脚本会生成一个可安全用于 URL 的 PostgreSQL 密码和一个 96 字符的 JWT 密钥。请至少填写已启用功能所需的 LLM 和嵌入模型凭据。保持 `VITE_SERVER_URL` 为空，使浏览器通过同源 Nginx 代理使用当前 IP 或域名。

生成的文件已被 Git 忽略，并以 `0600` 权限创建。切勿提交此文件，也不要将其中的值复制到前端的 `VITE_*` 变量中；Vite 变量会被打包进公开的 JavaScript 文件。

## 3. 部署并验证

```bash
sh scripts/deploy-production.sh
```

该脚本会验证 Compose 配置、构建 API/worker/web 镜像、执行数据库迁移、启动各项服务，并等待 API 健康检查通过。请执行以下命令进行验证：

```bash
curl http://SERVER_PUBLIC_IP/health
curl http://SERVER_PUBLIC_IP/api-health
docker compose --env-file .env.production -f docker-compose.prod.yaml ps
docker compose --env-file .env.production -f docker-compose.prod.yaml logs --tail=100 api worker
```

随后测试用户注册和登录、上传一个文档、进行一次 AI 对话，以及完成一道编程练习。创建初始账户后，将 `AUTH_ALLOW_REGISTRATION=false` 写入配置并重新部署，以关闭公开注册。

## 4. 备份与恢复

创建 PostgreSQL 逻辑转储，并将已上传和已生成的文件打包归档：

```bash
sh scripts/backup-production.sh
```

备份会写入 `backups/<UTC 时间戳>/`。请将此目录复制到其他计算机或对象存储桶；与应用存放在同一台服务器上的备份无法防范磁盘损坏或丢失。

以下示例会按服务器时间每天 03:20 执行备份：

```cron
20 3 * * * cd /opt/edu-agent && /bin/sh scripts/backup-production.sh >> /var/log/edu-agent-backup.log 2>&1
```

在依赖这些备份之前，请先在一次性测试服务器上验证恢复流程。恢复操作会有意替换当前数据库和已上传的文件：

```bash
RESTORE_CONFIRM=restore-production sh scripts/restore-production.sh backups/20260715T000000Z
```

## 5. 更新应用

先执行备份，再更新已检出的源代码，最后重新运行具备幂等性的部署脚本：

```bash
sh scripts/backup-production.sh
git pull --ff-only
sh scripts/deploy-production.sh
```

## 6. 后续添加域名和 HTTPS

将域名的 A 记录指向服务器公网 IP。在现有 web 容器前部署 Caddy、Traefik 或主机上的 Nginx 等 TLS 终止代理，获取 Let's Encrypt 证书，并将 HTTP 重定向到 HTTPS。应用使用同源 `/api` 请求，因此从 IP 切换到域名时无需重新构建前端。

如果 TLS 在主机上终止，请将 `.env.production` 中的 `HTTP_BIND_ADDRESS` 改为 `127.0.0.1`，使 80 端口不再直接对公网开放，并将域名请求代理到 `http://127.0.0.1:80`。

## 运维命令

```bash
# 查看状态和资源使用情况
docker compose --env-file .env.production -f docker-compose.prod.yaml ps
docker stats

# 持续查看日志
docker compose --env-file .env.production -f docker-compose.prod.yaml logs -f --tail=100

# 重启应用容器
docker compose --env-file .env.production -f docker-compose.prod.yaml restart api worker web

# 停止服务但不删除持久化卷
docker compose --env-file .env.production -f docker-compose.prod.yaml down
```

不要在生产环境中运行 `down -v`，因为它会删除具名数据卷。
