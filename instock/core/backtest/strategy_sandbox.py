#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略安全沙箱 — 编译和验证用户策略代码

安全措施：
- 白名单导入（仅允许 math/numpy/pandas/talib）
- 禁止危险函数（exec/eval/open/import os/sys）
- 超时保护（回测引擎层面实现）
"""

import logging
import re

__author__ = 'InStock'
__date__ = '2026/03/13'

# 禁止的关键字和模块
_FORBIDDEN_PATTERNS = [
    r'\bimport\s+os\b',
    r'\bimport\s+sys\b',
    r'\bimport\s+subprocess\b',
    r'\bimport\s+shutil\b',
    r'\b__import__\b',
    r'\beval\s*\(',
    r'\bexec\s*\(',
    r'\bcompile\s*\(',
    r'\bopen\s*\(',
    r'\bgetattr\s*\(',
    r'\bsetattr\s*\(',
    r'\bdelattr\s*\(',
    r'\bglobals\s*\(',
    r'\blocals\s*\(',
]

# 允许的导入模块
_ALLOWED_IMPORTS = {
    'math', 'numpy', 'np', 'pandas', 'pd',
    'talib', 'ta', 'datetime', 'collections',
    'functools', 'itertools', 'operator',
}


def validate_code(code_str):
    """
    验证策略代码安全性。

    Args:
        code_str: Python 策略代码字符串

    Returns:
        (bool, str): (是否安全, 错误信息)
    """
    if not code_str or not code_str.strip():
        return False, "策略代码为空"

    # 检查禁止的模式
    for pattern in _FORBIDDEN_PATTERNS:
        match = re.search(pattern, code_str)
        if match:
            return False, f"策略代码包含禁止的操作: {match.group()}"

    # 检查导入语句
    import_pattern = r'import\s+(\w+)'
    for match in re.finditer(import_pattern, code_str):
        module = match.group(1)
        if module not in _ALLOWED_IMPORTS:
            return False, f"不允许导入模块: {module}（允许的模块: {', '.join(sorted(_ALLOWED_IMPORTS))}）"

    # 检查必要函数
    if 'def initialize' not in code_str:
        return False, "策略代码必须定义 initialize(context) 函数"

    if 'def handle_data' not in code_str:
        return False, "策略代码必须定义 handle_data(context, data) 函数"

    return True, ""


def compile_strategy(code_str):
    """
    编译策略代码，提取策略函数。

    Args:
        code_str: Python 策略代码字符串

    Returns:
        dict: {
            'initialize': callable,
            'handle_data': callable,
            'before_trading_start': callable or None,
            'after_trading_end': callable or None,
        }

    Raises:
        ValueError: 代码验证失败
        SyntaxError: Python 语法错误
    """
    # 安全验证
    ok, err = validate_code(code_str)
    if not ok:
        raise ValueError(f"策略代码验证失败: {err}")

    # 编译执行
    namespace = _create_safe_namespace()

    try:
        exec(compile(code_str, '<strategy>', 'exec'), namespace)
    except SyntaxError as e:
        raise SyntaxError(f"策略代码语法错误 (行{e.lineno}): {e.msg}")

    # 提取函数
    result = {}

    if 'initialize' not in namespace or not callable(namespace['initialize']):
        raise ValueError("未找到 initialize(context) 函数")
    result['initialize'] = namespace['initialize']

    if 'handle_data' not in namespace or not callable(namespace['handle_data']):
        raise ValueError("未找到 handle_data(context, data) 函数")
    result['handle_data'] = namespace['handle_data']

    result['before_trading_start'] = namespace.get('before_trading_start')
    result['after_trading_end'] = namespace.get('after_trading_end')

    return result


def _create_safe_namespace():
    """创建安全的执行命名空间"""
    import math
    ns = {
        '__builtins__': {
            # 安全的内置函数
            'abs': abs, 'all': all, 'any': any, 'bool': bool,
            'dict': dict, 'enumerate': enumerate, 'filter': filter,
            'float': float, 'frozenset': frozenset, 'int': int,
            'isinstance': isinstance, 'len': len, 'list': list,
            'map': map, 'max': max, 'min': min, 'print': print,
            'range': range, 'reversed': reversed, 'round': round,
            'set': set, 'slice': slice, 'sorted': sorted, 'str': str,
            'sum': sum, 'tuple': tuple, 'type': type, 'zip': zip,
            'True': True, 'False': False, 'None': None,
            'Exception': Exception, 'ValueError': ValueError,
            'TypeError': TypeError, 'KeyError': KeyError,
            'IndexError': IndexError, 'AttributeError': AttributeError,
        },
        'math': math,
    }

    # 尝试注入可选库
    try:
        import numpy
        ns['numpy'] = numpy
        ns['np'] = numpy
    except ImportError:
        pass

    try:
        import pandas
        ns['pandas'] = pandas
        ns['pd'] = pandas
    except ImportError:
        pass

    try:
        import talib
        ns['talib'] = talib
    except ImportError:
        pass

    return ns
