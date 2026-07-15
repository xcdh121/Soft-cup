# Self-hosted authentication

EduAgent stores account records in its own PostgreSQL `users` table and issues
its own HS256 access tokens. Supabase is not required.

## Configuration

Generate a secret with at least 32 random characters and add it to the root
`.env` file:

```env
AUTH_JWT_SECRET=replace-with-a-random-secret
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=10080
AUTH_ALLOW_REGISTRATION=true
AUTH_ADMIN_USERNAMES=admin
ALLOW_DEV_AUTH_BYPASS=false
```

`AUTH_ADMIN_USERNAMES` is a comma-separated allowlist. A matching account name
becomes an administrator when it registers. After provisioning accounts,
set `AUTH_ALLOW_REGISTRATION=false` if public registration is not desired.

Apply the database migration before using authentication:

```bash
alembic upgrade head
```

Docker Compose runs the migration service automatically.

## HTTP API

- `POST /api/v1/auth/register` creates an account and returns a bearer token.
- `POST /api/v1/auth/login` verifies username/password and returns a bearer token.
- `GET /api/v1/auth/me` returns the authenticated account.
- `POST /api/v1/users` lets an administrator create another local account.

Passwords are never stored directly. They are salted and hashed with scrypt.
The frontend persists only the signed access token and sends it as an
`Authorization: Bearer ...` header.

## Existing users

Rows created by the former development/Supabase flow remain intact but have no
password and cannot log in. Create fresh local accounts for normal use. Do not
enable `ALLOW_DEV_AUTH_BYPASS` in a shared or public environment because it
maps every request to the same development account.
