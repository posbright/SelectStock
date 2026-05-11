#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M1 AI 基础层单元测试：config / provider / run_chat（mock requests）。"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instock.lib.ai import (
    AIConfig, AIError, ProviderError, RateLimitError,
    ChatMessage, get_provider, run_chat, load_config,
)
from instock.lib.ai.providers.openai_compat import OpenAICompatProvider


class TestConfig(unittest.TestCase):
    def test_load_config_defaults(self):
        with patch('instock.lib.ai.config._load_from_db', return_value={}), \
             patch('instock.lib.ai.config._load_from_env', return_value={}):
            cfg = load_config()
        self.assertEqual(cfg.provider, 'openai_compat')
        self.assertEqual(cfg.model, 'gpt-4o-mini')
        self.assertEqual(cfg.temperature, 0.3)

    def test_overrides_take_precedence(self):
        with patch('instock.lib.ai.config._load_from_db',
                   return_value={'model': 'db-model', 'api_key': 'db-key'}), \
             patch('instock.lib.ai.config._load_from_env',
                   return_value={'model': 'env-model'}):
            cfg = load_config({'model': 'override-model'})
        self.assertEqual(cfg.model, 'override-model')
        self.assertEqual(cfg.api_key, 'db-key')

    def test_db_over_env(self):
        with patch('instock.lib.ai.config._load_from_db', return_value={'model': 'db'}), \
             patch('instock.lib.ai.config._load_from_env', return_value={'model': 'env'}):
            cfg = load_config()
        self.assertEqual(cfg.model, 'db')


class TestProviderRegistry(unittest.TestCase):
    def test_get_provider_default(self):
        cfg = AIConfig(provider='openai_compat', api_key='x')
        self.assertIsInstance(get_provider(cfg), OpenAICompatProvider)

    def test_unknown_provider_raises(self):
        cfg = AIConfig(provider='nonexistent', api_key='x')
        with self.assertRaises(AIError):
            get_provider(cfg)


def _mock_response(status=200, json_body=None, text='ok'):
    m = MagicMock()
    m.status_code = status
    m.text = text
    m.json.return_value = json_body or {}
    return m


class TestOpenAICompatProvider(unittest.TestCase):
    def setUp(self):
        self.cfg = AIConfig(api_key='sk-test', model='test-model')
        self.provider = OpenAICompatProvider(self.cfg)

    def test_chat_success(self):
        body = {
            'choices': [{'message': {'content': 'hello world'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 7, 'total_tokens': 12},
        }
        with patch('instock.lib.ai.providers.openai_compat.requests.post',
                   return_value=_mock_response(200, body)) as mock_post:
            result = self.provider.chat([ChatMessage(role='user', content='hi')])
        self.assertEqual(result.content, 'hello world')
        self.assertEqual(result.total_tokens, 12)
        self.assertEqual(result.finish_reason, 'stop')
        # Verify URL composed correctly
        call_args = mock_post.call_args
        self.assertTrue(call_args[0][0].endswith('/chat/completions'))
        sent_payload = call_args[1]['json']
        self.assertEqual(sent_payload['model'], 'test-model')
        self.assertEqual(sent_payload['messages'][0]['role'], 'user')

    def test_rate_limit(self):
        with patch('instock.lib.ai.providers.openai_compat.requests.post',
                   return_value=_mock_response(429, {}, 'rate limited')):
            with self.assertRaises(RateLimitError):
                self.provider.chat([ChatMessage(role='user', content='hi')])

    def test_http_error(self):
        with patch('instock.lib.ai.providers.openai_compat.requests.post',
                   return_value=_mock_response(500, {}, 'server error')):
            with self.assertRaises(ProviderError) as ctx:
                self.provider.chat([ChatMessage(role='user', content='hi')])
        self.assertEqual(ctx.exception.status_code, 500)

    def test_malformed_response(self):
        with patch('instock.lib.ai.providers.openai_compat.requests.post',
                   return_value=_mock_response(200, {'no': 'choices'})):
            with self.assertRaises(ProviderError):
                self.provider.chat([ChatMessage(role='user', content='hi')])


class TestRunChat(unittest.TestCase):
    def test_run_chat_records_audit(self):
        body = {
            'choices': [{'message': {'content': 'pong'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
        }
        with patch('instock.lib.ai.config._load_from_db', return_value={'api_key': 'sk-x'}), \
             patch('instock.lib.ai.config._load_from_env', return_value={}), \
             patch('instock.lib.ai.providers.openai_compat.requests.post',
                   return_value=_mock_response(200, body)), \
             patch('instock.lib.ai.audit.record_call') as mock_audit:
            text = run_chat('ping', scene='unit_test')
        self.assertEqual(text, 'pong')
        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args.kwargs
        self.assertEqual(kwargs['scene'], 'unit_test')
        self.assertTrue(kwargs['ok'])
        self.assertEqual(kwargs['total_tokens'], 2)
        self.assertEqual(kwargs['response'], 'pong')

    def test_run_chat_audits_on_failure(self):
        with patch('instock.lib.ai.config._load_from_db', return_value={'api_key': 'sk-x'}), \
             patch('instock.lib.ai.config._load_from_env', return_value={}), \
             patch('instock.lib.ai.providers.openai_compat.requests.post',
                   return_value=_mock_response(429, {}, 'rl')), \
             patch('instock.lib.ai.audit.record_call') as mock_audit:
            with self.assertRaises(RateLimitError):
                run_chat('ping', scene='unit_test')
        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args.kwargs
        self.assertFalse(kwargs['ok'])
        self.assertIn('429', kwargs['error'])


if __name__ == '__main__':
    unittest.main()
