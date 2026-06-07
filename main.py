"""stu-agent - 面向中国大学生的通用桌面 Agent"""

import sys

from src.core.settings import load_settings


def main():
    print("stu-agent starting...")

    try:
        settings = load_settings("config/settings.yaml")
        print(f"  LLM Provider: {settings.llm.provider}")
        print(f"  Model: {settings.llm.model}")
    except (FileNotFoundError, ValueError) as e:
        print(f"配置加载失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
