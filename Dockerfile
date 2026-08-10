FROM node:22-alpine AS web-builder
WORKDIR /app
COPY src/mcp_hub/web/package.json src/mcp_hub/web/package-lock.json* ./
RUN npm ci --prefer-offline 2>/dev/null || npm install
COPY src/mcp_hub/web/ ./
RUN npm run build

FROM python:3.12-slim AS builder

WORKDIR /app

# 层缓存优化：先复制依赖声明文件
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple build

# 再复制源码和已构建的前端产物
COPY src/ src/
COPY --from=web-builder /app/static /app/src/mcp_hub/web/static
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple .

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN groupadd -r mcp-hub && useradd -r -g mcp-hub -d /app -s /sbin/nologin mcp-hub

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app/src /app/src
COPY --from=web-builder /app/static /usr/local/lib/python3.12/site-packages/mcp_hub/web/static

# 切换到非 root 用户
RUN chown -R mcp-hub:mcp-hub /app
USER mcp-hub

EXPOSE 3987
ENV MCP_HUB_HOST=0.0.0.0
ENV MCP_HUB_PORT=3987

CMD ["python3", "-m", "uvicorn", "mcp_hub.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "3987"]
