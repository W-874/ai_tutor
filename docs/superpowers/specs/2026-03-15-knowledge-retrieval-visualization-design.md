# 知识库检索与可视化功能设计文档

## 1. 概述

### 1.1 目标

移除系统中原有的前后端配置修改功能模块，集成知识库检索功能与数据可视化功能。

### 1.2 需求摘要

| 功能 | 描述 |
|------|------|
| 配置移除 | 完全移除运行时配置修改能力，仅保留环境变量/默认配置 |
| 知识检索 | 支持关键词搜索、语义检索，同时检索文档内容和知识图谱实体 |
| 知识树可视化 | 交互式知识树展示，支持章节视图和实体视图切换 |
| 知识抽取 | 新建混合抽取模块，结合规则/NLP 和 LLM 技术 |

---

## 2. 配置修改功能移除

### 2.1 移除范围

#### 前端

| 文件 | 修改内容 |
|------|----------|
| `frontend/app.py` | 删除 `view_settings()` 函数（约 L426-L446） |
| `frontend/app.py` | 从主页卡片列表中移除"系统设置"入口 |
| `frontend/app.py` | 从视图路由中移除 `settings` 分支 |

#### 后端

| 文件 | 修改内容 |
|------|----------|
| `backend/routers/config.py` | 删除整个文件 |
| `backend/main.py` | 移除 config 路由挂载 |
| `backend/models/schemas.py` | 移除 `LLMConfig`、`EmbeddingConfig` 等请求模型 |
| `backend/config/settings.py` | 简化为仅支持环境变量和默认配置，移除 `save_runtime_config()` 函数 |

### 2.2 保留内容

| 文件 | 保留内容 |
|------|----------|
| `backend/config/config.py` | 默认配置定义（EMBEDDING_CONFIG、LLM_CONFIG 等） |
| `backend/config/settings.py` | `get_settings()` 函数，从环境变量加载配置 |

### 2.3 简化后的配置加载流程

```
启动应用
    ↓
加载 config.py 默认配置
    ↓
读取环境变量覆盖
    ↓
生成 Settings 单例
    ↓
应用运行
```

---

## 3. 知识库检索功能

### 3.1 功能概述

在知识库管理页面新增"知识检索"Tab，支持两种检索模式：

| 检索类型 | 数据源 | 技术方案 |
|----------|--------|----------|
| 文档检索 | 知识库 chunks | 向量检索 + BM25 + RRF 融合 |
| 实体检索 | 知识图谱 | 图谱节点查询 + 关系遍历 |

### 3.2 API 设计

#### 3.2.1 统一检索接口

```
POST /api/v1/knowledge/search
```

**请求体：**

```json
{
  "kb_id": "string",
  "query": "string",
  "search_type": "document | entity | hybrid",
  "top_k": 10,
  "filters": {
    "source": "optional source file filter",
    "section_level": "optional section level filter"
  }
}
```

**响应体：**

```json
{
  "results": [
    {
      "id": "chunk_id or entity_id",
      "type": "document | entity",
      "content": "文本内容或实体描述",
      "score": 0.85,
      "metadata": {
        "source": "来源文件",
        "section_title": "章节标题",
        "entity_type": "实体类型（仅实体检索）",
        "relations": ["关联实体列表（仅实体检索）"]
      }
    }
  ],
  "total": 100,
  "query_time_ms": 150
}
```

### 3.3 检索服务实现

#### 3.3.1 文档检索

复用现有 `backend/services/rag.py` 中的混合检索逻辑：

```python
class SearchService:
    def search_documents(self, kb_id: str, query: str, top_k: int) -> List[SearchResult]:
        # 1. 向量检索
        vector_results = self.rag_service.vector_search(kb_id, query, top_k * 2)
        
        # 2. BM25 检索
        bm25_results = self.rag_service.bm25_search(kb_id, query, top_k * 2)
        
        # 3. RRF 融合
        merged = self.rrf_fusion(vector_results, bm25_results)
        
        return merged[:top_k]
```

#### 3.3.2 实体检索

新建图谱查询服务：

```python
class GraphSearchService:
    def search_entities(self, kb_id: str, query: str, top_k: int) -> List[EntityResult]:
        # 1. 加载知识图谱
        graph = self.graph_store.load_graph(kb_id)
        
        # 2. 实体名称/别名匹配
        matched_entities = self.match_entities(graph, query)
        
        # 3. 获取关联实体
        results = []
        for entity in matched_entities[:top_k]:
            relations = self.get_entity_relations(graph, entity)
            results.append(EntityResult(entity, relations))
        
        return results
```

### 3.4 前端界面

在 `view_knowledge()` 函数中新增 Tab：

