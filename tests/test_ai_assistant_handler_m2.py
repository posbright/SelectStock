#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M2 aiAssistantHandler 集成测试。"""

import json
import sys
import os
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

import instock.web.aiAssistantHandler as ai_h


def _make_app() -> Application:
    return Application([
        (r"/instock/api/ai/strategy/generate", ai_h.GenerateStrategyHandler),
        (r"/instock/api/ai/strategy/refine", ai_h.RefineStrategyHandler),
        (r"/instock/api/ai/strategy/repair", ai_h.RepairStrategyHandler),
        (r"/instock/api/ai/chat", ai_h.ChatHandler),
    ])


_VALID_CODE = '''def initialize(context):
    context.security = '000001'

def handle_data(context, data):
    pass
'''


class GenerateHandlerTests(AsyncHTTPTestCase):
    def get_app(self):
        return _make_app()

    def test_empty_prompt_returns_error(self):
        resp = self.fetch('/instock/api/ai/strategy/generate', method='POST',
                          body=json.dumps({'prompt': ''}))
        self.assertEqual(resp.code, 200)
        body = json.loads(resp.body)
        self.assertEqual(body['code'], -1)
        self.assertIn('prompt', body['msg'])

    def test_generate_success(self):
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        return_value=(_VALID_CODE, 'gpt-4o-mini')):
            resp = self.fetch('/instock/api/ai/strategy/generate', method='POST',
                              body=json.dumps({'prompt': '生成一个简单策略'}))
        self.assertEqual(resp.code, 200)
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0, body)
        self.assertTrue(body['data']['validated'])
        self.assertIn('def initialize', body['data']['code'])
        self.assertEqual(body['data']['model'], 'gpt-4o-mini')

    def test_generate_strips_code_fence(self):
        fenced = f"```python\n{_VALID_CODE}```"
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        return_value=(fenced, 'm1')):
            resp = self.fetch('/instock/api/ai/strategy/generate', method='POST',
                              body=json.dumps({'prompt': 'x'}))
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0, body)
        self.assertNotIn('```', body['data']['code'])

    def test_generate_unsafe_code_fails_validation(self):
        unsafe = "import os\n" + _VALID_CODE
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        return_value=(unsafe, 'm1')):
            resp = self.fetch('/instock/api/ai/strategy/generate', method='POST',
                              body=json.dumps({'prompt': 'x'}))
        body = json.loads(resp.body)
        self.assertEqual(body['code'], -2)
        self.assertFalse(body['data']['validated'])

    def test_generate_rate_limit(self):
        from instock.lib.ai import RateLimitError
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        side_effect=RateLimitError('429')):
            resp = self.fetch('/instock/api/ai/strategy/generate', method='POST',
                              body=json.dumps({'prompt': 'x'}))
        self.assertEqual(resp.code, 429)
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 429)


class RefineHandlerTests(AsyncHTTPTestCase):
    def get_app(self):
        return _make_app()

    def test_refine_requires_both_fields(self):
        resp = self.fetch('/instock/api/ai/strategy/refine', method='POST',
                          body=json.dumps({'prompt': 'x'}))
        body = json.loads(resp.body)
        self.assertEqual(body['code'], -1)

    def test_refine_success(self):
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        return_value=(_VALID_CODE, 'm1')) as m:
            resp = self.fetch('/instock/api/ai/strategy/refine', method='POST',
                              body=json.dumps({
                                  'prompt': '改成持仓 10 只',
                                  'code': _VALID_CODE,
                              }))
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0, body)
        # composed prompt should embed original code
        composed_arg = m.call_args.args[0]
        self.assertIn('改成持仓 10 只', composed_arg)
        self.assertIn("context.security = '000001'", composed_arg)


