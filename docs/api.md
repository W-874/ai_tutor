# AI TUTOR API 文档

## 概述

AI TUTOR API 是一个 RESTful API 服务，提供知识库管理、智能问答、习题生成、深度研究等功能。所有 API 端点均返回 JSON 格式数据。

### 基础信息

- **基础 URL**: `http://localhost:8001`
- **API 版本**: v1
- **API 前缀**: `/api/v1`
- **文档地址**: `http://localhost:8001/docs` (Swagger UI)

### 认证方式

当前版本暂无认证机制，后续版本将支持 API Key 认证。

---

## 通用说明

### 成功响应格式

所有成功响应遵循以下格式：

```json
{
  "success": true,
  "data": {},
  "session_id": "可选，会话ID",
  "task_id": "可选，任务ID",
  "citations": [],
  "metadata": {
    "tokens_used": 100,
    "duration_ms": 500
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 请求是否成功，成功时为 true |
| data | any | 响应数据，具体结构因接口而异 |
| session_id | string | 可选，会话标识符 |
| task_id | string | 可选，任务标识符 |
| citations | array | 可选，引用来源列表 |
| metadata | object | 可选，元数据信息 |

### 错误响应格式

所有错误响应遵循以下格式：

```json
{
  "success": false,
  "error": "错误描述信息",
  "code": "ERROR_CODE",
  "detail": "详细错误信息（仅在调试模式下显示）",
  "request_id": "请求唯一标识符"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 请求是否成功，失败时为 false |
| error | string | 用户友好的错误描述 |
| code | string | 错误代码，用于程序判断 |
| detail | string | 详细错误信息（可选） |
| request_id | string | 请求唯一标识符，用于日志追踪 |

### HTTP 状态码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 429 | 请求频率超限 |
| 500 | 服务器内部错误 |

### WebSocket 消息格式

WebSocket 连接用于流式输出，消息格式如下：

```json
{
  "type": "thinking|citation|answer|progress|content|done|error|ready|learning_path",
  "content": "完整内容",
  "delta": "增量内容",
  "citation": {},
  "percentage": 30,
  "stage": "research|synthesis|writing",
  "timestamp": "2024-01-01T00:00:00"
}
```

| type 值 | 说明 |
|---------|------|
| thinking | 思考过程 |
| citation | 引用块 |
| answer | 回答内容（增量） |
| progress | 进度更新 |
| content | 内容块（增量） |
| done | 完成 |
| error | 错误 |
| ready | 就绪状态 |
| learning_path | 学习路径数据 |

---

## API 端点

### 1. 知识库管理 API

知识库管理 API 用于上传文档、管理知识库、查询处理状态。

#### 1.1 上传文件到知识库

**POST** `/api/v1/knowledge/upload`

上传文件到知识库，支持 PDF、TXT、MD 格式。文件将在后台异步处理，包括文本提取、切块、向量化、建立索引。

**请求**

- 方法: POST
- Content-Type: multipart/form-data

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | file | 是 | 上传的文件，支持 .pdf, .txt, .md, .markdown 格式 |

**文件限制**

- 最大文件大小: 50MB
- 支持的格式: PDF, TXT, Markdown

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/knowledge/upload" \
  -F "file=@document.pdf"
```

**响应参数**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 是否成功 |
| data.kb_id | string | 知识库唯一标识符 |
| data.task_id | string | 任务标识符（与 kb_id 相同） |

**响应示例**

```json
{
  "success": true,
  "data": {
    "kb_id": "550e8400-e29b-41d4-a716-446655440000",
    "task_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**错误响应**

| 状态码 | 说明 |
|--------|------|
| 400 | 文件格式不支持或文件大小超限 |

---

#### 1.2 获取知识库列表

**GET** `/api/v1/knowledge/list`

获取所有知识库的列表信息。

**请求**

- 方法: GET

**请求示例**

```bash
curl "http://localhost:8001/api/v1/knowledge/list"
```

**响应参数**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 是否成功 |
| data | array | 知识库列表 |
| data[].kb_id | string | 知识库ID |
| data[].name | string | 知识库名称 |
| data[].status | string | 状态: processing/ready/failed |
| data[].chunks_count | number | 文本块数量 |
| data[].created_at | string | 创建时间 |

**响应示例**

```json
{
  "success": true,
  "data": [
    {
      "kb_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "document",
      "status": "ready",
      "chunks_count": 42,
      "created_at": "2024-01-01T10:00:00"
    }
  ]
}
```

---

#### 1.3 查询知识库处理进度

**GET** `/api/v1/knowledge/{kb_id}/status`

查询指定知识库的处理状态和进度。

**请求**

- 方法: GET

**路径参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| kb_id | string | 是 | 知识库ID |

**请求示例**

```bash
curl "http://localhost:8001/api/v1/knowledge/550e8400-e29b-41d4-a716-446655440000/status"
```

**响应参数**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 是否成功 |
| data.status | string | 状态: processing/ready/failed |
| data.progress | number | 处理进度 (0-100) |
| data.chunks_count | number | 已处理的文本块数量 |
| data.error | string | 错误信息（仅失败时） |

**响应示例**

```json
{
  "success": true,
  "data": {
    "status": "ready",
    "progress": 100,
    "chunks_count": 42
  }
}
```

**错误响应**

| 状态码 | 说明 |
|--------|------|
| 404 | 知识库不存在 |

---

### 2. 问题求解器 API

问题求解器 API 提供基于知识库的智能问答功能，支持 WebSocket 流式输出。

#### 2.1 发起/继续对话

**POST** `/api/v1/solver/chat`

发起新对话或继续已有对话。返回 session_id 用于 WebSocket 连接。

**请求**

- 方法: POST
- Content-Type: application/json

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| session_id | string | 否 | 会话ID，不传则创建新会话 |
| message | string | 是 | 用户消息内容 |
| kb_id | string | 否 | 关联的知识库ID，用于 RAG 检索 |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/solver/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "请解释这个文档的核心概念",
    "kb_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**响应参数**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| session_id | string | 会话ID，用于 WebSocket 连接 |
| task_id | string | 任务ID |

**响应示例**

```json
{
  "session_id": "660e8400-e29b-41d4-a716-446655440001",
  "task_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

---

#### 2.2 WebSocket 流式输出

**WebSocket** `/api/v1/solver/stream/{session_id}`

通过 WebSocket 连接接收流式回答内容。

**连接示例**

```javascript
const ws = new WebSocket('ws://localhost:8001/api/v1/solver/stream/660e8400-e29b-41d4-a716-446655440001');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg);
};
```

**消息类型**

| type | 说明 | 包含字段 |
|------|------|----------|
| thinking | 思考过程 | content, timestamp |
| answer | 回答增量 | delta, timestamp |
| done | 完成 | content, citations, timestamp |
| error | 错误 | content, timestamp |

**消息示例**

```json
// 思考消息
{"type": "thinking", "content": "正在思考中...", "timestamp": "2024-01-01T10:00:00"}

// 回答增量
{"type": "answer", "delta": "根据文档内容，", "timestamp": "2024-01-01T10:00:01"}

// 完成消息
{
  "type": "done",
  "content": "完整的回答内容...",
  "citations": [],
  "timestamp": "2024-01-01T10:00:10"
}
```

---

### 3. 习题生成器 API

习题生成器 API 用于根据知识库内容生成习题，并支持答案提交与批改。

#### 3.1 生成题目

**POST** `/api/v1/question/generate`

根据知识库或主题生成习题。

**请求**

- 方法: POST
- Content-Type: application/json

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| kb_id | string | 否 | 知识库ID |
| topic | string | 否 | 主题，与 kb_id 二选一 |
| difficulty | string | 否 | 难度: easy/medium/hard |
| count | number | 否 | 题目数量，默认 1 |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/question/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "kb_id": "550e8400-e29b-41d4-a716-446655440000",
    "difficulty": "medium",
    "count": 3
  }'
```

**响应参数**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 是否成功 |
| data.set_id | string | 题目集合ID |
| data.questions | array | 生成的题目列表 |
| data.questions[].id | string | 题目ID |
| data.questions[].question | string | 题目内容 |
| data.questions[].type | string | 题型: choice/open/unknown |
| data.questions[].options | array | 选项（选择题） |
| data.questions[].answer | string | 参考答案 |
| data.questions[].explanation | string | 解析 |
| data.questions[].difficulty | string | 难度 |

**响应示例**

```json
{
  "success": true,
  "data": {
    "set_id": "qs_topic_20240101120000_abc123",
    "questions": [
      {
        "id": "q_abc12345_def67890",
        "number": 1,
        "question": "什么是机器学习？",
        "type": "open",
        "options": [],
        "answer": "机器学习是人工智能的一个分支...",
        "explanation": "机器学习通过算法让计算机从数据中学习...",
        "difficulty": "medium"
      }
    ]
  }
}
```

---

#### 3.2 获取题目详情

**GET** `/api/v1/question/{question_id}`

获取指定题目的详细信息。

**请求**

- 方法: GET

**路径参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| question_id | string | 是 | 题目ID |

**请求示例**

```bash
curl "http://localhost:8001/api/v1/question/q_abc12345_def67890"
```

**响应示例**

```json
{
  "success": true,
  "data": {
    "id": "q_abc12345_def67890",
    "question": "什么是机器学习？",
    "type": "open",
    "options": [],
    "answer": "机器学习是人工智能的一个分支...",
    "explanation": "机器学习通过算法让计算机从数据中学习...",
    "difficulty": "medium"
  }
}
```

---

#### 3.3 提交答案并批改

**POST** `/api/v1/question/submit`

提交用户答案并获取批改结果。

**请求**

- 方法: POST
- Content-Type: application/json

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| question_id | string | 是 | 题目ID |
| answer | string | 是 | 用户答案 |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/question/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "question_id": "q_abc12345_def67890",
    "answer": "机器学习是一种让计算机自动学习的技术"
  }'
