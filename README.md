# ai_tutor

基于LightRAG、FastAPI和Streamlit的智能教学平台。

## 功能特性

- 📊 **学习概况** - 查看整体学习进度和掌握度统计
- 📤 **文档管理** - 上传文档或插入文本，自动构建技能树
- 🌳 **技能树** - 游戏化的知识点学习路径
- ❓ **智能问答** - 基于知识库的自然语言问答
- 📝 **测验评估** - 自动生成题目，AI辅助评分

## 技术栈

- **后端**: FastAPI + SQLAlchemy + SQLite
- **前端**: Streamlit
- **RAG引擎**: LightRAG (http://localhost:9621/)
- **其他**: httpx, python-multipart

## 项目结构

```
AITutor/
├── backend/
│   ├── main.py              # FastAPI主应用
│   ├── models/
│   │   └── database.py      # 数据库模型
│   ├── services/
│   │   ├── lightrag_client.py    # LightRAG客户端
│   │   ├── skill_tree_builder.py # 技能树构建器
│   │   └── quiz_generator.py     # 测验生成器
│   └── routers/
│       ├── documents.py     # 文档管理API
│       ├── skill_tree.py    # 技能树API
│       ├── quiz.py          # 测验API
│       └── learning.py      # 学习进度API
├── frontend/
│   └── app.py               # Streamlit前端应用
├── data/                    # 数据目录
│   └── uploads/             # 上传的文档
├── requirements.txt         # Python依赖
├── start_backend.bat        # Windows后端启动脚本
├── start_frontend.bat       # Windows前端启动脚本
├── start_backend.sh         # Linux/Mac后端启动脚本
└── start_frontend.sh        # Linux/Mac前端启动脚本
```

## 安装部署

### 前置要求

- Python 3.9+
- LightRAG服务已部署在 http://localhost:9621/

### 安装步骤

1. 克隆或下载项目
2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 确保LightRAG服务正在运行

## 一键启动与结束（Windows PowerShell）

在项目根目录执行：

```powershell
# 一键启动（默认 Ollama + LightRAG + backend + Flutter frontend）
powershell -ExecutionPolicy Bypass -File .\start_all.ps1

# 一键结束（仅结束本项目进程 + docker compose down）
# 不会停止 Ollama 进程，也不会停止 Docker Desktop/Engine
powershell -ExecutionPolicy Bypass -File .\stop_all.ps1
```

### 模型提供方模式（Ollama / OpenAI-compatible）

`start_all.ps1` 现支持 `-ModelProvider ollama`（默认）和 `-ModelProvider openai-compatible` 两种模式。

重要说明：
- API key 相关变量名需与当前 LightRAG 镜像版本匹配。
- 本项目当前按 LightRAG 官方 `env.example` 使用 `LLM_BINDING_API_KEY` 和 `EMBEDDING_BINDING_API_KEY`。
- 官方参考（请以你实际拉取的镜像版本为准）：https://github.com/HKUDS/LightRAG/blob/main/env.example

Ollama 模式（默认）：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_all.ps1

# 或显式指定
powershell -ExecutionPolicy Bypass -File .\start_all.ps1 `
  -ModelProvider ollama `
  -OllamaLlmModel gemma4:26b `
  -OllamaEmbeddingModel nomic-embed-text
```

OpenAI-compatible 模式：

```powershell
# 先在当前终端注入 key（不要写入仓库）
$env:LLM_BINDING_API_KEY = "<your-llm-api-key>"
$env:EMBEDDING_BINDING_API_KEY = "<your-embedding-api-key>"

powershell -ExecutionPolicy Bypass -File .\start_all.ps1 `
  -ModelProvider openai-compatible `
  -OpenAICompatibleLlmHost "https://<your-base-url>" `
  -OpenAICompatibleLlmModel "<your-llm-model>" `
  -OpenAICompatibleEmbeddingHost "https://<your-embedding-base-url>" `
  -OpenAICompatibleEmbeddingModel "<your-embedding-model>"
```

说明：
- OpenAI-compatible 模式下，如未通过参数传入 host/model，脚本会尝试读取环境变量：`LLM_BINDING_HOST`、`LLM_MODEL`、`EMBEDDING_BINDING_HOST`、`EMBEDDING_MODEL`。
- 若缺少 `LLM_BINDING_API_KEY` 或 `EMBEDDING_BINDING_API_KEY`，脚本会直接报错并停止，不会静默失败。

### 启动应用

**Windows:**
```cmd
# 启动后端
start_backend.bat

# 打开新终端，启动前端
start_frontend.bat
```

**Linux/Mac:**
```bash
# 启动后端
chmod +x start_backend.sh
./start_backend.sh

# 打开新终端，启动前端
chmod +x start_frontend.sh
./start_frontend.sh
```

### 访问应用

- 后端API文档: http://localhost:8000/docs
- 前端应用: http://localhost:8501

## 使用指南

### 1. 上传文档或插入文本

在"文档管理"页面上传文档（PDF/TXT/DOCX/MD）或直接输入文本内容，系统会自动：
- 将内容上传到LightRAG进行索引
- 使用AI分析并生成技能树结构
- 创建知识点节点

### 2. 学习技能树

在"技能树"页面：
- 查看所有知识点及其状态
- 选择可用的知识点开始学习
- AI会生成详细的教学内容
- 完成学习后标记为完成，解锁后续知识点

### 3. 智能问答

在"智能问答"页面：
- 输入自然语言问题
- 选择查询模式（推荐使用"mix"）
- 系统基于知识库返回准确答案

### 4. 测验评估

在"测验评估"页面：
- 选择要测验的知识点
- 设置题目数量
- AI生成混合题型（选择、判断、简答）
- 提交答案后获得评分和详细反馈

## API文档

启动后端后，访问 http://localhost:8000/docs 查看完整的API文档。

## 核心API

### 文档管理
- `POST /api/documents/upload` - 上传文档
- `POST /api/documents/insert-text` - 插入文本

### 技能树
- `GET /api/skill-tree/nodes` - 获取所有知识点
- `GET /api/skill-tree/nodes/{node_id}` - 获取单个知识点
- `GET /api/skill-tree/nodes/{node_id}/learning-content` - 获取教学内容
- `POST /api/skill-tree/nodes/{node_id}/complete` - 标记完成

### 测验评估
- `GET /api/quiz/generate/{node_id}` - 生成测验
- `POST /api/quiz/submit/{node_id}` - 提交答案
- `GET /api/quiz/records/{node_id}` - 获取测验历史

### 学习进度
- `GET /api/learning/query` - 智能问答
- `GET /api/learning/progress` - 获取学习进度
- `GET /api/learning/progress/{node_id}` - 获取单个知识点进度

## 注意事项

1. 确保LightRAG服务在 http://localhost:9621/ 正常运行
2. 首次使用需要先上传文档或插入文本
3. 技能树构建和教学内容生成可能需要一些时间
4. 学习数据存储在 `data/aitutor.db` SQLite数据库中

## 许可证

本项目遵循相关开源许可证。
