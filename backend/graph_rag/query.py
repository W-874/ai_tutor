"""
GraphRAG 查询：根据 query 找到相关实体与子图，用 LLM 基于子图上下文生成回答。

优化点：
- 利用实体的主名 + 别名（aliases）进行匹配，提升“同一实体不同叫法”的召回率
- 使用简单的关键词与别名包含匹配（后续可扩展为 embedding 匹配）
- 从匹配实体做 BFS 扩展得到子图，将节点+边描述拼成上下文，调用 LLM 生成答案
"""
from typing import Any, Dict, List, Tuple

from backend.config import get_settings
from backend.graph_rag.graph_store import load_graph
from backend.services import llm


def _collect_subgraph(
    nodes: List[Dict],
    edges: List[Dict],
    seed_node_ids: List[str],
    max_nodes: int,
) -> Tuple[List[Dict], List[Dict]]:
    """从 seed 节点 BFS 扩展，返回子图的 nodes 与 edges。"""
    node_by_id = {n["id"]: n for n in nodes}
    out_edges = {e["source"]: [] for e in edges}
    for e in edges:
        out_edges.setdefault(e["source"], []).append(e)
    sub_nodes = []
    sub_edges = []
    seen = set(seed_node_ids)
    queue = list(seed_node_ids)
    while queue and len(seen) < max_nodes:
        nid = queue.pop(0)
        if nid in node_by_id:
            sub_nodes.append(node_by_id[nid])
        for e in out_edges.get(nid, []):
            sub_edges.append(e)
            tid = e["target"]
            if tid not in seen:
                seen.add(tid)
                queue.append(tid)
    return sub_nodes, sub_edges


def _match_entities_to_query(nodes: List[Dict], query: str) -> List[str]:
    """
    基于“主名 + 别名”的关键词匹配：
    - 若 query 中包含实体名或别名（或反向包含），则选中该实体
    - 无命中时退化为选前若干实体
    """
    q_lower = (query or "").lower().strip()
    if not q_lower:
        return []
    matched: List[str] = []
    for n in nodes:
        names = [n.get("name") or ""]
        aliases = n.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        for cand in names + list(aliases):
            cand_l = (cand or "").lower().strip()
            if not cand_l:
                continue
            if cand_l in q_lower or q_lower in cand_l:
                matched.append(n["id"])
                break
    if not matched:
        # 若无匹配则取前几个节点作为 seed
        matched = [n["id"] for n in nodes[: get_settings().graph_rag.community_summary_max_nodes]]
    return matched


def _format_subgraph_context(nodes: List[Dict], edges: List[Dict]) -> str:
    """将子图格式化为给 LLM 的上下文文本。"""
    lines = ["实体："]
    for n in nodes:
        alias_str = ""
        aliases = n.get("aliases") or []
        if aliases:
            alias_str = f"（别名：{', '.join(aliases[:5])}）"
        lines.append(
            f"- {n.get('name', '')}{alias_str}（{n.get('type', '')}）：{n.get('description', '')}"
        )
    lines.append("\n关系：")
    node_names = {n["id"]: n.get("name", n["id"]) for n in nodes}
    for e in edges:
        s = node_names.get(e["source"], e["source"])
        t = node_names.get(e["target"], e["target"])
        lines.append(f"- {s} --[{e.get('relation', '')}]--> {t}")
    return "\n".join(lines)


async def graph_rag_query(kb_id: str, question: str) -> str:
    """
    执行 GraphRAG 查询：加载图 → 基于主名+别名匹配实体 → 扩展子图 → 组织上下文 → LLM 生成答案。
    """
    nodes, edges = load_graph(kb_id)
    if not nodes:
        return "当前知识库尚未构建图，无法进行 GraphRAG 查询。"
    cfg = get_settings().graph_rag
    seed_ids = _match_entities_to_query(nodes, question)
    sub_nodes, sub_edges = _collect_subgraph(nodes, edges, seed_ids, cfg.community_summary_max_nodes)
    context = _format_subgraph_context(sub_nodes, sub_edges)
    prompt = f"""基于以下知识图谱片段回答问题。若图中信息不足，可简要说明。

知识图谱片段：
{context}

问题：{question}

请结合实体及其别名的信息，给出尽量准确、简洁的回答。"""
    result = await llm.chat([{"role": "user", "content": prompt}], stream=False)
    return result if isinstance(result, str) else ""