```

**响应参数**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 是否成功 |
| data.correct | boolean | 是否正确 |
| data.score | number | 得分 (0-100) |
| data.feedback | string | 批改反馈 |
| data.reference_answer | string | 参考答案 |

**响应示例**

```json
{
  "success": true,
  "data": {
    "correct": true,
    "score": 85,
    "feedback": "回答基本正确，涵盖了机器学习的核心概念...",
    "reference_answer": "机器学习是人工智能的一个分支..."
  }
}
```

---

#### 3.4 获取题目列表

**GET** `/api/v1/question/list`

获取题目列表。

**请求**

- 方法: GET

**查询参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| kb_id | string | 否 | 按知识库筛选 |
| limit | number | 否 | 返回数量限制，默认 20 |

**请求示例**

```bash
curl "http://localhost:8001/api/v1/question/list?limit=10"
```

---

#### 3.5 获取题目集合列表

**GET** `/api/v1/question/sets/list`

获取题目集合列表。

**请求示例**

```bash
curl "http://localhost:8001/api/v1/question/sets/list"
```

---

#### 3.6 获取题目集合详情

**GET** `/api/v1/question/sets/{set_id}`

获取指定题目集合的详细信息，包含所有题目。

**请求示例**

```bash
curl "http://localhost:8001/api/v1/question/sets/qs_topic_20240101120000_abc123"
```

---

### 4. 深度研究 API

深度研究 API 用于生成多阶段研究报告，通过 WebSocket 流式输出。

#### 4.1 启动深度研究任务

**POST** `/api/v1/research/start`

启动一个新的深度研究任务。

**请求**

- 方法: POST
- Content-Type: application/json

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| topic | string | 是 | 研究主题 |
| kb_id | string | 否 | 关联的知识库ID |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/research/start" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "人工智能在教育领域的应用",
    "kb_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**响应示例**

```json
{
  "task_id": "770e8400-e29b-41d4-a716-446655440002",
  "success": true
}
```

---

#### 4.2 获取研究任务状态

**GET** `/api/v1/research/{task_id}`

获取指定研究任务的状态和结果。

**请求示例**

```bash
curl "http://localhost:8001/api/v1/research/770e8400-e29b-41d4-a716-446655440002"
```

**响应示例**

```json
{
  "success": true,
  "data": {
    "task_id": "770e8400-e29b-41d4-a716-446655440002",
    "topic": "人工智能在教育领域的应用",
    "status": "completed",
    "stages": [
      {
        "name": "research",
        "description": "资料收集与分析",
        "content": "..."
      }
    ],
    "report": "完整的研究报告内容..."
  }
}
```

---

#### 4.3 WebSocket 流式输出研究报告

**WebSocket** `/api/v1/research/stream/{task_id}`

通过 WebSocket 连接接收流式研究报告内容。

**连接示例**

```javascript
const ws = new WebSocket('ws://localhost:8001/api/v1/research/stream/770e8400-e29b-41d4-a716-446655440002');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg);
};
```

**消息类型**

| type | 说明 | 包含字段 |
|------|------|----------|
| progress | 进度更新 | stage, description, percentage |
| content | 内容增量 | stage, delta |
| done | 完成 | content, task_id |
| error | 错误 | content |

**消息示例**

```json
// 进度消息
{
  "type": "progress",
  "stage": "research",
  "description": "资料收集与分析",
  "percentage": 30
}

