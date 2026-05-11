#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M5 测试：/ai/config + /ai/agents 路由 + provider/agent 元数据。"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

import instock.web.aiAssistantHandler as ai_h
from instock.lib.ai import config as ai_config
from instock.lib.ai import prompt_loader


def _make_app() -> Application:
    return Application([
        (r"/instock/api/ai/config", ai_h.GetAiConfigHandler),
        (r"/instock/api/ai/agents", ai_h.ListAiAgentsHandler),
    ])


class ProviderProfileTests(unittest.TestCase):
    def setUp(self):
        # 备份并清理相关 env
        self._saved = {k: v for k, v in os.environ.items()
                       if k.startswith('INSTOCK_AI_PROVIDER_')
                       or k == 'INSTOCK_AI_DEFAULT_PROVIDER'}
        for k in list(self._saved.keys()):
            del os.environ[k]

    def tearDown(self):
        for k in list(os.environ.keys()):
            if k.startswith('INSTOCK_AI_PROVIDER_'):
                del os.environ[k]
        for k, v in self._saved.items():
            os.environ[k] = v

    def test_default_profile_always_present(self):
        data = ai_config.list_provider_profiles()
        names = {p['name'] for p in data['profiles']}
        self.assertIn('default', names)
        self.assertIn('default', data)

    def test_namespaced_provider_discovered(self):
        os.environ['INSTOCK_AI_PROVIDER_DEEPSEEK_API_BASE'] = 'https://api.deepseek.com/v1'
        os.environ['INSTOCK_AI_PROVIDER_DEEPSEEK_API_KEY'] = 'sk-test'
        os.environ['INSTOCK_AI_PROVIDER_DEEPSEEK_MODELS'] = 'deepseek-chat,deepseek-coder'
        os.environ['INSTOCK_AI_PROVIDER_DEEPSEEK_DEFAULT_MODEL'] = 'deepseek-chat'
        os.environ['INSTOCK_AI_DEFAULT_PROVIDER'] = 'deepseek'
        data = ai_config.list_provider_profiles()
        ds = next(p for p in data['profiles'] if p['name'] == 'deepseek')
        self.assertEqual(ds['api_base'], 'https://api.deepseek.com/v1')
        self.assertTrue(ds['has_key'])
        self.assertIn('deepseek-chat', ds['models'])
        self.assertIn('deepseek-coder', ds['models'])
        self.assertEqual(ds['default_model'], 'deepseek-chat')
        self.assertEqual(data['default'], 'deepseek')

    def test_api_key_never_returned(self):
        os.environ['INSTOCK_AI_PROVIDER_QWEN_API_KEY'] = 'sk-secret'
        data = ai_config.list_provider_profiles()
        for p in data['profiles']:
            self.assertNotIn('api_key', p)


class PromptLoaderAgentsTests(unittest.TestCase):
    def test_list_agents_contains_builtins(self):
        agents = prompt_loader.list_agents()
        names = {a['name'] for a in agents}
        self.assertIn('strategy_coder', names)
        self.assertIn('strategy_repairer', names)
        for a in agents:
            self.assertTrue(a['is_builtin'])
            self.assertIn('system_prompt', a)


class GetAiConfigHandlerTests(AsyncHTTPTestCase):
    def get_app(self):
        return _make_app()

    def test_get_config_shape(self):
        resp = self.fetch('/instock/api/ai/config')
        self.assertEqual(resp.code, 200)
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0, body)
        data = body['data']
        self.assertIn('profiles', data)
        self.assertIn('agents', data)
        self.assertIn('default', data)
        # api_key / system_prompt 不外露
        for p in data['profiles']:
            self.assertNotIn('api_key', p)
        for a in data['agents']:
            self.assertNotIn('system_prompt', a)


class ListAiAgentsHandlerTests(AsyncHTTPTestCase):
    def get_app(self):
        return _make_app()

    def test_list_default_no_prompt(self):
        resp = self.fetch('/instock/api/ai/agents')
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0)
        for a in body['data']['agents']:
            self.assertNotIn('system_prompt', a)

    def test_list_include_prompt(self):
        resp = self.fetch('/instock/api/ai/agents?include_prompt=1')
        body = json.loads(resp.body)
        self.assertEqual(body['code'], 0)
        agents = body['data']['agents']
        self.assertTrue(all('system_prompt' in a for a in agents))


if __name__ == '__main__':
    unittest.main()
