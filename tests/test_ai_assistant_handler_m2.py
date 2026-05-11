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
                        return_value=_VALID_CODE):
            resp = self.fetch('/instock/api/ai/strategy/generate', method='POST',
                              body=json.dumps({'prompt': '生成一个简单策略'}))
        self.assertEqual(resp.code, 200)
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0, body)
        self.assertTrue(body['data']['validated'])
        self.assertIn('def initialize', body['data']['code'])

    def test_generate_strips_code_fence(self):
        fenced = f"```python\n{_VALID_CODE}```"
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        return_value=fenced):
            resp = self.fetch('/instock/api/ai/strategy/generate', method='POST',
                              body=json.dumps({'prompt': 'x'}))
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0, body)
        self.assertNotIn('```', body['data']['code'])

    def test_generate_unsafe_code_fails_validation(self):
        unsafe = "import os\n" + _VALID_CODE
        with mock.patch('instock.web.aiAssistantHandler._call_ai_blocking',
                        return_value=unsafe):
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
                        return_value=_VALID_CODE) as m:
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
                        return_value=_VALID_CODE) as m:
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
                        return_value='hello world'):
            resp = self.fetch('/instock/api/ai/chat', method='POST',
                              body=json.dumps({'prompt': 'hi'}))
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0)
        self.assertEqual(body['data']['content'], 'hello world')


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


if __name__ == '__main__':
    unittest.main()
