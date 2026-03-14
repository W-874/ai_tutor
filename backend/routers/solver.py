"""
问题求解器 - 对话 + WebSocket 流式输出

需实现的接口：
- POST /api/v1/solver/chat：发起新对话或继续对话
  - 请求体：session_id（可选）、message、kb_id（可选，做 RAG）
  - 返回 session_id、task_id，供前端连接 WebSocket
- WebSocket ws://.../api/v1/solver/stream/{session_id}
  - 实时流式返回：type 为 thinking | citation | answer | done | error 的 JSON 消息
  - 实现打字机效果：delta 为增量文本；citation 为引用片段
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from backend.models.schemas import SolverChatRequest, SolverChatResponse, WSMessage
from backend.services import session as session_svc
from backend.services import llm
from backend.services import rag
from backend.services import prompts

router = APIRouter()


@router.post(
    "/chat",
    response_model=SolverChatResponse,
    summary="发起/继续对话",
)
async def solver_chat(body: SolverChatRequest):
    """
    若未传 session_id 则新建会话；将 user message 写入会话；
    可选根据 kb_id 做 RAG 检索，再调用 LLM；
    返回 session_id 与 task_id，前端用 session_id 连 WebSocket 收流式结果。
    """
    session_id = body.session_id
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())

    session_svc.append_message(session_id, "user", body.message)

    context = ""
    if body.kb_id:
        results = await rag.query(body.kb_id, body.message)
        if results:
            context = "\n\n".join([
                f"【来源: {r.get('source', '未知')}】\n{r.get('text', '')}"
                for r in results
            ])

    system_prompt = prompts.get_system_prompt("solver")
    if context:
        user_prompt = prompts.format_user_prompt(
            "rag_answer",
            context=context,
            question=body.message,
        )
    else:
        user_prompt = body.message

    messages = session_svc.get_messages(session_id)
    messages.insert(0, {"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    return SolverChatResponse(session_id=session_id, task_id=session_id)


@router.websocket("/stream/{session_id}")
async def solver_stream(websocket: WebSocket, session_id: str):
    """
    接受 WebSocket 连接后，根据 session_id 取最后一条 user message，
    流式调用 LLM（及 RAG），按 WSMessage 格式推送：
    - type=thinking：思考过程
    - type=citation：引用块
    - type=answer：delta 为增量内容
    - type=done：结束
    - type=error：错误信息
    """
    await websocket.accept()
    try:
        session = session_svc.get_session(session_id)
        if not session:
            await websocket.send_text(
                json.dumps({"type": "error", "content": "会话不存在"})
            )
            return

        messages = session.get("messages", [])
        if not messages:
            await websocket.send_text(
                json.dumps({"type": "error", "content": "会话无消息"})
            )
            return

        system_prompt = prompts.get_system_prompt("solver")
        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)

        async for chunk in llm.chat(full_messages, stream=True):
            await websocket.send_text(
                json.dumps({"type": "answer", "delta": chunk})
            )

        full_content = "".join(session.get("content", []))
        session_svc.append_message(session_id, "assistant", full_content)

        await websocket.send_text(
            json.dumps({"type": "done", "content": ""})
        )
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_text(
            json.dumps({"type": "error", "content": str(e)})
        )
    finally:
        await websocket.close()
