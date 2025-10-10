"""
环境变量加载模块

安全加载.env文件，自动处理编码问题
"""

from dotenv import load_dotenv, find_dotenv


def safe_load_dotenv():
    """安全加载.env文件，自动处理编码问题"""
    env_path = find_dotenv()
    if not env_path:
        print("WARNING: .env file not found, using environment variables")
        return

    encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'gbk', 'gb2312']

    for encoding in encodings:
        try:
            load_dotenv(env_path, encoding=encoding)
            print(f"SUCCESS: .env file loaded with encoding: {encoding}")
            return
        except (UnicodeDecodeError, FileNotFoundError):
            continue

    print("WARNING: Could not read .env file, using environment variables or defaults")


# 自动加载环境变量
safe_load_dotenv()
