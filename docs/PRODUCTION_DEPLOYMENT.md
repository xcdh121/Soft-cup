# Production deployment with a public IP

[简体中文版](PRODUCTION_DEPLOYMENT.zh-CN.md)

This deployment exposes only the frontend reverse proxy on port 80. The API,
PostgreSQL, Redis, and Piston remain reachable only inside the Compose network.
A domain is not required: deploy against the server public IP now, then add DNS
and TLS later without rebuilding the SPA.

## 1. Prepare the host

Use Ubuntu 22.04/24.04 with Docker Engine and the Docker Compose plugin. For a
2-core/4-GB host, create 2-4 GB of swap before building images. Configure the
cloud firewall/security group as follows:

- TCP 22: allow only trusted administrator IPs where possible.
- TCP 80: allow public access.
- TCP 443: reserve for HTTPS after the domain is available.
- Do not expose 2000, 5432/5433, 6379, or 8000.

Clone or copy the repository to the server, then work from the repository root.

## 2. Create production secrets

```bash
sh scripts/init-production-env.sh
nano .env.production
```

The initializer generates a URL-safe PostgreSQL password and a 96-character
JWT secret. Fill at least the LLM and embedding credentials required by the
enabled features. Keep `VITE_SERVER_URL` empty so the browser uses the current
IP/domain through the same-origin Nginx proxy.

The generated file is ignored by Git and is created with mode `0600`. Never
commit it or copy its values into frontend `VITE_*` variables; Vite values are
bundled into public JavaScript.

## 3. Deploy and verify

```bash
sh scripts/deploy-production.sh
```

The script validates Compose, builds the API/worker/web images, runs database
migrations, starts the services, and waits for the API health probe. Verify:

```bash
curl http://SERVER_PUBLIC_IP/health
curl http://SERVER_PUBLIC_IP/api-health
docker compose --env-file .env.production -f docker-compose.prod.yaml ps
docker compose --env-file .env.production -f docker-compose.prod.yaml logs --tail=100 api worker
```

Then test registration/login, one document upload, one AI conversation, and one
programming exercise. Disable public registration after creating the initial
accounts by setting `AUTH_ALLOW_REGISTRATION=false` and redeploying.

## 4. Back up and restore

Create a logical PostgreSQL dump plus an archive of uploaded/generated files:

```bash
sh scripts/backup-production.sh
```

Backups are written under `backups/<UTC timestamp>/`. Copy this directory to a
different machine or object-storage bucket; a backup on the same server does
not protect against disk loss.

Example daily cron entry at 03:20 server time:

```cron
20 3 * * * cd /opt/edu-agent && /bin/sh scripts/backup-production.sh >> /var/log/edu-agent-backup.log 2>&1
```

Test restoration in a disposable server before relying on the backups. A
restore intentionally replaces the active database and uploaded files:

```bash
RESTORE_CONFIRM=restore-production sh scripts/restore-production.sh backups/20260715T000000Z
```

## 5. Update the application

Back up first, update the checked-out source, then run the idempotent deploy
script again:

```bash
sh scripts/backup-production.sh
git pull --ff-only
sh scripts/deploy-production.sh
```

## 6. Add the domain and HTTPS later

Point the domain A record at the server public IP. Put a TLS terminator such as
Caddy, Traefik, or host Nginx in front of the existing web container, obtain a
Let's Encrypt certificate, and redirect HTTP to HTTPS. The application uses
same-origin `/api` requests, so changing from an IP to a domain does not require
a frontend rebuild.

If TLS terminates on the host, change `HTTP_BIND_ADDRESS` in `.env.production`
to `127.0.0.1` so port 80 is no longer directly public, and proxy the domain to
`http://127.0.0.1:80`.

## Operations

```bash
# Status and resource usage
docker compose --env-file .env.production -f docker-compose.prod.yaml ps
docker stats

# Follow logs
docker compose --env-file .env.production -f docker-compose.prod.yaml logs -f --tail=100

# Restart application containers
docker compose --env-file .env.production -f docker-compose.prod.yaml restart api worker web

# Stop without deleting persistent volumes
docker compose --env-file .env.production -f docker-compose.prod.yaml down
```

Do not run `down -v` in production because it deletes named data volumes.
