"""
单例模式工具模块 - 提供线程安全的单例实现

使用方法：
1. 使用装饰器：
   @singleton
   class MyClass:
       pass

2. 使用元类：
   class MyClass(metaclass=SingletonMeta):
       pass

3. 使用基类：
   class MyClass(Singleton):
       pass
"""
import threading
from typing import Any, Dict, Optional, Type, TypeVar

T = TypeVar('T')


_singleton_instances: Dict[Type, Any] = {}
_singleton_lock = threading.Lock()


def singleton(cls: Type[T]) -> Type[T]:
    """
    单例装饰器 - 将类转换为单例模式
    
    使用示例：
        @singleton
        class Database:
            def __init__(self):
                self.connection = None
        
        db1 = Database()
        db2 = Database()
        assert db1 is db2
    """
    original_new = cls.__new__
    
    def __new__(_cls, *args, **kwargs):
        if cls not in _singleton_instances:
            with _singleton_lock:
                if cls not in _singleton_instances:
                    if original_new is object.__new__:
                        instance = object.__new__(_cls)
                    else:
                        instance = original_new(_cls, *args, **kwargs)
                    _singleton_instances[cls] = instance
        return _singleton_instances[cls]
    
    cls.__new__ = __new__
    return cls


class SingletonMeta(type):
    """
    单例元类 - 通过元类实现单例模式
    
    使用示例：
        class Database(metaclass=SingletonMeta):
            def __init__(self):
                self.connection = None
    """
    _instances: Dict[Type, Any] = {}
    _lock: threading.Lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]


class Singleton:
    """
    单例基类 - 继承此类实现单例模式
    
    使用示例：
        class Database(Singleton):
            def __init__(self):
                self.connection = None
    """
    _instances: Dict[Type, Any] = {}
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__new__(cls)
                    cls._instances[cls] = instance
        return cls._instances[cls]


def get_singleton_instance(cls: Type[T]) -> Optional[T]:
    """
    获取单例实例（如果存在）
    
    Args:
        cls: 单例类
        
    Returns:
        单例实例，如果不存在则返回 None
    """
    return _singleton_instances.get(cls)


def clear_singleton_instance(cls: Type[T]) -> bool:
    """
    清除单例实例
    
    Args:
        cls: 单例类
        
    Returns:
        是否成功清除
    """
    if cls in _singleton_instances:
        with _singleton_lock:
            if cls in _singleton_instances:
                del _singleton_instances[cls]
                return True
    return False


def clear_all_singletons() -> None:
    """清除所有单例实例"""
    with _singleton_lock:
        _singleton_instances.clear()