class RepairHandlerTests(AsyncHTTPTestCase):
    def get_app(self):
        return _make_app()

    def test_repair_requires_strategy_id(self):
        resp = self.fetch('/instock/api/ai/strategy/repair', method='POST',
                          body=json.dumps({}))
        self.assertEqual(json.loads(resp.body)['code'], -1)

    def test_repair_no_failure_record(self):
        with mock.patch('instock.core.backtest.task_recorder.fetch_last_failure',
                        return_value=None):
            resp = self.fetch('/instock/api/ai/strategy/repair', method='POST',
                              body=json.dumps({'strategy_id': 999, 'code': _VALID_CODE}))
        body = json.loads(resp.body)
        self.assertEqual(body['code'], -1)
        self.assertIn('未找到', body['msg'])

    def test_repair_success(self):
        last = {'id': 7, 'started_at': '2026-05-11', 'completed_at': '2026-05-11',
                'error_message': 'ZeroDivisionError'}
        with mock.patch('instock.core.backtest.task_recorder.fetch_last_failure',
                        return_value=last), \
             mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        return_value=(_VALID_CODE, 'm1')) as m:
            resp = self.fetch('/instock/api/ai/strategy/repair', method='POST',
                              body=json.dumps({'strategy_id': 7, 'code': _VALID_CODE}))
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0, body)
        self.assertEqual(body['data']['failure']['error_message'], 'ZeroDivisionError')
        composed = m.call_args.args[0]
        self.assertIn('ZeroDivisionError', composed)


class ChatHandlerTests(AsyncHTTPTestCase):
    def get_app(self):
        return _make_app()

    def test_chat_returns_raw_content(self):
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        return_value=('hello world', 'm1')):
            resp = self.fetch('/instock/api/ai/chat', method='POST',
                              body=json.dumps({'prompt': 'hi'}))
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0)
        self.assertEqual(body['data']['content'], 'hello world')

    def test_chat_rate_limit_status_429(self):
        from instock.lib.ai import RateLimitError
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        side_effect=RateLimitError('429')):
            resp = self.fetch('/instock/api/ai/chat', method='POST',
                              body=json.dumps({'prompt': 'hi'}))
        self.assertEqual(resp.code, 429)
        self.assertEqual(json.loads(resp.body)['code'], 429)


class StripFenceTests(unittest.TestCase):
    def test_python_fence(self):
        self.assertEqual(
            ai_h._strip_code_fence('```python\nprint(1)\n```'),
            'print(1)',
        )

    def test_no_fence(self):
        self.assertEqual(ai_h._strip_code_fence('x=1\n'), 'x=1')

    def test_empty(self):
        self.assertEqual(ai_h._strip_code_fence(''), '')


# ─── B1：SSE 流式生成 ──────────────────────────────────────────
def _sse_app() -> Application:
    return Application([
        (r"/instock/api/ai/strategy/generate/stream",
         ai_h.GenerateStrategyStreamHandler),
    ])


def _parse_sse(body: bytes):
    """把 SSE 响应体按 data: 拆为事件 dict 列表。"""
    out = []
    for chunk in body.split(b'\n\n'):
        s = chunk.strip()
        if not s.startswith(b'data:'):
            continue
        try:
            out.append(json.loads(s[5:].strip()))
        except Exception:
            continue
    return out


class GenerateStreamHandlerTests(AsyncHTTPTestCase):
    def get_app(self):
        return _sse_app()

    def test_stream_empty_prompt(self):
        resp = self.fetch('/instock/api/ai/strategy/generate/stream',
                          method='POST', body=json.dumps({'prompt': ''}))
        # _write_error 路径走普通 JSON
        body = json.loads(resp.body)
        self.assertEqual(body['code'], -1)

    def test_stream_yields_chunks_then_done(self):
        chunks = ['def initi', 'alize(context):\n    ', "context.security = '000001'\n",
                  '\ndef handle_data(context, data):\n    pass\n']

        def _fake(*args, **kwargs):
            yield from chunks

        with mock.patch('instock.web.aiAssistantHandler.stream_chat',
                        side_effect=_fake):
            resp = self.fetch('/instock/api/ai/strategy/generate/stream',
                              method='POST', body=json.dumps({'prompt': 'x'}))
        self.assertEqual(resp.code, 200)
        events = _parse_sse(resp.body)
        types = [e.get('type') for e in events]
        self.assertEqual(types.count('chunk'), len(chunks))
        self.assertEqual(types[-1], 'done')
        done = events[-1]
        self.assertTrue(done['validated'], done)
        self.assertIn('def initialize', done['code'])
        self.assertIn('model', done)

    def test_stream_rate_limit_emits_error(self):
        from instock.lib.ai import RateLimitError

        def _boom(*args, **kwargs):
            raise RateLimitError('429')
            yield  # pragma: no cover

        with mock.patch('instock.web.aiAssistantHandler.stream_chat',
                        side_effect=_boom):
            resp = self.fetch('/instock/api/ai/strategy/generate/stream',
                              method='POST', body=json.dumps({'prompt': 'x'}))
        events = _parse_sse(resp.body)
        self.assertTrue(any(e.get('type') == 'error' and e.get('code') == 429
                            for e in events), events)


