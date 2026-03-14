"""
Embedding 服务：调用 Silicon Flow BGE API 生成向量。
配置从 backend.config.settings 读取（api_key、base_url、model）。
"""
from typing import List, Union

import httpx

from backend.config import get_settings


async def embed_texts(texts: Union[str, List[str]]) -> List[List[float]]:
    """
    调用 Silicon Flow Embedding API（BGE 模型）。
    - texts: 单条字符串或字符串列表（单次最多 32 条）
    - 返回与 texts 顺序一致的向量列表，每条为 list[float]
    """
    settings = get_settings()
    cfg = settings.embedding
    if not cfg.api_key:
        raise ValueError("未配置 Embedding API Key，请在环境变量 EMBEDDING_API_KEY 中设置")

    if isinstance(texts, str):
        texts = [texts]
    if len(texts) > cfg.batch_size:
        raise ValueError(f"单次请求最多 {cfg.batch_size} 条，当前 {len(texts)} 条")

    url = f"{cfg.base_url.rstrip('/')}/embeddings"
    payload = {
        "model": cfg.model,
        "input": texts,
    }
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=cfg.timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    # 按 index 排序后取 embedding，保证与 input 顺序一致
    items = sorted(data.get("data", []), key=lambda x: x["index"])
    return [item["embedding"] for item in items]


async def embed_batch_large(texts: List[str]) -> List[List[float]]:
    """
    大批量文本分批调用 embed_texts，合并返回。
    """
    settings = get_settings()
    batch_size = settings.embedding.batch_size
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        all_embeddings.extend(await embed_texts(chunk))
    return all_embeddings
