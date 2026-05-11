#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 助手 HTTP 接口 — 路由前缀 /instock/api/ai/*。

M2 提供：
  POST /instock/api/ai/strategy/generate  生成策略代码
  POST /instock/api/ai/strategy/refine    在已有代码上做局部修改
  POST /instock/api/ai/strategy/repair    根据失败信息修复代码
  POST /instock/api/ai/chat               通用聊天（无 strict 校验）

所有调用均通过 instock.lib.ai.run_chat → audit 落库 → strict 校验。
长耗时任务在共享 ThreadPoolExecutor 中执行，避免阻塞 IOLoop。
"""

import json
import logging
import re
import queue
import threading
from abc import ABC
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple

from tornado import gen
from tornado.ioloop import IOLoop

import instock.web.base as webBase
from instock.core.backtest.strategy_sandbox import validate_code_strict
from instock.lib.ai import RateLimitError, ProviderError, AIError, run_chat, stream_chat
from instock.lib.ai import prompt_loader

__author__ = 'InStock'
__date__ = '2026/05/11'

# ── 共享线程池：所有 AI 调用 handler 共用，限制并发避免上游限流 ──
_AI_EXECUTOR: Optional[ThreadPoolExecutor] = None


def _get_executor() -> ThreadPoolExecutor:
    global _AI_EXECUTOR
    if _AI_EXECUTOR is None:
        _AI_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix='ai-call')
    return _AI_EXECUTOR


_FENCE_RE = re.compile(r'^\s*```(?:python|py)?\s*\n(.*?)\n```\s*$', re.DOTALL | re.IGNORECASE)


def _strip_code_fence(text: str) -> str:
    """如果模型返回了 Markdown 代码围栏，剥离掉只保留代码体。"""
    if not text:
        return ''
    m = _FENCE_RE.match(text.strip())
    if m:
        return m.group(1).strip()
    return text.strip()


def _client_ip(handler) -> str:
    return handler.request.remote_ip or ''


def _validate_or_msg(code: str) -> Tuple[bool, str]:
    ok, err = validate_code_strict(code)
    return ok, err if not ok else ''


def _write_error(handler, code: int, msg: str, **extra):
    body = {'code': code, 'msg': msg}
    body.update(extra)
    handler.set_header('Content-Type', 'application/json')
    # HTTP 状态码语义对齐（前端 axios 拦截器可按 status 区分限流）
    if code == 429:
        handler.set_status(429)
    handler.write(json.dumps(body, ensure_ascii=False))


def _call_ai_blocking(prompt: str, system: str, scene: str, agent: str, user_id: str,
                      overrides: Optional[dict] = None):
    """在线程池中执行的同步 AI 调用。

    返回 (content, resolved_model) —— 让上层把实际使用的模型回传给前端，
    便于 SaveStrategyCodeHandler 落库 ai_model 字段（N1 修正）。
    """
    from instock.lib.ai.config import load_config as _load_cfg
    cfg = _load_cfg(overrides)
    content = run_chat(
        prompt, scene=scene, system=system, agent=agent,
        user_id=user_id, overrides=overrides,
    )
    return content, cfg.model


# M3：strict 校验失败自动重试上限。设计为环境可调，方便测试。
import os as _os
_MAX_REPAIR_ATTEMPTS = max(0, int(_os.environ.get('INSTOCK_AI_REPAIR_MAX_ATTEMPTS', '3')))


def _build_repair_prompt(prev_code: str, err: str, original_intent: str) -> str:
    """生成"修复 prompt"：携带上一次代码 + strict 错误 + 用户原始意图。"""
    return (
        f"你上一轮生成的策略代码未通过沙箱安全校验。\n\n"
        f"用户原始需求：\n{original_intent}\n\n"
        f"上一轮代码：\n{prev_code}\n\n"
        f"沙箱校验错误：\n{err}\n\n"
        f"请输出修复后的完整 Python 代码（不要解释、不要 Markdown 围栏），"
        f"要求保留原意图、移除所有 import os/sys/subprocess 等违禁项。"
    )


# ──────────────────────────────────────────────────────────────────────
# 1) 策略生成
# ──────────────────────────────────────────────────────────────────────
class GenerateStrategyHandler(webBase.BaseHandler, ABC):
    """根据自然语言 prompt 生成策略代码。

    请求体: {"prompt": "...", "model": "...", "api_key": "...", "api_base": "..."}
    响应:   {"code":0, "data": {"code": "...", "validated": true}} 或
            {"code":-1, "msg": "...", "data": {"raw": "...", "code": "..."}}
    """

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body or b'{}')
        except Exception as exc:
            _write_error(self, -1, f'请求体解析失败: {exc}')
            return

        user_prompt = (body.get('prompt') or '').strip()
        if not user_prompt:
            _write_error(self, -1, 'prompt 不能为空')
            return

        overrides = _build_overrides(body)
        system = prompt_loader.load('strategy_coder')
        try:
            raw, resolved_model = yield IOLoop.current().run_in_executor(
                _get_executor(),
                _call_ai_blocking,
                user_prompt, system, 'strategy_gen', 'strategy_coder',
                _client_ip(self), overrides,
            )
        except RateLimitError as exc:
            _write_error(self, 429, f'触发限流: {exc}')
            return
        except (ProviderError, AIError) as exc:
            _write_error(self, -1, f'AI 调用失败: {exc}')
            return
        except Exception as exc:
            logging.exception('GenerateStrategyHandler 未知异常')
            _write_error(self, -1, f'内部错误: {exc}')
            return

        code = _strip_code_fence(raw)
        ok, err = _validate_or_msg(code)
        attempts = 0
        # M3：strict 校验失败自动重试 ≤ N 轮
        if not ok and _MAX_REPAIR_ATTEMPTS > 0:
            repairer_sys = prompt_loader.load('strategy_repairer')
            for _ in range(_MAX_REPAIR_ATTEMPTS):
                attempts += 1
                fix_prompt = _build_repair_prompt(code, err, user_prompt)
                try:
                    raw, resolved_model = yield IOLoop.current().run_in_executor(
                        _get_executor(),
                        _call_ai_blocking,
                        fix_prompt, repairer_sys,
                        'strategy_gen_repair', 'strategy_repairer',
                        _client_ip(self), overrides,
                    )
                except RateLimitError as exc:
                    # 重试中触发限流：返回最近一次失败结果（已包含 raw/error）
                    logging.warning(f'生成自动修复阶段触发限流: {exc}')
                    break
                except (ProviderError, AIError) as exc:
                    logging.warning(f'生成自动修复阶段 AI 调用失败: {exc}')
                    break
                code = _strip_code_fence(raw)
                ok, err = _validate_or_msg(code)
                if ok:
                    break
        payload = {
            'code': 0 if ok else -2,
            'msg': '' if ok else f'代码沙箱校验失败: {err}',
            'data': {
                'code': code,
                'raw': raw,
                'validated': ok,
                'validation_error': err,
                'model': resolved_model,
                'repair_attempts': attempts,
            },
        }
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(payload, ensure_ascii=False))


# ──────────────────────────────────────────────────────────────────────
# 2) 策略局部修改 (refine)
# ──────────────────────────────────────────────────────────────────────
class RefineStrategyHandler(webBase.BaseHandler, ABC):
    """在已有代码上做局部修改。

    请求体: {"prompt": "把持仓从5只改成10只", "code": "...原代码..."}
    """

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body or b'{}')
        except Exception as exc:
            _write_error(self, -1, f'请求体解析失败: {exc}')
            return

        user_prompt = (body.get('prompt') or '').strip()
        original_code = (body.get('code') or '').strip()
        if not user_prompt or not original_code:
            _write_error(self, -1, 'prompt 与 code 均不能为空')
            return

        overrides = _build_overrides(body)
        system = prompt_loader.load('strategy_coder')
        composed = (
            f"以下是用户当前的策略代码（保持整体结构，按需求局部修改）：\n\n"
            f"{original_code}\n\n"
            f"用户的修改需求：{user_prompt}"
        )
        try:
            raw, resolved_model = yield IOLoop.current().run_in_executor(
                _get_executor(),
                _call_ai_blocking,
                composed, system, 'strategy_refine', 'strategy_coder',
                _client_ip(self), overrides,
            )
        except RateLimitError as exc:
            _write_error(self, 429, f'触发限流: {exc}')
            return
        except (ProviderError, AIError) as exc:
            _write_error(self, -1, f'AI 调用失败: {exc}')
            return
        except Exception as exc:
            logging.exception('RefineStrategyHandler 未知异常')
            _write_error(self, -1, f'内部错误: {exc}')
            return

        code = _strip_code_fence(raw)
        ok, err = _validate_or_msg(code)
        attempts = 0
        if not ok and _MAX_REPAIR_ATTEMPTS > 0:
            repairer_sys = prompt_loader.load('strategy_repairer')
            for _ in range(_MAX_REPAIR_ATTEMPTS):
                attempts += 1
                fix_prompt = _build_repair_prompt(code, err, user_prompt)
                try:
                    raw, resolved_model = yield IOLoop.current().run_in_executor(
                        _get_executor(),
                        _call_ai_blocking,
                        fix_prompt, repairer_sys,
                        'strategy_refine_repair', 'strategy_repairer',
                        _client_ip(self), overrides,
                    )
                except RateLimitError as exc:
                    logging.warning(f'修改自动修复阶段触发限流: {exc}')
                    break
                except (ProviderError, AIError) as exc:
                    logging.warning(f'修改自动修复阶段 AI 调用失败: {exc}')
                    break
                code = _strip_code_fence(raw)
                ok, err = _validate_or_msg(code)
                if ok:
                    break
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({
            'code': 0 if ok else -2,
            'msg': '' if ok else f'代码沙箱校验失败: {err}',
            'data': {'code': code, 'raw': raw, 'validated': ok,
                     'validation_error': err, 'model': resolved_model,
                     'repair_attempts': attempts},
        }, ensure_ascii=False))


# ──────────────────────────────────────────────────────────────────────
# 3) 策略修复 (repair) — 基于 task_recorder 的失败信息
# ──────────────────────────────────────────────────────────────────────
class RepairStrategyHandler(webBase.BaseHandler, ABC):
    """根据上一次失败的 backtest 结果（task_recorder.fetch_last_failure）修复代码。

    请求体: {"strategy_id": 123, "code": "...当前代码（可选，为空则从 DB 取）..."}
    """

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body or b'{}')
        except Exception as exc:
            _write_error(self, -1, f'请求体解析失败: {exc}')
            return

        strategy_id = body.get('strategy_id')
        if not strategy_id:
            _write_error(self, -1, 'strategy_id 不能为空')
            return

        # 获取失败信息
        from instock.core.backtest.task_recorder import fetch_last_failure
        try:
            last = fetch_last_failure(int(strategy_id))
        except Exception as exc:
            _write_error(self, -1, f'读取失败信息异常: {exc}')
            return
        if not last:
            _write_error(self, -1, '未找到该策略的失败回测记录')
            return

        # 取代码（请求体优先；否则从 DB 当前 cn_stock_strategy_code 取）
        original_code = (body.get('code') or '').strip()
        if not original_code:
            try:
                import instock.lib.database as mdb
                rows = mdb.executeSqlFetch(
                    'SELECT code FROM cn_stock_strategy_code WHERE id=%s', (int(strategy_id),))
                if rows and rows[0]:
                    original_code = rows[0][0] if isinstance(rows[0], (list, tuple)) else rows[0].get('code', '')
            except Exception as exc:
                logging.warning(f'读取策略代码失败: {exc}')
        if not original_code:
            _write_error(self, -1, '无法获取策略代码（请在请求体中提供 code 字段）')
            return

        error_text = (last.get('error_message') or '').strip()
        composed = (
            f"以下是当前策略代码：\n\n{original_code}\n\n"
            f"该代码在最近一次回测中失败，错误信息：\n{error_text or '(无)'}\n\n"
            f"请输出修复后的完整代码。"
        )

        overrides = _build_overrides(body)
        system = prompt_loader.load('strategy_repairer')
        try:
            raw, resolved_model = yield IOLoop.current().run_in_executor(
                _get_executor(),
                _call_ai_blocking,
                composed, system, 'strategy_repair', 'strategy_repairer',
                _client_ip(self), overrides,
            )
        except RateLimitError as exc:
            _write_error(self, 429, f'触发限流: {exc}')
            return
        except (ProviderError, AIError) as exc:
            _write_error(self, -1, f'AI 调用失败: {exc}')
            return
        except Exception as exc:
            logging.exception('RepairStrategyHandler 未知异常')
            _write_error(self, -1, f'内部错误: {exc}')
            return

        code = _strip_code_fence(raw)
        ok, err = _validate_or_msg(code)
        attempts = 0
        if not ok and _MAX_REPAIR_ATTEMPTS > 0:
            repairer_sys = prompt_loader.load('strategy_repairer')
            for _ in range(_MAX_REPAIR_ATTEMPTS):
                attempts += 1
                fix_prompt = _build_repair_prompt(code, err, error_text or '原始代码有安全问题')
                try:
                    raw, resolved_model = yield IOLoop.current().run_in_executor(
                        _get_executor(),
                        _call_ai_blocking,
                        fix_prompt, repairer_sys,
                        'strategy_repair_retry', 'strategy_repairer',
                        _client_ip(self), overrides,
                    )
                except RateLimitError as exc:
                    logging.warning(f'修复重试触发限流: {exc}')
                    break
                except (ProviderError, AIError) as exc:
                    logging.warning(f'修复重试 AI 调用失败: {exc}')
                    break
                code = _strip_code_fence(raw)
                ok, err = _validate_or_msg(code)
                if ok:
                    break
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({
            'code': 0 if ok else -2,
            'msg': '' if ok else f'代码沙箱校验失败: {err}',
            'data': {
                'code': code, 'raw': raw,
                'validated': ok, 'validation_error': err,
                'model': resolved_model,
                'repair_attempts': attempts,
                'failure': {
                    'error_message': error_text,
                    'started_at': str(last.get('started_at') or ''),
                    'backtest_id': last.get('id'),
                },
            },
        }, ensure_ascii=False))


# ──────────────────────────────────────────────────────────────────────
# 4) 通用聊天 — 不做 strict 校验（用于"AI 解释"等场景）
# ──────────────────────────────────────────────────────────────────────
class ChatHandler(webBase.BaseHandler, ABC):
    """通用聊天接口。请求体: {"prompt": "...", "system": "...(可选)", "scene": "...(默认 chat)"}。"""

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body or b'{}')
        except Exception as exc:
            _write_error(self, -1, f'请求体解析失败: {exc}')
            return

        user_prompt = (body.get('prompt') or '').strip()
        if not user_prompt:
            _write_error(self, -1, 'prompt 不能为空')
            return

        system = body.get('system') or None
        scene = body.get('scene') or 'chat'
        agent = body.get('agent') or None
        overrides = _build_overrides(body)
        try:
            raw, resolved_model = yield IOLoop.current().run_in_executor(
                _get_executor(),
                _call_ai_blocking,
                user_prompt, system, scene, agent,
                _client_ip(self), overrides,
            )
        except RateLimitError as exc:
            _write_error(self, 429, f'触发限流: {exc}')
            return
        except (ProviderError, AIError) as exc:
            _write_error(self, -1, f'AI 调用失败: {exc}')
            return
        except Exception as exc:
            logging.exception('ChatHandler 未知异常')
            _write_error(self, -1, f'内部错误: {exc}')
            return

        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({'code': 0,
                               'data': {'content': raw, 'model': resolved_model}},
                              ensure_ascii=False))


# ──────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────
def _build_overrides(body: dict) -> dict:
    """从请求体提取 provider/model/api_key 等覆写项。"""
    keys = ('provider', 'api_base', 'api_key', 'model', 'temperature', 'max_tokens', 'timeout')
    out = {}
    for k in keys:
        if k in body and body[k] not in (None, ''):
            out[k] = body[k]
    return out


# ──────────────────────────────────────────────────────────────────────
# 5) 策略生成（流式 SSE）  —— 文档 §4.1 / B1
#    POST /instock/api/ai/strategy/generate/stream
#    Content-Type: text/event-stream
#    事件:  data: {"type":"chunk","text":"..."}\n\n
#           data: {"type":"done","code":"...","validated":true,"validation_error":""}\n\n
#           data: {"type":"error","code":429|-1,"msg":"..."}\n\n
# ──────────────────────────────────────────────────────────────────────
_STREAM_SENTINEL = object()


class GenerateStrategyStreamHandler(webBase.BaseHandler, ABC):
    """流式生成。后台线程消费 stream_chat()，IOLoop 协程从队列取出并 flush。"""

    @gen.coroutine
    def post(self):
        try:
            body = json.loads(self.request.body or b'{}')
        except Exception as exc:
            _write_error(self, -1, f'请求体解析失败: {exc}')
            return

        user_prompt = (body.get('prompt') or '').strip()
        if not user_prompt:
            _write_error(self, -1, 'prompt 不能为空')
            return

        overrides = _build_overrides(body)
        system = prompt_loader.load('strategy_coder')
        user_id = _client_ip(self)
        # 提前解析模型名（与 stream_chat 内部使用同一份合并配置）以回传前端
        from instock.lib.ai.config import load_config as _load_cfg
        resolved_model = _load_cfg(overrides).model

        # SSE 响应头
        self.set_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.set_header('Cache-Control', 'no-cache')
        self.set_header('X-Accel-Buffering', 'no')

        q: 'queue.Queue' = queue.Queue(maxsize=64)

        def _producer():
            try:
                for piece in stream_chat(
                    user_prompt, scene='strategy_gen_stream', system=system,
                    agent='strategy_coder', user_id=user_id, overrides=overrides,
                ):
                    q.put(('chunk', piece))
            except RateLimitError as exc:
                q.put(('error', {'code': 429, 'msg': f'触发限流: {exc}'}))
            except (ProviderError, AIError) as exc:
                q.put(('error', {'code': -1, 'msg': f'AI 调用失败: {exc}'}))
            except Exception as exc:
                logging.exception('GenerateStrategyStreamHandler producer 异常')
                q.put(('error', {'code': -1, 'msg': f'内部错误: {exc}'}))
            finally:
                q.put((_STREAM_SENTINEL, None))

        threading.Thread(target=_producer, name='ai-stream-producer', daemon=True).start()

        pieces = []
        loop = IOLoop.current()
        try:
            while True:
                item = yield loop.run_in_executor(None, q.get)
                kind, payload = item
                if kind is _STREAM_SENTINEL:
                    break
                if kind == 'chunk':
                    pieces.append(payload)
                    self.write('data: ' + json.dumps(
                        {'type': 'chunk', 'text': payload}, ensure_ascii=False) + '\n\n')
                    yield self.flush()
                elif kind == 'error':
                    self.write('data: ' + json.dumps(
                        {'type': 'error', **payload}, ensure_ascii=False) + '\n\n')
                    yield self.flush()
                    return
        except Exception:
            logging.exception('GenerateStrategyStreamHandler 写出异常')
            return

        full = ''.join(pieces)
        code = _strip_code_fence(full)
        ok, err = _validate_or_msg(code)
        attempts = 0
        # M3：流式生成完成后，如沙箱校验失败，串行做最多 N 次修复
        if not ok and _MAX_REPAIR_ATTEMPTS > 0:
            repairer_sys = prompt_loader.load('strategy_repairer')
            for _ in range(_MAX_REPAIR_ATTEMPTS):
                attempts += 1
                fix_prompt = _build_repair_prompt(code, err, user_prompt)
                try:
                    raw, _model = yield IOLoop.current().run_in_executor(
                        _get_executor(),
                        _call_ai_blocking,
                        fix_prompt, repairer_sys,
                        'strategy_gen_stream_repair', 'strategy_repairer',
                        _client_ip(self), overrides,
                    )
                except (RateLimitError, ProviderError, AIError) as exc:
                    logging.warning(f'SSE 修复阶段异常: {exc}')
                    break
                self.write('data: ' + json.dumps(
                    {'type': 'repair', 'attempt': attempts}, ensure_ascii=False) + '\n\n')
                yield self.flush()
                code = _strip_code_fence(raw)
                ok, err = _validate_or_msg(code)
                if ok:
                    break
        self.write('data: ' + json.dumps({
            'type': 'done',
            'code': code,
            'raw': full,
            'validated': ok,
            'validation_error': err,
            'model': resolved_model,
            'repair_attempts': attempts,
        }, ensure_ascii=False) + '\n\n')
        yield self.flush()
