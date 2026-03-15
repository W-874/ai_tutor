"""
结构化日志模块 - 提供统一的日志记录功能

功能特性：
- 支持 JSON 格式和文本格式的结构化日志
- 请求 ID 追踪功能
- 性能监控日志
"""
import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional


LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

_json_format: bool = False


def set_json_format(enabled: bool = True):
    """设置是否使用 JSON 格式输出日志"""
    global _json_format
    _json_format = enabled


def is_json_format() -> bool:
    """检查是否使用 JSON 格式"""
    return _json_format


def get_request_id() -> Optional[str]:
    """获取当前请求 ID"""
    return _request_id_var.get()


def set_request_id(request_id: Optional[str] = None) -> str:
    """
    设置当前请求 ID，如果未提供则自动生成。

    Args:
        request_id: 可选的请求 ID，不提供则自动生成 UUID

    Returns:
        设置的请求 ID
    """
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]
    _request_id_var.set(request_id)
    return request_id


def clear_request_id():
    """清除当前请求 ID"""
    _request_id_var.set(None)


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器，支持文本和 JSON 格式"""

    def __init__(self, json_format: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.json_format = json_format

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }

        request_id = get_request_id()
        if request_id:
            log_data["request_id"] = request_id

        if hasattr(record, "extra_data") and record.extra_data:
            log_data["data"] = record.extra_data

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if self.json_format:
            return json.dumps(log_data, ensure_ascii=False, default=str)
        else:
            base_msg = f"{log_data['timestamp']} - {log_data['logger']} - {log_data['level']}"
            if request_id:
                base_msg += f" - [{request_id}]"
            base_msg += f" - {log_data['message']}"
            if "data" in log_data:
                base_msg += f" | {json.dumps(log_data['data'], ensure_ascii=False)}"
            if "exception" in log_data:
                base_msg += f"\n{log_data['exception']}"
            return base_msg


class StructuredLogger:
    """结构化日志记录器包装类"""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _log(self, level: int, message: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        """内部日志方法"""
        extra = kwargs.get("extra", {})
        if data:
            extra["extra_data"] = data
        kwargs["extra"] = extra
        self._logger.log(level, message, **kwargs)

    def debug(self, message: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        self._log(logging.DEBUG, message, data, **kwargs)

    def info(self, message: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        self._log(logging.INFO, message, data, **kwargs)

    def warning(self, message: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        self._log(logging.WARNING, message, data, **kwargs)

    def error(self, message: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        self._log(logging.ERROR, message, data, **kwargs)

    def critical(self, message: str, data: Optional[Dict[str, Any]] = None, **kwargs):
        self._log(logging.CRITICAL, message, data, **kwargs)


def setup_logger(
    name: str = "aitutor",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    json_format: bool = False,
) -> logging.Logger:
    """
    配置并返回一个日志记录器。

    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 可选的日志文件路径
        json_format: 是否使用 JSON 格式输出

    Returns:
        配置好的日志记录器
    """
    global _json_format
    _json_format = json_format

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = StructuredFormatter(json_format=json_format)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


_logger: Optional[logging.Logger] = None


def get_logger() -> StructuredLogger:
    """获取全局结构化日志记录器"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return StructuredLogger(_logger)


def get_raw_logger() -> logging.Logger:
    """获取原始日志记录器（用于兼容旧代码）"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


def log_request(method: str, path: str, **kwargs):
    """记录 HTTP 请求"""
    logger = get_logger()
    data = {"method": method, "path": path}
    if kwargs:
        data.update(kwargs)
    logger.info(f"HTTP Request: {method} {path}", data=data)


def log_response(method: str, path: str, status_code: int, duration_ms: float, **kwargs):
    """记录 HTTP 响应"""
    logger = get_logger()
    data = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
    }
    if kwargs:
        data.update(kwargs)
    logger.info(f"HTTP Response: {method} {path} - {status_code}", data=data)


def log_error(error: Exception, context: Optional[dict] = None):
    """记录错误"""
    logger = get_logger()
    data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    if context:
        data["context"] = context
    logger.error(f"Error: {type(error).__name__}: {error}", data=data, exc_info=True)


def log_llm_call(
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    duration_ms: float = 0,
    **kwargs,
):
    """记录 LLM 调用"""
    logger = get_logger()
    data = {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "duration_ms": round(duration_ms, 2),
    }
    if kwargs:
        data.update(kwargs)
    logger.info(f"LLM Call: {model}", data=data)


def log_rag_query(kb_id: str, query: str, results_count: int, duration_ms: float, **kwargs):
    """记录 RAG 查询"""
    logger = get_logger()
    data = {
        "kb_id": kb_id,
        "query": query[:100] if len(query) > 100 else query,
        "results_count": results_count,
        "duration_ms": round(duration_ms, 2),
    }
    if kwargs:
        data.update(kwargs)
    logger.info(f"RAG Query: {kb_id}", data=data)


def log_performance(
    operation: str,
    duration_ms: float,
    success: bool = True,
    metrics: Optional[Dict[str, Any]] = None,
    **kwargs,
):
    """
    记录性能监控日志。

    Args:
        operation: 操作名称
        duration_ms: 持续时间（毫秒）
        success: 是否成功
        metrics: 额外的性能指标
        **kwargs: 其他额外参数
    """
    logger = get_logger()
    data = {
        "operation": operation,
        "duration_ms": round(duration_ms, 2),
        "success": success,
    }
    if metrics:
        data["metrics"] = metrics
    if kwargs:
        data.update(kwargs)

    level = logging.INFO if success else logging.WARNING
    logger._log(level, f"Performance: {operation}", data=data)


class PerformanceTimer:
    """性能计时器上下文管理器"""

    def __init__(self, operation: str, **kwargs):
        self.operation = operation
        self.kwargs = kwargs
        self.start_time: Optional[float] = None
        self.duration_ms: float = 0
        self.success: bool = True

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.time() - self.start_time) * 1000
        self.success = exc_type is None
        log_performance(
            operation=self.operation,
            duration_ms=self.duration_ms,
            success=self.success,
            **self.kwargs,
        )
        return False

    def add_metric(self, key: str, value: Any):
        """添加额外的性能指标"""
        if "metrics" not in self.kwargs:
            self.kwargs["metrics"] = {}
        self.kwargs["metrics"][key] = value


def timed(operation: str):
    """
    性能计时装饰器。

    用法:
        @timed("my_function")
        def my_function():
            ...
    """
    def decorator(func):
        import functools

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with PerformanceTimer(operation):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with PerformanceTimer(operation):
                return await func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