# ─── B3：refine / repair 也应返回 HTTP 429 ──────────────────────
class RateLimitStatusTests(AsyncHTTPTestCase):
    def get_app(self):
        return _make_app()

    def test_refine_rate_limit_status_429(self):
        from instock.lib.ai import RateLimitError
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        side_effect=RateLimitError('429')):
            resp = self.fetch('/instock/api/ai/strategy/refine', method='POST',
                              body=json.dumps({'prompt': 'x', 'code': _VALID_CODE}))
        self.assertEqual(resp.code, 429)

    def test_repair_rate_limit_status_429(self):
        from instock.lib.ai import RateLimitError
        last = {'id': 1, 'started_at': '2026-05-11', 'error_message': 'boom'}
        with mock.patch('instock.core.backtest.task_recorder.fetch_last_failure',
                        return_value=last), \
             mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        side_effect=RateLimitError('429')):
            resp = self.fetch('/instock/api/ai/strategy/repair', method='POST',
                              body=json.dumps({'strategy_id': 1, 'code': _VALID_CODE}))
        self.assertEqual(resp.code, 429)


# ─── M3：strict 校验失败自动重试 ≤3 轮 ──────────────────────────
_UNSAFE_CODE = "import os\n" + _VALID_CODE


class M3RetryTests(AsyncHTTPTestCase):
    def get_app(self):
        return _make_app()

    def test_generate_unsafe_then_repaired_by_retry(self):
        """首轮返回 import os（不安全），重试第 1 轮返回安全代码 → 验收通过。"""
        seq = [(_UNSAFE_CODE, 'm1'), (_VALID_CODE, 'm1')]
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        side_effect=seq):
            resp = self.fetch('/instock/api/ai/strategy/generate', method='POST',
                              body=json.dumps({'prompt': 'x'}))
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0, body)
        self.assertTrue(body['data']['validated'])
        self.assertEqual(body['data']['repair_attempts'], 1)
        self.assertNotIn('import os', body['data']['code'])

    def test_generate_all_attempts_fail_returns_minus2(self):
        """3 次重试都返回不安全代码 → 应返回 code=-2 + repair_attempts=3。"""
        bad = [(_UNSAFE_CODE, 'm1')] * 4  # 1 次首轮 + 3 次重试
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        side_effect=bad):
            resp = self.fetch('/instock/api/ai/strategy/generate', method='POST',
                              body=json.dumps({'prompt': 'x'}))
        body = json.loads(resp.body)
        self.assertEqual(body['code'], -2)
        self.assertFalse(body['data']['validated'])
        self.assertEqual(body['data']['repair_attempts'], 3)

    def test_refine_repair_attempts_succeed_on_2nd(self):
        """refine 首轮失败、第 2 轮成功 → repair_attempts=2。"""
        seq = [(_UNSAFE_CODE, 'm1'), (_UNSAFE_CODE, 'm1'), (_VALID_CODE, 'm1')]
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        side_effect=seq):
            resp = self.fetch('/instock/api/ai/strategy/refine', method='POST',
                              body=json.dumps({'prompt': 'x', 'code': _VALID_CODE}))
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0, body)
        self.assertEqual(body['data']['repair_attempts'], 2)


if __name__ == '__main__':
    unittest.main()
