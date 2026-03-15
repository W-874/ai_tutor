"""
异常处理模块 - 提供统一的异常处理

本模块定义了 AI TUTOR 项目的所有自定义异常类，用于：
- 统一错误处理和响应格式
- 提供清晰的错误码和错误信息
- 支持详细的错误详情记录

异常层次结构：
    AITutorError (基类)
    ├── ConfigurationError - 配置相关错误
    ├── LLMError - LLM 调用相关错误
    │   ├── APIConnectionError - API 连接错误
    │   └── RateLimitError - 速率限制错误
    ├── EmbeddingError - Embedding 调用错误
    ├── RAGError - RAG 检索错误
    ├── KnowledgeBaseError - 知识库错误
    ├── SessionError - 会话错误
    ├── ValidationError - 验证错误
    ├── NotFoundError - 资源未找到错误
    ├── FileProcessingError - 文件处理错误
    └── WebSocketError - WebSocket 通信错误
"""
from enum import Enum
from typing import Any, Optional


class ErrorCode(str, Enum):
    """
    错误码枚举类

    错误码命名规范：
    - 使用大写下划线格式
    - 按模块/功能分组
    - 保持与异常类的对应关系

    分类：
    - 通用错误: 1xxx
    - 配置错误: 2xxx
    - LLM/AI 相关: 3xxx
    - 知识库相关: 4xxx
    - 会话相关: 5xxx
    - 文件处理: 6xxx
    - WebSocket: 7xxx
    """

    UNKNOWN_ERROR = "UNKNOWN_ERROR"

    CONFIGURATION_ERROR = "CONFIG_ERROR_2000"
    ENVIRONMENT_ERROR = "CONFIG_ERROR_2001"

    LLM_ERROR = "LLM_ERROR_3000"
    API_CONNECTION_ERROR = "LLM_ERROR_3001"
    RATE_LIMIT_ERROR = "LLM_ERROR_3002"
    LLM_TIMEOUT_ERROR = "LLM_ERROR_3003"
    LLM_AUTH_ERROR = "LLM_ERROR_3004"

    EMBEDDING_ERROR = "EMBED_ERROR_3100"

    RAG_ERROR = "RAG_ERROR_3200"
    RAG_INDEX_ERROR = "RAG_ERROR_3201"
    RAG_RETRIEVAL_ERROR = "RAG_ERROR_3202"

    KNOWLEDGE_BASE_ERROR = "KB_ERROR_4000"
    KNOWLEDGE_BASE_NOT_FOUND = "KB_ERROR_4001"
    KNOWLEDGE_BASE_DUPLICATE = "KB_ERROR_4002"

    SESSION_ERROR = "SESSION_ERROR_5000"
    SESSION_NOT_FOUND = "SESSION_ERROR_5001"
    SESSION_EXPIRED = "SESSION_ERROR_5002"

    VALIDATION_ERROR = "VALIDATION_ERROR_1001"
    NOT_FOUND = "NOT_FOUND_1002"
    PERMISSION_DENIED = "PERMISSION_DENIED_1003"

    FILE_PROCESSING_ERROR = "FILE_ERROR_6000"
    FILE_NOT_FOUND = "FILE_ERROR_6001"
    FILE_TOO_LARGE = "FILE_ERROR_6002"
    FILE_TYPE_NOT_SUPPORTED = "FILE_ERROR_6003"
    FILE_PARSE_ERROR = "FILE_ERROR_6004"

    WEBSOCKET_ERROR = "WS_ERROR_7000"
    WEBSOCKET_CONNECTION_ERROR = "WS_ERROR_7001"
    WEBSOCKET_MESSAGE_ERROR = "WS_ERROR_7002"


class AITutorError(Exception):
    """
    AI TUTOR 基础异常类

    所有自定义异常的基类，提供统一的错误处理接口。

    Attributes:
        message: 错误消息，人类可读的描述
        code: 错误码，用于程序化处理
        details: 错误详情，包含额外的上下文信息

    Example:
        >>> raise AITutorError("操作失败", code="CUSTOM_ERROR", details={"key": "value"})
    """

    default_code: ErrorCode = ErrorCode.UNKNOWN_ERROR
    default_status_code: int = 400

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code or self.default_code.value
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """将异常转换为字典格式，用于 API 响应"""
        return {
            "success": False,
            "error": self.message,
            "code": self.code,
            "detail": self.details if self.details else None,
        }


