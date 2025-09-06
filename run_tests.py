#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试运行脚本

提供便捷的测试运行选项
"""

import sys
import subprocess
import argparse


def run_command(cmd):
    """运行命令并显示结果"""
    print(f"执行命令: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("错误信息:", result.stderr)
        
        return result.returncode == 0
    
    except Exception as e:
        print(f"命令执行失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Multi-AI-Agent 测试运行工具")
    
    parser.add_argument(
        '--type', 
        choices=['all', 'unit', 'integration', 'ollama', 'mcp'],
        default='all',
        help='测试类型 (默认: all)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='详细输出'
    )
    
    parser.add_argument(
        '--fast',
        action='store_true', 
        help='快速测试，跳过耗时的集成测试'
    )
    
    args = parser.parse_args()
    
    # 基础pytest命令
    base_cmd = ['pytest']
    
    if args.verbose:
        base_cmd.append('-v')
    
    # 根据测试类型构建命令
    if args.type == 'unit':
        cmd = base_cmd + ['tests/unit/']
        print("运行单元测试...")
        
    elif args.type == 'integration':
        cmd = base_cmd + ['tests/integration/']
        print("运行集成测试...")
        
    elif args.type == 'ollama':
        cmd = base_cmd + ['tests/integration/test_ollama_integration.py']
        print("运行Ollama专项测试...")
        
    elif args.type == 'mcp':
        cmd = ['python', 'tests/test_fetch_mcp.py']
        print("运行MCP服务器测试...")
        
    elif args.fast:
        cmd = base_cmd + ['tests/unit/', '-v']
        print("运行快速测试（仅单元测试）...")
        
    else:
        cmd = base_cmd + ['tests/', '--tb=short']
        print("运行全部测试...")
    
    # 运行测试
    success = run_command(cmd)
    
    if success:
        print("\n[SUCCESS] 测试通过！")
        return 0
    else:
        print("\n[FAILED] 测试失败！")
        return 1


if __name__ == "__main__":
    sys.exit(main())