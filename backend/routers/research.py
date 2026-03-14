"""
深度研究 - 多阶段研究与流式报告

需实现的接口：
- POST /api/v1/research/start：输入主题，启动多阶段研究
  - 返回 task_id，供 WebSocket 连接
- WebSocket ws://.../api/v1/research/stream/{task_id}
  - 实时推送：type=progress（percentage、stage）、阶段报告、最终 Markdown 报告
  - stage 如 research | synthesis | writing
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.models.schemas import ResearchStartRequest, WSMessage
from backend.services import llm
from backend.services import prompts

router = APIRouter()


@router.post(
    "/start",
    response_model=dict,
    summary="启动深度研究任务",
)
async def research_start(body: ResearchStartRequest):
    """
    创建研究任务，返回 task_id；后台执行多阶段：检索/分析 → 综合 → 撰写报告。
    前端用 task_id 连 WebSocket 收进度与结果。
    """
    import uuid
    task_id = str(uuid.uuid4())
    return {"task_id": task_id, "success": True}


@router.websocket("/stream/{task_id}")
async def research_stream(websocket: WebSocket, task_id: str):
    """
    按 task_id 执行多阶段研究，推送 progress（percentage、stage）、
    各阶段内容、最终 Markdown；type=done 时结束。
    """
    await websocket.accept()
    try:
        system_prompt = prompts.get_system_prompt("research_assistant")
        await websocket.send_text(json.dumps({
            "type": "system",
            "content": system_prompt
        }))
        await websocket.send_text(json.dumps({"type": "done", "content": ""}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))
    finally:
        await websocket.close()
