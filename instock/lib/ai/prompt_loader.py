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
    # M10 新增：编排管线 / 跨场景内置 agent
    {
        'name': 'strategy_analyst',
        'display_name': '策略分析师',
        'description': '把自然语言需求拆解为思路 + 伪代码（pipeline 第一步）。',
        'is_builtin': True,
    },
    {
        'name': 'market_summarizer',
        'display_name': '行情/回测解读',
        'description': '把回测指标或行情数据解读成简洁中文摘要（IM / 复盘文案）。',
        'is_builtin': True,
    },
]


def list_agents():
    """返回所有可用 agent 元数据列表。

    M7：DB 优先（cn_stock_ai_agent），文件兜底（内置 agent prompt 来自 prompt/*.md）。
    流程：
      1) 启动时 upsert_builtin_agents（懒触发，仅一次）保证内置记录存在
      2) 从 DB 读取所有 enabled agent
      3) 若 DB 不可用，回退到旧的纯文件列表（M5 行为）
    """
    _bootstrap_builtins()
    try:
        from instock.lib.ai import agent_store
        rows = agent_store.list_agents(enabled_only=True)
    except Exception:
        rows = []
    if rows:
        out = []
        for r in rows:
            sp = r.get('system_prompt') or ''
            # 内置 agent 若 DB 中 system_prompt 被清空，则回退到文件
            if r.get('is_builtin') and not sp.strip():
                sp = load(r['name'])
            out.append({
                'name': r['name'],
                'display_name': r.get('display_name') or r['name'],
                'description': r.get('description') or '',
                'is_builtin': bool(r.get('is_builtin')),
                'system_prompt': sp,
                'has_prompt': bool(sp),
                'default_provider': r.get('default_provider'),
                'default_model': r.get('default_model'),
                'allowed_tools': r.get('allowed_tools'),
                'temperature': r.get('temperature'),
                'max_tokens': r.get('max_tokens'),
                'enabled': bool(r.get('enabled', True)),
            })
        return out
    # DB 不可用 / 空表：兜底文件
    out = []
    for meta in _BUILTIN_AGENTS:
        prompt_text = load(meta['name'])
        out.append({
            **meta,
            'system_prompt': prompt_text,
            'has_prompt': bool(prompt_text),
        })
    return out


_bootstrap_done = False
_bootstrap_lock = threading.Lock()


def _bootstrap_builtins():
    """首次访问时把内置 agent upsert 进 DB（is_builtin=1）。"""
    global _bootstrap_done
    if _bootstrap_done:
        return
    with _bootstrap_lock:
        if _bootstrap_done:
            return
        try:
            from instock.lib.ai import agent_store
            payloads = []
            for meta in _BUILTIN_AGENTS:
                prompt_text = load(meta['name'])
                if not prompt_text:
                    continue
                payloads.append({
                    'name': meta['name'],
                    'display_name': meta.get('display_name'),
                    'description': meta.get('description'),
                    'system_prompt': prompt_text,
                })
            if payloads:
                agent_store.upsert_builtin_agents(payloads)
        except Exception:
            # 失败不影响业务，list_agents 会走文件兜底
            pass
        finally:
            _bootstrap_done = True


def _reset_bootstrap_for_test():
    """仅供测试用：强制下次 list_agents 重新 bootstrap。"""
    global _bootstrap_done
    with _bootstrap_lock:
        _bootstrap_done = False
