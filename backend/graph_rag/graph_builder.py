"""
GraphRAG 建图：从知识库 chunk 文本中抽取实体与关系，构建图并持久化。

优化点（针对知识型内容）：
- 使用 LLM 对每个 chunk 做实体识别与关系抽取
- 对同一实体的不同命名（别名/缩写/中英文）做归一化与合并
- 过滤无意义实体（代词、泛化词），减少噪声节点
- 边为 (source_entity, target_entity, relation)，最终写入 graph_store
"""
import json
import re
from typing import Any, Dict, List, Tuple

from backend.config import get_settings
from backend.graph_rag.graph_store import save_graph
from backend.services import llm


async def _extract_entities_relations_llm(chunk_text: str) -> Tuple[List[Dict], List[Dict]]:
    """
    调用 LLM 从单段文本抽取实体与关系。
    返回 (entities, relations)，entities 为 [{"name","type","description?"}]，
    relations 为 [{"source","target","relation"}].
    """
    cfg = get_settings().graph_rag
    prompt = f"""从以下文本中抽取实体与关系（面向“知识型内容”，如概念、理论、论文、人物等）。
要求：
- 尽量抽取“知识性实体”，如学科概念、理论名称、模型、算法、重要人物、论文/书籍标题等。
- 避免把代词（如“它”“他们”）、纯数字、日期或“本章”“上文”等泛化词作为实体。
- 同一实体的不同命名（别名/缩写/中英文）要放在同一个实体对象的 aliases 字段中。
- 实体最多 {cfg.max_entities_per_chunk} 个，关系最多 {cfg.max_relations_per_chunk} 条。
- 以 JSON 格式返回，且只返回一个 JSON 对象，不要其他说明。

格式示例：
{{
  "entities":[
    {{"name":"反向传播算法","type":"algorithm","aliases":["BP 算法","Backpropagation"]}},
    {{"name":"卷积神经网络","type":"model","aliases":["CNN","Convolutional Neural Network"]}}
  ],
  "relations":[
    {{"source":"卷积神经网络","target":"反向传播算法","relation":"使用"}},
    {{"source":"卷积神经网络","target":"图像分类","relation":"常用于"}}
  ]
}}

文本：
{chunk_text[:2000]}
"""
    resp = await llm.chat([{"role": "user", "content": prompt}], stream=False)
    if not resp or not isinstance(resp, str):
        return [], []
    raw = resp.strip()
    for start in ("```json", "```"):
        if raw.startswith(start):
            raw = raw[len(start):].strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [], []
    return data.get("entities", []), data.get("relations", [])


def _normalize_entity_name(name: str) -> str:
    """基础标准化：去空格、统一大小写、限制长度。"""
    n = (name or "").strip()
    # 去掉多余空格
    n = re.sub(r"\s+", " ", n)
    # 中英文统一使用小写做匹配，但保留原始大小写在节点属性中
    return n[:200]


def _alias_keys(name: str) -> List[str]:
    """
    生成用于“同一实体判定”的若干正则化 key：
    - 全部小写
    - 去除标点和空格
    - 去除常见后缀（如 “算法”“模型”“理论”等），便于“BP 算法”≈“BP”。
    """
    base = (name or "").strip().lower()
    # 去掉空格和常见标点
    base_clean = re.sub(r"[\\s，,。\\.、·_\\-]+", "", base)
    # 去掉常见技术后缀
    suffixes = ["算法", "模型", "理论", "方法", "函数", "公式"]
    for suf in suffixes:
        if base_clean.endswith(suf):
            base_clean = base_clean[: -len(suf)]
            break
    keys = {base_clean, base}
    return [k for k in keys if k]


_STOP_ENTITY_NAMES = {
    "它",
    "他们",
    "我们",
    "你们",
    "this",
    "that",
    "they",
    "we",
    "it",
    "chapter",
    "section",
}