```python
def view_knowledge():
    tab1, tab2, tab3 = st.tabs(["📤 上传文档", "📋 知识库列表", "🔍 知识检索"])
    
    with tab3:
        st.subheader("知识检索")
        
        # 检索模式选择
        search_type = st.radio("检索类型", ["文档检索", "实体检索", "混合检索"])
        
        # 检索输入
        query = st.text_input("输入检索内容")
        
        # 检索结果展示
        if st.button("检索"):
            results = api_post("/knowledge/search", {...})
            display_search_results(results)
```

---

## 4. 知识抽取模块

### 4.1 模块位置

新建文件：`backend/services/knowledge_extractor.py`

### 4.2 混合抽取架构

```
┌─────────────────────────────────────────────────────────────┐
│                    知识抽取流水线                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ 文档输入    │ -> │ 规则预处理  │ -> │ NLP 分析    │     │
│  │ (PDF/TXT)   │    │ (结构识别)  │    │ (实体识别)  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                              │              │
│                                              ▼              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ 知识树输出  │ <- │ 结果融合    │ <- │ LLM 抽取    │     │
│  │ (JSON)      │    │ (去重/归一) │    │ (深度分析)  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 抽取阶段详解

#### 阶段 1：规则预处理

```python
class RulePreprocessor:
    """基于规则的文档结构识别"""
    
    def extract_structure(self, text: str) -> DocumentStructure:
        # 1. 标题识别（正则匹配）
        sections = self.extract_sections(text)
        
        # 2. 列表识别
        lists = self.extract_lists(text)
        
        # 3. 表格识别
        tables = self.extract_tables(text)
        
        return DocumentStructure(sections, lists, tables)
```

#### 阶段 2：NLP 分析

```python
class NLPAnalyzer:
    """基于 NLP 的实体和关键词识别"""
    
    def analyze(self, text: str) -> NLPResult:
        # 1. 中文分词（jieba）
        tokens = jieba.lcut(text)
        
        # 2. 关键词提取（TF-IDF / TextRank）
        keywords = self.extract_keywords(tokens)
        
        # 3. 命名实体识别（简单规则）
        entities = self.recognize_entities(tokens)
        
        return NLPResult(keywords, entities)
```

#### 阶段 3：LLM 深度抽取

```python
class LLMExtractor:
    """基于 LLM 的深度知识抽取"""
    
    async def extract(self, text: str, nlp_hints: NLPResult) -> LLMExtraction:
        prompt = f"""
        从以下文本中抽取知识：
        
        文本：{text}
        
        已识别的关键词：{nlp_hints.keywords}
        已识别的实体：{nlp_hints.entities}
        
        请抽取：
        1. 核心概念及其定义
        2. 概念之间的关系（包含、依赖、关联等）
        3. 重要属性和特征
        
        以 JSON 格式返回。
        """
        
        result = await self.llm.generate(prompt)
        return parse_llm_result(result)
```

#### 阶段 4：结果融合

```python
class KnowledgeFusion:
    """多源抽取结果融合"""
    
    def fuse(self, rule_result: RuleResult, nlp_result: NLPResult, 
             llm_result: LLMExtraction) -> KnowledgeTree:
        # 1. 合并章节结构
        sections = rule_result.sections
        
        # 2. 为每个章节关联知识
        for section in sections:
            # 关联 NLP 识别的关键词
            section.keywords = self.match_keywords(section, nlp_result)
            
            # 关联 LLM 抽取的概念
            section.concepts = self.match_concepts(section, llm_result)
        
        # 3. 构建知识树
        return self.build_tree(sections)
```

### 4.4 数据模型

```python
class KnowledgeNode(BaseModel):
    """知识树节点"""
    id: str
    type: str  # "section" | "concept" | "property"
    name: str
    content: Optional[str] = None
    parent_id: Optional[str] = None
    children: List["KnowledgeNode"] = []
    metadata: Dict[str, Any] = {}

class KnowledgeTree(BaseModel):
    """知识树"""
    kb_id: str
    root_nodes: List[KnowledgeNode]
    entity_index: Dict[str, KnowledgeNode]  # 实体名 -> 节点映射
    created_at: datetime
```

### 4.5 存储设计

知识树数据存储路径：

```
data/knowledge_bases/{kb_id}/
├── knowledge_tree.json      # 知识树结构
├── entity_index.json        # 实体索引
└── ...
```

---

## 5. 知识树可视化

### 5.1 技术选型

使用 `streamlit-agraph` 库实现交互式图谱展示。

**依赖添加：**

```
streamlit-agraph>=0.0.45
```

### 5.2 视图模式

#### 章节视图

按文档章节层级展示，节点类型：

| 节点类型 | 图标 | 颜色 |
|----------|------|------|
| 章节 | 📖 | 蓝色 |
| 概念 | 💡 | 绿色 |
| 属性 | 📌 | 橙色 |

#### 实体视图

按实体关系网络展示，节点类型：

| 节点类型 | 图标 | 颜色 |
|----------|------|------|
| 概念/理论 | 🔵 | 蓝色 |
| 方法/算法 | 🟢 | 绿色 |
| 工具/技术 | 🟡 | 黄色 |
| 人物 | 🔴 | 红色 |

### 5.3 前端实现

```python
def view_knowledge_tree(kb_id: str):
    st.subheader("知识树")
    
    # 视图切换
    view_mode = st.radio("视图模式", ["章节视图", "实体视图"], horizontal=True)
    
    # 加载知识树数据
    tree_data = api_get(f"/knowledge/{kb_id}/tree")
    
    # 搜索过滤
    search_term = st.text_input("搜索节点")
    if search_term:
        tree_data = filter_tree(tree_data, search_term)
    
    # 渲染图谱
    if view_mode == "章节视图":
        render_section_view(tree_data)
    else:
        render_entity_view(tree_data)
    
    # 节点详情侧边栏
    if st.session_state.get("selected_node"):
        show_node_details(st.session_state.selected_node)

