#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 服务层统一异常。"""

__author__ = 'InStock'
__date__ = '2026/05/11'


class AIError(Exception):
    """AI 调用通用错误基类。"""


class RateLimitError(AIError):
    """触发限流（本地或上游 429）。"""


class ValidationError(AIError):
    """AI 输出校验失败（沙箱/格式）。"""


class ProviderError(AIError):
    """上游提供商返回错误（非 429）。"""

    def __init__(self, message: str, status_code: int = 0, body: str = ''):
        super().__init__(message)
        self.status_code = status_code
        self.body = body
