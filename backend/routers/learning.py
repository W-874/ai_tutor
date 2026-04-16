from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, AsyncGenerator
import json
import httpx
import os
from pydantic import BaseModel

from ..models.database import get_db, SkillNode, LearningProgress
from ..services.lightrag_client import LightRAGClient

router = APIRouter(prefix="/api/learning", tags=["learning"])

lightrag_client = LightRAGClient()
LIGHTRAG_BASE_URL = os.getenv("LIGHTRAG_BASE_URL", "http://localhost:9621").rstrip("/")


class StudioGenerateRequest(BaseModel):
    action: str
    topic: str = "knowledge"
    mode: str = "mix"


def _build_studio_prompt(action: str, topic: str) -> Dict[str, Any]:
    action_key = action.strip().lower()
    if action_key == "audio_overview":
        return {
            "prompt": f"请基于主题「{topic}」生成音频概览脚本（文本）。输出：1) 3分钟口播稿；2) 关键点清单；3) 可选BGM与节奏建议。不要输出音频文件。",
            "delivery_type": "text_script",
            "capability_note": "当前链路仅支持文本，不直接生成音频文件。"
        }
    if action_key == "video_overview":
        return {
            "prompt": f"请基于主题「{topic}」生成视频概览脚本（文本）。输出：1) 分镜脚本（镜头、时长、画面描述）；2) 旁白文案；3) 结尾总结。不要输出视频文件。",
            "delivery_type": "text_storyboard",
            "capability_note": "当前链路仅支持文本，不直接生成视频文件。"
        }
    if action_key == "report":
        return {
            "prompt": f"请基于主题「{topic}」生成结构化学习报告，包含：摘要、核心概念、知识关系、常见误区、学习建议、参考问答。",
            "delivery_type": "text_markdown",
            "capability_note": "可直接生成。"
        }
    if action_key == "flashcards":
        return {
            "prompt": f"请基于主题「{topic}」生成12张学习闪卡。格式：Q: 问题 / A: 答案 / Tag: 标签。",
            "delivery_type": "text_flashcards",
            "capability_note": "可直接生成。"
        }
    if action_key == "quiz":
        return {
            "prompt": f"请基于主题「{topic}」生成一套测验：5道单选、3道判断、2道简答，并给出标准答案与评分要点。",
            "delivery_type": "text_quiz",
            "capability_note": "可直接生成。"
        }
    if action_key == "presentation":
        return {
            "prompt": f"请基于主题「{topic}」生成10页演示文稿大纲。每页包含：标题、要点、讲解备注。",
            "delivery_type": "text_slides",
            "capability_note": "可直接生成文本大纲，不直接导出PPT文件。"
        }
    if action_key == "table":
        return {
            "prompt": f"请基于主题「{topic}」输出一个结构化数据表（Markdown表格），至少8行，列建议：概念、定义、示例、易错点、应用场景。",
            "delivery_type": "text_table",
            "capability_note": "可直接生成。"
        }

    return {
        "prompt": f"请基于主题「{topic}」生成一份学习草稿。",
        "delivery_type": "text",
        "capability_note": "可直接生成。"
    }

@router.get("/query")
async def query_knowledge(query: str, mode: str = "mix", include_references: bool = False):
    result = await lightrag_client.query(query, mode, include_references)
    return {
        "query": query,
        "mode": mode,
        "response": result.get("response", ""),
        "references": result.get("references", [])
    }


@router.post("/studio/generate")
async def studio_generate(request: StudioGenerateRequest):
    try:
        spec = _build_studio_prompt(request.action, request.topic)
        result = await lightrag_client.query(
            query=spec["prompt"],
            mode=request.mode,
            include_references=False
        )
        return {
            "action": request.action,
            "topic": request.topic,
            "mode": request.mode,
            "delivery_type": spec["delivery_type"],
            "capability_note": spec["capability_note"],
            "content": result.get("response", ""),
            "references": result.get("references", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate studio content: {str(e)}")

@router.get("/graph")
async def get_knowledge_graph(
    label: str,
    max_depth: int = 3,
    max_nodes: int = 100
):
    try:
        result = await lightrag_client.get_knowledge_graph(
            label=label,
            max_depth=max_depth,
            max_nodes=max_nodes
        )
        return {
            "label": label,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "graph": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch knowledge graph: {str(e)}")

@router.post("/query/stream")
async def query_knowledge_stream(request: dict):
    query = request.get("query", "")
    mode = request.get("mode", "mix")
    include_references = request.get("include_references", False)
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    f"{LIGHTRAG_BASE_URL}/query/stream",
                    json={
                        "query": query,
                        "mode": mode,
                        "include_references": include_references,
                        "stream": True
                    }
                ) as response:
                    async for line in response.aiter_lines():
                        if line.strip():
                            yield line + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="application/x-ndjson"
    )

@router.get("/progress")
async def get_learning_progress(db: Session = Depends(get_db)):
    nodes = db.query(SkillNode).all()
    
    total_nodes = len(nodes)
    completed_nodes = len([n for n in nodes if n.status == "completed"])
    learning_nodes = len([n for n in nodes if n.status == "learning"])
    available_nodes = len([n for n in nodes if n.status == "available"])
    
    if total_nodes > 0:
        overall_progress = (completed_nodes / total_nodes) * 100
        avg_mastery = sum(n.mastery for n in nodes) / total_nodes
    else:
        overall_progress = 0.0
        avg_mastery = 0.0
    
    return {
        "summary": {
            "total_nodes": total_nodes,
            "completed_nodes": completed_nodes,
            "learning_nodes": learning_nodes,
            "available_nodes": available_nodes,
            "locked_nodes": total_nodes - completed_nodes - learning_nodes - available_nodes,
            "overall_progress": overall_progress,
            "average_mastery": avg_mastery
        },
        "nodes": [
            {
                "id": node.id,
                "name": node.name,
                "status": node.status,
                "mastery": node.mastery
            }
            for node in nodes
        ]
    }

@router.get("/progress/{node_id}")
async def get_node_progress(node_id: str, db: Session = Depends(get_db)):
    progress = db.query(LearningProgress).filter(LearningProgress.node_id == node_id).first()
    node = db.query(SkillNode).filter(SkillNode.id == node_id).first()
    
    if not node:
        raise HTTPException(status_code=404, detail="Skill node not found")
    
    return {
        "node_id": node_id,
        "node_name": node.name,
        "node_status": node.status,
        "mastery": node.mastery,
        "progress": {
            "study_time": progress.study_time if progress else 0,
            "quiz_scores": progress.quiz_scores if progress else [],
            "last_visit": progress.last_visit if progress else None
        }
    }