class ConfigurationError(AITutorError):
    """
    配置错误

    当系统配置缺失、无效或无法加载时抛出。

    常见场景：
    - 环境变量缺失
    - 配置文件格式错误
    - 必要配置项未设置

    Example:
        >>> raise ConfigurationError("API Key 未配置", details={"env_var": "OPENAI_API_KEY"})
        >>> raise ConfigurationError(errors=["EMBEDDING_API_KEY 未配置", "LLM_API_KEY 未配置"])
    """

    default_code = ErrorCode.CONFIGURATION_ERROR
    default_status_code = 500

    def __init__(
        self,
        message: str = None,
        errors: list = None,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        if message is None and errors:
            message = self._format_errors(errors)
        super().__init__(message or "配置错误", code=code, details=details)
        self.errors = errors or []

    def _format_errors(self, errors: list) -> str:
        lines = ["配置验证失败，请检查以下问题：", "-" * 50]
        for i, error in enumerate(errors, 1):
            lines.append(f"{i}. {error}")
        lines.append("-" * 50)
        lines.append("提示：请设置相应的环境变量或在 data/user/config.json 中配置")
        return "\n".join(lines)


class LLMError(AITutorError):
    """
    LLM 调用错误

    当与大语言模型的交互出现问题时抛出。

    常见场景：
    - 模型返回错误响应
    - 响应格式不符合预期
    - 模型能力限制

    Example:
        >>> raise LLMError("模型响应解析失败", details={"raw_response": "..."})
    """

    default_code = ErrorCode.LLM_ERROR
    default_status_code = 500


class APIConnectionError(LLMError):
    """
    API 连接错误

    当无法连接到 LLM API 服务时抛出。

    常见场景：
    - 网络连接失败
    - API 服务不可用
    - DNS 解析失败
    - 连接超时

    Example:
        >>> raise APIConnectionError("无法连接到 OpenAI API", details={"endpoint": "https://api.openai.com"})
    """

    default_code = ErrorCode.API_CONNECTION_ERROR
    default_status_code = 503


class RateLimitError(LLMError):
    """
    速率限制错误

    当 API 请求超过速率限制时抛出。

    常见场景：
    - 请求频率过高
    - Token 配额用尽
    - 并发请求超限

    Attributes:
        retry_after: 建议的重试等待时间（秒）

    Example:
        >>> raise RateLimitError("请求过于频繁，请稍后重试", retry_after=60)
    """

    default_code = ErrorCode.RATE_LIMIT_ERROR
    default_status_code = 429

    def __init__(
        self,
        message: str = "请求过于频繁，请稍后重试",
        retry_after: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        details = details or {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, code=self.default_code.value, details=details)
        self.retry_after = retry_after


class EmbeddingError(AITutorError):
    """
    Embedding 调用错误

    当文本嵌入服务出现问题时抛出。

    常见场景：
    - Embedding API 调用失败
    - 文本过长无法处理
    - 向量维度不匹配

    Example:
        >>> raise EmbeddingError("文本嵌入失败", details={"text_length": 10000})
    """

    default_code = ErrorCode.EMBEDDING_ERROR
    default_status_code = 500


class RAGError(AITutorError):
    """
    RAG 检索错误

    当检索增强生成流程出现问题时抛出。

    常见场景：
    - 向量检索失败
    - 索引构建错误
    - 上下文组装失败

    Example:
        >>> raise RAGError("向量检索失败", details={"query": "...", "index": "main"})
    """

    default_code = ErrorCode.RAG_ERROR
    default_status_code = 500


class KnowledgeBaseError(AITutorError):
    """
    知识库错误

    当知识库操作出现问题时抛出。

    常见场景：
    - 知识库创建失败
    - 文档索引错误
    - 知识库配置无效

    Example:
        >>> raise KnowledgeBaseError("知识库创建失败", details={"kb_name": "my_kb"})
    """

    default_code = ErrorCode.KNOWLEDGE_BASE_ERROR
    default_status_code = 500


class SessionError(AITutorError):
    """
    会话错误

    当会话管理出现问题时抛出。

    常见场景：
    - 会话不存在
    - 会话已过期
    - 会话状态无效

    Example:
        >>> raise SessionError("会话不存在", details={"session_id": "xxx"})
    """

    default_code = ErrorCode.SESSION_ERROR
    default_status_code = 400


class ValidationError(AITutorError):
    """
    验证错误

    当输入数据验证失败时抛出。

    常见场景：
    - 参数格式错误
    - 必填字段缺失
    - 值超出允许范围

    Example:
        >>> raise ValidationError("参数验证失败", details={"field": "name", "reason": "不能为空"})
    """

    default_code = ErrorCode.VALIDATION_ERROR
    default_status_code = 422


class NotFoundError(AITutorError):
    """
    资源未找到错误

    当请求的资源不存在时抛出。

    常见场景：
    - ID 对应的资源不存在
    - 文件或目录不存在
    - API 路由不存在

    Example:
        >>> raise NotFoundError("会话", "session_123")
    """

    default_code = ErrorCode.NOT_FOUND
    default_status_code = 404

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} 不存在: {resource_id}",
            code=self.default_code.value,
            details={"resource": resource, "id": resource_id},
        )


class FileProcessingError(AITutorError):
    """
    文件处理错误

    当文件上传、解析或处理出现问题时抛出。

    常见场景：
    - 文件格式不支持
    - 文件过大
    - 文件解析失败
    - 文件损坏

    Example:
        >>> raise FileProcessingError("文件解析失败", details={"filename": "doc.pdf", "reason": "文件损坏"})
    """

    default_code = ErrorCode.FILE_PROCESSING_ERROR
    default_status_code = 400


class WebSocketError(AITutorError):
    """
    WebSocket 通信错误

    当 WebSocket 连接或消息处理出现问题时抛出。

    常见场景：
    - WebSocket 连接断开
    - 消息格式错误
    - 消息处理超时
    - 连接认证失败

    Example:
        >>> raise WebSocketError("连接已断开", details={"connection_id": "xxx", "reason": "timeout"})
    """

    default_code = ErrorCode.WEBSOCKET_ERROR
    default_status_code = 400


_EXCEPTION_STATUS_MAP: dict[type[AITutorError], int] = {
    ConfigurationError: 500,
    LLMError: 500,
    APIConnectionError: 503,
    RateLimitError: 429,
    EmbeddingError: 500,
    RAGError: 500,
    KnowledgeBaseError: 500,
    SessionError: 400,
    ValidationError: 422,
    NotFoundError: 404,
    FileProcessingError: 400,
    WebSocketError: 400,
}


def get_status_code(exc: AITutorError) -> int:
    """
    根据异常类型获取对应的 HTTP 状态码

    Args:
        exc: AI TUTOR 异常实例

    Returns:
        对应的 HTTP 状态码
    """
    for exc_type, status_code in _EXCEPTION_STATUS_MAP.items():
        if isinstance(exc, exc_type):
            return status_code
    return exc.default_status_code
