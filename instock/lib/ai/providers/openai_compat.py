#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenAI 兼容 Provider：覆盖 OpenAI / DeepSeek / Qwen / Kimi / vLLM / Ollama 等。

零新增依赖：使用项目已存在的 `requests`。
"""

import json
import logging
from typing import Iterator, List

import requests

from instock.lib.ai.exceptions import ProviderError, RateLimitError
from instock.lib.ai.providers.base import ChatMessage, ChatResult, Provider

__author__ = 'InStock'
__date__ = '2026/05/11'


class OpenAICompatProvider(Provider):
    name = 'openai_compat'

    def _headers(self):
        h = {'Content-Type': 'application/json'}
        if self.config.api_key:
            h['Authorization'] = f'Bearer {self.config.api_key}'
        return h

    def _build_payload(self, messages: List[ChatMessage], **kwargs) -> dict:
        payload = {
            'model': kwargs.get('model') or self.config.model,
            'messages': [
                {k: v for k, v in {
                    'role': m.role,
                    'content': m.content,
                    'name': m.name,
                    'tool_call_id': m.tool_call_id,
                }.items() if v is not None}
                for m in messages
            ],
            'temperature': kwargs.get('temperature', self.config.temperature),
            'max_tokens': kwargs.get('max_tokens', self.config.max_tokens),
        }
        # 透传扩展字段（tools/tool_choice/response_format 等）
        for k in ('tools', 'tool_choice', 'response_format', 'top_p', 'stop'):
            if k in kwargs and kwargs[k] is not None:
                payload[k] = kwargs[k]
        return payload

    def chat(self, messages: List[ChatMessage], **kwargs) -> ChatResult:
        url = f"{self.config.api_base.rstrip('/')}/chat/completions"
        payload = self._build_payload(messages, **kwargs)
        try:
            resp = requests.post(
                url, headers=self._headers(), json=payload,
                timeout=kwargs.get('timeout', self.config.timeout),
            )
        except requests.RequestException as exc:
            raise ProviderError(f'网络错误: {exc}') from exc

        if resp.status_code == 429:
            raise RateLimitError(f'上游 429: {resp.text[:200]}')
        if resp.status_code >= 400:
            raise ProviderError(
                f'HTTP {resp.status_code}',
                status_code=resp.status_code,
                body=resp.text[:500],
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderError(f'非 JSON 响应: {resp.text[:200]}') from exc

        try:
            choice = data['choices'][0]
            content = (choice.get('message') or {}).get('content') or ''
            finish_reason = choice.get('finish_reason') or ''
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f'响应结构异常: {str(data)[:200]}') from exc

        usage = data.get('usage') or {}
        return ChatResult(
            content=content,
            prompt_tokens=int(usage.get('prompt_tokens') or 0),
            completion_tokens=int(usage.get('completion_tokens') or 0),
            total_tokens=int(usage.get('total_tokens') or 0),
            finish_reason=finish_reason,
            raw=data,
        )

    def stream(self, messages: List[ChatMessage], **kwargs) -> Iterator[str]:
        url = f"{self.config.api_base.rstrip('/')}/chat/completions"
        payload = self._build_payload(messages, **kwargs)
        payload['stream'] = True
        try:
            resp = requests.post(
                url, headers=self._headers(), json=payload, stream=True,
                timeout=kwargs.get('timeout', self.config.timeout),
            )
        except requests.RequestException as exc:
            raise ProviderError(f'网络错误: {exc}') from exc

        if resp.status_code == 429:
            raise RateLimitError(f'上游 429: {resp.text[:200]}')
        if resp.status_code >= 400:
            raise ProviderError(
                f'HTTP {resp.status_code}',
                status_code=resp.status_code,
                body=resp.text[:500],
            )

        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if not line.startswith('data:'):
                continue
            payload_str = line[5:].strip()
            if payload_str == '[DONE]':
                break
            try:
                chunk = json.loads(payload_str)
                delta = (chunk.get('choices', [{}])[0].get('delta') or {})
                piece = delta.get('content')
                if piece:
                    yield piece
            except Exception as exc:
                logging.debug(f"[ai.openai_compat] 流式解析失败: {exc}")
                continue
