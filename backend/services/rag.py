"""
RAG：Silicon Flow BGE 向量检索 + BM25 关键词检索，混合 RRF 融合 + BGE 重排序。
向量库与 BM25 索引均本地持久化（Chroma 存盘、BM25 pickle）。
"""
from pathlib import Path
import json
import pickle
import re
import uuid
from typing import List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from rank_bm25 import BM25Okapi

from backend.config import get_settings
from backend.services import embedding as embedding_svc
from backend.services import reranker as reranker_svc


def _data_root() -> Path:
    return get_settings().data_root


def _kb_dir(kb_id: str) -> Path:
    return _data_root() / get_settings().rag.persist_chroma_path / kb_id


def _chroma_path(kb_id: str) -> Path:
    return _kb_dir(kb_id) / "chroma"


def _bm25_path(kb_id: str) -> Path:
    return _kb_dir(kb_id) / get_settings().rag.persist_bm25_filename


def _chunks_meta_path(kb_id: str) -> Path:
    return _kb_dir(kb_id) / "chunks_meta.json"


def _index_path(kb_id: str) -> Path:
    return _kb_dir(kb_id) / "index.json"


# ---------- 文本解析 ----------
def _read_text_file(path: Path) -> str:
    """读取 TXT/MD 文件为 UTF-8 文本。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _read_pdf(path: Path) -> str:
    """读取 PDF 文本（需安装 pymupdf: pip install pymupdf）。"""
    try:
        import fitz  # pymupdf
    except ImportError:
        raise RuntimeError("PDF 解析需要安装 pymupdf: pip install pymupdf")
    text = []
    doc = fitz.open(path)
    for page in doc:
        text.append(page.get_text())
    doc.close()
    return "\n\n".join(text)


def _extract_text(path: Path) -> str:
    suf = path.suffix.lower()
    if suf == ".pdf":
        return _read_pdf(path)
    if suf in (".txt", ".md", ".markdown"):
        return _read_text_file(path)
    raise ValueError(f"不支持的文件类型: {suf}")


# ---------- 切块 ----------
def _chunk_text(
    text: str,
    source: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[dict]:
    """按字符切块，带重叠。返回 [{"id","text","source"}, ...]。"""
    if not text or not text.strip():
        return []
    # 先按段落再按长度切
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = []
    current_len = 0
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if current_len + len(p) + 1 <= chunk_size and current:
            current.append(p)
            current_len += len(p) + 1
        else:
            if current:
                block = "\n".join(current)
                chunks.append({"text": block, "source": source})
            # 重叠：保留上一块末尾
            current = [p]
            current_len = len(p)
            if chunks and chunk_overlap > 0:
                last = chunks[-1]["text"]
                overlap_text = last[-chunk_overlap:] if len(last) >= chunk_overlap else last
                if overlap_text.strip():
                    current.insert(0, overlap_text.strip())
                    current_len += len(overlap_text)
    if current:
        chunks.append({"text": "\n".join(current), "source": source})

    out = []
    for i, c in enumerate(chunks):
        cid = str(uuid.uuid4())
        out.append({"id": cid, "text": c["text"], "source": c["source"], "index": i})
    return out


# ---------- 中文 BM25 分词 ----------
def _tokenize_cn(text: str) -> List[str]:
    """简单中文分词（可用 jieba 增强）。"""
    try:
        import jieba
        return list(jieba.cut_for_search(text))
    except ImportError:
        return list(text.replace(" ", ""))  # 单字回退


# ---------- 知识库创建 ----------
def _save_index(kb_id: str, name: str, status: str, chunks_count: int) -> None:
    d = _kb_dir(kb_id)
    d.mkdir(parents=True, exist_ok=True)
    index = {
        "kb_id": kb_id,
        "name": name,
        "status": status,
        "chunks_count": chunks_count,
    }
    with open(_index_path(kb_id), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


async def create_knowledge_base(kb_id: str, file_paths: List[Path], name: Optional[str] = None) -> dict:
    """
    解析文件 → 切块 → BGE embedding → 写入 Chroma（持久化）→ 构建 BM25 并 pickle 持久化。
    """
    settings = get_settings()
    rag_cfg = settings.rag
    kb_path = _kb_dir(kb_id)
    kb_path.mkdir(parents=True, exist_ok=True)
    _save_index(kb_id, name or kb_id, "processing", 0)

    all_chunks = []
    for fp in file_paths:
        if not fp.exists():
            continue
        try:
            text = _extract_text(fp)
        except Exception as e:
            _save_index(kb_id, name or kb_id, "failed", 0)
            return {"status": "failed", "error": str(e), "chunks_count": 0}
        source = f"{fp.name}"
        chunks = _chunk_text(
            text,
            source,
            rag_cfg.chunk_size,
            rag_cfg.chunk_overlap,
        )
        all_chunks.extend(chunks)

    if not all_chunks:
        _save_index(kb_id, name or kb_id, "ready", 0)
        return {"status": "ready", "chunks_count": 0}

    # Embedding 批量
    texts = [c["text"] for c in all_chunks]
    embeddings = await embedding_svc.embed_batch_large(texts)

    # Chroma 持久化
    chroma_dir = str(_chroma_path(kb_id))
    client = chromadb.PersistentClient(path=chroma_dir, settings=ChromaSettings(anonymized_telemetry=False))
    coll = client.get_or_create_collection("chunks", metadata={"hnsw:space": "cosine"})
    coll.add(
        ids=[c["id"] for c in all_chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[{"source": c["source"], "index": c["index"]} for c in all_chunks],
    )

    # chunks_meta 供 BM25 与展示
    meta = [{"id": c["id"], "text": c["text"], "source": c["source"], "index": c["index"]} for c in all_chunks]
    with open(_chunks_meta_path(kb_id), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # BM25
    tokenized = [_tokenize_cn(c["text"]) for c in all_chunks]
    bm25 = BM25Okapi(tokenized)
    with open(_bm25_path(kb_id), "wb") as f:
        pickle.dump({"bm25": bm25, "chunk_ids": [c["id"] for c in all_chunks]}, f)

    _save_index(kb_id, name or kb_id, "ready", len(all_chunks))
    return {"status": "ready", "chunks_count": len(all_chunks)}


def get_kb_status(kb_id: str) -> dict:
    """从 index.json 读状态。"""
    p = _index_path(kb_id)
    if not p.exists():
        return {"kb_id": kb_id, "status": "not_found", "progress": 0.0, "chunks_count": 0}
    with open(p, "r", encoding="utf-8") as f:
        idx = json.load(f)
    return {
        "kb_id": kb_id,
        "status": idx.get("status", "unknown"),
        "progress": 100.0 if idx.get("status") == "ready" else 0.0,
        "chunks_count": idx.get("chunks_count", 0),
    }


def _rrf_merge(
    vector_results: List[tuple],  # (chunk_id, score)
    bm25_results: List[tuple],   # (chunk_id, score)
    k: int = 60,
) -> List[str]:
    """RRF 融合：score = sum 1/(k+rank)。返回按 RRF 分排序的 chunk_id 列表。"""
    def rrf_score(rank: int) -> float:
        return 1.0 / (k + rank + 1)

    scores = {}
    for r, (cid, _) in enumerate(vector_results):
        scores[cid] = scores.get(cid, 0) + rrf_score(r)
    for r, (cid, _) in enumerate(bm25_results):
        scores[cid] = scores.get(cid, 0) + rrf_score(r)
    sorted_ids = sorted(scores.keys(), key=lambda x: -scores[x])
    return sorted_ids


async def query(
    kb_id: str,
    question: str,
    top_k: Optional[int] = None,
    use_rerank: Optional[bool] = None,
) -> List[dict]:
    """
    混合检索：BGE 向量 + BM25，RRF 融合后进行 BGE 重排序，返回 top_k 条。
    每条 {"id","text","source","score"}。
    """
    settings = get_settings()
    rag_cfg = settings.rag
    k = top_k or rag_cfg.hybrid_top_k
    enable_rerank = use_rerank if use_rerank is not None else rag_cfg.use_rerank
    rerank_top_k = rag_cfg.rerank_top_k

    kb_path = _kb_dir(kb_id)
    if not kb_path.exists() or not _index_path(kb_id).exists():
        return []
    with open(_index_path(kb_id), "r", encoding="utf-8") as f:
        idx = json.load(f)
    if idx.get("status") != "ready":
        return []

    # 向量检索
    chroma_dir = str(_chroma_path(kb_id))
    client = chromadb.PersistentClient(path=chroma_dir, settings=ChromaSettings(anonymized_telemetry=False))
    coll = client.get_collection("chunks")
    q_emb = await embedding_svc.embed_texts(question)
    vector_res = coll.query(
        query_embeddings=q_emb,
        n_results=min(rag_cfg.vector_top_k, idx.get("chunks_count", 1)),
        include=["metadatas", "documents"],
    )
    v_ids = vector_res["ids"][0]
    v_metas = vector_res["metadatas"][0] or []
    v_docs = vector_res["documents"][0] or []
    vector_tuples = list(zip(v_ids, [1.0 - d for d in (vector_res["distances"][0] if vector_res.get("distances") else [0] * len(v_ids))]))

    # BM25 检索
    with open(_bm25_path(kb_id), "rb") as f:
        bm25_data = pickle.load(f)
    bm25, chunk_ids = bm25_data["bm25"], bm25_data["chunk_ids"]
    q_tokens = _tokenize_cn(question)
    bm25_scores = bm25.get_scores(q_tokens)
    bm25_rank = sorted(range(len(bm25_scores)), key=lambda i: -bm25_scores[i])[: rag_cfg.bm25_top_k]
    bm25_tuples = [(chunk_ids[i], float(bm25_scores[i])) for i in bm25_rank]

    # RRF 融合
    merged_ids = _rrf_merge(vector_tuples, bm25_tuples, k=rag_cfg.rrf_k)[:k]

    # 组装 text/source：从 chunks_meta 取
    with open(_chunks_meta_path(kb_id), "r", encoding="utf-8") as f:
        meta_list = json.load(f)
    meta_by_id = {m["id"]: m for m in meta_list}

    # 构建待重排序的文档列表
    candidate_docs = []
    candidate_ids = []
    for cid in merged_ids:
        m = meta_by_id.get(cid, {})
        candidate_docs.append(m.get("text", ""))
        candidate_ids.append(cid)

    # 重排序
    if enable_rerank and candidate_docs and settings.rerank.enabled:
        try:
            rerank_results = await reranker_svc.rerank(
                query=question,
                documents=candidate_docs,
                top_n=rerank_top_k,
            )
            # 根据重排序结果构建最终结果
            results = []
            for r in rerank_results:
                idx = r.get("index")
                if idx is not None and 0 <= idx < len(candidate_ids):
                    cid = candidate_ids[idx]
                    m = meta_by_id.get(cid, {})
                    results.append({
                        "id": cid,
                        "text": m.get("text", ""),
                        "source": m.get("source", ""),
                        "score": r.get("relevance_score", 0.0),
                    })
            return results
        except Exception:
            pass

    # 未使用重排序或重排序失败时，返回原始 RRF 结果
    results = []
    for cid in merged_ids:
        m = meta_by_id.get(cid, {})
        results.append({
            "id": cid,
            "text": m.get("text", ""),
            "source": m.get("source", ""),
            "score": 0.92,
        })
    return results[:rerank_top_k]


def list_knowledge_bases() -> List[dict]:
    """扫描 persist 目录下各 kb_id 的 index.json。"""
    root = _data_root() / get_settings().rag.persist_chroma_path
    if not root.exists():
        return []
    out = []
    for path in root.iterdir():
        if not path.is_dir():
            continue
        idx_path = path / "index.json"
        if not idx_path.exists():
            continue
        with open(idx_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
        out.append({
            "kb_id": idx.get("kb_id", path.name),
            "name": idx.get("name", path.name),
            "status": idx.get("status", "unknown"),
            "chunks_count": idx.get("chunks_count", 0),
        })
    return out
