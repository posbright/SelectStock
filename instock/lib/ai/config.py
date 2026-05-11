#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 服务层配置：三层合并 (.env ← cn_stock_strategy_params.ai_model ← request overrides)。

读取顺序（高 → 低）：
  1. 调用方 overrides（dict 参数）
  2. 数据库 ai_model 组（用户在策略参数页设置）
  3. 环境变量（INSTOCK_AI_*）
  4. 代码默认值
"""

import logging
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Optional

import instock.lib.envconfig as _cfg

__author__ = 'InStock'
__date__ = '2026/05/11'


# ── 默认值 ──
_DEFAULT_PROVIDER = 'openai_compat'
_DEFAULT_API_BASE = 'https://api.openai.com/v1'
_DEFAULT_MODEL = 'gpt-4o-mini'
_DEFAULT_TEMPERATURE = 0.3
_DEFAULT_MAX_TOKENS = 2000
_DEFAULT_TIMEOUT = 60


@dataclass
class AIConfig:
    """单次 AI 调用所需的运行时配置。"""

    provider: str = _DEFAULT_PROVIDER
    api_base: str = _DEFAULT_API_BASE
    api_key: str = ''
    model: str = _DEFAULT_MODEL
    temperature: float = _DEFAULT_TEMPERATURE
    max_tokens: int = _DEFAULT_MAX_TOKENS
    timeout: int = _DEFAULT_TIMEOUT
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _load_from_env() -> Dict[str, Any]:
    """从环境变量读取（最低优先级层之一）。

    G1：兼容文档 §4.2 的 `INSTOCK_AI_DEFAULT_*` 命名；优先取
    `INSTOCK_AI_*`，回退到 `INSTOCK_AI_DEFAULT_*`。
    """
    def _str(name: str) -> str:
        v = _cfg.get_str(name, '')
        if v:
            return v
        return _cfg.get_str(name.replace('INSTOCK_AI_', 'INSTOCK_AI_DEFAULT_', 1), '')

    out: Dict[str, Any] = {}
    provider = _str('INSTOCK_AI_PROVIDER')
    if provider:
        out['provider'] = provider
    api_base = _str('INSTOCK_AI_API_BASE')
    if api_base:
        out['api_base'] = api_base
    api_key = _str('INSTOCK_AI_API_KEY')
    if api_key:
        out['api_key'] = api_key
    model = _str('INSTOCK_AI_MODEL')
    if model:
        out['model'] = model
    env = _envkeys()
    if 'INSTOCK_AI_TEMPERATURE' in env or 'INSTOCK_AI_DEFAULT_TEMPERATURE' in env:
        key = 'INSTOCK_AI_TEMPERATURE' if 'INSTOCK_AI_TEMPERATURE' in env else 'INSTOCK_AI_DEFAULT_TEMPERATURE'
        out['temperature'] = _cfg.get_float(key, _DEFAULT_TEMPERATURE)
    if 'INSTOCK_AI_MAX_TOKENS' in env or 'INSTOCK_AI_DEFAULT_MAX_TOKENS' in env:
        key = 'INSTOCK_AI_MAX_TOKENS' if 'INSTOCK_AI_MAX_TOKENS' in env else 'INSTOCK_AI_DEFAULT_MAX_TOKENS'
        out['max_tokens'] = _cfg.get_int(key, _DEFAULT_MAX_TOKENS)
    if 'INSTOCK_AI_TIMEOUT' in env or 'INSTOCK_AI_DEFAULT_TIMEOUT' in env:
        key = 'INSTOCK_AI_TIMEOUT' if 'INSTOCK_AI_TIMEOUT' in env else 'INSTOCK_AI_DEFAULT_TIMEOUT'
        out['timeout'] = _cfg.get_int(key, _DEFAULT_TIMEOUT)
    return out


def _envkeys():
    import os
    return os.environ


def _load_from_db() -> Dict[str, Any]:
    """从 cn_stock_strategy_params 的 ai_model 组读取。

    复用现有 strategyParamsHandler.get_strategy_params。失败时返回空 dict（不阻断）。
    """
    out: Dict[str, Any] = {}
    try:
        from instock.web.strategyParamsHandler import get_strategy_params
        params = get_strategy_params('ai_model')
    except Exception as exc:
        logging.debug(f"[ai.config] 读取 ai_model 组失败（首次启动属正常）: {exc}")
        return out
    if not params:
        return out
    values: Dict[str, Any] = {}
    for group in params.get('groups', []):
        for p in group.get('params', []):
            values[p['key']] = p['value']
    if not values:
        return out
    if values.get('api_base'):
        out['api_base'] = values['api_base']
    if values.get('api_key'):
        out['api_key'] = values['api_key']
    model = values.get('model')
    if model == 'custom':
        model = values.get('custom_model') or None
    if model:
        out['model'] = model
    for k, caster in (('temperature', float), ('max_tokens', int), ('timeout', int)):
        if values.get(k) not in (None, ''):
            try:
                out[k] = caster(values[k])
            except (ValueError, TypeError):
                pass
    return out


def load_config(overrides: Optional[Dict[str, Any]] = None) -> AIConfig:
    """三层合并生成 AIConfig。"""
    merged: Dict[str, Any] = {}
    merged.update(_load_from_env())
    merged.update(_load_from_db())
    if overrides:
        merged.update({k: v for k, v in overrides.items() if v is not None})
    valid_keys = {'provider', 'api_base', 'api_key', 'model',
                  'temperature', 'max_tokens', 'timeout', 'extra'}
    extra = {k: v for k, v in merged.items() if k not in valid_keys}
    cfg_kwargs = {k: v for k, v in merged.items() if k in valid_keys}
    if extra:
        cfg_kwargs.setdefault('extra', {}).update(extra)
    return AIConfig(**cfg_kwargs)
