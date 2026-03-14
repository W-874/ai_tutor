"""
统一 LLM 调用层：从 backend.config 读取配置，调用 OpenAI 兼容接口（含 Silicon Flow）。
支持流式与非流式，配置来自 config.py / data/user/config.json / 环境变量。
"""
from typing import AsyncGenerator, List, Optional

import httpx

from backend.config import get_settings


async def chat(
    messages: List[dict],
    stream: bool = False,
    model: Optional[str] = None,
) -> str | AsyncGenerator[str, None]:
    """
    统一聊天接口。配置从 get_settings().llm 读取。
    - messages: [{"role":"user","content":"..."}, ...]
    - stream=True 时返回异步生成器，逐段 yield 文本
    """
    cfg = get_settings().llm
    if not cfg.api_key:
        raise ValueError("未配置 LLM API Key，请在环境变量 LLM_API_KEY 中设置")
    url = f"{cfg.base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model or cfg.model,
        "messages": messages,
        "stream": stream,
    }
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }

    if not stream:
        async with httpx.AsyncClient(timeout=cfg.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
        return content

    async def stream_gen():
        async with httpx.AsyncClient(timeout=cfg.timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or line.strip() != line or not line.startswith("data: "):
                        continue
                    if line.strip() == "data: [DONE]":
                        break
                    try:
                        import json
                        chunk = json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content") or ""
                        if delta:
                            yield delta
                    except Exception:
                        pass

    return stream_gen()


async def chat_with_tools(
    messages: List[dict],
    tools: Optional[list] = None,
) -> tuple[str, list]:
    """带 function calling 的调用，返回 (assistant_message, tool_calls)。"""
    cfg = get_settings().llm
    if not cfg.api_key:
        return "", []
    url = f"{cfg.base_url.rstrip('/')}/chat/completions"
    payload = {"model": cfg.model, "messages": messages}
    if tools:
        payload["tools"] = tools
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=cfg.timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    choice = data.get("choices", [{}])[0] or {}
    msg = choice.get("message", {})
    content = msg.get("content", "") or ""
    tool_calls = msg.get("tool_calls") or []
    return content, tool_calls
