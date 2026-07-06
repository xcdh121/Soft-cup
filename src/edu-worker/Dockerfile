# Same base as API
FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# 1. Copy Monorepo Metadata
COPY pyproject.toml uv.lock /app/

# 2. Copy Source Code
COPY src /app/src

# 3. Install Dependencies
WORKDIR /app/src/edu-worker
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV UV_SYSTEM_CERTS=true
RUN sed -i \
    -e 's#https://files.pythonhosted.org#https://pypi.tuna.tsinghua.edu.cn#g' \
    -e 's#https://pypi.org/simple#https://pypi.tuna.tsinghua.edu.cn/simple#g' \
    /app/uv.lock
RUN uv sync --frozen

# 4. Run arq worker
ENV PATH="/app/.venv/bin:$PATH"
CMD ["arq", "worker.WorkerSettings"]