// 内容增量
{
  "type": "content",
  "stage": "research",
  "delta": "人工智能在教育领域的应用主要包括..."
}

// 完成消息
{
  "type": "done",
  "content": "完整的研究报告...",
  "task_id": "770e8400-e29b-41d4-a716-446655440002"
}
```

---

#### 4.4 获取研究任务列表

**GET** `/api/v1/research/list`

获取研究任务列表。

**查询参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| limit | number | 否 | 返回数量限制，默认 20 |

**请求示例**

```bash
curl "http://localhost:8001/api/v1/research/list"
```

---

### 5. 笔记本管理 API

笔记本管理 API 用于管理用户的笔记本，支持 CRUD 操作和内容添加。

#### 5.1 获取笔记本列表

**GET** `/api/v1/notebook`

获取用户的笔记本列表。

**查询参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| tag | string | 否 | 按标签筛选 |

**请求示例**

```bash
curl "http://localhost:8001/api/v1/notebook"
```

**响应示例**

```json
{
  "success": true,
  "data": [
    {
      "id": "880e8400-e29b-41d4-a716-446655440003",
      "title": "学习笔记",
      "tags": ["AI", "学习"],
      "created_at": "2024-01-01T10:00:00",
      "updated_at": "2024-01-01T11:00:00"
    }
  ]
}
```

---

#### 5.2 创建笔记本

**POST** `/api/v1/notebook`

创建新的笔记本。

**请求**

- 方法: POST
- Content-Type: application/json

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| title | string | 是 | 笔记本标题 |
| content | string | 否 | 初始内容 |
| tags | array | 否 | 标签列表 |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/notebook" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "机器学习笔记",
    "content": "这是我的机器学习学习笔记",
    "tags": ["ML", "学习"]
  }'
```

