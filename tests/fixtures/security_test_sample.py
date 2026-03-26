"""测试文件 - 包含一些安全问题用于测试扫描器."""

import os
import pickle


def unsafe_function(user_input):
    """This function uses eval which is unsafe."""
    result = eval(user_input)  # nosec: testing purpose
    return result


def unsafe_pickle(data):
    """This function uses unsafe pickle loading."""
    return pickle.loads(data)  # nosec: testing purpose


def unsafe_command(user_input):
    """This function uses os.system which is unsafe."""
    os.system(f"echo {user_input}")  # nosec: testing purpose


def password_hardcoded():
    """This function has a hardcoded password."""
    password = "super_secret_password_123"  # should trigger bandit
    return password


if __name__ == "__main__":
    print("Test file for security scanning")
