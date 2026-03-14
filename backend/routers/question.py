"""
习题生成器 - 生成题目、提交答案与批改

需实现的接口：
- POST /api/v1/question/generate：根据知识库/主题/难度生成题目
  - 请求体：kb_id、topic、difficulty、count
  - 返回题目列表（含 question_id、题干、选项/开放题、答案要点等），可选用 LLM 流式生成
- POST /api/v1/question/submit：提交答案 → 批改 + 解析
  - 请求体：question_id、answer
  - 返回批改结果（对错、得分、解析、citations）
"""
from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    SuccessResponse,
    ErrorResponse,
    QuestionGenerateRequest,
    QuestionSubmitRequest,
)
from backend.services import llm
from backend.services import rag
from backend.services import prompts

router = APIRouter()


@router.post(
    "/generate",
    response_model=SuccessResponse,
    summary="根据知识库/主题/难度生成题目",
)
async def question_generate(body: QuestionGenerateRequest):
    """
    可选从 kb_id 检索相关上下文，结合 topic、difficulty 调用 LLM 生成 count 道题；
    题目持久化到 data/user/ 或会话，返回 question_id 列表与题目内容。
    """
    context = ""
    if body.kb_id:
        results = await rag.query(body.kb_id, body.topic or "生成题目", top_k=5)
        context = "\n\n".join([r.get("text", "") for r in results])

    system_prompt = prompts.get_system_prompt("question_generator")
    user_prompt = prompts.format_user_prompt(
        "question_generate",
        context=context or "无特定知识内容",
        topic=body.topic or "综合",
        difficulty=body.difficulty or "中等",
        count=body.count or 3,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        result = await llm.chat(messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成题目失败: {str(e)}")

    return SuccessResponse(data={"questions": [], "raw": result})


@router.post(
    "/submit",
    response_model=SuccessResponse,
    summary="提交答案并批改",
)
async def question_submit(body: QuestionSubmitRequest):
    """
    根据 question_id 取原题与参考答案，用 LLM 批改用户 answer，返回对错、得分、解析、citations。
    """
    system_prompt = prompts.get_system_prompt("answer_grader")
    user_prompt = prompts.format_user_prompt(
        "answer_grade",
        question=body.question or "",
        user_answer=body.answer or "",
        reference_answer=body.reference_answer or "",
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        result = await llm.chat(messages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批改失败: {str(e)}")

    return SuccessResponse(
        data={
            "correct": False,
            "score": 0,
            "feedback": result,
            "citations": [],
        }
    )
