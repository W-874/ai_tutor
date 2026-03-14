"""
协同写作 - 文本改写与 TTS 朗读（MVP 可选）

需实现的接口：
- POST /api/v1/cowriter/rewrite：文本改写/扩展/缩短/加注释
  - 请求体：text、action（rewrite|expand|shorten|annotate）、options
  - 返回改写结果，可选用短流式
- POST /api/v1/cowriter/tts：TTS 朗读，返回音频 URL 或 base64
"""
from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    SuccessResponse,
    CowriterRewriteRequest,
    CowriterTTSRequest,
)
from backend.services import llm
from backend.services import prompts

router = APIRouter()

ACTION_PROMPTS = {
    "rewrite": "请对以下文本进行改写，保持原意但优化表达方式，使其更加清晰、流畅。",
    "expand": "请对以下文本进行扩展，增加更多细节和内容，使其更加丰富完整。",
    "shorten": "请对以下文本进行精简，提取核心要点，去除冗余内容。",
    "annotate": "请对以下文本添加注释，为专业术语或复杂概念添加解释说明。",
}


@router.post(
    "/rewrite",
    response_model=SuccessResponse,
    summary="文本改写/扩展/缩短/加注释",
)
async def cowriter_rewrite(body: CowriterRewriteRequest):
    """
    根据 action 调用 LLM 对 text 进行改写、扩展、缩短或加注释；
    可选返回流式片段（short stream）。
    """
    system_prompt = prompts.get_system_prompt("cowriter")
    action_prompt = ACTION_PROMPTS.get(body.action, ACTION_PROMPTS["rewrite"])

    user_prompt = f"""{action_prompt}

原始文本：
{body.text}

请直接给出改写后的结果，无需额外说明。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        result = await llm.chat(messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"改写失败: {str(e)}")

    return SuccessResponse(data={"text": result})


@router.post(
    "/tts",
    response_model=SuccessResponse,
    summary="TTS 朗读",
)
async def cowriter_tts(body: CowriterTTSRequest):
    """
    调用 TTS 服务（如 Azure Speech、OpenAI TTS）生成音频；
    返回静态文件 URL（存 data/outputs/）或 base64 音频数据。
    """
    return SuccessResponse(data={"url": "", "base64": None})
