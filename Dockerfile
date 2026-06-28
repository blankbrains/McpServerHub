FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple build && \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple .

FROM node:22-alpine AS web-builder
WORKDIR /app
COPY src/mcp_hub/web/package.json src/mcp_hub/web/ ./
RUN npm install && npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app/src /app/src
COPY --from=web-builder /app/static /app/src/mcp_hub/web/static

EXPOSE 3987
ENV MCP_HUB_HOST=0.0.0.0
ENV MCP_HUB_PORT=3987

CMD ["python3", "-m", "uvicorn", "mcp_hub.api.app:create_app", "--host", "0.0.0.0", "--port", "3987"]
