"""示例项目 - 演示 GitConsistency 功能.

这是一个故意包含一些代码问题的示例项目，
用于展示 GitConsistency 的检测能力。
"""

import os
import subprocess

# 问题 1: 硬编码密码（安全问题）
DEFAULT_PASSWORD = "admin123"


# 问题 2: 使用 eval（安全问题）
def process_user_input(user_input):
    """处理用户输入."""
    result = eval(user_input)  # nosec
    return result


# 问题 3: 命令注入风险（安全问题）
def run_command(user_input):
    """运行命令."""
    cmd = f"echo {user_input}"
    subprocess.call(cmd, shell=True)  # nosec


# 问题 4: 未使用的导入（代码质量问题）
import json  # noqa: F401


def authenticate(username, password):
    """验证用户.

    问题 5: 硬编码凭证比较（安全问题）
    """
    if username == "admin" and password == DEFAULT_PASSWORD:
        return True
    return False


def calculate_discount(price, user_type):
    """计算折扣.

    问题 6: 复杂条件（代码质量问题）
    """
    if user_type == "vip" and price > 100 and price < 1000 and price % 2 == 0:
        return price * 0.8
    elif user_type == "vip" and price >= 1000:
        return price * 0.7
    elif user_type == "normal" and price > 500:
        return price * 0.9
    else:
        return price


if __name__ == "__main__":
    # 问题 7: 敏感信息打印（安全问题）
    print(f"Database URL: {os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost/db')}")

    result = process_user_input("1 + 2")
    print(f"Result: {result}")
