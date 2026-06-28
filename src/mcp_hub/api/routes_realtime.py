"""实时功能 API — SSE 日志流 + 实时状态。"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from mcp_hub.core.process_manager import get_process_manager

router = APIRouter(tags=["realtime"])


@router.get("/realtime/logs/{server_id:path}")
async def stream_logs(server_id: str, lines: int = 50):
    """SSE 实时日志流。"""
    log_file = (
        Path.home()
        / ".config"
        / "mcp-hub"
        / "logs"
        / f"{server_id.replace('/', '_').replace('@', '')}.log"
    )

    async def event_stream():
        # 发送初始日志
        if log_file.exists():
            with open(log_file, encoding="utf-8") as f:
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    yield f"data: {json.dumps({'type': 'log', 'line': line.rstrip()})}\n\n"

        # 实时跟踪
        if log_file.exists():
            with open(log_file, encoding="utf-8") as f:
                f.seek(0, 2)  # 跳到文件末尾
                while True:
                    line = f.readline()
                    if line:
                        yield f"data: {json.dumps({'type': 'log', 'line': line.rstrip()})}\n\n"
                    else:
                        await asyncio.sleep(0.1)
        else:
            yield f"data: {json.dumps({'type': 'info', 'line': '日志文件不存在'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/realtime/status")
async def stream_status():
    """SSE 实时进程状态推送。"""

    async def event_stream():
        while True:
            pm = get_process_manager()
            running = pm.list_running()
            status = {}
            for p in running:
                status[p.server_id] = {
                    "pid": p.pid,
                    "uptime": int(time.time() - (p.started_at or time.time())),
                }
            yield f"data: {json.dumps({'type': 'status', 'running': status})}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
