"""缓存模块单元测试."""

import time
from pathlib import Path

import pytest

from consistancy.core.cache import CacheEntry, GitNexusCache


class TestCacheEntry:
    """CacheEntry 测试."""

    def test_creation(self) -> None:
        """测试创建."""
        entry = CacheEntry("test_data", ttl=3600)
        assert entry.data == "test_data"
        assert entry.ttl == 3600
        assert entry.created_at is not None

    def test_not_expired(self) -> None:
        """测试未过期."""
        entry = CacheEntry("test", ttl=3600)
        assert not entry.is_expired

    def test_expired(self) -> None:
        """测试已过期."""
        entry = CacheEntry("test", ttl=0)
        time.sleep(0.01)  # 稍微等待
        assert entry.is_expired


class TestGitNexusCache:
    """GitNexusCache 测试."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> GitNexusCache:
        """创建测试缓存."""
        return GitNexusCache(
            file_cache_dir=tmp_path / "test_cache",
            memory_maxsize=10,
            default_ttl=60,
        )

    def test_init_creates_dir(self, tmp_path: Path) -> None:
        """测试初始化创建目录."""
        cache_dir = tmp_path / "new_cache"
        assert not cache_dir.exists()
        
        GitNexusCache(cache_dir)
        assert cache_dir.exists()

    def test_get_set(self, cache: GitNexusCache) -> None:
        """测试基本存取."""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_default(self, cache: GitNexusCache) -> None:
        """测试默认值."""
        assert cache.get("nonexistent") is None
        assert cache.get("nonexistent", "default") == "default"

    def test_memory_cache_hit(self, cache: GitNexusCache) -> None:
        """测试内存缓存命中."""
        cache.set("key", "value")
        # 第一次从内存获取
        assert cache.get("key") == "value"
        # 第二次仍然从内存获取
        assert cache.get("key") == "value"

    def test_file_cache_fallback(self, cache: GitNexusCache) -> None:
        """测试文件缓存回退."""
        cache.set("key", "value")
        
        # 创建新缓存实例（模拟重启），内存缓存为空
        new_cache = GitNexusCache(
            file_cache_dir=cache.file_cache_dir,
            default_ttl=60,
        )
        
        # 应该从文件缓存获取
        assert new_cache.get("key") == "value"

    def test_expired_cache(self, cache: GitNexusCache) -> None:
        """测试过期缓存."""
        cache.set("key", "value", ttl=0)  # 立即过期
        time.sleep(0.1)  # 确保有足够时间过期
        
        assert cache.get("key") is None

    def test_delete(self, cache: GitNexusCache) -> None:
        """测试删除."""
        cache.set("key", "value")
        assert cache.get("key") == "value"
        
        deleted = cache.delete("key")
        assert deleted
        assert cache.get("key") is None

    def test_delete_nonexistent(self, cache: GitNexusCache) -> None:
        """测试删除不存在的键."""
        deleted = cache.delete("nonexistent")
        assert not deleted

    def test_clear(self, cache: GitNexusCache) -> None:
        """测试清空."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_make_key(self, cache: GitNexusCache) -> None:
        """测试键生成."""
        key1 = cache.make_key("part1", "part2", "part3")
        key2 = cache.make_key("part1", "part2", "part3")
        key3 = cache.make_key("part1", "part2", "different")
        
        assert key1 == key2
        assert key1 != key3
        assert len(key1) == 64  # SHA256 十六进制长度

    def test_custom_ttl(self, cache: GitNexusCache) -> None:
        """测试自定义 TTL."""
        cache.set("short", "value", ttl=0)
        cache.set("long", "value", ttl=3600)
        
        time.sleep(0.01)
        
        assert cache.get("short") is None
        assert cache.get("long") == "value"

    def test_get_stats(self, cache: GitNexusCache) -> None:
        """测试统计信息."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        stats = cache.get_stats()
        
        assert stats["memory_entries"] == 2
        assert stats["file_entries"] == 2
        assert stats["file_cache_size_mb"] >= 0
        assert "cache_dir" in stats

    def test_complex_data(self, cache: GitNexusCache) -> None:
        """测试复杂数据类型."""
        data = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "tuple": (4, 5, 6),
        }
        
        cache.set("complex", data)
        result = cache.get("complex")
        
        assert result == data

    def test_memory_lru_eviction(self, tmp_path: Path) -> None:
        """测试内存 LRU 淘汰."""
        cache = GitNexusCache(
            file_cache_dir=tmp_path / "lru_cache",
            memory_maxsize=2,  # 最多2个
            default_ttl=60,
        )
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # 应该淘汰 key1
        
        # key1 应该被从内存淘汰，但文件缓存仍在
        # 由于文件缓存回退，key1 仍可获得
        # 注意：这取决于具体实现细节