**响应示例**

```json
{
  "success": true,
  "data": {
    "id": "990e8400-e29b-41d4-a716-446655440004",
    "title": "机器学习笔记",
    "content": "这是我的机器学习学习笔记",
    "tags": ["ML", "学习"],
    "entries": [],
    "created_at": "2024-01-01T12:00:00",
    "updated_at": "2024-01-01T12:00:00"
  }
}
```

---

#### 5.3 获取笔记本详情

**GET** `/api/v1/notebook/{id}`

获取指定笔记本的详细信息。

**请求示例**

```bash
curl "http://localhost:8001/api/v1/notebook/990e8400-e29b-41d4-a716-446655440004"
```

---

#### 5.4 更新笔记本

**PUT** `/api/v1/notebook/{id}`

更新指定笔记本的内容。

**请求**

- 方法: PUT
- Content-Type: application/json

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| title | string | 否 | 新标题 |
| content | string | 否 | 新内容 |
| tags | array | 否 | 新标签列表 |

**请求示例**

```bash
curl -X PUT "http://localhost:8001/api/v1/notebook/990e8400-e29b-41d4-a716-446655440004" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "机器学习学习笔记",
    "tags": ["ML", "AI", "学习"]
  }'
```

---

#### 5.5 删除笔记本

**DELETE** `/api/v1/notebook/{id}`

