"""
引导式学习 - 根据笔记本生成学习路径与交互式对话

需实现的接口：
- POST /api/v1/guide/start：根据笔记本生成学习路径与第一步内容
  - 请求体：notebook_id；返回 session_id
- WebSocket ws://.../api/v1/guide/stream/{session_id}
  - 交互式学习对话，推送 HTML 可视化片段、下一步建议等；type 同通用 WS 格式
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.models.schemas import GuideStartRequest
from backend.services import prompts

router = APIRouter()


@router.post(
    "/start",
    response_model=dict,
    summary="启动引导式学习",
)
async def guide_start(body: GuideStartRequest):
    """
    根据 notebook_id 读取笔记本内容，用 LLM 生成学习路径与第一步；
    创建 guide 会话，返回 session_id 供 WebSocket 连接。
    """
    import uuid
    session_id = str(uuid.uuid4())
    return {"session_id": session_id, "success": True}


@router.websocket("/stream/{session_id}")
async def guide_stream(websocket: WebSocket, session_id: str):
    """
    交互式学习：接收用户回复，推送下一步内容、HTML 片段等；
    type 可为 thinking | answer | progress | done | error。
    """
    await websocket.accept()
    try:
        system_prompt = prompts.get_system_prompt("guide_tutor")
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
