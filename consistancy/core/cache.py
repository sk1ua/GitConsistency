"""GitNexus 缓存管理.

提供内存缓存 + 文件缓存的两级缓存机制.
"""

from __future__ import annotations

import hashlib
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generic, TypeVar

from cachetools import TTLCache  # type: ignore[import-untyped]

T = TypeVar("T")


class CacheEntry(Generic[T]):
    """缓存条目."""

    def __init__(self, data: T, ttl: int) -> None:
        self.data = data
        self.created_at = datetime.utcnow()
        self.ttl = ttl

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() - self.created_at > timedelta(seconds=self.ttl)


class GitNexusCache:
    """GitNexus 两级缓存管理器.

    内存缓存（TTLCache）+ 文件缓存（pickle）

    Attributes:
        memory_cache: 内存缓存实例
        file_cache_dir: 文件缓存目录
        default_ttl: 默认过期时间（秒）
    """

    def __init__(
        self,
        file_cache_dir: Path | str = ".cache/gitnexus",
        memory_maxsize: int = 128,
        default_ttl: int = 3600,
    ) -> None:
        """初始化缓存管理器.

        Args:
            file_cache_dir: 文件缓存目录
            memory_maxsize: 内存缓存最大条目数
            default_ttl: 默认过期时间（秒）
        """
        self.memory_cache: TTLCache = TTLCache(
            maxsize=memory_maxsize,
            ttl=default_ttl,
        )
        self.file_cache_dir = Path(file_cache_dir)
        self.file_cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl

    def _get_file_path(self, key: str) -> Path:
        """获取缓存文件路径."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.file_cache_dir / f"{key_hash}.cache"

    def _is_file_cache_valid(self, path: Path, ttl: int) -> bool:
        """检查文件缓存是否有效."""
        if not path.exists():
            return False

        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.utcnow() - mtime < timedelta(seconds=ttl)

    def get(self, key: str, default: T | None = None) -> T | None:
        """获取缓存值.

        Args:
            key: 缓存键
            default: 默认值

        Returns:
            缓存值或默认值
        """
        # 1. 尝试内存缓存
        if key in self.memory_cache:
            entry: CacheEntry[T] = self.memory_cache[key]
            if not entry.is_expired:
                return entry.data
            del self.memory_cache[key]

        # 2. 尝试文件缓存
        file_path = self._get_file_path(key)
        if self._is_file_cache_valid(file_path, self.default_ttl):
            try:
                with open(file_path, "rb") as f:
                    file_entry: CacheEntry[T] = pickle.load(f)
                if not file_entry.is_expired:
                    # 回填内存缓存
                    self.memory_cache[key] = file_entry
                    return file_entry.data
            except (pickle.PickleError, OSError):
                pass

        return default

    def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """设置缓存值.

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），默认使用初始化值
        """
        ttl = ttl or self.default_ttl
        entry = CacheEntry(value, ttl)

        # 1. 写入内存缓存
        self.memory_cache[key] = entry

        # 2. 写入文件缓存
        file_path = self._get_file_path(key)
        try:
            with open(file_path, "wb") as f:
                pickle.dump(entry, f)
        except OSError:
            pass  # 文件缓存失败不影响功能

    def delete(self, key: str) -> bool:
        """删除缓存.

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        deleted = False

        # 删除内存缓存
        if key in self.memory_cache:
            del self.memory_cache[key]
            deleted = True

        # 删除文件缓存
        file_path = self._get_file_path(key)
        if file_path.exists():
            try:
                file_path.unlink()
                deleted = True
            except OSError:
                pass

        return deleted

    def clear(self) -> None:
        """清空所有缓存."""
        # 清空内存缓存
        self.memory_cache.clear()

        # 清空文件缓存
        for f in self.file_cache_dir.glob("*.cache"):
            try:
                f.unlink()
            except OSError:
                pass

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计信息."""
        memory_size = len(self.memory_cache)
        file_size = len(list(self.file_cache_dir.glob("*.cache")))

        total_file_size = sum(
            f.stat().st_size
            for f in self.file_cache_dir.glob("*.cache")
        )

        return {
            "memory_entries": memory_size,
            "file_entries": file_size,
            "file_cache_size_mb": round(total_file_size / 1024 / 1024, 2),
            "cache_dir": str(self.file_cache_dir),
        }

    def make_key(self, *parts: str) -> str:
        """生成缓存键.

        Args:
            *parts: 键的组成部分

        Returns:
            哈希后的缓存键
        """
        combined = "|".join(parts)
        return hashlib.sha256(combined.encode()).hexdigest()
