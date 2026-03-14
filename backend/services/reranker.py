"""
重排序服务：调用 Silicon Flow BAAI/bge-reranker-v2-m3 API 对检索结果进行重排序。
配置从 backend.config.settings 读取（api_key、base_url、model）。
"""
from typing import List

import httpx

from backend.config import get_settings


async def rerank(
    query: str,
    documents: List[str],
    top_n: int = None,
) -> List[dict]:
    """
    调用 Silicon Flow Rerank API 对文档进行重排序。
    - query: 查询字符串
    - documents: 待排序的文档列表
    - top_n: 返回前 N 条结果，默认返回全部
    - 返回: [{"index": int, "document": str, "relevance_score": float}, ...]
    """
    settings = get_settings()
    cfg = settings.rerank
    if not cfg.api_key:
        raise ValueError("未配置 Rerank API Key，请在环境变量 RERANK_API_KEY 中设置")

    if not documents:
        return []

    url = f"{cfg.base_url.rstrip('/')}/rerank"
    payload = {
        "model": cfg.model,
        "query": query,
        "documents": documents,
        "top_n": top_n or len(documents),
    }
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=cfg.timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    return [
        {
            "index": r.get("index"),
            "document": r.get("document"),
            "relevance_score": r.get("relevance_score"),
        }
        for r in results
    ]