删除指定的笔记本。

**请求示例**

```bash
curl -X DELETE "http://localhost:8001/api/v1/notebook/990e8400-e29b-41d4-a716-446655440004"
```

**响应示例**

```json
{
  "success": true,
  "data": {
    "deleted": true
  }
}
```

---

#### 5.6 添加内容到笔记本

**POST** `/api/v1/notebook/{id}/add`

从其他模块添加内容到笔记本。

**请求**

- 方法: POST
- Content-Type: application/json

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| source | string | 是 | 来源模块: solver/research/question 等 |
| content | string | 是 | 添加的内容 |
| ref_id | string | 否 | 来源引用ID |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/notebook/990e8400-e29b-41d4-a716-446655440004/add" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "solver",
    "content": "机器学习是人工智能的一个分支...",
    "ref_id": "660e8400-e29b-41d4-a716-446655440001"
  }'
```

---

### 6. 引导式学习 API

引导式学习 API 用于根据笔记本内容生成学习路径，并通过 WebSocket 进行交互式学习。

#### 6.1 启动引导式学习

**POST** `/api/v1/guide/start`

启动一个新的引导式学习会话。

**请求**

- 方法: POST
- Content-Type: application/json

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| notebook_id | string | 是 | 笔记本ID |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/guide/start" \
  -H "Content-Type: application/json" \
  -d '{
    "notebook_id": "990e8400-e29b-41d4-a716-446655440004"
  }'
```

**响应示例**

```json
{
  "session_id": "aa0e8400-e29b-41d4-a716-446655440005",
  "success": true
}
```

---

#### 6.2 获取学习会话状态

**GET** `/api/v1/guide/{session_id}`

获取指定学习会话的状态。

**请求示例**

```bash
curl "http://localhost:8001/api/v1/guide/aa0e8400-e29b-41d4-a716-446655440005"
```

---

#### 6.3 WebSocket 流式交互

**WebSocket** `/api/v1/guide/stream/{session_id}`

通过 WebSocket 连接进行交互式学习。

**连接示例**

```javascript
const ws = new WebSocket('ws://localhost:8001/api/v1/guide/stream/aa0e8400-e29b-41d4-a716-446655440005');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg);
};

// 发送用户消息
ws.send(JSON.stringify({ content: '请详细解释这个概念' }));
```

**消息类型**

| type | 说明 | 包含字段 |
|------|------|----------|
| progress | 进度更新 | stage, message, percentage |
| learning_path | 学习路径 | data (goals, modules) |
| content | 内容增量 | delta |
| ready | 就绪 | message |
| error | 错误 | content |

---

#### 6.4 获取学习会话列表

**GET** `/api/v1/guide/list`

获取学习会话列表。

**请求示例**

```bash
curl "http://localhost:8001/api/v1/guide/list"
```

---

### 7. 协同写作 API

协同写作 API 提供文本改写、扩展、精简、注释功能。

