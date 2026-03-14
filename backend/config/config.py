"""
DeepTutor 应用配置文件
所有 API Key 从环境变量获取：
- EMBEDDING_API_KEY (Silicon Flow)
- LLM_API_KEY (OpenAI/Silicon Flow)
- RERANK_API_KEY (Silicon Flow)
"""
import os

EMBEDDING_CONFIG = {
    "provider": "silicon_flow",
    "base_url": os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1"),
    "api_key": os.getenv("EMBEDDING_API_KEY", ""),
    "model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5"),
    "batch_size": 32,
    "timeout": 60.0,
}

LLM_CONFIG = {
    "provider": "openai",
    "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
    "api_key": os.getenv("LLM_API_KEY", ""),
    "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    "timeout": 120.0,
}

RERANK_CONFIG = {
    "provider": "silicon_flow",
    "base_url": os.getenv("RERANK_BASE_URL", "https://api.siliconflow.cn/v1"),
    "api_key": os.getenv("RERANK_API_KEY", ""),
    "model": os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3"),
    "timeout": 60.0,
    "enabled": True,
}

RAG_CONFIG = {
    "chunk_size": 512,
    "chunk_overlap": 50,
    "vector_top_k": 10,
    "bm25_top_k": 10,
    "hybrid_top_k": 10,
    "rerank_top_k": 5,
    "rrf_k": 60,
    "use_rerank": True,
    "persist_chroma_path": "knowledge_bases",
    "persist_bm25_filename": "bm25_index.pkl",
}

GRAPH_RAG_CONFIG = {
    "enabled": True,
    "max_entities_per_chunk": 5,
    "max_relations_per_chunk": 10,
    "community_summary_max_nodes": 20,
    "graph_filename": "graph.json",
}
