#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加载 instock/lib/ai/prompt/*.md 系统提示词。"""

import os
import threading
from typing import Dict

__author__ = 'InStock'
__date__ = '2026/05/11'

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), 'prompt')
_cache: Dict[str, str] = {}
_lock = threading.Lock()


def load(name: str, *, refresh: bool = False) -> str:
    """加载 prompt/{name}.md。失败时返回空字符串。"""
    if not refresh and name in _cache:
        return _cache[name]
    path = os.path.join(_PROMPT_DIR, f'{name}.md')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except OSError:
        text = ''
    with _lock:
        _cache[name] = text
    return text


def clear_cache() -> None:
    with _lock:
        _cache.clear()


# ── M5：内置 agent 元数据（提示词从 prompt/*.md 读取） ─────────
_BUILTIN_AGENTS = [
    {
        'name': 'strategy_coder',
        'display_name': '策略生成器',
        'description': '根据自然语言描述生成 Pinetrade DSL 策略代码。',
        'is_builtin': True,
    },
    {
        'name': 'strategy_repairer',
        'display_name': '策略修复器',
        'description': '根据沙箱报错或回测错误信息修复策略代码。',
        'is_builtin': True,
    },
]


def list_agents():
    """返回所有可用 agent 元数据列表（仅内置；自定义留给 M7）。"""
    out = []
    for meta in _BUILTIN_AGENTS:
        prompt_text = load(meta['name'])
        out.append({
            **meta,
            'system_prompt': prompt_text,
            'has_prompt': bool(prompt_text),
        })
    return out