def _is_trivial_entity(name: str) -> bool:
    """过滤明显无意义的实体（代词、章节指代等）。"""
    n = (name or "").strip().lower()
    if not n:
        return True
    if n in _STOP_ENTITY_NAMES:
        return True
    # 纯数字或几乎全是数字
    if re.fullmatch(r"[0-9\\.\\-/]+", n):
        return True
    return False


async def build_graph_from_chunks(chunks: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict]]:
    """
    从 chunk 列表（每项含 text）逐个抽取实体与关系，合并去重后构成图。
    - 针对知识型内容做实体别名合并与噪声过滤
    chunks: [{"id","text","source"}, ...]
    返回 (nodes, edges)，供 save_graph 写入。
    """
    # name_key -> 节点 id，用于别名/缩写归一化
    key_to_id: Dict[str, str] = {}
    nodes: List[Dict] = []
    edges: List[Dict] = []

    for c in chunks:
        text = c.get("text", "")
        if not text.strip():
            continue
        ents, rels = await _extract_entities_relations_llm(text)

        # ---- 实体处理：归一化 + 别名合并 ----
        for e in ents:
            raw_name = e.get("name", "") or ""
            name = _normalize_entity_name(raw_name)
            if _is_trivial_entity(name):
                continue

            # aliases 里也可能有“同一实体的不同叫法”
            raw_aliases = e.get("aliases") or []
            if isinstance(raw_aliases, str):
                raw_aliases = [raw_aliases]
            aliases = [a for a in (raw_aliases or []) if isinstance(a, str) and a.strip()]

            # 所有候选命名（主名 + 别名）
            candidate_names = [name] + aliases
            candidate_keys: List[str] = []
            for cand in candidate_names:
                for k in _alias_keys(cand):
                    candidate_keys.append(k)

            # 查看是否已经有匹配的实体（任意 key 命中即视为同一实体）
            existing_id: str | None = None
            for k in candidate_keys:
                if k in key_to_id:
                    existing_id = key_to_id[k]
                    break

            if existing_id is None:
                # 新实体
                nid = f"e_{len(nodes)}"
                # 记录 key -> id
                for k in candidate_keys:
                    key_to_id.setdefault(k, nid)
                nodes.append(
                    {
                        "id": nid,
                        "name": name,
                        "type": e.get("type", "entity"),
                        "aliases": aliases,
                        "description": e.get("description", ""),
                    }
                )
            else:
                # 已有实体：合并别名
                for node in nodes:
                    if node["id"] == existing_id:
                        existing_aliases = set(node.get("aliases") or [])
                        for cand in candidate_names:
                            if cand and cand != node["name"]:
                                existing_aliases.add(cand)
                        node["aliases"] = sorted(existing_aliases)[: get_settings().graph_rag.max_entities_per_chunk]
                        # 更新 key 索引，避免后续重复创建
                        for k in candidate_keys:
                            key_to_id.setdefault(k, existing_id)
                        break

        # ---- 关系处理：按归一化后的实体 id 建边 ----
        for r in rels:
            s_raw = _normalize_entity_name(r.get("source", ""))
            t_raw = _normalize_entity_name(r.get("target", ""))
            if not s_raw or not t_raw or s_raw == t_raw:
                continue
            # 使用 alias key 做映射
            s_id = None
            t_id = None
            for k in _alias_keys(s_raw):
                if k in key_to_id:
                    s_id = key_to_id[k]
                    break
            for k in _alias_keys(t_raw):
                if k in key_to_id:
                    t_id = key_to_id[k]
                    break
            if not s_id or not t_id or s_id == t_id:
                continue
            edges.append(
                {
                    "source": s_id,
                    "target": t_id,
                    "relation": (r.get("relation") or "").strip()[:500],
                }
            )

    return nodes, edges


async def build_and_save_graph(kb_id: str, chunks: List[Dict[str, Any]]) -> None:
    """建图并持久化到 data/graph_rag/{kb_id}/。"""
    nodes, edges = await build_graph_from_chunks(chunks)
    save_graph(kb_id, nodes, edges)
