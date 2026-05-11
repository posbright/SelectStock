#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Provider 抽象基类。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

__author__ = 'InStock'
__date__ = '2026/05/11'


@dataclass
class ChatMessage:
    role: str  # system / user / assistant / tool
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


@dataclass
class ChatResult:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = ''
    raw: Dict[str, Any] = field(default_factory=dict)


class Provider(ABC):
    """LLM 提供商抽象。所有实现必须支持同步 chat。"""

    name: str = 'base'

    def __init__(self, config):
        self.config = config

    @abstractmethod
    def chat(self, messages: List[ChatMessage], **kwargs) -> ChatResult:
        """同步聊天补全。"""

    def stream(self, messages: List[ChatMessage], **kwargs) -> Iterator[str]:
        """可选：流式输出（默认 fallback 到 chat 一次性返回）。"""
        result = self.chat(messages, **kwargs)
        yield result.content
