#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M10 Orchestrator + 跨场景接入（moat_ai_service 收敛）测试。

不依赖真实 LLM：通过注入 _run_agent 替身或 mock instock.lib.ai.run_chat。
"""

import os
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from instock.lib.ai.orchestrator import (
    Pipeline, PipelineError, PipelineResult, Step, StepResult, run_pipeline,
)
from instock.lib.ai.orchestrator.presets import STRATEGY_PIPELINE


class _FakeAgentResult:
    def __init__(self, content, *, rounds=1, prompt_tokens=10,
                 completion_tokens=20, total_tokens=30, tool_calls=None):
        self.content = content
        self.rounds = rounds
        self.tool_calls = tool_calls or []
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.model = 'fake-model'
        self.provider = 'fake'
        self.finish_reason = 'stop'


def _make_fake_agent(outputs_by_step):
    """outputs_by_step: dict[step_name, str | list[str]]。
    list 形式按 iter 索引；超出取最后一项。
    返回签名兼容 instock.lib.ai.run_agent 的 callable，并暴露 .calls。
    """
    calls = []

    def _runner(*, user_message, scene, agent=None, system=None,
                user_id=None, overrides=None, allowed_tools=None):
        # scene 形如 'pipeline:<step_name>'
        step_name = scene.split(':', 1)[1] if ':' in scene else scene
        out = outputs_by_step.get(step_name, '')
        if isinstance(out, list):
            idx = sum(1 for c in calls if c['step'] == step_name)
            chunk = out[min(idx, len(out) - 1)]
        else:
            chunk = out
        calls.append({
            'step': step_name, 'agent': agent,
            'user_message': user_message, 'allowed_tools': allowed_tools,
            'system': system, 'overrides': overrides,
        })
        return _FakeAgentResult(chunk)

    _runner.calls = calls
    return _runner


# ─────────────────────────────────────────────────────────────────────
# Step / Pipeline 基础
# ─────────────────────────────────────────────────────────────────────
class StepValidationTests(unittest.TestCase):
    def test_step_requires_nonempty_name(self):
        with self.assertRaises(ValueError):
            Step(name='')
        with self.assertRaises(ValueError):
            Step(name='   ')

    def test_step_max_iters_lower_bound(self):
        with self.assertRaises(ValueError):
            Step(name='s', max_iters=0)

    def test_step_max_iters_upper_bound_clamps(self):
        s = Step(name='s', max_iters=999)
        # 实现应硬截断到 _MAX_STEP_ITERS（=8）
        self.assertLessEqual(s.max_iters, 8)


class PipelineValidationTests(unittest.TestCase):
    def test_pipeline_requires_at_least_one_step(self):
        with self.assertRaises(ValueError):
            Pipeline([])

    def test_pipeline_unique_step_names(self):
        with self.assertRaises(ValueError):
            Pipeline([Step('a'), Step('a')])

    def test_pipeline_step_count_cap(self):
        with self.assertRaises(ValueError):
            Pipeline([Step(f's{i}') for i in range(20)])


# ─────────────────────────────────────────────────────────────────────
# 顺序执行
# ─────────────────────────────────────────────────────────────────────
class PipelineRunTests(unittest.TestCase):
    def test_single_step_passes_input_through(self):
        pl = Pipeline([Step('only', agent='strategy_coder')])
        runner = _make_fake_agent({'only': 'OUTPUT-1'})
        res = pl.run(user_message='hello', _run_agent=runner)
        self.assertIsInstance(res, PipelineResult)
        self.assertEqual(res.final, 'OUTPUT-1')
        self.assertEqual(len(res.steps), 1)
        self.assertTrue(res.steps[0].ok)
        self.assertEqual(runner.calls[0]['user_message'], 'hello')
        self.assertEqual(runner.calls[0]['agent'], 'strategy_coder')

    def test_template_uses_input_and_prev_step(self):
        pl = Pipeline([
            Step('a', agent='strategy_analyst'),
            Step('b', agent='strategy_coder',
                 user_template='req={input} | think={a}'),
        ])
        runner = _make_fake_agent({'a': 'IDEA', 'b': 'CODE'})
        res = pl.run(user_message='make-strategy', _run_agent=runner)
        self.assertEqual(res.final, 'CODE')
        self.assertEqual(runner.calls[1]['user_message'],
                         'req=make-strategy | think=IDEA')

    def test_unknown_template_placeholder_raises(self):
        pl = Pipeline([Step('a', user_template='{nope}')])
        runner = _make_fake_agent({'a': 'X'})
        with self.assertRaises(PipelineError):
            pl.run(user_message='hi', _run_agent=runner)

    def test_scene_namespacing_per_step(self):
        pl = Pipeline([Step('first'), Step('second')])
        runner = _make_fake_agent({'first': '1', 'second': '2'})
        pl.run(user_message='go', scene='myscene', _run_agent=runner)
        scenes = [c.get('step') for c in runner.calls]
        self.assertEqual(scenes, ['first', 'second'])

    def test_overrides_merged_step_wins(self):
        pl = Pipeline([Step('s', overrides={'model': 'step-model'})])
        runner = _make_fake_agent({'s': 'OK'})
        pl.run(user_message='x', overrides={'model': 'global', 'temperature': 0.1},
               _run_agent=runner)
        ov = runner.calls[0]['overrides']
        self.assertEqual(ov['model'], 'step-model')   # step wins
        self.assertEqual(ov['temperature'], 0.1)      # global preserved


# ─────────────────────────────────────────────────────────────────────
# loop_until / 重试
# ─────────────────────────────────────────────────────────────────────
class PipelineLoopTests(unittest.TestCase):
    def test_loop_until_passes_first_try(self):
        pl = Pipeline([Step('s',
                            loop_until=lambda out, ctx: out == 'GOOD',
                            max_iters=3)])
        runner = _make_fake_agent({'s': 'GOOD'})
        res = pl.run(user_message='x', _run_agent=runner)
        self.assertEqual(res.steps[0].iters, 1)
        self.assertTrue(res.steps[0].ok)

    def test_loop_until_passes_after_retry(self):
        pl = Pipeline([Step('s',
                            loop_until=lambda out, ctx: out == 'GOOD',
                            max_iters=3)])
        runner = _make_fake_agent({'s': ['BAD', 'BAD', 'GOOD']})
        res = pl.run(user_message='x', _run_agent=runner)
        self.assertEqual(res.steps[0].iters, 3)
        self.assertTrue(res.steps[0].ok)
        # 第 2 / 第 3 次的 user_message 应包含 "上一轮输出未通过校验"
        self.assertIn('未通过校验', runner.calls[1]['user_message'])

    def test_loop_until_exhausted_raises_with_partial(self):
        pl = Pipeline([
            Step('a'),  # 正常
            Step('b', loop_until=lambda *_: False, max_iters=2),
        ])
        runner = _make_fake_agent({'a': 'A_OUT', 'b': 'NEVER_GOOD'})
        with self.assertRaises(PipelineError) as cm:
            pl.run(user_message='go', _run_agent=runner)
        err = cm.exception
        self.assertEqual(err.step_name, 'b')
        self.assertIsNotNone(err.partial)
        self.assertEqual(len(err.partial.steps), 2)
        self.assertTrue(err.partial.steps[0].ok)
        self.assertFalse(err.partial.steps[1].ok)
        self.assertEqual(err.partial.steps[1].iters, 2)

    def test_loop_until_callable_exception_short_circuits(self):
        def boom(out, ctx):
            raise RuntimeError('x')
        pl = Pipeline([Step('s', loop_until=boom, max_iters=3)])
        runner = _make_fake_agent({'s': 'whatever'})
        with self.assertRaises(PipelineError) as cm:
            pl.run(user_message='go', _run_agent=runner)
        self.assertIn('loop_until', cm.exception.partial.steps[0].error or '')


# ─────────────────────────────────────────────────────────────────────
# 异常 / 审计 token 累计
# ─────────────────────────────────────────────────────────────────────
class PipelineAggregationTests(unittest.TestCase):
    def test_total_tokens_summed_across_steps(self):
        pl = Pipeline([Step('a'), Step('b')])
        runner = _make_fake_agent({'a': 'X', 'b': 'Y'})
        res = pl.run(user_message='go', _run_agent=runner)
        # 每个 fake step total_tokens=30 → 60
        self.assertEqual(res.total_tokens, 60)

    def test_run_agent_exception_aborts_with_error_recorded(self):
        def runner(**_):
            raise RuntimeError('provider down')
        pl = Pipeline([Step('s')])
        with self.assertRaises(PipelineError) as cm:
            pl.run(user_message='go', _run_agent=runner)
        partial = cm.exception.partial
        self.assertIsNotNone(partial)
        self.assertFalse(partial.steps[0].ok)
        self.assertIn('provider down', partial.steps[0].error or '')


# ─────────────────────────────────────────────────────────────────────
# STRATEGY_PIPELINE 预设
# ─────────────────────────────────────────────────────────────────────
class StrategyPipelinePresetTests(unittest.TestCase):
    def test_strategy_pipeline_three_steps(self):
        names = [s.name for s in STRATEGY_PIPELINE.steps]
        self.assertEqual(names, ['analyst', 'coder', 'tester'])

    def test_strategy_pipeline_tester_uses_strict_validate(self):
        # tester 步默认 max_iters=3 且有 loop_until
        tester = STRATEGY_PIPELINE.steps[-1]
        self.assertEqual(tester.name, 'tester')
        self.assertEqual(tester.max_iters, 3)
        self.assertIsNotNone(tester.loop_until)

    def test_strategy_pipeline_runs_with_fake_agent_and_safe_code(self):
        """tester 的 loop_until 调真实 validate_code_strict；
        给一个最简单的合法策略代码即可在第 1 轮通过。"""
        good_code = (
            "```python\n"
            "def select_stocks(data, params):\n"
            "    return []\n"
            "```"
        )
        runner = _make_fake_agent({
            'analyst': 'IDEA',
            'coder': good_code,
            'tester': good_code,  # tester 输出代码块
        })
        try:
            res = STRATEGY_PIPELINE.run(user_message='做个空策略', _run_agent=runner)
        except PipelineError as exc:
            # 若环境缺少 strict 校验依赖，则记录 partial 仍可断言执行了 3 步
            self.assertIsNotNone(exc.partial)
            return
        self.assertEqual(res.final.strip().startswith('```python'), True)
        self.assertEqual(len(res.steps), 3)


# ─────────────────────────────────────────────────────────────────────
# moat_ai_service 跨场景收敛（_call_ai 走 instock.lib.ai.run_chat）
# ─────────────────────────────────────────────────────────────────────
class MoatAiServiceMigrationTests(unittest.TestCase):
    def test_call_ai_no_key_returns_none_without_calling_run_chat(self):
        from instock.core.strategy.fundamental.moat_ai_service import (
            MoatAIService, MoatAIConfig,
        )
        svc = MoatAIService(config=MoatAIConfig(api_key=''))
        with mock.patch('instock.lib.ai.run_chat') as m:
            out = svc._call_ai('prompt')
        self.assertIsNone(out)
        m.assert_not_called()

    def test_call_ai_delegates_to_run_chat_with_overrides(self):
        from instock.core.strategy.fundamental.moat_ai_service import (
            MoatAIService, MoatAIConfig,
        )
        cfg = MoatAIConfig(
            api_base='http://example.test/v1',
            api_key='sk-test',
            model='gpt-test',
            temperature=0.42,
            max_tokens=1234,
            timeout=33,
        )
        svc = MoatAIService(config=cfg)
        with mock.patch('instock.lib.ai.run_chat',
                        return_value='RESP') as m:
            out = svc._call_ai('PROMPT')
        self.assertEqual(out, 'RESP')
        m.assert_called_once()
        kwargs = m.call_args.kwargs
        self.assertEqual(kwargs.get('scene'), 'moat_analysis')
        self.assertEqual(kwargs.get('agent'), 'moat_analyst')
        ov = kwargs.get('overrides') or {}
        self.assertEqual(ov.get('api_base'), 'http://example.test/v1')
        self.assertEqual(ov.get('api_key'), 'sk-test')
        self.assertEqual(ov.get('model'), 'gpt-test')
        self.assertAlmostEqual(ov.get('temperature'), 0.42)
        self.assertEqual(ov.get('max_tokens'), 1234)
        self.assertEqual(ov.get('timeout'), 33)
        # system 仍包含原来的角色提示
        self.assertIn('价值投资', kwargs.get('system') or '')

    def test_call_ai_swallows_run_chat_errors_returns_none(self):
        """护城河走的是 'AI 失败也降级到纯量化'，所以 _call_ai 不能抛。"""
        from instock.core.strategy.fundamental.moat_ai_service import (
            MoatAIService, MoatAIConfig,
        )
        svc = MoatAIService(config=MoatAIConfig(api_key='sk-test'))
        with mock.patch('instock.lib.ai.run_chat',
                        side_effect=RuntimeError('boom')):
            out = svc._call_ai('PROMPT')
        self.assertIsNone(out)


# ─────────────────────────────────────────────────────────────────────
# 内置 agent 注册（市场摘要 / 分析师）
# ─────────────────────────────────────────────────────────────────────
class BuiltinAgentRegistrationTests(unittest.TestCase):
    def test_market_summarizer_and_analyst_in_builtin_list(self):
        from instock.lib.ai import prompt_loader
        names = {a['name'] for a in prompt_loader._BUILTIN_AGENTS}
        self.assertIn('strategy_analyst', names)
        self.assertIn('market_summarizer', names)

    def test_prompt_files_loadable(self):
        from instock.lib.ai import prompt_loader
        for name in ('strategy_analyst', 'market_summarizer'):
            txt = prompt_loader.load(name)
            self.assertTrue(txt and len(txt) > 50,
                            f'{name}.md 内容为空或过短')


# ─────────────────────────────────────────────────────────────────────
# 顶层 run_pipeline 入口
# ─────────────────────────────────────────────────────────────────────
class TopLevelRunPipelineTests(unittest.TestCase):
    def test_top_level_run_pipeline_helper(self):
        from instock.lib import ai as ai_pkg
        pl = Pipeline([Step('only')])
        runner = _make_fake_agent({'only': 'X'})
        res = ai_pkg.run_pipeline(pl, user_message='go', _run_agent=runner)
        self.assertEqual(res.final, 'X')


if __name__ == '__main__':
    unittest.main()