#### 7.1 文本改写

**POST** `/api/v1/cowriter/rewrite`

对文本进行改写、扩展、精简或添加注释。

**请求**

- 方法: POST
- Content-Type: application/json

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| text | string | 是 | 原始文本 |
| action | string | 是 | 操作类型: rewrite/expand/shorten/annotate |
| options | object | 否 | 额外选项 |

**Action 说明**

| Action | 说明 |
|--------|------|
| rewrite | 改写文本，保持原意但优化表达 |
| expand | 扩展文本，增加更多细节和内容 |
| shorten | 精简文本，提取核心要点 |
| annotate | 添加注释，解释专业术语或复杂概念 |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/cowriter/rewrite" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "机器学习是人工智能的一个分支，它使计算机能够从数据中学习。",
    "action": "expand"
  }'
```

**响应示例**

```json
{
  "success": true,
  "data": {
    "text": "机器学习是人工智能的一个重要分支，它赋予计算机从数据中自动学习和改进的能力，而无需进行明确的编程。通过算法和统计模型，机器学习系统能够识别数据中的模式，并利用这些模式做出预测或决策。"
  }
}
```

---

### 8. 创意生成 API

创意生成 API 用于从笔记本内容生成研究创意和创新点。

#### 8.1 生成研究创意

**POST** `/api/v1/ideagen/generate`

从笔记本内容生成研究创意。

**请求**

- 方法: POST
- Content-Type: application/json

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| notebook_id | string | 是 | 笔记本ID |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/ideagen/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "notebook_id": "990e8400-e29b-41d4-a716-446655440004"
  }'
```

**响应示例**

```json
{
  "success": true,
  "data": {
    "id": "bb0e8400-e29b-41d4-a716-446655440006",
    "notebook_id": "990e8400-e29b-41d4-a716-446655440004",
    "ideas": [
      {
        "id": "cc0e8400-e29b-41d4-a716-446655440007",
        "title": "基于深度学习的个性化学习路径推荐",
        "description": "利用深度学习技术分析学习者的学习行为和知识掌握情况...",
        "novelty": "结合知识图谱和学习者画像进行个性化推荐",
        "feasibility": "需要大量学习者数据和计算资源",
        "potential_impact": "可显著提升学习效率和学习体验",
        "next_steps": ["收集学习者数据", "设计推荐算法", "构建原型系统"]
      }
    ]
  }
}
```

---

#### 8.2 获取创意详情

**GET** `/api/v1/ideagen/{idea_id}`

获取指定创意批次的详细信息。

**请求示例**

```bash
curl "http://localhost:8001/api/v1/ideagen/bb0e8400-e29b-41d4-a716-446655440006"
```

---

#### 8.3 获取创意列表

**GET** `/api/v1/ideagen/list`

获取创意列表。

**查询参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| notebook_id | string | 否 | 按笔记本筛选 |
| limit | number | 否 | 返回数量限制，默认 20 |

**请求示例**

```bash
curl "http://localhost:8001/api/v1/ideagen/list"
```

---

#### 8.4 细化某个创意

**POST** `/api/v1/ideagen/refine/{idea_id}`

对某个创意进行深入细化和扩展。

**请求**

- 方法: POST

**路径参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| idea_id | string | 是 | 创意批次ID |

**查询参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| idea_index | number | 否 | 创意索引，默认 0 |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/ideagen/refine/bb0e8400-e29b-41d4-a716-446655440006?idea_index=0"
```

---

### 9. 配置管理 API

配置管理 API 用于查看和修改系统配置。

#### 9.1 查看 LLM 配置

**GET** `/api/v1/config/llm`

获取当前 LLM 配置信息。API Key 会脱敏显示。

**请求示例**

```bash
curl "http://localhost:8001/api/v1/config/llm"
```

**响应示例**

```json
{
  "success": true,
  "data": {
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "api_key": "sk-****abcd",
    "timeout": 120.0
  }
}
```

---

#### 9.2 修改 LLM 配置

**POST** `/api/v1/config/llm`

修改 LLM 配置并持久化。

**请求**

- 方法: POST
- Content-Type: application/json

**请求参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| provider | string | 否 | 提供商: openai/azure 等 |
| base_url | string | 否 | API 根地址 |
| model | string | 否 | 模型名称 |
| api_key | string | 否 | API Key |
| timeout | number | 否 | 请求超时秒数 |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/config/llm" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "api_key": "sk-your-new-key"
  }'
```

