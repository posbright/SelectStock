#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M8 ConversationMemory + ChatHandler 历史接续测试。

不依赖真实 MySQL：
* 默认 inmem 后端测试 base 行为；
* DB 后端测试通过 mock executeSql/executeSqlFetch 验证 SQL；
* ChatHandler 集成测试通过 mock run_chat / get_memory 验证流程。
"""

from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from instock.lib.ai.memory import (
    Conversation, Message,
    estimate_tokens, estimate_messages_tokens, truncate_to_budget,
    get_memory, reset_memory_for_tests,
)
from instock.lib.ai.memory.inmem import InMemoryConversationMemory


class TokenAndTruncateTests(unittest.TestCase):
    def test_estimate_tokens(self):
        self.assertEqual(estimate_tokens(''), 0)
        # 5 字符 / 2.5 = 2 tokens (向下取整后 max 1)
        self.assertEqual(estimate_tokens('hello'), 2)

    def test_truncate_keeps_system_head(self):
        msgs = [
            Message('system', 'sys'),
            Message('user', 'a' * 100),
            Message('assistant', 'b' * 100),
            Message('user', 'tail'),
        ]
        # max_tokens 极小，应只保留 head system + 最后一条
        kept = truncate_to_budget(msgs, max_tokens=5)
        self.assertEqual([m.role for m in kept], ['system', 'user'])
        self.assertEqual(kept[-1].content, 'tail')

    def test_truncate_preserves_when_under_budget(self):
        msgs = [Message('user', 'hi'), Message('assistant', 'ok')]
        self.assertEqual(len(truncate_to_budget(msgs, max_tokens=1000)), 2)

    def test_truncate_empty(self):
        self.assertEqual(truncate_to_budget([], max_tokens=100), [])


class InMemoryMemoryTests(unittest.TestCase):
    def setUp(self):
        self.m = InMemoryConversationMemory()

    def test_create_append_load_roundtrip(self):
        self.m.get_or_create('c1', scene='chat', user_id='u1')
        self.m.append('c1', 'user', 'hello world', scene='chat', user_id='u1')
        self.m.append('c1', 'assistant', 'hi back')
        loaded = self.m.load('c1', max_tokens=4000)
        self.assertEqual(len(loaded), 2)
        conv = self.m.get('c1')
        self.assertEqual(conv.title, 'hello world')
        self.assertGreater(conv.total_tokens, 0)

    def test_list_filter_by_user_and_scene(self):
        self.m.get_or_create('a', scene='chat', user_id='u1')
        self.m.get_or_create('b', scene='chat', user_id='u2')
        self.m.get_or_create('c', scene='strategy_gen', user_id='u1')
        self.assertEqual(
            sorted(c.conversation_id for c in self.m.list(user_id='u1')),
            ['a', 'c'])
        self.assertEqual(
            [c.conversation_id for c in self.m.list(scene='strategy_gen')],
            ['c'])

    def test_delete_and_rename(self):
        self.m.get_or_create('x', scene='chat', user_id='u')
        self.assertTrue(self.m.rename('x', '我的会话'))
        self.assertEqual(self.m.get('x').title, '我的会话')
        self.assertTrue(self.m.delete('x'))
        self.assertIsNone(self.m.get('x'))
        self.assertFalse(self.m.delete('x'))

    def test_lru_eviction(self):
        os.environ['INSTOCK_AI_MEMORY_MAX_CONVS'] = '12'
        try:
            m = InMemoryConversationMemory()
            for i in range(20):
                m.get_or_create(f'c{i}', scene='chat')
            self.assertLessEqual(len(m.list(limit=100)), 12)
        finally:
            del os.environ['INSTOCK_AI_MEMORY_MAX_CONVS']

    def test_load_unknown_returns_empty(self):
        self.assertEqual(self.m.load('nope', max_tokens=100), [])


class FactoryTests(unittest.TestCase):
    def setUp(self):
        reset_memory_for_tests(None)
        self._snap = os.environ.get('INSTOCK_AI_MEMORY_BACKEND')

    def tearDown(self):
        reset_memory_for_tests(None)
        if self._snap is None:
            os.environ.pop('INSTOCK_AI_MEMORY_BACKEND', None)
        else:
            os.environ['INSTOCK_AI_MEMORY_BACKEND'] = self._snap

    def test_factory_inmem(self):
        os.environ['INSTOCK_AI_MEMORY_BACKEND'] = 'inmem'
        mem = get_memory()
        self.assertIsInstance(mem, InMemoryConversationMemory)
        # singleton
        self.assertIs(mem, get_memory())

    def test_factory_db_falls_back_when_unavailable(self):
        os.environ['INSTOCK_AI_MEMORY_BACKEND'] = 'db'
        # 把 DbConversationMemory 类替换成会抛错的 stub，验证回退
        with mock.patch('instock.lib.ai.memory.db.DbConversationMemory',
                        side_effect=RuntimeError('no db')):
            mem = get_memory()
        # 应该回退到 inmem
        self.assertIsInstance(mem, InMemoryConversationMemory)


class DbBackendSqlTests(unittest.TestCase):
    """验证 DbConversationMemory 的关键 SQL 拼装与 messages_json 序列化。"""

    def setUp(self):
        from instock.lib.ai.memory import db as dbmod
        # 强制 _table_ready=True，避免每次 _ensure_table 触发 mdb 调用
        dbmod._table_ready = True

    def test_append_inserts_messages_json(self):
        from instock.lib.ai.memory.db import DbConversationMemory
        captured = []

        def fake_fetch(sql, params):
            # get() 走 SELECT；首次返回空列表 = 不存在
            return []

        def fake_exec(sql, params):
            captured.append((sql, params))

        with mock.patch('instock.lib.ai.memory.db.mdb.executeSqlFetch',
                        side_effect=fake_fetch), \
             mock.patch('instock.lib.ai.memory.db.mdb.executeSql',
                        side_effect=fake_exec):
            mem = DbConversationMemory()
            mem.append('cid-1', 'user', 'hello', scene='chat', user_id='u1')

        # 至少发生过 INSERT (get_or_create) + UPDATE messages_json
        sqls = [s for s, _ in captured]
        self.assertTrue(any('INSERT INTO cn_stock_ai_conversation' in s for s in sqls))
        self.assertTrue(any('UPDATE cn_stock_ai_conversation' in s
                            and 'messages_json=%s' in s for s in sqls))
        # messages_json 参数应是 JSON 数组字符串
        upd = next(p for s, p in captured if 'messages_json=%s' in s)
        decoded = json.loads(upd[0])
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0]['role'], 'user')
        self.assertEqual(decoded[0]['content'], 'hello')

    def test_get_parses_row(self):
        from instock.lib.ai.memory.db import DbConversationMemory
        row = (
            1, 'cid-2', 'chat', 'general_assistant', 'title-x',
            json.dumps([{'role': 'user', 'content': 'hi', 'ts': 1.0}]),
            10, 'u9', None, None,
        )
        with mock.patch('instock.lib.ai.memory.db.mdb.executeSqlFetch',
                        return_value=[row]):
            mem = DbConversationMemory()
            conv = mem.get('cid-2')
        self.assertEqual(conv.title, 'title-x')
        self.assertEqual(len(conv.messages), 1)
        self.assertEqual(conv.messages[0].content, 'hi')
        self.assertEqual(conv.user_id, 'u9')


class HandlerHistoryWiringTests(unittest.TestCase):
    """验证 ChatHandler 在线程池路径上把 history 透传到 _call_ai_blocking。"""

    def test_call_ai_blocking_passes_history_to_run_chat(self):
        from instock.web import aiAssistantHandler as h
        from instock.lib.ai.providers.base import ChatMessage

        captured = {}

        def fake_run_chat(prompt, **kw):
            captured.update(kw)
            captured['prompt'] = prompt
            return 'ok'

        # load_config 也会被调；mock 简化为返回带 .model 属性的 stub
        class _Cfg:
            provider = 'openai_compat'
            model = 'fake-model'

        with mock.patch('instock.web.aiAssistantHandler.run_chat',
                        side_effect=fake_run_chat), \
             mock.patch('instock.lib.ai.config.load_config', return_value=_Cfg()):
            history = [ChatMessage(role='user', content='earlier')]
            content, model = h._call_ai_blocking(
                'now', None, 'chat', None, '1.2.3.4',
                {}, False, history,
            )
        self.assertEqual(content, 'ok')
        self.assertEqual(model, 'fake-model')
        self.assertEqual(captured['history'], history)
        self.assertFalse(captured['rate_limit_loop'])


class RunChatHistoryBuildTests(unittest.TestCase):
    """验证 run_chat 的 history 参数被合并到 messages 列表。"""

    def test_run_chat_prepends_history_between_system_and_prompt(self):
        from instock.lib import ai as ai_mod
        from instock.lib.ai.providers.base import ChatMessage, ChatResult
        os.environ['INSTOCK_AI_RATE_DISABLED'] = '1'
        try:
            captured_msgs = {}

            class _FakeProvider:
                def chat(self, messages, **kw):
                    captured_msgs['msgs'] = messages
                    return ChatResult(content='reply', total_tokens=5)

            with mock.patch.object(ai_mod, 'get_provider',
                                    return_value=_FakeProvider()):
                history = [
                    ChatMessage(role='user', content='Q1'),
                    ChatMessage(role='assistant', content='A1'),
                ]
                out = ai_mod.run_chat(
                    'Q2', system='SYS', history=history,
                    user_id='1.1.1.1', scene='chat',
                )
                self.assertEqual(out, 'reply')
                roles = [m.role for m in captured_msgs['msgs']]
                self.assertEqual(roles, ['system', 'user', 'assistant', 'user'])
                self.assertEqual(captured_msgs['msgs'][0].content, 'SYS')
                self.assertEqual(captured_msgs['msgs'][-1].content, 'Q2')
        finally:
            del os.environ['INSTOCK_AI_RATE_DISABLED']


if __name__ == '__main__':
    unittest.main()
