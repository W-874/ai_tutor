"""
AI TUTOR Streamlit 前端
"""
import os
import time
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from functools import wraps

import streamlit as st
import httpx

API_BASE = os.getenv("API_BASE", "http://localhost:8001")

DEFAULT_TIMEOUT = 60.0
UPLOAD_TIMEOUT = 120.0
MAX_RETRIES = 3
RETRY_DELAY = 1.0


class APIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, is_retryable: bool = False):
        self.message = message
        self.status_code = status_code
        self.is_retryable = is_retryable
        super().__init__(self.message)


def get_friendly_error_message(error: Exception) -> str:
    if isinstance(error, APIError):
        return error.message
    
    error_str = str(error).lower()
    
    if "connection" in error_str or "connect" in error_str:
        return "无法连接到服务器，请检查服务器是否正在运行"
    elif "timeout" in error_str or "timed out" in error_str:
        return "请求超时，请稍后重试"
    elif "network" in error_str:
        return "网络错误，请检查网络连接"
    elif "500" in error_str:
        return "服务器内部错误，请稍后重试"
    elif "401" in error_str or "unauthorized" in error_str:
        return "认证失败，请检查 API 配置"
    elif "403" in error_str or "forbidden" in error_str:
        return "权限不足，无法访问该资源"
    elif "404" in error_str or "not found" in error_str:
        return "请求的资源不存在"
    elif "429" in error_str or "rate limit" in error_str:
        return "请求过于频繁，请稍后重试"
    else:
        return f"请求失败: {str(error)}"


def is_retryable_error(error: Exception) -> bool:
    if isinstance(error, APIError):
        return error.is_retryable
    
    error_str = str(error).lower()
    retryable_keywords = ["timeout", "connection", "network", "500", "502", "503", "504", "429"]
    return any(keyword in error_str for keyword in retryable_keywords)


def api_request(
    method: str,
    endpoint: str,
    params: dict = None,
    data: dict = None,
    files: dict = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES
) -> Dict[str, Any]:
    url = f"{API_BASE}{endpoint}"
    last_error = None
    
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=timeout) as client:
                if method.upper() == "GET":
                    resp = client.get(url, params=params)
                elif method.upper() == "POST":
                    if files:
                        resp = client.post(url, files=files)
                    else:
                        resp = client.post(url, json=data)
                else:
                    raise ValueError(f"不支持的 HTTP 方法: {method}")
                
                if resp.status_code >= 500:
                    raise APIError(
                        f"服务器错误 (HTTP {resp.status_code})",
                        status_code=resp.status_code,
                        is_retryable=True
                    )
                
                if resp.status_code == 429:
                    raise APIError(
                        "请求过于频繁，请稍后重试",
                        status_code=resp.status_code,
                        is_retryable=True
                    )
                
                if resp.status_code >= 400:
                    try:
                        error_data = resp.json()
                        error_msg = error_data.get("detail", error_data.get("error", f"HTTP {resp.status_code}"))
                    except:
                        error_msg = f"请求失败 (HTTP {resp.status_code})"
                    raise APIError(error_msg, status_code=resp.status_code, is_retryable=False)
                
                return resp.json()
                
        except httpx.TimeoutException as e:
            last_error = APIError("请求超时", is_retryable=True)
        except httpx.ConnectError as e:
            last_error = APIError("无法连接到服务器", is_retryable=True)
        except httpx.NetworkError as e:
            last_error = APIError("网络错误", is_retryable=True)
        except APIError as e:
            last_error = e
            if not e.is_retryable:
                break
        except Exception as e:
            last_error = APIError(str(e), is_retryable=False)
            break
        
        if attempt < max_retries - 1 and is_retryable_error(last_error):
            time.sleep(RETRY_DELAY * (attempt + 1))
    
    return {
        "success": False,
        "error": get_friendly_error_message(last_error),
        "is_retryable": is_retryable_error(last_error)
    }