---

#### 9.3 查看 Embedding 配置

**GET** `/api/v1/config/embedding`

获取当前 Embedding 配置信息。

**请求示例**

```bash
curl "http://localhost:8001/api/v1/config/embedding"
```

**响应示例**

```json
{
  "success": true,
  "data": {
    "provider": "silicon_flow",
    "base_url": "https://api.siliconflow.cn/v1",
    "model": "BAAI/bge-large-zh-v1.5",
    "api_key": "sk-****efgh",
    "batch_size": 32
  }
}
```

---

#### 9.4 修改 Embedding 配置

**POST** `/api/v1/config/embedding`

修改 Embedding 配置并持久化。

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/config/embedding" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "your-silicon-flow-key"
  }'
```

---

### 10. 输出文件 API

输出文件 API 用于下载用户生成的文件。

#### 10.1 下载用户文件

**GET** `/api/outputs/{user_id}/{filename}`

下载用户生成的文件（如研究报告、音频等）。

**路径参数**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| user_id | string | 是 | 用户ID |
| filename | string | 是 | 文件名 |

**请求示例**

```bash
curl -O "http://localhost:8001/api/outputs/user123/report.pdf"
```

**响应**

成功时返回文件内容，失败时返回 404 错误。

---

### 11. 健康检查

#### 11.1 服务健康检查

**GET** `/health`

检查服务是否正常运行。

**请求示例**

```bash
curl "http://localhost:8001/health"
```

**响应示例**

```json
{
  "status": "ok",
  "request_id": "dd0e8400-e29b-41d4-a716-446655440008"
}
```

---

## 附录

### 数据类型定义

#### KnowledgeBase

```typescript
interface KnowledgeBase {
  kb_id: string;
  name: string;
  status: 'processing' | 'ready' | 'failed';
  chunks_count: number;
  created_at: string;
}
```

#### Question

```typescript
interface Question {
  id: string;
  number: number;
  question: string;
  type: 'choice' | 'open' | 'unknown';
  options: string[];
  answer: string;
  explanation: string;
  difficulty: 'easy' | 'medium' | 'hard';
  kb_id: string;
  created_at: string;
}
```

#### Notebook

```typescript
interface Notebook {
  id: string;
  title: string;
  content: string;
  tags: string[];
  entries: NotebookEntry[];
  created_at: string;
  updated_at: string;
}

interface NotebookEntry {
  source: string;
  content: string;
  ref_id: string;
  added_at: string;
}
```

#### Idea

```typescript
interface Idea {
  id: string;
  title: string;
  description: string;
  novelty: string;
  feasibility: string;
  potential_impact: string;
  next_steps: string[];
}
```

### 错误码列表

| 错误码 | 说明 |
|--------|------|
| CONFIGURATION_ERROR | 配置错误 |
| VALIDATION_ERROR | 参数验证错误 |
| NOT_FOUND_ERROR | 资源不存在 |
| RATE_LIMIT_ERROR | 请求频率超限 |
| LLM_ERROR | LLM 调用错误 |
| EMBEDDING_ERROR | Embedding 调用错误 |
| UNKNOWN_ERROR | 未知错误 |

---

## 更新日志

### v0.1.0 (2024-01-01)

- 初始版本发布
- 支持知识库管理、智能问答、习题生成等核心功能
- 集成 RAG 和 GraphRAG 技术
