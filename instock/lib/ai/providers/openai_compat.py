#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenAI 兼容 Provider：覆盖 OpenAI / DeepSeek / Qwen / Kimi / vLLM / Ollama 等。

零新增依赖：使用项目已存在的 `requests`。
"""

import json
import logging
import re
from typing import Iterator, List

import requests

from instock.lib.ai.exceptions import ProviderError, RateLimitError
from instock.lib.ai.providers.base import ChatMessage, ChatResult, Provider, ToolCall

__author__ = 'InStock'
__date__ = '2026/05/11'

# C2：异常消息中可能回显请求头/凭证 → 在外抛前做正则脱敏
# 覆盖：Bearer xxx / sk-xxx / api_key=xxx / x-api-key: xxx / ?key=xxx
_SECRET_RE = re.compile(
    r'(Bearer\s+[A-Za-z0-9._\-]{8,}'
    r'|sk-[A-Za-z0-9._\-]{8,}'
    r'|(?:x-)?api[_-]?key["\']?\s*[:=]\s*["\']?[A-Za-z0-9._\-]{8,}'
    r'|[?&]key=[A-Za-z0-9._\-]{8,})',
    re.IGNORECASE,
)


def _scrub(text: str) -> str:
    if not text:
        return text
    return _SECRET_RE.sub('[REDACTED]', text)


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
                    'tool_calls': m.tool_calls,
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
            message = choice.get('message') or {}
            content = message.get('content') or ''
            finish_reason = choice.get('finish_reason') or ''
            # M6：解析 tool_calls（OpenAI 函数调用协议）
            tool_calls: List[ToolCall] = []
            for tc in (message.get('tool_calls') or []):
                func = tc.get('function') or {}
                args_raw = func.get('arguments') or '{}'
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except (ValueError, TypeError):
                        args = {'_raw': args_raw}
                else:
                    args = dict(args_raw) if isinstance(args_raw, dict) else {}
                tool_calls.append(ToolCall(
                    id=str(tc.get('id') or ''),
                    name=str(func.get('name') or ''),
                    arguments=args,
                ))
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
            tool_calls=tool_calls,
        )

    def stream(self, messages: List[ChatMessage], **kwargs) -> Iterator[str]:
        url = f"{self.config.api_base.rstrip('/')}/chat/completions"
        payload = self._build_payload(messages, **kwargs)
        payload['stream'] = True
        try:
            # 使用 with 确保消费者中途异常 / GeneratorExit 时连接被释放（B4）
            resp = requests.post(
                url, headers=self._headers(), json=payload, stream=True,
                timeout=kwargs.get('timeout', self.config.timeout),
            )
        except requests.RequestException as exc:
            raise ProviderError(f'网络错误: {_scrub(str(exc))}') from exc

        try:
            if resp.status_code == 429:
                raise RateLimitError(f'上游 429: {_scrub(resp.text[:200])}')
            if resp.status_code >= 400:
                raise ProviderError(
                    f'HTTP {resp.status_code}',
                    status_code=resp.status_code,
                    body=_scrub(resp.text[:500]),
                )

            # 关键：OpenAI 兼容供应商（Moonshot/DeepSeek/...）的 SSE 响应往往不
            # 声明 charset，requests 默认按 ISO-8859-1 解码 text/event-stream，
            # 中文会变成 latin-1 字节再被前端/DB 当 UTF-8 存入，导致双重编码
            # mojibake（如 "基本面" → "å\x9fºæ\x9c¬é\x9d¢"）。
            # 这里强制 utf-8 解码，与非流式 chat() 路径的 resp.json() 行为一致。
            resp.encoding = 'utf-8'

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
        except requests.RequestException as exc:
            # P0-E2：迭代过程中网络异常也需脱敏后再外抛
            raise ProviderError(f'流式读取失败: {_scrub(str(exc))}') from exc
        finally:
            # 无论正常 break / 早退 / 异常，都关闭底层连接
            try:
                resp.close()
            except Exception:
                pass
