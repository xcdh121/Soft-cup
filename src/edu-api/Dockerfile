# Use Python 3.12 slim
FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# 1. Copy Monorepo Metadata
COPY pyproject.toml uv.lock alembic.ini /app/

# 2. Copy Source Code
# CRITICAL: We copy the whole 'src' so 'edu-shared' is available to the API
COPY src /app/src

# 3. Install Dependencies
WORKDIR /app/src/edu-api
# Create the virtualenv outside /app/src so docker-compose bind mounts don't overwrite it
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV UV_SYSTEM_CERTS=true
RUN sed -i \
    -e 's#https://files.pythonhosted.org#https://pypi.tuna.tsinghua.edu.cn#g' \
    -e 's#https://pypi.org/simple#https://pypi.tuna.tsinghua.edu.cn/simple#g' \
    /app/uv.lock
RUN uv sync --frozen

# 4. Run FastAPI
# We point directly to the venv created by uv
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "main.py"]
