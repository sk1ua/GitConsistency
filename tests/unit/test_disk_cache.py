"""Tests for disk_cache module."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from consistency.reviewer.disk_cache import DiskCache
from consistency.reviewer.models import CommentCategory, ReviewComment, ReviewResult, Severity


class TestDiskCacheInitialization:
    """Test DiskCache initialization."""

    def test_default_initialization(self, tmp_path: Path):
        """Test default initialization."""
        cache = DiskCache(tmp_path)

        assert cache.cache_dir == tmp_path
        assert cache.ttl == 3600
        assert cache.max_entries == 1000
        assert cache._stats["hits"] == 0
        assert cache._stats["misses"] == 0

    def test_custom_initialization(self, tmp_path: Path):
        """Test custom initialization."""
        cache = DiskCache(tmp_path, ttl=7200, max_entries=500)

        assert cache.ttl == 7200
        assert cache.max_entries == 500

    def test_creates_directory(self, tmp_path: Path):
        """Test directory is created."""
        cache_dir = tmp_path / "new_cache"
        DiskCache(cache_dir)

        assert cache_dir.exists()


class TestDiskCacheGetSet:
    """Test DiskCache get and set operations."""

    def _create_sample_result(self) -> ReviewResult:
        """Create a sample ReviewResult."""
        comment = ReviewComment(
            message="Test comment",
            severity=Severity.HIGH,
            category=CommentCategory.SECURITY,
            line=10,
            file_path="test.py",
        )
        return ReviewResult(comments=[comment], summary="Test summary")

    def test_set_and_get(self, tmp_path: Path):
        """Test setting and getting cache entry."""
        cache = DiskCache(tmp_path)
        result = self._create_sample_result()

        cache.set("key1", result, "gpt-4")
        cached = cache.get("key1")

        assert cached is not None
        cached_result, model = cached
        assert model == "gpt-4"
        assert len(cached_result.comments) == 1
        assert cached_result.comments[0].message == "Test comment"

    def test_get_nonexistent_key(self, tmp_path: Path):
        """Test getting non-existent key."""
        cache = DiskCache(tmp_path)

        result = cache.get("nonexistent")

        assert result is None
        assert cache._stats["misses"] == 1

    def test_get_expired_entry(self, tmp_path: Path):
        """Test getting expired entry."""
        cache = DiskCache(tmp_path, ttl=0)  # TTL of 0 means immediate expiration
        result = self._create_sample_result()

        cache.set("key1", result, "gpt-4")
        cached = cache.get("key1")

        assert cached is None  # Expired

    def test_set_creates_subdirectories(self, tmp_path: Path):
        """Test set creates subdirectories."""
        cache = DiskCache(tmp_path)
        result = self._create_sample_result()

        cache.set("abcdef123", result, "gpt-4")

        # Should create ab/abcdef123.json
        assert (tmp_path / "ab" / "abcdef123.json").exists()

    def test_get_updates_stats(self, tmp_path: Path):
        """Test get updates stats correctly."""
        cache = DiskCache(tmp_path)
        result = self._create_sample_result()

        cache.set("key1", result, "gpt-4")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        assert cache._stats["hits"] == 1
        assert cache._stats["misses"] == 1

    def test_get_corrupted_file(self, tmp_path: Path):
        """Test getting corrupted cache file."""
        cache = DiskCache(tmp_path)

        # Create corrupted file - key "corrupted" -> subdir "co"
        cache.cache_dir.mkdir(parents=True, exist_ok=True)
        subdir = cache.cache_dir / "co"
        subdir.mkdir(exist_ok=True)
        (subdir / "corrupted.json").write_text("not valid json")

        result = cache.get("corrupted")

        assert result is None
        assert cache._stats["errors"] == 1


class TestDiskCacheDelete:
    """Test DiskCache delete operations."""

    def test_delete_existing(self, tmp_path: Path):
        """Test deleting existing entry."""
        cache = DiskCache(tmp_path)
        from consistency.reviewer.models import ReviewResult

        cache.set("key1", ReviewResult(comments=[], summary="s1"), "model")

        result = cache.delete("key1")

        assert result is True
        assert cache.get("key1") is None

    def test_delete_nonexistent(self, tmp_path: Path):
        """Test deleting non-existent entry."""
        cache = DiskCache(tmp_path)

        result = cache.delete("nonexistent")

        assert result is False


class TestDiskCacheCleanup:
    """Test DiskCache cleanup operations."""

    def test_cleanup_expired(self, tmp_path: Path):
        """Test cleaning expired entries."""
        cache = DiskCache(tmp_path, ttl=3600)

        # Create expired entry
        subdir = tmp_path / "ab"
        subdir.mkdir(parents=True)
        expired_file = subdir / "expired.json"
        expired_data = {
            "result": {"comments": []},
            "timestamp": time.time() - 7200,  # 2 hours ago
            "model": "gpt-4",
        }
        expired_file.write_text(json.dumps(expired_data))

        # Create valid entry
        valid_file = subdir / "valid.json"
        valid_data = {
            "result": {"comments": []},
            "timestamp": time.time(),  # Now
            "model": "gpt-4",
        }
        valid_file.write_text(json.dumps(valid_data))

        cleaned = cache.cleanup_expired()

        assert cleaned == 1
        assert not expired_file.exists()
        assert valid_file.exists()

    def test_cleanup_corrupted(self, tmp_path: Path):
        """Test cleaning corrupted files."""
        cache = DiskCache(tmp_path)

        subdir = tmp_path / "ab"
        subdir.mkdir(parents=True)
        corrupted = subdir / "corrupted.json"
        corrupted.write_text("invalid json")

        cleaned = cache.cleanup_expired()

        assert cleaned == 1
        assert not corrupted.exists()

    def test_cleanup_empty_directories(self, tmp_path: Path):
        """Test cleaning empty directories."""
        cache = DiskCache(tmp_path)

        subdir = tmp_path / "ab"
        subdir.mkdir(parents=True)
        (subdir / "file.json").write_text("{}")

        cache.cleanup_expired()  # Removes file.json

        assert not subdir.exists()  # Empty dir should be removed


class TestDiskCacheClear:
    """Test DiskCache clear operation."""

    def test_clear_removes_all(self, tmp_path: Path):
        """Test clear removes all entries."""
        cache = DiskCache(tmp_path)
        from consistency.reviewer.models import ReviewResult

        cache.set("key1", ReviewResult(comments=[], summary="s1"), "model")
        cache.set("key2", ReviewResult(comments=[], summary="s2"), "model")

        count = cache.clear()

        assert count == 2
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestDiskCacheStats:
    """Test DiskCache stats."""

    def test_get_stats(self, tmp_path: Path):
        """Test getting stats."""
        cache = DiskCache(tmp_path, ttl=7200)
        from consistency.reviewer.models import ReviewResult

        cache.set("key1", ReviewResult(comments=[], summary="s"), "model")
        cache.get("key1")  # Hit
        cache.get("nonexistent")  # Miss

        stats = cache.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["writes"] == 1
        assert stats["dir"] == str(tmp_path)
        assert stats["file_count"] == 1
        assert stats["ttl_seconds"] == 7200
        assert "total_size_bytes" in stats

    def test_len(self, tmp_path: Path):
        """Test __len__ method."""
        cache = DiskCache(tmp_path)
        from consistency.reviewer.models import ReviewResult

        assert len(cache) == 0

        cache.set("key1", ReviewResult(comments=[], summary="s1"), "model")
        cache.set("key2", ReviewResult(comments=[], summary="s2"), "model")

        assert len(cache) == 2


class TestDiskCacheCleanupIfNeeded:
    """Test _cleanup_if_needed method."""

    @patch("random.random", return_value=0.05)  # Less than 0.1
    def test_triggers_cleanup(self, mock_random, tmp_path: Path):
        """Test cleanup triggers at 10% probability."""
        cache = DiskCache(tmp_path, ttl=0)
        from consistency.reviewer.models import ReviewResult

        # Create an entry that will be expired
        cache.set("key1", ReviewResult(comments=[], summary="s"), "model")

        # Trigger cleanup through random check
        cache._cleanup_if_needed()

        # Entry should be cleaned up
        assert len(cache) == 0

    @patch("random.random", return_value=0.5)  # Greater than 0.1
    def test_skips_cleanup(self, mock_random, tmp_path: Path):
        """Test cleanup skips at 90% probability."""
        cache = DiskCache(tmp_path)
        from consistency.reviewer.models import ReviewResult

        cache.set("key1", ReviewResult(comments=[], summary="s"), "model")

        cache._cleanup_if_needed()

        # Entry should still exist
        assert len(cache) == 1
