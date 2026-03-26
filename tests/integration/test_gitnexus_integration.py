"""GitNexus 集成本地测试脚本.

测试内容：
1. GitNexus 可用性检测
2. 可选降级策略
3. Agent 集成（Security/Logic/Style）
4. 调用链分析功能
5. 超时和错误处理
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))


def test_gitnexus_availability():
    """测试 GitNexus 可用性检测."""
    print("\n" + "=" * 60)
    print("Test 1: GitNexus Availability Check")
    print("=" * 60)

    from consistency.core.gitnexus_client import GitNexusClient

    # 测试可用性检测
    is_available = GitNexusClient.is_available()
    print(f"GitNexus Available: {is_available}")

    if is_available:
        print("[OK] GitNexus is installed/available")
        try:
            client = GitNexusClient()
            print(f"[OK] GitNexusClient created successfully")
            print(f"  - Client type: {type(client).__name__}")
        except Exception as e:
            print(f"[FAIL] GitNexusClient creation failed: {e}")
    else:
        print("[WARN] GitNexus not available (optional dependency)")

    return is_available


def test_agent_without_gitnexus():
    """测试 Agent 在没有 GitNexus 时正常工作."""
    print("\n" + "=" * 60)
    print("测试 2: Agent 无 GitNexus 降级测试")
    print("=" * 60)

    from consistency.agents.security_agent import SecurityAgent
    from consistency.agents.logic_agent import LogicAgent
    from consistency.agents.style_agent import StyleAgent

    test_code = """
def hello():
    print("Hello World")
"""

    async def run_tests():
        results = []

        # 测试 SecurityAgent
        print("\n--- SecurityAgent (无 GitNexus) ---")
        try:
            agent = SecurityAgent(gitnexus_client=None)
            result = await agent.analyze(Path("test.py"), test_code)
            print(f"[OK] SecurityAgent 正常工作")
            print(f"  - 发现问题: {len(result.comments)}")
            print(f"  - 摘要: {result.summary}")
            results.append(("SecurityAgent", True))
        except Exception as e:
            print(f"[FAIL] SecurityAgent 失败: {e}")
            results.append(("SecurityAgent", False))

        # 测试 LogicAgent
        print("\n--- LogicAgent (无 GitNexus) ---")
        try:
            agent = LogicAgent(gitnexus_client=None)
            result = await agent.analyze(Path("test.py"), test_code)
            print(f"[OK] LogicAgent 正常工作")
            print(f"  - 发现问题: {len(result.comments)}")
            print(f"  - 摘要: {result.summary}")
            results.append(("LogicAgent", True))
        except Exception as e:
            print(f"[FAIL] LogicAgent 失败: {e}")
            results.append(("LogicAgent", False))

        # 测试 StyleAgent
        print("\n--- StyleAgent (无 GitNexus) ---")
        try:
            agent = StyleAgent(gitnexus_client=None)
            result = await agent.analyze(Path("test.py"), test_code)
            print(f"[OK] StyleAgent 正常工作")
            print(f"  - 发现问题: {len(result.comments)}")
            print(f"  - 摘要: {result.summary}")
            results.append(("StyleAgent", True))
        except Exception as e:
            print(f"[FAIL] StyleAgent 失败: {e}")
            results.append(("StyleAgent", False))

        return results

    return asyncio.run(run_tests())


def test_agent_with_mock_gitnexus():
    """测试 Agent 在有 GitNexus 时的增强功能."""
    print("\n" + "=" * 60)
    print("测试 3: Agent 带 Mock GitNexus 增强测试")
    print("=" * 60)

    from consistency.agents.security_agent import SecurityAgent

    # 创建 Mock GitNexus 客户端
    mock_gitnexus = MagicMock()
    mock_gitnexus.is_available.return_value = True

    # Mock 上下文返回
    mock_context = MagicMock()
    mock_context.callers = [{"name": "caller1"}, {"name": "caller2"}]
    mock_context.callees = [{"name": "callee1"}]
    mock_gitnexus.get_context = AsyncMock(return_value=mock_context)

    test_code = """
import os

def dangerous():
    eval("1+1")  # 危险函数
    os.system("ls")  # 系统调用
"""

    async def run_test():
        print("\n--- SecurityAgent (带 GitNexus) ---")
        try:
            agent = SecurityAgent(gitnexus_client=mock_gitnexus)
            result = await agent.analyze(Path("test.py"), test_code)
            print(f"[OK] SecurityAgent 带 GitNexus 正常工作")
            print(f"  - 发现问题: {len(result.comments)}")
            print(f"  - 来源: {result.metadata.get('sources', [])}")

            # 验证 GitNexus 被调用
            if mock_gitnexus.get_context.called:
                print(f"[OK] GitNexus 增强分析已执行")
                call_count = mock_gitnexus.get_context.call_count
                print(f"  - get_context 调用次数: {call_count}")
            else:
                print(f"[WARN] GitNexus 未被调用（可能没有检测到危险函数）")

            return True
        except Exception as e:
            print(f"[FAIL] SecurityAgent 带 GitNexus 失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    return asyncio.run(run_test())


def test_supervisor_with_optional_gitnexus():
    """测试 Supervisor 的 GitNexus 可选集成."""
    print("\n" + "=" * 60)
    print("测试 4: Supervisor GitNexus 可选集成")
    print("=" * 60)

    from consistency.agents.supervisor import ReviewSupervisor

    test_code = """
def example():
    # TODO: 实现这个功能
    pass
