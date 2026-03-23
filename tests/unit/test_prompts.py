"""Prompt 模板单元测试."""

from consistency.reviewer.prompts import (
    PromptCache,
    PromptTemplate,
    ReviewContext,
    ReviewType,
)


class TestReviewContext:
    """ReviewContext 测试."""

    def test_basic_creation(self) -> None:
        """测试基本创建."""
        context = ReviewContext(
            diff="test diff",
            files_changed=["file1.py", "file2.py"],
            lines_added=10,
            lines_deleted=5,
        )

        assert context.diff == "test diff"
        assert len(context.files_changed) == 2

    def test_to_dict(self) -> None:
        """测试转换为字典."""
        context = ReviewContext(
            diff="test" * 10000,  # 长 diff
            files_changed=["file.py"],
            security_findings=[{"severity": "HIGH", "message": "Issue"}],
        )

        data = context.to_dict()

        assert "diff" in data
        assert len(data["diff"]) <= 5000  # 应该被截断
        assert data["security_findings_count"] == 1


class TestPromptTemplate:
    """PromptTemplate 测试."""

    def test_build_basic(self) -> None:
        """测试基本构建."""
        context = ReviewContext(
            diff="def hello(): pass",
            files_changed=["test.py"],
        )

        messages = PromptTemplate.build(context, ReviewType.GENERAL)

        assert len(messages) == 3  # system + context + review
        assert messages[0]["role"] == "system"
        assert "Code Review Context" in messages[1]["content"]

    def test_build_with_findings(self) -> None:
        """测试带发现的构建."""
        context = ReviewContext(
            diff="test",
            security_findings=[
                {"severity": "HIGH", "message": "Security issue"},
            ],
            drift_findings=[
                {"message": "Naming drift"},
            ],
            hotspot_findings=[
                {"message": "Complex code"},
            ],
        )

        messages = PromptTemplate.build(context, ReviewType.GENERAL)
        content = messages[1]["content"]

        assert "Security Findings" in content
        assert "Consistency Drifts" in content
        assert "Technical Debt Hotspots" in content

    def test_build_security_review(self) -> None:
        """测试安全审查类型."""
        context = ReviewContext(diff="test")

        messages = PromptTemplate.build(context, ReviewType.SECURITY)
        content = messages[2]["content"]

        assert "Security-focused review" in content
        assert "Injection vulnerabilities" in content

    def test_build_consistency_review(self) -> None:
        """测试一致性审查类型."""
        context = ReviewContext(diff="test")

        messages = PromptTemplate.build(context, ReviewType.CONSISTENCY)
        content = messages[2]["content"]

        assert "Consistency-focused review" in content
        assert "Naming conventions" in content

    def test_build_performance_review(self) -> None:
        """测试性能审查类型."""
        context = ReviewContext(diff="test")

        messages = PromptTemplate.build(context, ReviewType.PERFORMANCE)
        content = messages[2]["content"]

        assert "Performance-focused review" in content
        assert "Algorithmic complexity" in content

    def test_output_format_instructions(self) -> None:
        """测试输出格式指令."""
        content = PromptTemplate._output_format_instructions()

        assert "Output Format" in content
        assert "JSON" in content
        assert "summary" in content
        assert "comments" in content


class TestPromptCache:
    """PromptCache 测试."""

    def test_get_set(self) -> None:
        """测试获取和设置."""
        cache = PromptCache()
        context = ReviewContext(diff="test")

        # 首次获取为空
        assert cache.get(context, ReviewType.GENERAL) is None

        # 设置
        messages = [{"role": "user", "content": "test"}]
        cache.set(context, ReviewType.GENERAL, messages)

        # 再次获取
        cached = cache.get(context, ReviewType.GENERAL)
        assert cached == messages

    def test_cache_key_same_content(self) -> None:
        """测试相同内容的缓存键."""
        cache = PromptCache()
        context1 = ReviewContext(diff="test diff")
        context2 = ReviewContext(diff="test diff")

        key1 = cache.get_key(context1, ReviewType.GENERAL)
        key2 = cache.get_key(context2, ReviewType.GENERAL)

        assert key1 == key2

    def test_cache_key_different_content(self) -> None:
        """测试不同内容的缓存键."""
        cache = PromptCache()
        context1 = ReviewContext(diff="diff1")
        context2 = ReviewContext(diff="diff2")

        key1 = cache.get_key(context1, ReviewType.GENERAL)
        key2 = cache.get_key(context2, ReviewType.GENERAL)

        assert key1 != key2

    def test_cache_size_limit(self) -> None:
        """测试缓存大小限制."""
        cache = PromptCache(max_size=2)

        # 添加超过限制
        for i in range(5):
            context = ReviewContext(diff=f"diff{i}")
            cache.set(context, ReviewType.GENERAL, [])

        # 缓存应该被清理
        assert len(cache._cache) <= 2

    def test_clear(self) -> None:
        """测试清空."""
        cache = PromptCache()
        context = ReviewContext(diff="test")
        cache.set(context, ReviewType.GENERAL, [])

        assert len(cache._cache) == 1

        cache.clear()

        assert len(cache._cache) == 0
