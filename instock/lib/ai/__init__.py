#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一 AI 服务层入口。

对外暴露：
    run_chat(prompt, *, scene='general', system=None, agent=None, user_id=None,
             overrides=None, **kwargs) -> str
    stream_chat(prompt, ...) -> Iterator[str]
    get_provider(config=None) -> Provider

后续阶段（M6+）会扩展 run_agent / 工具循环 / 编排管线。
"""

import logging
import time
from typing import Any, Dict, Iterator, List, Optional

from instock.lib.ai import audit
from instock.lib.ai import rate_limiter
from instock.lib.ai.config import AIConfig, load_config
from instock.lib.ai.exceptions import AIError, ProviderError, RateLimitError, ValidationError
from instock.lib.ai.providers.base import ChatMessage, ChatResult, Provider, ToolCall
from instock.lib.ai.providers.openai_compat import OpenAICompatProvider

__author__ = 'InStock'
__date__ = '2026/05/11'

__all__ = [
    'run_chat', 'stream_chat', 'get_provider', 'run_agent', 'run_pipeline',
    'AIConfig', 'load_config',
    'AIError', 'RateLimitError', 'ValidationError', 'ProviderError',
    'ChatMessage', 'ChatResult', 'Provider', 'ToolCall',
]


_PROVIDER_REGISTRY = {
    'openai_compat': OpenAICompatProvider,
}


def get_provider(config: Optional[AIConfig] = None) -> Provider:
    """根据配置返回对应 Provider 实例。"""
    cfg = config or load_config()
    cls = _PROVIDER_REGISTRY.get(cfg.provider)
    if cls is None:
        raise AIError(f"未注册的 provider: {cfg.provider}")
    return cls(cfg)


def _build_messages(prompt: str, system: Optional[str],
                    history: Optional[List[ChatMessage]] = None) -> List[ChatMessage]:
    msgs: List[ChatMessage] = []
    if system:
        msgs.append(ChatMessage(role='system', content=system))
    if history:
        for m in history:
            # 跳过 system（避免与 system 参数重复）和空消息
            if not m or not getattr(m, 'content', None):
                continue
            if m.role == 'system' and system:
                continue
            msgs.append(m)
    msgs.append(ChatMessage(role='user', content=prompt))
    return msgs


def run_chat(
    prompt: str,
    *,
    scene: str = 'general',
    system: Optional[str] = None,
    agent: Optional[str] = None,
    user_id: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
    rate_limit_loop: bool = False,
    history: Optional[List[ChatMessage]] = None,
    **kwargs: Any,
) -> str:
    """同步聊天。返回 assistant 文本内容；异常会被审计后重新抛出。

    rate_limit_loop=True 表示当前调用是修复闭环内部重试（spec §4.4），
    其本身不计入 (user_id, scene) 滑窗配额，并在审计记录中落 
    tools_used.rate_limit_loop=true，供 rate_limiter 后续查询排除。
    """
    cfg = load_config(overrides)
    # spec §16.5：在 provider 调用前检查滑窗配额（fail-open）
    rate_limiter.check_quota(
        user_id=user_id, scene=scene, rate_limit_loop=rate_limit_loop)
    provider = get_provider(cfg)
    messages = _build_messages(prompt, system, history)
    started = time.time()
    content = ''
    ok = False
    err_text: Optional[str] = None
    result: Optional[ChatResult] = None
    try:
        result = provider.chat(messages, **kwargs)
        content = result.content
        ok = True
        return content
    except Exception as exc:
        err_text = str(exc)
        raise
    finally:
        latency_ms = int((time.time() - started) * 1000)
        try:
            audit.record_call(
                scene=scene,
                agent=agent,
                provider=cfg.provider,
                model=cfg.model,
                user_id=user_id,
                prompt=prompt,
                response=content,
                ok=ok,
                prompt_tokens=result.prompt_tokens if result else None,
                completion_tokens=result.completion_tokens if result else None,
                total_tokens=result.total_tokens if result else None,
                latency_ms=latency_ms,
                error=err_text,
                rate_limit_loop=rate_limit_loop,
            )
        except Exception as audit_exc:
            # J1：审计写入错误不得遮蔽业务返回值或原始异常
            logging.warning(f'[ai.run_chat] 审计写入失败（忽略）: {audit_exc}')


def stream_chat(
    prompt: str,
    *,
    scene: str = 'general',
    system: Optional[str] = None,
    agent: Optional[str] = None,
    user_id: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
    rate_limit_loop: bool = False,
    history: Optional[List[ChatMessage]] = None,
    **kwargs: Any,
) -> Iterator[str]:
    """流式聊天，yield 文本片段；结束后写一条审计记录（response 为完整拼接）。"""
    cfg = load_config(overrides)
    rate_limiter.check_quota(
        user_id=user_id, scene=scene, rate_limit_loop=rate_limit_loop)
    provider = get_provider(cfg)
    messages = _build_messages(prompt, system, history)
    started = time.time()
    pieces: List[str] = []
    ok = False
    err_text: Optional[str] = None
    try:
        for piece in provider.stream(messages, **kwargs):
            pieces.append(piece)
            yield piece
        ok = True
    except Exception as exc:
        err_text = str(exc)
        raise
    finally:
        latency_ms = int((time.time() - started) * 1000)
        try:
            audit.record_call(
                scene=scene,
                agent=agent,
                provider=cfg.provider,
                model=cfg.model,
                user_id=user_id,
                prompt=prompt,
                response=''.join(pieces),
                ok=ok,
                latency_ms=latency_ms,
                error=err_text,
                rate_limit_loop=rate_limit_loop,
            )
        except Exception as audit_exc:
            logging.warning(f'[ai.stream_chat] 审计写入失败（忽略）: {audit_exc}')


def run_agent(*args, **kwargs):
    """惰性导入避免与 agent 模块的循环依赖。"""
    from instock.lib.ai.agent import run_agent as _impl
    return _impl(*args, **kwargs)


def run_pipeline(*args, **kwargs):
    """M10 编排管线便捷入口；惰性导入避免循环。"""
    from instock.lib.ai.orchestrator import run_pipeline as _impl
    return _impl(*args, **kwargs)
