"""
公共文件辅助模块 - 提供统一的文件操作工具函数

功能：
- 获取数据根目录
- 确保目录存在
- 通用 JSON 文件加载/保存
- 加载笔记本数据
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from backend.config import get_settings


def get_data_root() -> Path:
    """获取数据根目录路径"""
    return get_settings().data_root


def ensure_dir(path: Union[str, Path]) -> Path:
    """
    确保目录存在，如果不存在则创建
    
    Args:
        path: 目录路径
        
    Returns:
        Path: 目录路径对象
    """
    p = Path(path) if isinstance(path, str) else path
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_user_data_dir(subdir: str) -> Path:
    """
    获取用户数据子目录路径
    
    Args:
        subdir: 子目录名称，如 'questions', 'research', 'notebooks' 等
        
    Returns:
        Path: 用户数据子目录路径
    """
    path = get_data_root() / "user" / subdir
    ensure_dir(path)
    return path


def load_json_file(path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """
    加载 JSON 文件
    
    Args:
        path: 文件路径
        
    Returns:
        解析后的字典，如果文件不存在或解析失败则返回 None
    """
    p = Path(path) if isinstance(path, str) else path
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_json_file(path: Union[str, Path], data: Dict[str, Any]) -> bool:
    """
    保存数据到 JSON 文件
    
    Args:
        path: 文件路径
        data: 要保存的数据
        
    Returns:
        是否保存成功
    """
    p = Path(path) if isinstance(path, str) else path
    ensure_dir(p.parent)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def delete_file(path: Union[str, Path]) -> bool:
    """
    删除文件
    
    Args:
        path: 文件路径
        
    Returns:
        是否删除成功
    """
    p = Path(path) if isinstance(path, str) else path
    if p.exists():
        try:
            p.unlink()
            return True
        except IOError:
            return False
    return False


def list_json_files(directory: Union[str, Path]) -> List[Path]:
    """
    列出目录中的所有 JSON 文件
    
    Args:
        directory: 目录路径
        
    Returns:
        JSON 文件路径列表
    """
    d = Path(directory) if isinstance(directory, str) else directory
    if not d.exists():
        return []
    return list(d.glob("*.json"))


def load_notebook(notebook_id: str) -> Optional[Dict[str, Any]]:
    """
    加载笔记本数据
    
    Args:
        notebook_id: 笔记本 ID
        
    Returns:
        笔记本数据字典，如果不存在则返回 None
    """
    path = get_user_data_dir("notebooks") / f"{notebook_id}.json"
    return load_json_file(path)


def get_questions_dir() -> Path:
    """获取题目存储目录"""
    return get_user_data_dir("questions")


def get_question_sets_dir() -> Path:
    """获取题目集合存储目录"""
    return get_user_data_dir("question_sets")


def get_research_dir() -> Path:
    """获取研究任务存储目录"""
    return get_user_data_dir("research")


def get_notebooks_dir() -> Path:
    """获取笔记本存储目录"""
    return get_user_data_dir("notebooks")


def get_guide_dir() -> Path:
    """获取引导式学习会话存储目录"""
    return get_user_data_dir("guide")


def get_ideas_dir() -> Path:
    """获取创意存储目录"""
    return get_user_data_dir("ideas")


def get_outputs_dir() -> Path:
    """获取输出文件存储目录"""
    return get_data_root() / "outputs"


def get_knowledge_bases_dir() -> Path:
    """获取知识库存储目录"""
    return get_data_root() / get_settings().rag.persist_chroma_path