def api_get(endpoint: str, params: dict = None, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    return api_request("GET", endpoint, params=params, timeout=timeout)


def api_post(
    endpoint: str,
    data: dict = None,
    files: dict = None,
    timeout: float = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    return api_request("POST", endpoint, data=data, files=files, timeout=timeout)


def show_error_with_retry(
    error_message: str,
    is_retryable: bool = False,
    retry_callback: Callable = None,
    retry_key: str = None
):
    st.error(f"❌ {error_message}")
    
    if is_retryable and retry_callback and retry_key:
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            if st.button("🔄 重试", key=retry_key):
                retry_callback()
                st.rerun()


def init_session_state(defaults: Dict[str, Any]):
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_session_state(keys: list = None, prefix: str = None):
    if keys:
        for key in keys:
            if key in st.session_state:
                del st.session_state[key]
    elif prefix:
        keys_to_delete = [k for k in st.session_state.keys() if k.startswith(prefix)]
        for key in keys_to_delete:
            del st.session_state[key]


def get_kb_options() -> tuple:
    result = api_get("/api/v1/knowledge/list")
    
    if not result.get("success", False):
        return ["不使用知识库"], {}
    
    data = result.get("data", [])
    kb_options = ["不使用知识库"] + [kb.get("name", "未命名") for kb in data]
    kb_map = {kb.get("name"): kb.get("kb_id") for kb in data}
    
    return kb_options, kb_map


def page_home():
    st.title("📚 AI TUTOR")
    
    st.markdown("""
    <p style='font-size: 1.2em; color: #666;'>
    AI驱动的个性化学习助手 - 帮助您更高效地学习和研究
    </p>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div style='padding: 20px; background: #f0f2f6; border-radius: 10px;'>
        <h3>📚 知识库管理</h3>
        <p>上传文档，构建个人知识库。支持PDF、TXT、Markdown格式。</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='padding: 20px; background: #f0f2f6; border-radius: 10px;'>
        <h3>💬 智能问答</h3>
        <p>基于知识库的智能问答，提供精准引用和详细解释。</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style='padding: 20px; background: #f0f2f6; border-radius: 10px;'>
        <h3>📝 习题生成</h3>
        <p>自动生成练习题，支持多种题型和难度级别。</p>
        </div>
        """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div style='padding: 20px; background: #f0f2f6; border-radius: 10px;'>
        <h3>🔍 深度研究</h3>
        <p>多阶段研究流程，生成结构化研究报告。</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='padding: 20px; background: #f0f2f6; border-radius: 10px;'>
        <h3>📓 笔记本</h3>
        <p>个人知识管理，记录学习心得和研究成果。</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style='padding: 20px; background: #f0f2f6; border-radius: 10px;'>
        <h3>💡 创意生成</h3>
        <p>从笔记内容中自动生成研究创意和新想法。</p>
        </div>
        """, unsafe_allow_html=True)


def page_knowledge():
    st.title("📚 知识库管理")
    
    init_session_state({
        "kb_refresh_count": 0,
        "kb_upload_in_progress": False
    })
    
    tab1, tab2 = st.tabs(["上传文档", "知识库列表"])
    
    with tab1:
        st.markdown("### 上传文档")
        st.markdown("支持 PDF、TXT、Markdown 格式")
        
        uploaded_file = st.file_uploader("选择文件", type=["pdf", "txt", "md"])
        
        if uploaded_file is not None:
            st.info(f"文件: {uploaded_file.name} ({uploaded_file.size} bytes)")
            
            if st.button("📤 上传并处理", type="primary", disabled=st.session_state.kb_upload_in_progress):
                st.session_state.kb_upload_in_progress = True
                
                with st.status("正在上传和处理文档...", expanded=True) as status:
                    status.write("📁 准备文件...")
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
                        tmp.write(uploaded_file.getbuffer())
                        temp_path = tmp.name
                    
                    try:
                        status.write("⬆️ 上传文件到服务器...")
                        result = api_post(
                            "/api/v1/knowledge/upload",
                            files={"file": (uploaded_file.name, open(temp_path, "rb"))},
                            timeout=UPLOAD_TIMEOUT
                        )
                        
                        if result.get("success"):
                            kb_id = result.get("data", {}).get("kb_id")
                            status.update(label="✅ 上传成功！", state="complete")
                            st.success(f"✅ 上传成功！知识库ID: {kb_id}")
                            st.info("文档正在后台处理中，请稍后刷新查看状态")
                            st.session_state.kb_refresh_count += 1
                        else:
                            status.update(label="❌ 上传失败", state="error")
                            show_error_with_retry(
                                result.get("error", "未知错误"),
                                result.get("is_retryable", True),
                                lambda: None,
                                "retry_upload"
                            )
                    finally:
                        os.unlink(temp_path)
                        st.session_state.kb_upload_in_progress = False
    
    with tab2:
        st.markdown("### 知识库列表")
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🔄 刷新"):
                st.session_state.kb_refresh_count += 1
                st.rerun()
        
        with st.spinner("加载知识库列表..."):
            kb_list = api_get("/api/v1/knowledge/list")
        
        if not kb_list.get("success", False):
            show_error_with_retry(
                kb_list.get("error", "获取知识库列表失败"),
                kb_list.get("is_retryable", True),
                lambda: st.rerun(),
                "retry_kb_list"
            )
        else:
            data = kb_list.get("data", [])
            
            if not data:
                st.info("暂无知识库，请先上传文档")
            else:
                for kb in data:
                    with st.expander(f"📁 {kb.get('name', '未命名')} - {kb.get('status', 'unknown')}"):
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.write(f"**ID:** {kb.get('kb_id')}")
                            st.write(f"**状态:** {kb.get('status')}")
                            st.write(f"**文档块数:** {kb.get('chunks_count', 0)}")
                        
                        with col2:
                            if st.button("📊 查看详情", key=f"detail_{kb.get('kb_id')}"):
                                with st.spinner("获取详情..."):
                                    status = api_get(f"/api/v1/knowledge/{kb.get('kb_id')}/status")
                                if status.get("success"):
                                    st.json(status.get("data"))
                                else:
                                    st.error(status.get("error", "获取详情失败"))


def page_solver():
    st.title("💬 智能问答")
    
    init_session_state({
        "solver_messages": [],
        "solver_session_id": None,
        "solver_kb_id": None
    })
    
    with st.spinner("加载知识库列表..."):
        kb_options, kb_map = get_kb_options()
    
    selected_kb = st.selectbox("选择知识库", kb_options, key="solver_kb_select")
    kb_id = kb_map.get(selected_kb) if selected_kb != "不使用知识库" else None
    st.session_state.solver_kb_id = kb_id
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🗑️ 清空对话"):
            reset_session_state(["solver_messages", "solver_session_id"])
            st.rerun()
    
    for msg in st.session_state.solver_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    user_input = st.chat_input("输入您的问题...")
    
    if user_input:
        st.session_state.solver_messages.append({"role": "user", "content": user_input})
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            
            with st.status("思考中...", expanded=False) as status:
                status.write("🧠 分析问题...")
                
                result = api_post("/api/v1/solver/chat", {
                    "message": user_input,
                    "kb_id": kb_id,
                    "session_id": st.session_state.solver_session_id
                }, timeout=120.0)
                
                if result.get("success", False):
                    if result.get("session_id"):
                        st.session_state.solver_session_id = result.get("session_id")
                    
                    response_text = result.get("data", {}).get("response", "")
                    status.update(label="✅ 回答完成", state="complete")
                    response_placeholder.markdown(response_text)
                    st.session_state.solver_messages.append({"role": "assistant", "content": response_text})
                else:
                    status.update(label="❌ 请求失败", state="error")
                    error_msg = result.get("error", "未知错误")
                    response_placeholder.error(f"❌ {error_msg}")
                    
                    if result.get("is_retryable"):
                        if st.button("🔄 重试", key="retry_solver"):
                            st.session_state.solver_messages.pop()
                            st.rerun()


def page_question():
    st.title("📝 习题生成")
    
    init_session_state({
        "question_generated": [],
        "question_topic": "",
        "question_difficulty": "中等"
    })
    
    tab1, tab2 = st.tabs(["生成习题", "提交答案"])
    
    with tab1:
        st.markdown("### 生成习题")
        
        with st.spinner("加载知识库列表..."):
            kb_options, kb_map = get_kb_options()
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_kb = st.selectbox("选择知识库", kb_options, key="question_kb_select")
            kb_id = kb_map.get(selected_kb) if selected_kb != "不使用知识库" else None
        
        with col2:
            topic = st.text_input("主题（可选）", value=st.session_state.question_topic)
            difficulty = st.select_slider("难度", ["简单", "中等", "困难"], value=st.session_state.question_difficulty)
            count = st.slider("题目数量", 1, 10, 3)
        
        if st.button("📝 生成习题", type="primary"):
            st.session_state.question_topic = topic
            st.session_state.question_difficulty = difficulty
            
            with st.status("正在生成习题...", expanded=True) as status:
                status.write("📚 分析知识库内容...")
                status.write("🧠 生成习题...")
                
                result = api_post("/api/v1/question/generate", {
                    "kb_id": kb_id,
                    "topic": topic,
                    "difficulty": difficulty,
                    "count": count
                }, timeout=120.0)
                
                if result.get("success"):
                    questions = result.get("data", {}).get("questions", [])
                    status.update(label=f"✅ 成功生成 {len(questions)} 道习题！", state="complete")
                    st.success(f"✅ 成功生成 {len(questions)} 道习题！")
                    
                    for i, q in enumerate(questions):
                        with st.expander(f"题目 {i+1}: {q.get('question', '')[:50]}..."):
                            st.markdown(f"**题干:** {q.get('question')}")
                            if q.get("options"):
                                st.markdown(f"**选项:** {', '.join(q.get('options'))}")
                            st.markdown(f"**类型:** {q.get('type')}")
                            st.markdown(f"**难度:** {q.get('difficulty')}")
                            st.session_state[f"question_{q.get('id')}"] = q
                    
                    st.session_state.question_generated = questions
                else:
                    status.update(label="❌ 生成失败", state="error")
                    show_error_with_retry(
                        result.get("error", "未知错误"),
                        result.get("is_retryable", True),
                        lambda: None,
                        "retry_question_gen"
                    )
    
    with tab2:
        st.markdown("### 提交答案")
        
        question_id = st.text_input("题目ID")
        answer = st.text_area("您的答案")
        
        if st.button("📤 提交答案", type="primary"):
            if not question_id or not answer:
                st.warning("请输入题目ID和答案")
            else:
                with st.status("正在批改...", expanded=True) as status:
                    status.write("📝 分析答案...")
                    
                    result = api_post("/api/v1/question/submit", {
                        "question_id": question_id,
                        "answer": answer
                    }, timeout=60.0)
                    
                    if result.get("success"):
                        data = result.get("data", {})
                        status.update(label="✅ 批改完成！", state="complete")
                        st.success(f"✅ 批改完成！得分: {data.get('score', 0)}")
                        st.markdown(f"**是否正确:** {'✅' if data.get('correct') else '❌'}")
                        st.markdown(f"**反馈:** {data.get('feedback')}")
                    else:
                        status.update(label="❌ 批改失败", state="error")
                        show_error_with_retry(
                            result.get("error", "未知错误"),
                            result.get("is_retryable", True),
                            lambda: None,
                            "retry_submit"
                        )


def page_research():
    st.title("🔍 深度研究")
    
    init_session_state({
        "research_tasks": [],
        "research_refresh_count": 0
    })
    
    st.markdown("输入研究主题，系统将进行多阶段深度研究并生成报告。")
    
    topic = st.text_input("研究主题", placeholder="例如：人工智能在教育领域的应用")
    
    if st.button("🚀 开始研究", type="primary"):
        if not topic:
            st.warning("请输入研究主题")
        else:
            with st.status("正在启动研究任务...", expanded=True) as status:
                status.write("📋 准备研究计划...")
                
                result = api_post("/api/v1/research/start", {"topic": topic}, timeout=60.0)
                
                if result.get("success"):
                    task_id = result.get("task_id")
                    status.update(label="✅ 研究任务已启动！", state="complete")
                    st.success(f"✅ 研究任务已启动！任务ID: {task_id}")
                    
                    st.markdown("### 研究进度")
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    stages = ["资料收集", "知识综合", "报告撰写"]
                    for i, stage in enumerate(stages):
                        progress_bar.progress((i + 1) * 33)
                        status_text.markdown(f"**当前阶段:** {stage}")
                        time.sleep(0.5)
                    
                    progress_bar.progress(100)
                    status_text.markdown("**状态:** ✅ 完成")
                    
                    st.info("研究任务已完成，请查看研究历史获取报告")
                    st.session_state.research_tasks.append(task_id)
                else:
                    status.update(label="❌ 启动失败", state="error")
                    show_error_with_retry(
                        result.get("error", "未知错误"),
                        result.get("is_retryable", True),
                        lambda: None,
                        "retry_research"
                    )
    
    st.markdown("### 研究历史")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 刷新"):
            st.session_state.research_refresh_count += 1
            st.rerun()
    
    with st.spinner("加载研究历史..."):
        research_list = api_get("/api/v1/research/list")
    
    if research_list.get("success"):
        for r in research_list.get("data", []):
            with st.expander(f"📁 {r.get('topic', '未知主题')} - {r.get('status', 'unknown')}"):
                st.write(f"**任务ID:** {r.get('task_id')}")
                st.write(f"**创建时间:** {r.get('created_at')}")
    else:
        show_error_with_retry(
            research_list.get("error", "获取研究历史失败"),
            research_list.get("is_retryable", True),
            lambda: st.rerun(),
            "retry_research_list"
        )


def page_notebook():
    st.title("📓 笔记本管理")
    
    init_session_state({
        "notebook_refresh_count": 0
    })
    
    tab1, tab2, tab3 = st.tabs(["笔记本列表", "创建笔记本", "添加内容"])
    
    with tab1:
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🔄 刷新"):
                st.session_state.notebook_refresh_count += 1
                st.rerun()
        
        with st.spinner("加载笔记本列表..."):
            notebooks = api_get("/api/v1/notebook")
        
        if not notebooks.get("success"):
            show_error_with_retry(
                notebooks.get("error", "获取笔记本列表失败"),
                notebooks.get("is_retryable", True),
                lambda: st.rerun(),
                "retry_notebook_list"
            )
        else:
            data = notebooks.get("data", [])
            
            if not data:
                st.info("暂无笔记本，请创建一个")
            else:
                for nb in data:
                    with st.expander(f"📓 {nb.get('title', '未命名')}"):
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.write(f"**ID:** {nb.get('id')}")
                            st.write(f"**标签:** {', '.join(nb.get('tags', []))}")
                            st.write(f"**创建时间:** {nb.get('created_at')}")
                        
                        with col2:
                            if st.button("🗑️ 删除", key=f"del_{nb.get('id')}"):
                                with st.spinner("删除中..."):
                                    result = api_post(f"/api/v1/notebook/{nb.get('id')}", {})
                                if result.get("success"):
                                    st.success("已删除")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error(result.get("error", "删除失败"))
    
    with tab2:
        st.markdown("### 创建新笔记本")
        
        title = st.text_input("标题")
        content = st.text_area("内容（可选）")
        tags = st.text_input("标签（逗号分隔）")
        
        if st.button("➕ 创建"):
            if not title:
                st.warning("请输入标题")
            else:
                with st.spinner("创建中..."):
                    result = api_post("/api/v1/notebook", {
                        "title": title,
                        "content": content,
                        "tags": [t.strip() for t in tags.split(",") if t.strip()]
                    })
                
                if result.get("success"):
                    st.success("✅ 笔记本创建成功！")
                    st.session_state.notebook_refresh_count += 1
                else:
                    show_error_with_retry(
                        result.get("error", "未知错误"),
                        result.get("is_retryable", True),
                        lambda: None,
                        "retry_create_nb"
                    )
    
    with tab3:
        st.markdown("### 添加内容到笔记本")
        
        with st.spinner("加载笔记本列表..."):
            notebooks = api_get("/api/v1/notebook")
        
        if not notebooks.get("success"):
            show_error_with_retry(
                notebooks.get("error", "获取笔记本列表失败"),
                notebooks.get("is_retryable", True),
                lambda: st.rerun(),
                "retry_nb_list_add"
            )
        else:
            nb_data = notebooks.get("data", [])
            nb_options = [nb.get("title") for nb in nb_data]
            nb_map = {nb.get("title"): nb.get("id") for nb in nb_data}
            
            if not nb_options:
                st.info("请先创建笔记本")
            else:
                selected_nb = st.selectbox("选择笔记本", nb_options)
                nb_id = nb_map.get(selected_nb)
                
                source = st.selectbox("来源", ["solver", "research", "question", "manual"])
                content = st.text_area("内容")
                
                if st.button("➕ 添加"):
                    if not content:
                        st.warning("请输入内容")
                    else:
                        with st.spinner("添加中..."):
                            result = api_post(f"/api/v1/notebook/{nb_id}/add", {
                                "source": source,
                                "content": content
                            })
                        
                        if result.get("success"):
                            st.success("✅ 内容已添加！")
                        else:
                            show_error_with_retry(
                                result.get("error", "未知错误"),
                                result.get("is_retryable", True),
                                lambda: None,
                                "retry_add_content"
                            )


def page_guide():
    st.title("🎯 引导式学习")
    
    init_session_state({
        "guide_session_id": None
    })
    
    st.markdown("选择一个笔记本开始引导式学习，系统将为您生成个性化的学习路径。")
    
    with st.spinner("加载笔记本列表..."):
        notebooks = api_get("/api/v1/notebook")
    
    nb_options = []
    nb_map = {}
    
    if notebooks.get("success", True):
        for nb in notebooks.get("data", []):
            nb_options.append(nb.get("title"))
            nb_map[nb.get("title")] = nb.get("id")
    
    if not nb_options:
        st.info("请先创建笔记本")
    else:
        selected_nb = st.selectbox("选择笔记本", nb_options)
        nb_id = nb_map.get(selected_nb)
        
        if st.button("🚀 开始学习", type="primary"):
            with st.status("正在生成学习路径...", expanded=True) as status:
                status.write("📚 分析笔记本内容...")
                status.write("🎯 生成个性化学习路径...")
                
                result = api_post("/api/v1/guide/start", {"notebook_id": nb_id}, timeout=120.0)
                
                if result.get("success"):
                    session_id = result.get("session_id")
                    st.session_state.guide_session_id = session_id
                    status.update(label="✅ 学习会话已创建！", state="complete")
                    st.success(f"✅ 学习会话已创建！会话ID: {session_id}")
                    st.info("学习路径正在生成中...")
                else:
                    status.update(label="❌ 启动失败", state="error")
                    show_error_with_retry(
                        result.get("error", "未知错误"),
                        result.get("is_retryable", True),
                        lambda: None,
                        "retry_guide"
                    )


def page_cowriter():
    st.title("✍️ 协同写作")
    
    init_session_state({
        "cowriter_history": []
    })
    
    st.markdown("### 文本处理")
    
    text = st.text_area("输入文本", height=150)
    action = st.selectbox("处理方式", ["rewrite", "expand", "shorten", "annotate"])
    
    action_names = {
        "rewrite": "重写",
        "expand": "扩展",
        "shorten": "精简",
        "annotate": "注释"
    }
    
    if st.button("✨ 处理"):
        if not text:
            st.warning("请输入文本")
        else:
            with st.status(f"正在{action_names.get(action, '处理')}...", expanded=True) as status:
                status.write(f"📝 正在{action_names.get(action, '处理')}文本...")
                
                result = api_post("/api/v1/cowriter/rewrite", {
                    "text": text,
                    "action": action
                }, timeout=120.0)
                
                if result.get("success"):
                    status.update(label="✅ 处理完成！", state="complete")
                    st.success("✅ 处理完成！")
                    st.markdown("### 处理结果")
                    processed_text = result.get("data", {}).get("text", "")
                    st.write(processed_text)
                    st.session_state.cowriter_history.append({
                        "action": action,
                        "original": text,
                        "result": processed_text
                    })
                else:
                    status.update(label="❌ 处理失败", state="error")
                    show_error_with_retry(
                        result.get("error", "未知错误"),
                        result.get("is_retryable", True),
                        lambda: None,
                        "retry_cowriter"
                    )


def page_ideagen():
    st.title("💡 创意生成")
    
    init_session_state({
        "ideagen_results": []
    })
    
    st.markdown("从笔记本内容中生成研究创意和新想法。")
    
    with st.spinner("加载笔记本列表..."):
        notebooks = api_get("/api/v1/notebook")
    
    nb_options = []
    nb_map = {}
    
    if notebooks.get("success", True):
        for nb in notebooks.get("data", []):
            nb_options.append(nb.get("title"))
            nb_map[nb.get("title")] = nb.get("id")
    
    if not nb_options:
        st.info("请先创建笔记本")
    else:
        selected_nb = st.selectbox("选择笔记本", nb_options)
        nb_id = nb_map.get(selected_nb)
        
        if st.button("💡 生成创意", type="primary"):
            with st.status("正在生成创意...", expanded=True) as status:
                status.write("📚 分析笔记本内容...")
                status.write("💡 生成研究创意...")
                
                result = api_post("/api/v1/ideagen/generate", {"notebook_id": nb_id}, timeout=120.0)
                
                if result.get("success"):
                    ideas = result.get("data", {}).get("ideas", [])
                    status.update(label=f"✅ 成功生成 {len(ideas)} 个创意！", state="complete")
                    
                    st.markdown("### 生成的创意")
                    st.session_state.ideagen_results = ideas
                    
                    for i, idea in enumerate(ideas):
                        with st.expander(f"💡 创意 {i+1}: {idea.get('title', '未命名')}"):
                            st.markdown(f"**描述:** {idea.get('description', '')}")
                            st.markdown(f"**新颖性:** {idea.get('novelty', '')}")
                            st.markdown(f"**可行性:** {idea.get('feasibility', '')}")
                            st.markdown(f"**潜在影响:** {idea.get('potential_impact', '')}")
                            if idea.get('next_steps'):
                                st.markdown(f"**下一步:** {', '.join(idea.get('next_steps', []))}")
                else:
                    status.update(label="❌ 生成失败", state="error")
                    show_error_with_retry(
                        result.get("error", "未知错误"),
                        result.get("is_retryable", True),
                        lambda: None,
                        "retry_ideagen"
                    )


def page_settings():
    st.title("⚙️ 设置")
    
    init_session_state({
        "settings_llm_provider": "openai",
        "settings_llm_base_url": "https://api.openai.com/v1",
        "settings_llm_model": "gpt-4o-mini"
    })
    
    tab1, tab2 = st.tabs(["LLM 配置", "Embedding 配置"])
    
    with tab1:
        st.markdown("### LLM 配置")
        
        with st.spinner("加载当前配置..."):
            current = api_get("/api/v1/config/llm")
        
        if current.get("success"):
            data = current.get("data", {})
            
            st.write(f"**Provider:** {data.get('provider')}")
            st.write(f"**Base URL:** {data.get('base_url')}")
            st.write(f"**Model:** {data.get('model')}")
            st.write(f"**API Key:** {data.get('api_key')}")
        else:
            st.warning("无法加载当前配置")
        
        st.markdown("### 更新配置")
        
        provider = st.text_input("Provider", value=st.session_state.settings_llm_provider)
        base_url = st.text_input("Base URL", value=st.session_state.settings_llm_base_url)
        model = st.text_input("Model", value=st.session_state.settings_llm_model)
        api_key = st.text_input("API Key", type="password")
        
        if st.button("💾 保存"):
            with st.spinner("保存配置中..."):
                result = api_post("/api/v1/config/llm", {
                    "provider": provider,
                    "base_url": base_url,
                    "model": model,
                    "api_key": api_key
                })
            
            if result.get("success"):
                st.success("✅ 配置已更新！")
                st.session_state.settings_llm_provider = provider
                st.session_state.settings_llm_base_url = base_url
                st.session_state.settings_llm_model = model
            else:
                show_error_with_retry(
                    result.get("error", "未知错误"),
                    result.get("is_retryable", True),
                    lambda: None,
                    "retry_save_llm"
                )
    
    with tab2:
        st.markdown("### Embedding 配置")
        
        with st.spinner("加载当前配置..."):
            current = api_get("/api/v1/config/embedding")
        
        if current.get("success"):
            data = current.get("data", {})
            
            st.write(f"**Provider:** {data.get('provider')}")
            st.write(f"**Base URL:** {data.get('base_url')}")
            st.write(f"**Model:** {data.get('model')}")
        else:
            st.warning("无法加载当前配置")


def main():
    st.set_page_config(page_title="AI TUTOR - AI学习助手", layout="wide")
    
    init_session_state({
        "page": "首页"
    })
    
    pages = ["首页", "知识库", "智能问答", "习题生成", "深度研究", "笔记本", "引导学习", "协同写作", "创意生成", "设置"]
    
    with st.sidebar:
        st.markdown("### 🧭 导航")
        page = st.radio(
            "导航",
            pages,
            index=pages.index(st.session_state.page),
            label_visibility="collapsed"
        )
        
        st.divider()
        
        if st.button("🔄 重置所有状态", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key != "page":
                    del st.session_state[key]
            st.rerun()
    
    st.session_state.page = page
    
    page_handlers = {
        "首页": page_home,
        "知识库": page_knowledge,
        "智能问答": page_solver,
        "习题生成": page_question,
        "深度研究": page_research,
        "笔记本": page_notebook,
        "引导学习": page_guide,
        "协同写作": page_cowriter,
        "创意生成": page_ideagen,
        "设置": page_settings
    }
    
    handler = page_handlers.get(page)
    if handler:
        handler()


if __name__ == "__main__":
    main()
