FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.21 /uv /uvx /bin/

# Create user early
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -m -d /app -s /bin/false appuser

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

# Copy dependency files first for better caching
COPY uv.lock pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

# Copy source code
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev && \
    chown -R appuser:appgroup /app

USER appuser
# 8000: OAuth
EXPOSE 8000
# 8001: MCP server
EXPOSE 8001
CMD ["uv", "run", "src/mcp_server_box.py", "--transport=streamable-http", "--box-auth=oauth", "--no-mcp-server-auth", "--host=0.0.0.0", "--port=8001"]
