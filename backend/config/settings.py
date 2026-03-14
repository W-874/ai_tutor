"""
统一配置：LLM、Embedding（Silicon Flow BGE）、RAG、GraphRAG 等。
加载顺序：config.py -> data/user/config.json -> 环境变量（后者覆盖前者）。
"""
import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from backend.config.config import (
    EMBEDDING_CONFIG,
    LLM_CONFIG,
    RERANK_CONFIG,
    RAG_CONFIG,
    GRAPH_RAG_CONFIG,
)


_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_RUNTIME_CONFIG_FILE = _PROJECT_ROOT / "data" / "user" / "config.json"


class EmbeddingConfig(BaseModel):
    """Embedding API 配置（Silicon Flow BGE）。"""
    provider: str = "silicon_flow"
    base_url: str = Field(default="https://api.siliconflow.cn/v1", description="Silicon Flow API 根地址")
    api_key: str = Field(default="", description="Silicon Flow API Key")
    model: str = Field(
        default="BAAI/bge-large-zh-v1.5",
        description="BGE 模型名，如 BAAI/bge-large-zh-v1.5、BAAI/bge-m3",
    )
    batch_size: int = Field(default=32, description="单次请求最大文本数，API 限制 32")
    timeout: float = Field(default=60.0, description="请求超时秒数")


class LLMConfig(BaseModel):
    """LLM 对话 API 配置（OpenAI 兼容）。"""
    provider: str = "openai"
    base_url: str = Field(default="https://api.openai.com/v1", description="API 根地址，如 Silicon Flow 对话端点")
    api_key: str = Field(default="", description="API Key")
    model: str = Field(default="gpt-4o-mini", description="模型名")
    timeout: float = Field(default=120.0, description="请求超时秒数")


class RerankConfig(BaseModel):
    """重排序 API 配置（Silicon Flow BAAI/bge-reranker-v2-m3）。"""
    provider: str = "silicon_flow"
    base_url: str = Field(default="https://api.siliconflow.cn/v1", description="Silicon Flow API 根地址")
    api_key: str = Field(default="", description="Silicon Flow API Key")
    model: str = Field(
        default="BAAI/bge-reranker-v2-m3",
        description="重排序模型名，如 BAAI/bge-reranker-v2-m3",
    )
    timeout: float = Field(default=60.0, description="请求超时秒数")
    enabled: bool = Field(default=True, description="是否启用重排序")


class RAGConfig(BaseModel):
    """RAG 检索与知识库配置。"""
    chunk_size: int = Field(default=512, description="切块最大字符/ token 数")
    chunk_overlap: int = Field(default=50, description="块重叠")
    vector_top_k: int = Field(default=10, description="向量检索 top-k")
    bm25_top_k: int = Field(default=10, description="BM25 检索 top-k")
    hybrid_top_k: int = Field(default=10, description="混合检索后重排序前条数")
    rerank_top_k: int = Field(default=5, description="重排序后返回条数")
    rrf_k: int = Field(default=60, description="RRF 常数 k，用于融合向量与 BM25 排序")
    use_rerank: bool = Field(default=True, description="是否启用重排序")
    persist_chroma_path: str = Field(default="knowledge_bases", description="Chroma 持久化子目录名")
    persist_bm25_filename: str = Field(default="bm25_index.pkl", description="BM25 索引文件名")


class GraphRAGConfig(BaseModel):
    """GraphRAG 配置。"""
    enabled: bool = Field(default=True, description="是否启用 GraphRAG")
    max_entities_per_chunk: int = Field(default=5, description="每块最多抽取实体数")
    max_relations_per_chunk: int = Field(default=10, description="每块最多抽取关系数")
    community_summary_max_nodes: int = Field(default=20, description="社区摘要最大节点数")
    graph_filename: str = Field(default="graph.json", description="图持久化文件名")


class AppConfig(BaseModel):
    """应用总配置。"""
    data_root: Path = Field(default_factory=lambda: _PROJECT_ROOT / "data")
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    rerank: RerankConfig = Field(default_factory=RerankConfig)
    graph_rag: GraphRAGConfig = Field(default_factory=GraphRAGConfig)


def _load_runtime_config() -> dict:
    """从 data/user/config.json 加载运行时覆盖（如 API 通过 POST 写入的配置）。"""
    if not _RUNTIME_CONFIG_FILE.exists():
        return {}
    try:
        with open(_RUNTIME_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并 override 到 base（仅覆盖存在的键）。"""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


_settings: Optional[AppConfig] = None


def get_settings() -> AppConfig:
    """单例获取配置；config.py -> runtime config.json。"""
    global _settings
    if _settings is not None:
        return _settings
    config_data = {
        "embedding": EMBEDDING_CONFIG.copy(),
        "llm": LLM_CONFIG.copy(),
        "rerank": RERANK_CONFIG.copy(),
        "rag": RAG_CONFIG.copy(),
        "graph_rag": GRAPH_RAG_CONFIG.copy(),
    }
    runtime_data = _load_runtime_config()
    if runtime_data:
        config_data = _deep_merge(config_data, runtime_data)
    _settings = AppConfig(**config_data)
    return _settings


def reload_settings() -> AppConfig:
    """重新加载配置（如修改了配置文件后）。"""
    global _settings
    _settings = None
    return get_settings()


def save_runtime_config(updates: dict) -> None:
    """将运行时配置写入 data/user/config.json（如 API 修改 LLM/embedding 后持久化）。"""
    _RUNTIME_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    current = _load_runtime_config()
    merged = _deep_merge(current, updates)
    with open(_RUNTIME_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    reload_settings()