"""

    async def run_tests():
        results = []

        # 测试无 GitNexus
        print("\n--- Supervisor (无 GitNexus) ---")
        try:
            supervisor = ReviewSupervisor(gitnexus_client=None, quick_mode=False)
            result = await supervisor.review(Path("test.py"), test_code)
            print(f"[OK] Supervisor 无 GitNexus 正常工作")
            print(f"  - 激活 Agent: {supervisor.get_stats()['agents']}")
            print(f"  - 发现评论: {len(result.comments)}")
            results.append(("Supervisor 无 GitNexus", True))
        except Exception as e:
            print(f"[FAIL] Supervisor 无 GitNexus 失败: {e}")
            import traceback
            traceback.print_exc()
            results.append(("Supervisor 无 GitNexus", False))

        # 测试快速模式
        print("\n--- Supervisor (快速模式) ---")
        try:
            supervisor = ReviewSupervisor(gitnexus_client=None, quick_mode=True)
            result = await supervisor.review(Path("test.py"), test_code)
            print(f"[OK] Supervisor 快速模式正常工作")
            print(f"  - 激活 Agent: {supervisor.get_stats()['agents']}")
            print(f"  - 发现评论: {len(result.comments)}")
            results.append(("Supervisor 快速模式", True))
        except Exception as e:
            print(f"[FAIL] Supervisor 快速模式失败: {e}")
            results.append(("Supervisor 快速模式", False))

        return results

    return asyncio.run(run_tests())


def test_error_handling():
    """测试 GitNexus 错误处理."""
    print("\n" + "=" * 60)
    print("测试 5: GitNexus 错误处理")
    print("=" * 60)

    from consistency.agents.security_agent import SecurityAgent

    # 创建会抛出异常的 Mock
    mock_gitnexus = MagicMock()
    mock_gitnexus.is_available.return_value = True
    mock_gitnexus.get_context = AsyncMock(side_effect=Exception("GitNexus 连接失败"))

    test_code = """
def test():
    eval("1+1")
"""

    async def run_test():
        print("\n--- 模拟 GitNexus 异常 ---")
        try:
            agent = SecurityAgent(gitnexus_client=mock_gitnexus)
            result = await agent.analyze(Path("test.py"), test_code)
            print(f"[OK] Agent 在 GitNexus 异常时继续工作")
            print(f"  - 发现问题: {len(result.comments)}")
            print(f"  - 基础扫描正常工作")
            return True
        except Exception as e:
            print(f"[FAIL] Agent 在 GitNexus 异常时失败: {e}")
            return False

    return asyncio.run(run_test())


def test_review_diff_integration():
    """测试 review diff 命令的 GitNexus 集成."""
    print("\n" + "=" * 60)
    print("测试 6: review diff GitNexus 集成")
    print("=" * 60)

    from consistency.tools.diff_tools import DiffParser, IncrementalReviewer

    diff_text = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,6 @@
 def hello():
     print("Hello")
+    eval("1+1")  # 安全问题
+    x = 1
+    return x
"""

    async def run_test():
        print("\n--- DiffParser ---")
        try:
            parser = DiffParser()
            file_diffs = parser.parse(diff_text)
            print(f"[OK] DiffParser 正常工作")
            print(f"  - 解析文件数: {len(file_diffs)}")
            if file_diffs:
                print(f"  - 文件路径: {file_diffs[0].new_path}")
            return True
        except Exception as e:
            print(f"[FAIL] DiffParser 失败: {e}")
            return False

    return asyncio.run(run_test())


def test_cli_help():
    """测试 CLI 命令帮助信息."""
    print("\n" + "=" * 60)
    print("测试 7: CLI 命令帮助")
    print("=" * 60)

    import subprocess

    # 使用当前 Python 解释器路径
    python_exe = sys.executable
    commands = [
        [python_exe, "-m", "consistency", "review", "--help"],
        [python_exe, "-m", "consistency", "review", "diff", "--help"],
        [python_exe, "-m", "consistency", "review", "file", "--help"],
    ]

    results = []
    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=10,
            )
            if result.returncode == 0:
                print(f"[OK] {' '.join(cmd[3:])} 命令可用")
                results.append(True)
            else:
                print(f"[FAIL] {' '.join(cmd[3:])} 命令失败")
                results.append(False)
        except Exception as e:
            print(f"[FAIL] {' '.join(cmd[3:])} 执行异常: {e}")
            results.append(False)

    return results


def main():
    """运行所有测试."""
    print("\n" + "=" * 70)
    print("GitNexus 集成本地测试")
    print("=" * 70)
    print(f"Python: {sys.version}")
    print(f"平台: {sys.platform}")
    print(f"工作目录: {Path.cwd()}")

    all_results = []
    start_time = time.time()

    # 运行测试
    gitnexus_available = test_gitnexus_availability()
    all_results.extend(test_agent_without_gitnexus())
    all_results.append(("Mock GitNexus", test_agent_with_mock_gitnexus()))
    all_results.extend(test_supervisor_with_optional_gitnexus())
    all_results.append(("错误处理", test_error_handling()))
    all_results.append(("Diff 集成", test_review_diff_integration()))
    all_results.extend([(f"CLI {i+1}", r) for i, r in enumerate(test_cli_help())])

    # 总结
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)

    passed = sum(1 for _, r in all_results if r)
    total = len(all_results)

    for name, result in all_results:
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"  {status}: {name}")

    print(f"\n总计: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
    print(f"耗时: {elapsed:.2f}s")

    if gitnexus_available:
        print("\n注: GitNexus 可用，建议也进行实际集成测试")
    else:
        print("\n注: GitNexus 不可用（可选依赖），所有测试使用降级模式")

    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
