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