def render_section_view(tree_data: dict):
    from streamlit_agraph import agraph, Node, Edge, Config
    
    nodes = []
    edges = []
    
    for node in tree_data["root_nodes"]:
        nodes.append(Node(id=node["id"], label=node["name"], 
                         size=25, color="#4A90D9"))
        for child in node.get("children", []):
            nodes.append(Node(id=child["id"], label=child["name"],
                             size=20, color="#67B7DC"))
            edges.append(Edge(source=node["id"], target=child["id"]))
    
    config = Config(width="100%", height=500, directed=True)
    agraph(nodes=nodes, edges=edges, config=config)
```

### 5.4 交互功能

| 功能 | 实现方式 |
|------|----------|
| 节点展开/折叠 | 点击节点时动态加载子节点 |
| 节点详情查看 | 点击节点后在侧边栏显示详情 |
| 知识路径导航 | 面包屑导航显示当前路径 |
| 节点搜索定位 | 搜索框过滤并高亮匹配节点 |

---

## 6. API 接口汇总

### 6.1 新增接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/knowledge/search` | 统一知识检索 |
| GET | `/api/v1/knowledge/{kb_id}/tree` | 获取知识树 |
| POST | `/api/v1/knowledge/{kb_id}/extract` | 触发知识抽取 |
| GET | `/api/v1/knowledge/{kb_id}/node/{node_id}` | 获取节点详情 |

### 6.2 移除接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/config/llm` | 查看 LLM 配置 |
| POST | `/api/v1/config/llm` | 修改 LLM 配置 |
| GET | `/api/v1/config/embedding` | 查看 Embedding 配置 |
| POST | `/api/v1/config/embedding` | 修改 Embedding 配置 |

---

## 7. 文件变更清单

### 7.1 新增文件

| 文件路径 | 描述 |
|----------|------|
| `backend/services/knowledge_extractor.py` | 知识抽取服务 |
| `backend/services/graph_search.py` | 图谱检索服务 |

### 7.2 修改文件

| 文件路径 | 修改内容 |
|----------|----------|
| `frontend/app.py` | 移除设置页面，新增知识检索和知识树展示 |
| `backend/routers/knowledge.py` | 新增检索和知识树 API |
| `backend/main.py` | 移除 config 路由 |
| `backend/config/settings.py` | 简化配置加载逻辑 |
| `backend/models/schemas.py` | 新增检索/知识树数据模型，移除配置模型 |
| `pyproject.toml` | 添加 streamlit-agraph 依赖 |

### 7.3 删除文件

| 文件路径 | 描述 |
|----------|------|
| `backend/routers/config.py` | 配置修改 API |

---

## 8. 实施计划

### 阶段 1：配置移除（预计 1-2 小时）

1. 移除前端设置界面和路由
2. 删除后端 config 路由文件
3. 简化 settings.py 配置加载逻辑
4. 移除相关数据模型

### 阶段 2：知识检索功能（预计 2-3 小时）

1. 实现统一检索服务
2. 添加图谱检索逻辑
3. 新增检索 API 接口
4. 实现前端检索界面

### 阶段 3：知识抽取模块（预计 3-4 小时）

1. 实现规则预处理器
2. 实现 NLP 分析器
3. 实现 LLM 抽取器
4. 实现结果融合逻辑
5. 集成到知识库处理流程

### 阶段 4：知识树可视化（预计 2-3 小时）

1. 添加 streamlit-agraph 依赖
2. 实现章节视图渲染
3. 实现实体视图渲染
4. 实现交互功能（搜索、详情）

### 阶段 5：测试与优化（预计 1-2 小时）

1. 功能测试
2. 性能优化
3. 样式调整

---

## 9. 风险与注意事项

1. **LLM 调用成本**：知识抽取会调用 LLM，需注意 API 成本控制
2. **抽取质量**：混合抽取需要调优各阶段的权重和阈值
3. **图谱性能**：大型知识图谱的渲染可能需要优化
4. **向后兼容**：移除配置 API 可能影响现有用户的使用习惯
