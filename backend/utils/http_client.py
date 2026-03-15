"""
异步 HTTP 客户端工具类

提供共享的异步 HTTP 客户端，支持：
- 连接池管理
- 超时配置
- 重试机制
- 单例模式
- 优雅关闭
- 统一错误处理
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional, Union

import httpx

from backend.utils.exceptions import APIConnectionError, AITutorError, RateLimitError
from backend.utils.logger import get_raw_logger

logger = get_raw_logger()


class HTTPClientConfig:
    """HTTP 客户端配置"""

    def __init__(
        self,
        timeout: float = 30.0,
        connect_timeout: float = 10.0,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        keepalive_expiry: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_backoff_factor: float = 2.0,
        retry_status_codes: Optional[tuple] = None,
    ):
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections
        self.keepalive_expiry = keepalive_expiry
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff_factor = retry_backoff_factor
        self.retry_status_codes = retry_status_codes or (429, 500, 502, 503, 504)


class AsyncHTTPClient:
    """
    共享的异步 HTTP 客户端

    使用单例模式确保整个应用共享同一个客户端实例，
    从而复用连接池，提高性能。

    Example:
        # 获取客户端实例
        client = AsyncHTTPClient.get_instance()

        # 发送请求
        response = await client.post(url, json=data, headers=headers)

        # 使用上下文管理器
        async with AsyncHTTPClient.request_context() as client:
            response = await client.get(url)
    """

    _instance: Optional["AsyncHTTPClient"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, config: Optional[HTTPClientConfig] = None):
        self._config = config or HTTPClientConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    @classmethod
    async def get_instance(cls, config: Optional[HTTPClientConfig] = None) -> "AsyncHTTPClient":
        """
        获取单例实例

        线程安全的单例获取方法，确保整个应用共享同一个客户端。
        """
        if cls._instance is None or not cls._instance._initialized:
            async with cls._lock:
                if cls._instance is None or not cls._instance._initialized:
                    cls._instance = cls(config)
                    await cls._instance._initialize()
        return cls._instance

    @classmethod
    def get_sync_instance(cls, config: Optional[HTTPClientConfig] = None) -> "AsyncHTTPClient":
        """
        同步获取单例实例（用于非异步上下文）

        注意：返回的实例可能尚未初始化，需要在使用前调用 ensure_initialized()
        """
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    async def _initialize(self) -> None:
        """初始化 HTTP 客户端"""
        if self._initialized:
            return

        limits = httpx.Limits(
            max_connections=self._config.max_connections,
            max_keepalive_connections=self._config.max_keepalive_connections,
            keepalive_expiry=self._config.keepalive_expiry,
        )

        timeout = httpx.Timeout(
            connect=self._config.connect_timeout,
            read=self._config.timeout,
            write=self._config.timeout,
            pool=self._config.connect_timeout,
        )

        self._client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
        )

        self._initialized = True
        logger.debug(
            f"HTTP 客户端已初始化: max_connections={self._config.max_connections}, "
            f"timeout={self._config.timeout}s"
        )

    async def ensure_initialized(self) -> None:
        """确保客户端已初始化"""
        if not self._initialized:
            await self._initialize()

    async def close(self) -> None:
        """关闭客户端，释放资源"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            self._initialized = False
            logger.debug("HTTP 客户端已关闭")

    @classmethod
    async def close_instance(cls) -> None:
        """关闭单例实例"""
        if cls._instance is not None:
            await cls._instance.close()
            cls._instance = None

    async def _execute_with_retry(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """
        执行请求并支持重试

        Args:
            method: HTTP 方法
            url: 请求 URL
            **kwargs: 传递给 httpx 的其他参数

        Returns:
            httpx.Response 对象

        Raises:
            APIConnectionError: 连接失败
            RateLimitError: 速率限制
            AITutorError: 其他错误
        """
        await self.ensure_initialized()

        last_exception: Optional[Exception] = None
        retry_delay = self._config.retry_delay

        for attempt in range(self._config.max_retries + 1):
            try:
                response = await self._client.request(method, url, **kwargs)

                if response.status_code in self._config.retry_status_codes:
                    if attempt < self._config.max_retries:
                        logger.warning(
                            f"请求失败 (状态码 {response.status_code})，"
                            f"第 {attempt + 1} 次重试，等待 {retry_delay}s: {url}"
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay *= self._config.retry_backoff_factor
                        continue

                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        raise RateLimitError(
                            "请求过于频繁，请稍后重试",
                            retry_after=int(retry_after) if retry_after else None,
                            details={"url": url, "status_code": response.status_code},
                        )

                    response.raise_for_status()

                return response

            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < self._config.max_retries:
                    logger.warning(
                        f"请求超时，第 {attempt + 1} 次重试，等待 {retry_delay}s: {url}"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= self._config.retry_backoff_factor
                    continue

            except httpx.ConnectError as e:
                last_exception = e
                if attempt < self._config.max_retries:
                    logger.warning(
                        f"连接失败，第 {attempt + 1} 次重试，等待 {retry_delay}s: {url}"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= self._config.retry_backoff_factor
                    continue

            except httpx.HTTPStatusError as e:
                raise AITutorError(
                    f"HTTP 错误: {e.response.status_code}",
                    details={"url": url, "status_code": e.response.status_code},
                )

            except httpx.HTTPError as e:
                last_exception = e
                if attempt < self._config.max_retries:
                    logger.warning(
                        f"HTTP 错误，第 {attempt + 1} 次重试，等待 {retry_delay}s: {url}"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= self._config.retry_backoff_factor
                    continue

        raise APIConnectionError(
            f"请求失败: {str(last_exception)}",
            details={"url": url, "attempts": self._config.max_retries + 1},
        )

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> httpx.Response:
        """发送 GET 请求"""
        return await self._execute_with_retry("GET", url, params=params, headers=headers, **kwargs)

    async def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> httpx.Response:
        """发送 POST 请求"""
        return await self._execute_with_retry("POST", url, json=json, data=data, headers=headers, **kwargs)

    async def put(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> httpx.Response:
        """发送 PUT 请求"""
        return await self._execute_with_retry("PUT", url, json=json, data=data, headers=headers, **kwargs)

    async def delete(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> httpx.Response:
        """发送 DELETE 请求"""
        return await self._execute_with_retry("DELETE", url, headers=headers, **kwargs)

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> AsyncGenerator[httpx.Response, None]:
        """
        流式请求上下文管理器

        Example:
            async with client.stream("POST", url, json=data) as response:
                async for line in response.aiter_lines():
                    print(line)
        """
        await self.ensure_initialized()
        async with self._client.stream(method, url, **kwargs) as response:
            yield response

    @asynccontextmanager
    async def request_context(
        cls,
        config: Optional[HTTPClientConfig] = None,
    ) -> AsyncGenerator["AsyncHTTPClient", None]:
        """
        请求上下文管理器，用于管理客户端生命周期

        Example:
            async with AsyncHTTPClient.request_context() as client:
                response = await client.get(url)
        """
        client = cls(config)
        try:
            await client._initialize()
            yield client
        finally:
            await client.close()


http_client = AsyncHTTPClient.get_sync_instance()


async def get_http_client(config: Optional[HTTPClientConfig] = None) -> AsyncHTTPClient:
    """
    获取 HTTP 客户端实例的便捷函数

    Args:
        config: 可选的客户端配置

    Returns:
        初始化完成的 AsyncHTTPClient 实例
    """
    return await AsyncHTTPClient.get_instance(config)


async def close_http_client() -> None:
    """
    关闭 HTTP 客户端的便捷函数

    应在应用关闭时调用，确保资源正确释放。
    """
    await AsyncHTTPClient.close_instance()
