"""磁盘缓存管理.

提供持久化的缓存存储，支持 TTL 和自动清理.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from consistency.reviewer.models import ReviewResult

logger = logging.getLogger(__name__)


class DiskCache:
    """磁盘缓存.

    将审查结果持久化到磁盘，支持 TTL 过期和自动加载.

    Examples:
        >>> cache = DiskCache(Path(".cache/reviews"), ttl=3600)
        >>> cache.set("key123", result, model="deepseek-chat")
        >>> cached = cache.get("key123")
    """

    def __init__(
        self,
        cache_dir: str | Path,
        ttl: int = 3600,
        max_entries: int = 1000,
    ) -> None:
        """初始化磁盘缓存.

        Args:
            cache_dir: 缓存目录路径
            ttl: 缓存过期时间（秒）
            max_entries: 最大缓存条目数
        """
        self.cache_dir = Path(cache_dir)
        self.ttl = ttl
        self.max_entries = max_entries
        self._stats = {
            "hits": 0,
            "misses": 0,
            "writes": 0,
            "errors": 0,
        }

        self._ensure_dir()
        self._cleanup_if_needed()

    def _ensure_dir(self) -> None:
        """确保缓存目录存在."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_file(self, key: str) -> Path:
        """获取缓存文件路径."""
        # 使用键的前 2 个字符作为子目录，避免单目录文件过多
        subdir = key[:2] if len(key) >= 2 else "00"
        return self.cache_dir / subdir / f"{key}.json"

    def _cleanup_if_needed(self) -> None:
        """如果需要则清理过期缓存."""
        # 每 10 次访问检查一次
        import random

        if random.random() < 0.1:
            self.cleanup_expired()

    def get(self, key: str) -> tuple[ReviewResult, str] | None:
        """获取缓存项.

        Args:
            key: 缓存键

        Returns:
            (ReviewResult, model) 或 None
        """
        cache_file = self._cache_file(key)

        if not cache_file.exists():
            self._stats["misses"] += 1
            return None

        try:
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)

            # 检查 TTL
            if time.time() - data.get("timestamp", 0) > self.ttl:
                self._stats["misses"] += 1
                cache_file.unlink(missing_ok=True)
                return None

            result = ReviewResult.model_validate(data["result"])
            self._stats["hits"] += 1
            return result, data.get("model", "unknown")

        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.debug(f"磁盘缓存读取失败: {e}")
            self._stats["errors"] += 1
            cache_file.unlink(missing_ok=True)
            return None

    def set(self, key: str, result: ReviewResult, model: str) -> bool:
        """设置缓存项.

        Args:
            key: 缓存键
            result: 审查结果
            model: 使用的模型

        Returns:
            是否成功写入
        """
        cache_file = self._cache_file(key)

        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "result": result.model_dump(),
                "timestamp": time.time(),
                "model": model,
                "version": 1,  # 缓存格式版本
            }

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self._stats["writes"] += 1
            return True

        except (OSError, TypeError) as e:
            logger.debug(f"磁盘缓存写入失败: {e}")
            self._stats["errors"] += 1
            return False

    def delete(self, key: str) -> bool:
        """删除缓存项.

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        cache_file = self._cache_file(key)
        if cache_file.exists():
            cache_file.unlink()
            return True
        return False

    def cleanup_expired(self) -> int:
        """清理过期缓存.

        Returns:
            清理的文件数
        """
        cleaned = 0
        now = time.time()

        for cache_file in self.cache_dir.rglob("*.json"):
            try:
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)

                if now - data.get("timestamp", 0) > self.ttl:
                    cache_file.unlink()
                    cleaned += 1

            except (json.JSONDecodeError, OSError):
                # 损坏的文件直接删除
                cache_file.unlink(missing_ok=True)
                cleaned += 1

        # 清理空目录
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir() and not any(subdir.iterdir()):
                subdir.rmdir()

        if cleaned > 0:
            logger.debug(f"清理了 {cleaned} 个过期缓存文件")

        return cleaned

    def clear(self) -> int:
        """清空所有缓存.

        Returns:
            删除的文件数
        """
        count = 0
        for cache_file in self.cache_dir.rglob("*.json"):
            cache_file.unlink()
            count += 1

        # 删除子目录
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir():
                subdir.rmdir()

        logger.info(f"磁盘缓存已清空: {count} 个文件")
        return count

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计."""
        # 计算缓存大小
        total_size = 0
        file_count = 0
        for cache_file in self.cache_dir.rglob("*.json"):
            total_size += cache_file.stat().st_size
            file_count += 1

        return {
            **self._stats,
            "dir": str(self.cache_dir),
            "file_count": file_count,
            "total_size_bytes": total_size,
            "ttl_seconds": self.ttl,
        }

    def __len__(self) -> int:
        """返回缓存条目数."""
        return sum(1 for _ in self.cache_dir.rglob("*.json"))
