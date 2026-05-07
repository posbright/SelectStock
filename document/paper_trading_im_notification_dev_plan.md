# 模拟交易即时消息通知与交易决策留痕开发文档

> 日期：2026-04-30
> 范围：模拟交易信号通知、交易理由与决策依据存储、AI 综合评分扩展、钉钉优先接入、回测复用、未来 IM 交易指令扩展
> 状态：设计与开发计划
> 目标目录：`document/`

---

## 1. 背景与目标

当前项目已经具备组合回测、模拟交易、K 线与技术指标展示、模拟买卖点查看等能力。下一步希望在模拟交易出现买点或卖点时，先将交易信息推送到钉钉，并在通知中明确展示买卖动作、成交信息、策略真实触发理由、指标阈值对比、详情链接；后续再扩展企业微信、QQ、微信等渠道，并为 IM 确认交易或下达指令预留扩展。

同时，需要为后期 AI 辅助研判预留能力：当策略筛选出股票或准备买入、卖出前，系统可以汇总该股票的基础信息、常用技术指标、K 线窗口、策略筛选原因、账户与风险上下文，传入可配置的 AI 提示词和模型工具链，由 AI 输出综合评分、建议动作、风险提示和关键依据。该评分第一阶段只作为解释和辅助决策，后续可配置为买入/卖出的可选交易闸门。

本方案重点解决两个问题：

1. **通知可达**：交易信号产生后，稳定、可重试、可去重地发送到目标 IM 渠道。
2. **理由可信**：通知中的交易理由必须来自策略执行时的真实筛选数据和判断过程，而不是前端根据成交记录事后猜测。
3. **AI 可扩展**：AI 评分必须基于策略当时可见的数据包，可配置、可关闭、可追溯，并且不能替代必要的风控和人工确认。
4. **钉钉优先**：第一阶段只实现钉钉 webhook 的生产可用闭环，其他 IM 渠道保留抽象接口和后续计划。

---

## 2. 现状审计

### 2.1 当前模拟交易执行链路

```text
instock/web/web_service.py
  -> instock/paper_trading/scheduler.py
  -> run_all_paper_trading(scheduled=True)
  -> instock/paper_trading/paper_engine.py
  -> run_paper_trading_daily(paper_id, scheduled=True)
  -> 执行用户策略代码
  -> 策略调用 order/order_target/order_value/order_target_percent
  -> paper_engine 收集 pending_orders
  -> 撮合生成 TradeRecord
  -> 写入交易、持仓、净值、执行日志
```

通知的最佳切入点应位于 `run_paper_trading_daily` 生成交易记录并成功提交数据库之后。原因是策略调用下单函数时只是交易意图，最终是否成交、成交价、数量、费用、卖出盈亏等数据只有撮合后才完整；如果数据库提交前发送通知，容易出现“消息已发但交易未落库”的不一致。

### 2.2 当前交易理由能力缺口

当前 `paper_engine.py` 中的下单代理只记录基础意图：

```python
pending_orders.append({'code': code, 'amount': amount, 'value': value})
```

当前 `TradeRecord` 主要包含成交字段：

```text
date
code
name
direction
price
amount
value
commission
tax
slippage_cost
close_profit
return_rate
```

缺少以下关键字段或关联数据：

- 策略下单理由 `reason`。
- 决策明细 `decision_json`。
- 指标快照 `indicator_snapshot`。
- 阈值配置 `thresholds`。
- 策略候选池筛选过程 `selection_snapshot`。
- 下单前后账户状态 `portfolio_snapshot`。
- 通知发送状态 `notify_status`。

因此，如果现在直接做通知，只能发送“发生了买入/卖出”，但无法保证“为什么买入/卖出”的解释真实来自策略运行时。

### 2.3 现有前端解释的边界

`instock/fontWeb/src/views/algo/backtest-detail.vue` 已经有交易原因、指标快照和决策依据展示逻辑，但这些逻辑主要基于交易结果和 K 线指标重新组织展示。它可以作为 UI 复用参考，但不应作为通知理由的权威来源。权威来源应该在后端策略执行时产生并落库。

### 2.4 通知模块现状

当前项目未发现统一的 notification/webhook/message 模块。建议新增独立模块，不要将钉钉、企业微信、QQ 等具体渠道逻辑直接写入 `paper_engine.py`。

---

## 3. 设计原则

### 3.1 真实策略数据优先

通知中的交易理由必须来自策略运行时的真实判断数据。推荐让策略在调用下单函数时显式传入：

```python
order_target_percent(
    code,
    0.5,
    reason='收盘价接近布林下轨后反弹，MA5 上穿 MA20，触发建仓',
    decision={
        'rules': [
            {
                'name': 'BOLL 下轨接近度',
                'threshold': 'close <= boll_lower * 1.02',
                'actual': {'close': 3.74, 'boll_lower': 3.67, 'ratio': 1.0191},
                'passed': True,
                'note': '价格位于下轨 2% 范围内'
            }
        ]
    }
)
```

旧策略不传 `reason/decision` 时，系统提供兜底说明，但兜底说明必须标记为 `generated`，不能伪装成策略真实理由。

### 3.2 通知不阻塞交易主流程

模拟交易执行成功与通知发送成功应解耦。交易落库成功后写入通知 outbox 表；通知 worker 或服务函数发送。即使钉钉、企业微信不可用，也不能导致模拟交易失败。

### 3.3 去重和可追溯

通知必须有幂等键，避免调度重试或手工重跑导致重复发送。推荐幂等键：

```text
paper_id + run_id + trade_id + channel
```

如果历史数据没有 `run_id`，可降级为：

```text
paper_id + trade_date + code + direction + amount + price + channel
```

### 3.4 回测和模拟交易复用

“交易决策留痕”不应只服务模拟交易，也应服务组合回测。推荐抽象为通用概念：

- `trade_signal`：策略发出的交易意图。
- `trade_decision`：意图背后的规则、指标、阈值、实际值。
- `trade_execution`：最终成交结果。
- `notification_event`：对外通知事件。

### 3.5 AI 综合评分作为可选扩展点

AI 研判不应直接散落在策略代码、通知模板或前端页面中。推荐将其抽象为独立的 `ai_decision` 服务，输入是标准化数据包，输出是可审计评分结果。

买入前或卖出前可传入的数据包建议包括：

- 股票基础信息：代码、名称、市场、行业、概念、总市值、流通市值、市盈率、市净率、换手率、涨跌幅、停牌/涨跌停状态。
- 常用指标信息：MA、BOLL、MACD、KDJ、RSI、成交量均线、近期波动率、ATR、量价背离、趋势强度。
- K 线数据：最近 N 个交易日的日 K，必要时包含周 K、月 K；指标必须基于完整历史 K 线计算后截取。
- 策略上下文：策略名称、筛选阶段、通过/未通过规则、排序分数、触发阈值、实际值、策略原始理由。
- 账户与风控上下文：当前现金、持仓、目标仓位、单票仓位、组合回撤、当日交易次数、最大可买金额。
- 市场上下文：基准指数走势、板块涨跌、市场温度、是否重大节假日前后等可选数据。

AI 输出必须结构化保存，至少包括：

- `score`：0-100 综合评分。
- `action`：buy/sell/hold/skip/reduce/watch。
- `confidence`：置信度。
- `reason_summary`：简短理由。
- `evidence`：关键证据列表，需引用输入数据字段。
- `risk_flags`：风险提示列表。
- `threshold_result`：与配置阈值的比较结果。
- `prompt_version`、`model_name`、`input_hash`：用于追溯和复现。

第一阶段建议将 AI 评分作为通知内容和人工复核依据，不改变原策略交易结果。第二阶段可增加配置：当 `enabled_as_gate=1` 时，只有 `score >= buy_threshold` 且 `action in ('buy', 'hold')` 才允许买入；卖出可配置为 `score <= sell_threshold` 或 AI 明确建议 `sell/reduce` 时触发额外提醒。即便启用 AI gate，也必须记录“策略原始信号”和“AI 过滤结果”，避免丢失策略真实表现。

### 3.6 AI 配置必须版本化

AI 相关参数需要可修改，但每次运行必须固化快照，避免后续改了提示词后无法解释历史交易。建议版本化字段包括：

- provider/model/base_url/api_key_ref。
- system prompt、user prompt 模板、输出 JSON schema。
- temperature、max_tokens、timeout、重试次数。
- buy/sell 阈值、是否启用 gate、失败时 fallback 策略。
- 可接入工具列表，如财务摘要、行业数据、新闻摘要、指数状态、已有回测统计。

失败处理原则：AI 超时、返回非 JSON、评分缺失、配置禁用时，默认不阻塞策略交易；如果用户显式开启 `fail_closed`，才允许因 AI 失败拒绝下单，并必须写入拒绝原因。

### 3.7 前端可配置与后端安全边界

通知和 AI 研判需要支持前端界面调整，但不能把所有参数都开放给普通用户。推荐按“可视化配置、敏感引用、运行快照”三层处理。

前端建议可配置：

- 通知开关：是否启用、适用模拟盘、事件类型、只通知买入/卖出/异常/汇总。
- 钉钉配置：webhook 环境变量引用、secret 环境变量引用、接收范围、限流、测试发送。
- 通知模板：摘要字段顺序、详情字段上限、是否展示 AI 评分、是否展示关键原始参考数据。
- AI 开关：是否启用 AI 研判、是否作为 gate、买入/卖出阈值、失败策略、超时时间。
- AI 提示词：system prompt、user prompt 模板、输出 JSON schema、prompt 版本说明。
- AI 数据包范围：K 线窗口长度、是否包含周/月 K、是否包含基本面、是否包含市场/板块上下文、最多展示多少条证据。
- 工具接入开关：财务摘要、行业数据、新闻摘要、指数状态、历史回测统计等。

后端或环境变量中保留，不建议直接在前端明文编辑：

- 钉钉完整 webhook URL、secret 明文。
- AI API key、券商账号、实盘交易 token。
- 生产环境 base_url 白名单、可调用工具白名单。
- 系统级最大单笔交易金额、最大日交易金额、实盘风控硬阈值。

前端保存配置时只保存引用和版本，不保存敏感明文。例如 `api_key_ref=INSTOCK_AI_API_KEY`、`secret_ref=INSTOCK_DINGTALK_SECRET`。每次策略运行时，后端读取当前配置并固化运行快照，历史记录不随前端后续修改而改变。

---

## 4. 总体架构

### 4.1 推荐模块划分

```text
instock/
├── ai_decision/
│   ├── __init__.py
│   ├── config.py
│   ├── context_builder.py
│   ├── prompt_renderer.py
│   ├── service.py
│   ├── schema.py
│   └── providers/
│       ├── __init__.py
│       ├── base.py
│       └── openai_compatible.py
│
├── notification/
│   ├── __init__.py
│   ├── config.py
│   ├── service.py
│   ├── templates.py
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── dingtalk.py
│   │   └── future_wecom.py
│   └── command.py
│
├── core/backtest/
│   ├── strategy_context.py
│   └── trade_decision.py
│
└── paper_trading/
    └── paper_engine.py
```

### 4.2 数据流

```text
策略运行
  -> 计算指标和筛选结果
    -> 构造 AI 决策上下文 ai_context
    -> 可选调用 ai_decision.service 获取 score/action/risk_flags
    -> 根据配置决定 AI 仅留痕、仅通知展示，或作为交易 gate
  -> 调用 order_*(..., reason, decision)
  -> paper_engine 捕获交易意图 trade_signal
    -> 保存 AI 评分与 trade_signal 的关联
  -> 撮合成交，生成 trade_record
  -> 将 signal/decision 与 trade_record 关联落库
  -> 写入 notification_outbox
  -> notification.service 发送消息
  -> 更新发送状态
  -> 用户在 IM 中查看摘要和详情链接
```

### 4.3 推荐通知时机

| 通知时机 | 说明 | 默认 |
|---|---|---|
| `order_intent` | 策略发出下单意图，但未撮合 | 关闭 |
| `trade_executed` | 模拟交易撮合完成并落库 | 开启 |
| `run_summary` | 单个模拟盘每日运行摘要 | 可选 |
| `run_failed` | 策略执行失败或数据异常 | 开启 |
| `risk_alert` | 仓位、回撤、连续亏损等风险提醒 | 可选 |

---

## 5. 数据库表结构设计

### 5.1 交易信号表：`cn_stock_trade_signal`

用于记录策略在运行时发出的交易意图。组合回测和模拟交易都可复用。

```sql
CREATE TABLE IF NOT EXISTS `cn_stock_trade_signal` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `source_type` VARCHAR(32) NOT NULL COMMENT 'backtest/paper/live',
    `source_id` BIGINT NOT NULL COMMENT '回测ID、模拟盘ID或实盘策略ID',
    `run_id` VARCHAR(64) DEFAULT NULL COMMENT '单次运行ID',
    `strategy_id` BIGINT DEFAULT NULL COMMENT '策略ID',
    `strategy_name` VARCHAR(128) DEFAULT NULL COMMENT '策略名称快照',
    `trade_id` BIGINT DEFAULT NULL COMMENT '成交记录ID，撮合后回填',
    `signal_date` DATE NOT NULL COMMENT '信号日期',
    `code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `name` VARCHAR(64) DEFAULT NULL COMMENT '股票名称快照',
    `direction` VARCHAR(16) NOT NULL COMMENT 'buy/sell',
    `order_api` VARCHAR(64) DEFAULT NULL COMMENT 'order/order_target/order_value/order_target_percent',
    `requested_amount` DECIMAL(20,4) DEFAULT NULL COMMENT '策略请求数量变化',
    `requested_value` DECIMAL(20,4) DEFAULT NULL COMMENT '策略请求金额变化',
    `target_amount` DECIMAL(20,4) DEFAULT NULL COMMENT '目标持仓数量',
    `target_percent` DECIMAL(12,6) DEFAULT NULL COMMENT '目标仓位比例',
    `reason` TEXT DEFAULT NULL COMMENT '策略提供的人类可读理由',
    `reason_source` VARCHAR(32) DEFAULT 'strategy' COMMENT 'strategy/generated/manual/imported',
    `ai_score_id` BIGINT DEFAULT NULL COMMENT '关联 cn_stock_trade_ai_score.id',
    `ai_score` DECIMAL(8,4) DEFAULT NULL COMMENT 'AI 综合评分快照，0-100',
    `ai_action` VARCHAR(32) DEFAULT NULL COMMENT 'AI 建议动作 buy/sell/hold/skip/reduce/watch',
    `ai_gate_result` VARCHAR(32) DEFAULT NULL COMMENT 'not_enabled/pass/reject/fallback/error',
    `signal_hash` VARCHAR(64) NOT NULL COMMENT '幂等哈希',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_signal_hash` (`signal_hash`),
    KEY `idx_source_run` (`source_type`, `source_id`, `run_id`),
    KEY `idx_trade_id` (`trade_id`),
    KEY `idx_ai_score_id` (`ai_score_id`),
    KEY `idx_code_date` (`code`, `signal_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略交易信号表';
```

AI 字段只保存摘要和关联 ID，完整输入输出放在 `cn_stock_trade_ai_score`，避免交易信号表过宽。即使 AI gate 拒绝买入，也应保留策略原始信号和 AI 拒绝原因，方便后续评估“策略本来会买，但 AI 过滤后错过/规避了什么”。

### 5.2 交易决策明细表：`cn_stock_trade_decision`

用于记录每条交易信号对应的指标、阈值、实际值和判断结果。

```sql
CREATE TABLE IF NOT EXISTS `cn_stock_trade_decision` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `signal_id` BIGINT NOT NULL COMMENT '关联 cn_stock_trade_signal.id',
    `rule_group` VARCHAR(64) DEFAULT NULL COMMENT 'entry/exit/risk/position',
    `rule_name` VARCHAR(128) NOT NULL COMMENT '规则或指标名称',
    `indicator_key` VARCHAR(64) DEFAULT NULL COMMENT 'close/ma5/ma20/boll_lower/rsi14/macd_hist',
    `threshold_expr` VARCHAR(255) DEFAULT NULL COMMENT '阈值表达式',
    `threshold_value` JSON DEFAULT NULL COMMENT '阈值结构化数据',
    `actual_value` JSON DEFAULT NULL COMMENT '实际指标值结构化数据',
    `passed` TINYINT(1) DEFAULT NULL COMMENT '1通过，0未通过，NULL仅展示',
    `weight` DECIMAL(10,4) DEFAULT NULL COMMENT '规则权重',
    `score` DECIMAL(10,4) DEFAULT NULL COMMENT '规则得分',
    `note` TEXT DEFAULT NULL COMMENT '说明',
    `sort_order` INT DEFAULT 0 COMMENT '展示排序',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_signal_id` (`signal_id`),
    KEY `idx_rule_group` (`signal_id`, `rule_group`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易决策明细表';
```

### 5.3 指标快照表：`cn_stock_trade_indicator_snapshot`

用于存储交易时点完整指标快照，供通知、回测详情、模拟交易详情复用。

```sql
CREATE TABLE IF NOT EXISTS `cn_stock_trade_indicator_snapshot` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `signal_id` BIGINT NOT NULL COMMENT '关联 cn_stock_trade_signal.id',
    `period` VARCHAR(16) DEFAULT 'daily' COMMENT 'daily/weekly/monthly',
    `kline_date` DATE NOT NULL COMMENT '指标对应K线日期',
    `open` DECIMAL(20,6) DEFAULT NULL,
    `high` DECIMAL(20,6) DEFAULT NULL,
    `low` DECIMAL(20,6) DEFAULT NULL,
    `close` DECIMAL(20,6) DEFAULT NULL,
    `volume` DECIMAL(24,4) DEFAULT NULL,
    `amount` DECIMAL(24,4) DEFAULT NULL,
    `ma` JSON DEFAULT NULL COMMENT '均线，如 {"ma5":3.71,"ma20":3.70}',
    `boll` JSON DEFAULT NULL COMMENT 'BOLL 指标',
    `rsi` JSON DEFAULT NULL COMMENT 'RSI 指标',
    `macd` JSON DEFAULT NULL COMMENT 'MACD 指标',
    `kdj` JSON DEFAULT NULL COMMENT 'KDJ 指标',
    `extra` JSON DEFAULT NULL COMMENT '策略自定义指标',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_signal_period` (`signal_id`, `period`),
    KEY `idx_signal_date` (`signal_id`, `kline_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易时点指标快照表';
```

指标值必须基于完整历史 K 线计算后再截取交易时点，避免只用回测区间或模拟区间切片导致指标失真。

### 5.4 候选筛选快照表：`cn_stock_trade_selection_snapshot`

用于记录交易信号产生前的候选池和筛选原因，特别适合选股策略、基本面策略、多因子策略。

```sql
CREATE TABLE IF NOT EXISTS `cn_stock_trade_selection_snapshot` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `signal_id` BIGINT NOT NULL COMMENT '关联 cn_stock_trade_signal.id',
    `stage` VARCHAR(64) NOT NULL COMMENT 'universe/basic_filter/technical_filter/rank/final',
    `candidate_count_before` INT DEFAULT NULL COMMENT '筛选前数量',
    `candidate_count_after` INT DEFAULT NULL COMMENT '筛选后数量',
    `rank_value` DECIMAL(20,6) DEFAULT NULL COMMENT '该股票排序分值',
    `rank_position` INT DEFAULT NULL COMMENT '该股票排序名次',
    `filter_expr` VARCHAR(255) DEFAULT NULL COMMENT '筛选表达式',
    `actual_value` JSON DEFAULT NULL COMMENT '该股票在本阶段的实际值',
    `passed` TINYINT(1) DEFAULT NULL COMMENT '本阶段是否通过',
    `note` TEXT DEFAULT NULL COMMENT '说明',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_signal_stage` (`signal_id`, `stage`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易候选筛选快照表';
```

### 5.5 AI 决策配置表：`cn_stock_ai_decision_config`

用于管理 AI 提示词、模型参数、评分阈值和是否作为交易闸门。配置可以前端修改，但每次运行需要固化 `config_version` 和 prompt 快照。

```sql
CREATE TABLE IF NOT EXISTS `cn_stock_ai_decision_config` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(128) NOT NULL COMMENT '配置名称',
    `enabled` TINYINT(1) DEFAULT 0 COMMENT '是否启用 AI 研判',
    `source_type` VARCHAR(32) DEFAULT 'paper' COMMENT 'paper/backtest/live/all',
    `source_id` BIGINT DEFAULT NULL COMMENT '指定模拟盘、回测或策略，为空表示全部',
    `strategy_id` BIGINT DEFAULT NULL COMMENT '可绑定具体策略',
    `provider` VARCHAR(64) DEFAULT 'openai_compatible' COMMENT 'openai_compatible/deepseek/qwen/local等',
    `model_name` VARCHAR(128) DEFAULT NULL COMMENT '模型名称',
    `base_url` VARCHAR(255) DEFAULT NULL COMMENT '兼容接口地址，可为空',
    `api_key_ref` VARCHAR(255) DEFAULT NULL COMMENT '密钥引用，优先使用环境变量名',
    `system_prompt` MEDIUMTEXT DEFAULT NULL COMMENT '系统提示词',
    `user_prompt_template` MEDIUMTEXT DEFAULT NULL COMMENT '用户提示词模板',
    `output_schema` JSON DEFAULT NULL COMMENT '期望输出 JSON schema',
    `tool_config` JSON DEFAULT NULL COMMENT '允许调用的工具和数据源配置',
    `temperature` DECIMAL(6,4) DEFAULT 0.2000,
    `max_tokens` INT DEFAULT 2048,
    `timeout_seconds` INT DEFAULT 20,
    `retry_count` INT DEFAULT 1,
    `enabled_as_gate` TINYINT(1) DEFAULT 0 COMMENT '是否作为交易闸门',
    `fail_closed` TINYINT(1) DEFAULT 0 COMMENT 'AI失败时是否拒绝交易',
    `buy_threshold` DECIMAL(8,4) DEFAULT 70.0000 COMMENT '买入通过评分阈值',
    `sell_threshold` DECIMAL(8,4) DEFAULT 40.0000 COMMENT '卖出/减仓提醒阈值',
    `config_version` INT DEFAULT 1 COMMENT '配置版本',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY `idx_enabled_source` (`enabled`, `source_type`, `source_id`),
    KEY `idx_strategy` (`strategy_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI交易研判配置表';
```

密钥只保存引用，不保存明文。示例环境变量：`INSTOCK_AI_API_KEY`、`INSTOCK_AI_BASE_URL`、`INSTOCK_AI_MODEL`。

### 5.6 AI 评分结果表：`cn_stock_trade_ai_score`

用于保存某次策略筛选或交易前 AI 研判的输入摘要、输出评分、建议动作和失败状态。该表可被模拟交易、回测和未来实盘共用。

```sql
CREATE TABLE IF NOT EXISTS `cn_stock_trade_ai_score` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `config_id` BIGINT DEFAULT NULL COMMENT '关联 cn_stock_ai_decision_config.id',
    `config_version` INT DEFAULT NULL COMMENT '运行时配置版本快照',
    `source_type` VARCHAR(32) NOT NULL COMMENT 'paper/backtest/live',
    `source_id` BIGINT NOT NULL COMMENT '模拟盘、回测或实盘策略ID',
    `run_id` VARCHAR(64) DEFAULT NULL COMMENT '单次运行ID',
    `signal_id` BIGINT DEFAULT NULL COMMENT '关联 cn_stock_trade_signal.id，可后置回填',
    `strategy_id` BIGINT DEFAULT NULL,
    `strategy_name` VARCHAR(128) DEFAULT NULL,
    `code` VARCHAR(20) NOT NULL,
    `name` VARCHAR(64) DEFAULT NULL,
    `decision_date` DATE NOT NULL COMMENT '研判日期',
    `decision_phase` VARCHAR(32) NOT NULL COMMENT 'pre_buy/pre_sell/post_signal/review',
    `input_hash` VARCHAR(64) NOT NULL COMMENT '输入数据包哈希',
    `prompt_hash` VARCHAR(64) DEFAULT NULL COMMENT '提示词哈希',
    `prompt_version` VARCHAR(64) DEFAULT NULL COMMENT '提示词版本标签',
    `model_name` VARCHAR(128) DEFAULT NULL,
    `input_summary` JSON DEFAULT NULL COMMENT '基础信息、指标、K线窗口等摘要',
    `prompt_messages` JSON DEFAULT NULL COMMENT '实际发送的消息快照，可按安全策略裁剪',
    `raw_response` MEDIUMTEXT DEFAULT NULL COMMENT '模型原始响应',
    `score` DECIMAL(8,4) DEFAULT NULL COMMENT '0-100 综合评分',
    `action` VARCHAR(32) DEFAULT NULL COMMENT 'buy/sell/hold/skip/reduce/watch',
    `confidence` DECIMAL(8,4) DEFAULT NULL COMMENT '0-1 置信度',
    `reason_summary` TEXT DEFAULT NULL COMMENT 'AI 摘要理由',
    `evidence` JSON DEFAULT NULL COMMENT '引用输入字段的关键证据',
    `risk_flags` JSON DEFAULT NULL COMMENT '风险提示',
    `threshold_result` JSON DEFAULT NULL COMMENT '与 buy/sell 阈值比较结果',
    `gate_result` VARCHAR(32) DEFAULT 'not_enabled' COMMENT 'not_enabled/pass/reject/fallback/error',
    `status` VARCHAR(32) DEFAULT 'pending' COMMENT 'pending/succeeded/failed/skipped/timeout',
    `latency_ms` INT DEFAULT NULL,
    `error_message` TEXT DEFAULT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_input_phase` (`source_type`, `source_id`, `run_id`, `code`, `decision_phase`, `input_hash`),
    KEY `idx_signal_id` (`signal_id`),
    KEY `idx_code_date` (`code`, `decision_date`),
    KEY `idx_score_action` (`score`, `action`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI交易研判评分表';
```

`input_summary` 不建议存储完整长 K 线原文，可保存窗口长度、关键 OHLCV 切片、指标摘要和数据哈希；完整数据可通过 `source_type/source_id/run_id/code/decision_date` 重建。对外通知只展示 AI 摘要、评分、关键证据和风险提示，不展示 API key、完整 prompt 或敏感账户信息。

### 5.7 通知配置表：`cn_stock_notification_config`

```sql
CREATE TABLE IF NOT EXISTS `cn_stock_notification_config` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(128) NOT NULL COMMENT '配置名称',
    `channel` VARCHAR(32) NOT NULL COMMENT 'dingtalk/wecom/qq/serverchan/pushplus，第一阶段仅实现 dingtalk',
    `enabled` TINYINT(1) DEFAULT 1 COMMENT '是否启用',
    `source_type` VARCHAR(32) DEFAULT 'paper' COMMENT 'paper/backtest/live/all',
    `source_id` BIGINT DEFAULT NULL COMMENT '指定模拟盘或策略ID，为空表示全部',
    `event_types` JSON DEFAULT NULL COMMENT '启用事件类型列表',
    `webhook_url` TEXT DEFAULT NULL COMMENT 'Webhook URL，应加密或迁移至环境变量',
    `secret_ref` VARCHAR(255) DEFAULT NULL COMMENT '密钥引用，优先使用环境变量名',
    `receiver_config` JSON DEFAULT NULL COMMENT '接收人、群、机器人配置',
    `template_config` JSON DEFAULT NULL COMMENT '模板配置',
    `summary_config` JSON DEFAULT NULL COMMENT '通知摘要字段、排序和展示开关',
    `detail_config` JSON DEFAULT NULL COMMENT '通知详情字段、AI依据、原始参考数据展示上限',
    `rate_limit_per_minute` INT DEFAULT 20 COMMENT '限流',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY `idx_channel_enabled` (`channel`, `enabled`),
    KEY `idx_source` (`source_type`, `source_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='通知配置表';
```

安全建议：`webhook_url` 和密钥不建议明文长期存储。优先存环境变量名，例如 `INSTOCK_DINGTALK_WEBHOOK`、`INSTOCK_DINGTALK_SECRET`。

### 5.8 通知事件表：`cn_stock_notification_event`

用于 outbox、发送状态、失败重试和审计。

```sql
CREATE TABLE IF NOT EXISTS `cn_stock_notification_event` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `event_type` VARCHAR(64) NOT NULL COMMENT 'trade_executed/run_failed/run_summary/risk_alert',
    `source_type` VARCHAR(32) NOT NULL COMMENT 'paper/backtest/live',
    `source_id` BIGINT NOT NULL COMMENT '来源ID',
    `run_id` VARCHAR(64) DEFAULT NULL COMMENT '运行ID',
    `signal_id` BIGINT DEFAULT NULL COMMENT '交易信号ID',
    `trade_id` BIGINT DEFAULT NULL COMMENT '成交ID',
    `channel` VARCHAR(32) NOT NULL COMMENT '通知渠道',
    `config_id` BIGINT DEFAULT NULL COMMENT '通知配置ID',
    `dedupe_key` VARCHAR(128) NOT NULL COMMENT '通知幂等键',
    `title` VARCHAR(255) DEFAULT NULL COMMENT '标题',
    `message_text` MEDIUMTEXT DEFAULT NULL COMMENT '文本消息',
    `message_payload` JSON DEFAULT NULL COMMENT '渠道原始payload',
    `status` VARCHAR(32) DEFAULT 'pending' COMMENT 'pending/sending/sent/failed/skipped',
    `attempt_count` INT DEFAULT 0 COMMENT '发送次数',
    `next_retry_at` DATETIME DEFAULT NULL COMMENT '下次重试时间',
    `last_error` TEXT DEFAULT NULL COMMENT '最后错误',
    `sent_at` DATETIME DEFAULT NULL COMMENT '发送成功时间',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_dedupe` (`dedupe_key`),
    KEY `idx_status_retry` (`status`, `next_retry_at`),
    KEY `idx_signal` (`signal_id`),
    KEY `idx_source_run` (`source_type`, `source_id`, `run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='通知事件表';
```

### 5.9 IM 交易指令表：`cn_stock_trade_command`

用于未来通过 IM 确认或下达交易指令。第一阶段可不实现，仅预留设计。

```sql
CREATE TABLE IF NOT EXISTS `cn_stock_trade_command` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `source_channel` VARCHAR(32) NOT NULL COMMENT 'dingtalk/wecom/qq',
    `source_message_id` VARCHAR(128) DEFAULT NULL COMMENT 'IM消息ID',
    `operator_id` VARCHAR(128) DEFAULT NULL COMMENT '操作人外部ID',
    `operator_name` VARCHAR(128) DEFAULT NULL COMMENT '操作人名称',
    `command_type` VARCHAR(32) NOT NULL COMMENT 'confirm_buy/confirm_sell/cancel/adjust',
    `paper_id` BIGINT DEFAULT NULL COMMENT '关联模拟盘',
    `signal_id` BIGINT DEFAULT NULL COMMENT '关联交易信号',
    `code` VARCHAR(20) NOT NULL COMMENT '股票代码',
    `direction` VARCHAR(16) NOT NULL COMMENT 'buy/sell',
    `amount` DECIMAL(20,4) DEFAULT NULL COMMENT '指令数量',
    `value` DECIMAL(20,4) DEFAULT NULL COMMENT '指令金额',
    `price_limit` DECIMAL(20,6) DEFAULT NULL COMMENT '限价，可选',
    `status` VARCHAR(32) DEFAULT 'pending' COMMENT 'pending/approved/rejected/expired/executed/failed',
    `risk_check_json` JSON DEFAULT NULL COMMENT '风控检查结果',
    `request_payload` JSON DEFAULT NULL COMMENT '原始回调内容',
    `expire_at` DATETIME DEFAULT NULL COMMENT '指令过期时间',
    `approved_at` DATETIME DEFAULT NULL COMMENT '确认时间',
    `executed_at` DATETIME DEFAULT NULL COMMENT '执行时间',
    `execution_result` JSON DEFAULT NULL COMMENT '执行结果',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_channel_message` (`source_channel`, `source_message_id`),
    KEY `idx_signal` (`signal_id`),
    KEY `idx_status` (`status`, `expire_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='IM交易指令表';
```

---

## 6. 策略 API 扩展设计

### 6.1 兼容旧策略

当前策略可能大量使用：

```python
order(code, amount)
order_target(code, target)
order_value(code, value)
order_target_value(code, target_value)
order_target_percent(code, percent)
```

建议扩展为兼容形式：

```python
order(code, amount, reason=None, decision=None, indicators=None, selection=None)
order_target(code, target, reason=None, decision=None, indicators=None, selection=None)
order_value(code, value, reason=None, decision=None, indicators=None, selection=None)
order_target_value(code, target_value, reason=None, decision=None, indicators=None, selection=None)
order_target_percent(code, percent, reason=None, decision=None, indicators=None, selection=None)
```

旧策略无需修改即可运行。新策略可以传入结构化解释。

AI 评分建议不强制要求策略手工传入，而是由引擎在策略筛选结果和下单意图之间统一调用。策略可以选择传入 `selection/indicators` 作为 AI 输入增强数据，系统再补齐基础信息、K 线窗口、账户和风险上下文。

### 6.2 新增辅助 API

为了减少策略代码中手工拼 JSON 的成本，建议提供辅助函数：

```python
record_trade_decision(
    code,
    reason='...',
    rules=[...],
    indicators={...},
    selection=[...]
)

decision_rule(
    name='MA5 上穿 MA20',
    threshold='ma5 > ma20',
    actual={'ma5': ma5, 'ma20': ma20},
    passed=ma5 > ma20,
    note='短期趋势改善'
)
```

AI 研判辅助函数建议放在独立模块，避免策略直接绑定具体模型：

```python
build_ai_decision_context(
    code=code,
    phase='pre_buy',
    strategy_context=context,
    indicators=indicators,
    selection=selection,
    kline_window=120
)

score_trade_with_ai(context_payload, config_name='default_paper_pre_buy')
```

策略侧可只关心“是否需要 AI 评分”和“把哪些自定义指标交给系统”，具体 provider、prompt、阈值、超时、是否作为 gate 由配置决定。

### 6.3 默认兜底解释

当策略未提供 `reason` 时，系统可以生成兜底解释：

- 买入：`策略触发买入信号，按模拟盘撮合规则成交；该理由由系统根据成交结果生成，非策略显式说明。`
- 卖出：`策略触发卖出/调仓/风控信号，按模拟盘撮合规则成交；该理由由系统根据成交结果生成，非策略显式说明。`

同时写入：

```text
reason_source = generated
```

通知中也应展示“理由来源：系统兜底说明”。

---

## 7. 通知消息设计

通知消息必须采用“摘要优先、详情随后”的结构。用户在钉钉消息列表和手机通知中首先看到结论，点开后再看交易细节、策略依据、AI 评分和原始参考数据。

推荐结构：

```text
标题
摘要总结
    -> 方向、股票、评分、建议动作、成交金额、关键风险、是否需要人工复核
核心结论
    -> 策略理由一句话、AI 理由一句话、gate 结果
详情
    -> 成交信息、规则阈值对比、AI 关键依据、重要原始参考数据、风险提示
链接
    -> 系统详情页、信号详情 API、AI 评分详情 API
```

摘要中只放最重要的 5-8 个字段，详情中再展开数据。这样既能保证通知直观，也避免一条消息过长导致用户错过关键信息。

### 7.1 买入通知模板

```text
【模拟盘买入信号】600016 民生银行

摘要总结：
- 方向：买入
- AI评分：82.5 / 100，建议 buy，Gate 通过
- 成交金额：99,484.00 元，成交后仓位 49.80%
- 核心理由：BOLL 下轨附近反弹，MA5 上穿 MA20
- 关键风险：MA60 仍偏弱，跌破下轨需复核止损

模拟盘：BOLL 下轨策略模拟盘
策略：BOLL 下轨反弹策略
日期：2026-04-27
运行ID：paper-4-20260427-153000

成交信息：
- 方向：买入
- 成交价：3.74
- 数量：26,600 股
- 成交金额：99,484.00 元
- 佣金：29.85 元
- 滑点成本：49.74 元
- 成交后仓位：49.80%

买入理由：
BOLL 下轨附近反弹且 MA5 上穿 MA20，触发买入。

确认数据对比：
1. BOLL 下轨接近度
   阈值：close <= boll_lower * 1.02
   实际：close=3.74，boll_lower=3.67，ratio=1.0191
   结果：通过

2. 均线改善
   阈值：ma5 > ma20
   实际：ma5=3.71，ma20=3.70
   结果：通过

查看详情：
http://localhost:3000/algo/paper?id=4
信号详情：
http://localhost:3000/trade/signal?signal_id=12345
```

若启用 AI 研判，买入通知追加 AI 摘要块：

```text
AI 综合研判：
- 评分：82.5 / 100
- 建议：buy
- 置信度：0.76
- Gate：通过，阈值 buy_threshold=70

AI 关键依据：
1. 日线 close 位于 BOLL 下轨 2% 范围内，且 MA5 已重新站上 MA20。
2. 最近 20 日成交量温和放大，未出现明显放量破位。
3. 当前单票目标仓位 49.8%，未超过模拟盘最大仓位限制。

AI 风险提示：
- 中期 MA60 仍偏弱，若跌破下轨需触发止损复核。
- 评分来自配置版本 default_paper_pre_buy:v3，仅作为辅助研判。
```

### 7.2 卖出通知模板

```text
【模拟盘卖出信号】600016 民生银行

摘要总结：
- 方向：卖出/减仓
- AI评分：38.0 / 100，建议 reduce
- 平仓盈亏：+4,590.72 元，收益率 +4.61%
- 核心理由：止盈阈值达成，MACD 动能减弱
- 关键风险：若继续持有，需要复核止盈回撤阈值

成交信息：
- 方向：卖出
- 成交价：3.92
- 数量：26,600 股
- 成交金额：104,272.00 元
- 佣金：31.28 元
- 印花税：104.27 元
- 滑点成本：52.14 元
- 平仓盈亏：+4,590.72 元
- 收益率：+4.61%

卖出理由：
价格达到止盈阈值且 MACD 柱缩短，触发止盈卖出。

确认数据对比：
1. 止盈阈值
   阈值：return_rate >= 4.5%
   实际：return_rate=4.61%
   结果：通过

2. 动能减弱
   阈值：macd_hist_today < macd_hist_yesterday
   实际：today=0.012，yesterday=0.018
   结果：通过

AI 综合研判：
- 评分：38.0 / 100
- 建议：reduce
- Gate：触发减仓提醒

AI 风险提示：
- 短期收益已达到策略止盈区间，MACD 动能下降。
- 若继续持有，需要重新确认止盈回撤阈值。
```

### 7.3 渠道格式降级

钉钉 markdown 可以使用表格或分段列表。第一阶段以钉钉 markdown 为标准模板，企业微信、QQ、Server 酱等渠道后续通过模板降级适配：

```markdown
| 规则 | 阈值/判定 | 实际数据 | 结果 |
|---|---|---|---|
| BOLL 下轨接近度 | close <= lower * 1.02 | close=3.74, lower=3.67 | 通过 |
| MA5 上穿 MA20 | ma5 > ma20 | ma5=3.71, ma20=3.70 | 通过 |
```

QQ/普通文本渠道不一定支持 markdown 表格，因此模板层需要支持 plain text 降级。AI 评分块也必须支持降级为普通文本，避免重要风险提示在低能力渠道丢失。

### 7.4 AI 依据与重要原始参考数据展示规则

通知中应展示 AI 评价依据和重要原始参考数据，但不应展示完整 prompt、完整长 K 线、API key 或敏感账户信息。推荐分为“摘要可见”和“详情可见”。

摘要可见字段：

- AI 综合评分、建议动作、置信度、gate 结果。
- AI 一句话理由。
- 1-3 条最重要风险提示。
- 最关键的 2-3 个实际指标值，例如 `close`、`ma5`、`ma20`、`boll_lower`、`rsi14`、`macd_hist`。

详情可见字段：

- 股票基础快照：行业、市值、PE/PB、涨跌幅、换手率、停牌/涨跌停状态。
- K 线窗口摘要：数据截止日期、窗口长度、最近 5 根 OHLCV、近 20/60 日涨跌幅、波动率。
- 指标快照：MA/BOLL/MACD/KDJ/RSI/成交量均线等当前值和关键前值。
- 策略筛选证据：通过的筛选阶段、阈值、实际值、排名分数、候选池数量变化。
- 账户与风控快照：当前现金、目标仓位、单票仓位、组合回撤、当日交易次数。
- AI 输出结构：评分、建议、证据、风险、阈值比较、配置版本、模型名称、输入 hash。

不在通知中展示：

- 完整 API key、webhook、secret、券商账号。
- 完整 system prompt 和 user prompt 原文。
- 大段历史 K 线原文。通知只展示摘要和最近关键切片，完整数据通过系统详情页查看。
- 任何未来日期数据或交易日之后才可见的数据。

详情链接应指向系统页面，例如模拟交易详情、交易信号详情或 AI 评分详情。详情 API 需要支持权限控制，避免任何拿到钉钉消息的人都能访问敏感数据。

---

## 8. 通知渠道实现建议

| 渠道 | 发送提醒 | 接收指令 | 推荐度 | 说明 |
|---|---:|---:|---:|---|
| 钉钉群机器人 | 容易 | 中等 | 高 | webhook 简单，适合第一阶段 |
| 企业微信机器人/应用 | 容易 | 中等 | 高 | 通知和确认流程更稳 |
| QQ | 中等 | 中高 | 中 | 多依赖 OneBot 等生态，维护成本较高 |
| 个人微信 | 难 | 难 | 低 | 稳定性和风控风险较高，不建议优先做 |
| Server酱/PushPlus | 很容易 | 难 | 中 | 适合轻量通知，不适合交易指令 |

第一阶段只建议实现钉钉群机器人，目标是先把“成交后通知、签名、去重、重试、模板、AI 评分摘要展示”做成稳定闭环。企业微信保留模块接口和表字段兼容，但不作为第一批验收范围；QQ 和个人微信暂不进入实现计划。

### 8.1 钉钉一期实现边界

钉钉一期建议只实现群机器人 webhook：

- 配置项：`INSTOCK_DINGTALK_WEBHOOK`、`INSTOCK_DINGTALK_SECRET`、启用事件类型、限流参数。
- 安全：支持加签 `timestamp + secret`，不在日志中打印完整 webhook。
- 消息类型：优先 markdown；异常情况下降级为 text。
- 触发事件：`trade_executed`、`run_failed`、可选 `run_summary`。
- 内容：成交信息、策略真实理由、阈值实际值对比、AI 评分摘要、风险提示、详情链接。
- 可靠性：outbox 去重、失败重试、失败不阻塞模拟交易。
- 运维：提供测试发送函数和最小健康检查。

---

## 9. IM 交易指令扩展设计

不要直接实现“收到 IM 消息立即真实下单”。推荐流程：

```text
信号通知
  -> 用户确认
  -> 后端生成 trade_command
  -> 权限校验
  -> 风控校验
  -> 二次确认或人工审批
  -> 实盘交易服务执行
  -> 结果回传 IM
```

必要安全控制：

1. 操作人白名单。
2. IM 平台签名校验。
3. 回调请求防重放。
4. 指令一次性 token。
5. 指令过期时间。
6. 最大单笔金额限制。
7. 最大单日交易金额限制。
8. 禁止重复确认同一 signal。
9. 审计日志。
10. 实盘执行与模拟盘信号解耦。

当前项目已有 `instock/trade/trade_service.py` 和券商客户端配置基础，但真实交易系统和模拟交易系统需要通过独立的 `trade_command` 队列连接，不能直接在通知回调中调用券商下单。

---

## 10. 与回测系统的复用方案

### 10.1 后端复用

建议新增：

```text
instock/core/backtest/trade_decision.py
```

提供统一结构：

```python
class TradeDecisionRule:
    pass

class TradeDecisionSnapshot:
    pass

def normalize_decision_payload(payload):
    pass

def build_generated_reason(trade_record):
    pass
```

模拟交易和回测都调用该模块，避免两套理由结构。

### 10.2 前端复用

建议将交易决策展示抽取为：

```text
instock/fontWeb/src/components/trade-decision/
├── TradeDecisionPanel.vue
├── IndicatorSnapshotPanel.vue
├── TradeReasonSummary.vue
└── TradeMarkerTooltip.ts
```

回测详情页和模拟交易详情页共同使用。通知消息模板也使用同一套后端结构生成摘要。

### 10.3 API 复用

建议新增通用 API：

```text
GET /instock/api/trade/signal/detail?source_type=paper&source_id=4&trade_id=xxx
GET /instock/api/trade/signal/list?source_type=paper&source_id=4
GET /instock/api/trade/decision?signal_id=xxx
```

模拟交易详情接口可以内嵌最近或全部决策数据；回测详情接口也可以逐步迁移到该结构。

---

## 11. 开发计划

### Phase 1：钉钉通知基础设施 ✅ 已完成 (2026-05-07)

> 验收记录：
> - 模块文件：`instock/notification/{__init__,service,templates}.py`、`channels/{base,dingtalk}.py`。
> - 数据库表：`cn_stock_notification_config` + `cn_stock_notification_event`（uq_dedupe_key）。
> - 接入点：`instock/paper_trading/paper_engine.py` 成交落库后调用 `notify_trade_records()`。
> - 测试：`tests/test_notification_phase1.py` 6/6 通过（钉钉签名、payload、去重、出 box、process_pending、失败不阻塞）。
> - 生产事件：`cn_stock_notification_event` 已观测到 sent + skipped 行（依赖 .env webhook）。
> - 修复记录：`tools/diagnose_dingtalk.py` 排查脚本；`paper_engine.py` 修复 1062 race condition（commit `a118c82`）。

目标：模拟交易成交后能通过钉钉发送基础通知，具备配置、签名、去重、失败重试能力。

开发内容：

1. 新增 `instock/notification` 模块。
2. 实现 `NotificationChannel` 抽象。
3. 实现钉钉 webhook channel。
4. 新增 `cn_stock_notification_config`。
5. 新增 `cn_stock_notification_event`。
6. 在 `paper_engine.py` 成交落库后写入通知事件。
7. 实现同步发送和失败状态记录。
8. 支持配置开关：按模拟盘、按事件类型启用。
9. 保留企业微信、QQ 等 channel 抽象，不在第一阶段实现。

验收标准：

- 手工运行模拟盘后，能生成通知事件。
- 钉钉能收到买入/卖出通知。
- 重复运行不会重复发送同一事件。
- webhook 失败时交易主流程不失败。

### Phase 2：策略真实理由与决策留痕 ✅ 已完成 (2026-05-07)

> 验收记录：
> - 新模块：`instock/core/backtest/trade_decision.py`（normalize/resolve_reason/compute_signal_hash/serialize）；`instock/core/backtest/trade_signal_store.py`（DDL + persist + link + fetch）。
> - 4 张新表（按需创建，DDL 幂等，单独事务，列结构与 §5.1–§5.4 完全一致）：`cn_stock_trade_signal`（含 `target_amount/target_percent` 与 Phase 4 预留的 `ai_score_id/ai_score/ai_action/ai_gate_result`）、`cn_stock_trade_decision`、`cn_stock_trade_indicator_snapshot`（结构化 OHLCV + ma/boll/rsi/macd/kdj/extra JSON）、`cn_stock_trade_selection_snapshot`。
> - paper_engine 改造：`_order_proxy(..., reason, decision, indicators, selection, order_api, target_amount, target_percent)`；5 个 `order_*` lambda 全部接受 **kw 兼容旧策略；`order_target` 自动捕获 `target_amount`，`order_target_percent` 自动捕获 `target_percent`；撮合后建立 `signal_inputs` 平行表；主事务提交后 capture trade_id 并 `link_signal_to_trade`；信号持久化失败仅 warning，不回滚成交。
> - 通知模板扩展：`reason` + `reason_source` + `decision_rules` 渲染为「交易理由（来源标注）」与「决策规则对比」表，最多 5 行；`reason_source=generated` 时显式标注「系统兜底说明（非策略显式提供）」。
> - 通知服务：`enqueue_trade_notification(..., signal_id=...)` 自动 `fetch_signal_with_decision()` 注入策略真实 reason。
> - 测试：`tests/test_trade_signal_phase2.py` 16/16 通过（含结构化 OHLCV 拆分、target_percent 持久化校验）；与 Phase 1 / 1062 修复 / sandbox / recorder / recent_fixes 共 58/58 通过。

目标：通知中的交易理由来自策略运行时真实数据。

开发内容：

1. 扩展 `order_*` API，支持 `reason/decision/indicators/selection`。
2. 新增 `cn_stock_trade_signal`。
3. 新增 `cn_stock_trade_decision`。
4. 新增 `cn_stock_trade_indicator_snapshot`。
5. 新增 `cn_stock_trade_selection_snapshot`。
6. 撮合成交后将 `signal_id` 与 `trade_id` 关联。
7. 通知模板读取真实决策数据。
8. 未提供理由时生成兜底说明，并标记 `reason_source=generated`。

验收标准：

- 新策略传入 `reason/decision` 后，数据库能完整保存。
- 通知中能展示阈值、实际值、判断结果。
- 旧策略不传理由也能正常运行。
- 旧策略通知明确标记理由来源为系统兜底。

### Phase 3：回测与前端复用 ✅ 已完成 (2026-05-07)

> 验收记录：
> - 回测引擎接入：`instock/core/backtest/portfolio_engine.py` 5 个 `order_*` 全部接受 `**kw`（旧策略调用 100% 兼容），`_submit_order` 透传 `reason/decision/indicators/selection/order_api/target_amount/target_percent`；`_execute_single_order` 在 buy/sell 两条分支同时 `_signal_inputs.append(order_info)`，与 `_trade_records` 严格 1:1 对应。新增 `order_target_percent` API 与 paper 引擎齐平。
> - 持久化复用：`instock/core/backtest/trade_signal_store.py` 新增 `persist_backtest_signals(backtest_id, run_id, trade_records, signal_inputs)`，复用 Phase 2 的 `persist_signal_with_relations`；`source_type='backtest'` 写入同一套 `cn_stock_trade_signal/decision/indicator_snapshot/selection_snapshot` 表。回测主结果落库后由 `RunPortfolioBacktestHandler` 与 `StartPortfolioBacktestHandler` 各自调用，失败仅 warning，不回滚回测主结果。回测无独立 `cn_stock_backtest_trade` 行，故 `trade_id` 字段保持 NULL，复用通过 `(source_type, source_id, signal_date, code, direction)` 关联。
> - 详情数据扩展：`fetch_signal_with_decision()` 在 Phase 2 基础上追加 `indicators` 与 `selection` 两块（结构化 OHLCV + ma/boll/rsi/macd/kdj/extra；候选筛选阶段、阈值、实际值、排名）。新增 `list_signals_for_source(source_type, source_id)` 用于回测/模拟盘列表。
> - 统一 API：新增 `instock/web/tradeSignalHandler.py`，注册路由 `GET /instock/api/trade/signal/list?source_type=&source_id=` 与 `GET /instock/api/trade/signal/detail?signal_id=`；前端在 backtest-detail 与 paper-detail 页面可消费同一接口拿到一致的决策依据展示数据。
> - 测试：`tests/test_trade_signal_phase3.py` 11/11 通过；与 Phase 1/2、1062 修复、sandbox、recorder、recent_fixes、portfolio_backtest 共 **89/89 通过**。
> - 不变性保证：未触碰前端 backtest-detail.vue / paper detail Vue 组件（已自然兼容 `trade.reason`）；未改动 `cn_stock_backtest_portfolio` 与 `cn_stock_backtest_trade` schema；未改动 paper_engine 主撮合事务。

目标：回测详情和模拟交易详情复用同一套交易决策展示。

开发内容：

1. 新增 `trade_decision.py` 通用结构。
2. 回测引擎接入 `TradeSignal/TradeDecision`。
3. 模拟交易详情接口返回 `signals/decisions/snapshots`。
4. 回测详情接口返回相同结构。
5. 抽取前端 `TradeDecisionPanel` 等组件。
6. 回测详情页和模拟交易详情页共同使用。

验收标准：

- 回测交易和模拟交易都能展示同样风格的决策依据。
- 指标快照与 K 线图上的交易日期一致。
- 前端 tooltip、详情面板、通知内容中的关键数据一致。

### Phase 4：AI 综合评分扩展

目标：策略筛选出的股票在买入前或卖出前可以生成 AI 综合评分，并将评分、建议动作、关键依据和风险提示落库，供通知、模拟交易详情、回测分析复用。

开发内容：

1. 新增 `instock/ai_decision` 模块。
2. 新增 `cn_stock_ai_decision_config`。
3. 新增 `cn_stock_trade_ai_score`。
4. 实现股票基础信息、常用指标、K 线窗口、策略筛选原因、账户风控上下文的数据包构造。
5. 实现 prompt 模板渲染和 JSON 输出解析。
6. 支持 provider/model/prompt/temperature/max_tokens/timeout/threshold/gate 配置。
7. 默认 AI 只留痕和通知展示，不改变交易结果。
8. 可配置启用 AI gate，根据评分决定是否放行买入或触发卖出复核。
9. 通知模板展示 AI 评分摘要、关键证据、风险提示和配置版本。

验收标准：

- AI 禁用时，策略和通知流程完全不受影响。
- AI 启用但不作为 gate 时，交易照常执行，评分结果可追溯。
- AI 作为 gate 时，低于买入阈值的信号被标记为 `reject`，并保留策略原始信号。
- AI 超时或返回格式错误时，按 `fail_closed` 配置决定放行或拒绝，并落库错误原因。
- 修改 prompt 后，新交易记录保存新的 `prompt_version/prompt_hash`，历史记录不被覆盖。

### Phase 5：前端配置管理页面

目标：用户可以在前端配置通知渠道、通知模板、AI 研判参数和展示范围，同时敏感密钥仍由环境变量或后端安全配置管理。

开发内容：

1. 新增通知配置 API。
2. 新增通知事件列表 API。
3. 新增通知重试 API。
4. 新增 AI 配置 API。
5. 前端新增通知设置页面。
6. 前端新增 AI 研判配置页面。
7. 支持测试发送钉钉消息。
8. 支持按模拟盘、策略、事件类型启用或关闭通知。
9. 支持调整通知摘要字段、详情字段、AI 依据展示上限。
10. 支持调整 prompt 模板、模型参数、评分阈值、是否启用 gate。
11. 保存配置时生成 `config_version`，历史运行快照不被覆盖。

前端配置页面建议包含：

- 通知总开关、钉钉 channel 开关、测试发送按钮。
- 模拟盘/策略适用范围选择器。
- 事件类型多选：买入、卖出、异常、每日汇总、AI 拒绝。
- 摘要字段排序器：方向、股票、评分、成交额、仓位、核心理由、关键风险。
- 详情字段开关：成交明细、规则阈值、指标快照、AI 证据、原始参考数据摘要。
- AI provider/model/base_url 引用、prompt 编辑器、JSON schema 编辑器。
- AI 数据包范围：K 线窗口、周/月 K、基本面、市场上下文、账户风控上下文。
- AI gate 配置：启用状态、买入阈值、卖出阈值、失败策略、超时时间。

验收标准：

- 前端可以启用/禁用钉钉通知并测试发送。
- 前端可以调整摘要和详情展示字段，通知中摘要始终位于详情之前。
- 前端可以调整 AI prompt、阈值、数据包范围并生成新版本。
- 密钥明文不会出现在前端响应、浏览器控制台和通知事件日志中。
- 旧版本配置产生的历史 AI 评分记录不受新配置影响。

### Phase 6：IM 指令确认

目标：支持通过钉钉对交易信号进行确认或忽略；企业微信作为后续渠道扩展。

开发内容：

1. 新增 `cn_stock_trade_command`。
2. 实现 IM 回调 API。
3. 实现签名校验和操作人白名单。
4. 实现指令解析。
5. 实现指令过期与防重放。
6. 实现风控检查。
7. 暂时只写入指令表，不直接实盘下单。

### Phase 7：实盘交易连接

目标：将已确认指令安全地交给真实交易系统执行。

开发内容：

1. 设计 `trade_command` 到 `trade_service.py` 的 adapter。
2. 引入人工确认或二次确认机制。
3. 增加实盘风控阈值。
4. 记录实盘委托、成交、撤单状态。
5. 执行结果回发 IM。

---

## 12. 流程审计清单

### 12.1 策略运行审计

- 策略运行是否有唯一 `run_id`。
- 策略使用的数据日期是否与交易日期一致。
- 指标是否基于完整历史 K 线计算。
- 交易信号是否记录原始 `order_api`。
- 信号是否有 `signal_hash` 幂等键。
- 旧策略未提供理由时是否标记 `reason_source=generated`。

### 12.2 交易撮合审计

- 下单意图是否成功转换为成交记录。
- 部分成交或金额不足时，信号与成交是否正确关联。
- 卖出时盈亏、收益率、印花税是否正确。
- 成交后持仓、现金、净值是否一致。

### 12.3 决策数据审计

- 每条通知是否能追溯到 `signal_id`。
- 决策规则是否包含阈值和实际值。
- `passed` 是否真实表达策略判断结果。
- 指标快照是否与 K 线日期一致。
- 候选筛选数据是否能解释“为何选中该股票”。

### 12.4 通知审计

- 通知是否只在交易落库后发送。
- 是否有 outbox 事件。
- 是否有 dedupe key。
- 钉钉 webhook 签名是否正确。
- 钉钉 webhook 失败是否会重试。
- 钉钉 webhook 失败是否不会影响模拟交易运行。
- 消息中是否包含详情链接。
- 消息是否隐藏敏感密钥和账户信息。
- 通知是否采用“摘要总结在前、详情在后”的结构。
- 摘要是否包含方向、股票、成交/信号结论、AI 评分或 gate 结果、关键风险。
- 详情是否包含策略阈值对比、AI 关键依据和必要原始参考数据摘要。
- 详情链接是否有权限控制，避免敏感数据被无授权访问。

### 12.5 AI 研判审计

- AI 输入是否只包含策略当时可见的数据，避免使用未来 K 线或未来财务数据。
- K 线指标是否基于完整历史计算后截取，而不是只按交易区间重新计算。
- 输入数据包是否保存 `input_hash`，prompt 是否保存 `prompt_hash/prompt_version`。
- AI 输出是否为结构化 JSON，并经过 schema 校验。
- AI 评分、建议动作、关键证据和风险提示是否落库。
- AI 作为 gate 时，是否同时保留策略原始信号和 AI 拒绝原因。
- AI 超时、失败、禁用时是否按 `fail_closed` 配置处理。
- 通知中是否明确标注 AI 评分仅为辅助研判，或明确展示 gate 结果。
- AI 关键依据是否能追溯到输入数据字段，而不是纯自然语言判断。
- 通知中的原始参考数据是否只展示摘要和关键切片，不泄露完整 prompt、密钥或过长 K 线。

### 12.6 前端配置审计

- 通知开关、事件类型、摘要字段、详情字段是否可通过前端调整。
- AI prompt、模型参数、评分阈值、数据包范围是否可通过前端调整。
- 前端是否只保存密钥引用，不保存密钥明文。
- 每次保存配置是否生成版本号并记录修改人和修改时间。
- 前端测试发送是否写入通知事件或测试日志，便于排查。
- 配置修改是否不会影响历史交易和历史 AI 评分的解释。

### 12.7 IM 指令审计

- 回调签名是否校验。
- 操作人是否在白名单。
- 指令是否有过期时间。
- 指令是否有防重放 token。
- 风控结果是否落库。
- 是否禁止 IM 回调直接调用券商下单。
- 是否记录完整请求与响应审计。

---

## 13. 验证计划

### 13.1 单元测试

建议新增测试：

```text
tests/test_notification_channels.py
tests/test_trade_decision_payload.py
tests/test_paper_trade_signal_persistence.py
tests/test_notification_event_outbox.py
tests/test_ai_decision_context.py
tests/test_ai_decision_config.py
tests/test_ai_decision_gate.py
tests/test_notification_template_summary.py
tests/test_frontend_config_api.py
tests/test_im_trade_command_security.py
```

覆盖内容：

- 钉钉签名生成。
- 钉钉 markdown/text payload 格式。
- 决策 payload 标准化。
- 旧策略无 reason 兼容。
- 新策略 reason/decision 落库。
- AI 数据包不包含未来数据。
- AI prompt 版本和 hash 固化。
- AI JSON 输出解析和 schema 校验。
- AI gate 通过、拒绝、超时、fallback。
- 通知模板摘要在前、详情在后。
- 摘要字段和详情字段配置生效。
- 前端配置 API 不返回密钥明文。
- 通知 dedupe。
- 发送失败重试。
- IM 指令过期与防重放。

### 13.2 集成测试

场景 1：旧策略运行。

预期：模拟交易成功，生成交易记录和信号记录，`reason_source=generated`，通知正常发送。

场景 2：新策略运行并传入 reason/decision。

预期：`cn_stock_trade_signal.reason` 为策略传入理由，`cn_stock_trade_decision` 有多条规则，通知展示规则对比表。

场景 3：webhook 失败。

预期：模拟交易仍成功，通知事件状态为 `failed`，`attempt_count` 增加，`next_retry_at` 被设置。

场景 4：重复执行同一模拟盘同一日期。

预期：不重复插入相同 `signal_hash`，不重复发送相同 `dedupe_key`。

场景 5：回测详情复用。

预期：回测交易详情展示与通知中的规则数据一致，K 线 tooltip 中交易理由与详情面板一致。

场景 6：AI 禁用。

预期：模拟交易、决策留痕、钉钉通知均正常，`ai_gate_result=not_enabled` 或为空，不调用外部模型。

场景 7：AI 启用但不作为 gate。

预期：`cn_stock_trade_ai_score` 保存评分、建议动作、关键依据和风险提示；交易结果不因评分变化而改变；钉钉通知展示 AI 摘要。

场景 8：AI 作为买入 gate。

预期：评分高于阈值时买入放行；评分低于阈值时记录策略原始信号但不撮合买入，`ai_gate_result=reject`，通知或执行日志能看到拒绝原因。

场景 9：AI 超时或返回非法 JSON。

预期：`fail_closed=0` 时放行并记录 `fallback/error`；`fail_closed=1` 时拒绝交易并记录错误原因。

场景 10：前端调整通知模板。

预期：修改摘要字段排序和详情展示开关后，新通知按新模板生成；摘要总结始终在详情前面；历史通知事件不被改写。

场景 11：前端调整 AI 配置。

预期：修改 prompt、阈值或 K 线窗口后生成新的 `config_version`；新运行使用新配置，旧评分记录仍保留旧版本、prompt hash 和输入 hash。

场景 12：通知查看 AI 原始参考数据摘要。

预期：钉钉消息中可看到 AI 评分、关键证据、关键指标值、K 线窗口摘要和风险提示；完整 prompt、密钥、长 K 线原文不出现在通知中。

### 13.3 手工验收

1. 配置钉钉 webhook。
2. 运行模拟盘。
3. 查看 `cn_stock_trade_signal`。
4. 查看 `cn_stock_trade_decision`。
5. 查看 `cn_stock_notification_event`。
6. 如启用 AI，查看 `cn_stock_trade_ai_score`。
7. 确认钉钉群收到消息。
8. 点击详情链接返回系统页面。
9. 对比通知中的指标值、AI 评分与页面详情中的指标值和评分。
10. 在前端修改通知摘要字段和 AI 依据展示上限。
11. 再次运行模拟盘，确认新通知摘要优先展示且详情字段符合配置。

---

## 14. 风险与注意事项

### 14.1 不要事后伪造策略理由

如果策略没有提供真实理由，系统只能生成兜底说明，并明确标记来源。不能用前端指标回推后伪装成策略当时的判断。

### 14.2 数据日期必须一致

策略决策使用的指标日期、成交撮合日期、K 线展示日期可能不完全相同。必须记录 `signal_date`、`trade_date`、`kline_date`。对于停牌、非交易日、缺失 K 线等情况，需要明确采用“最近可用交易日”还是“下一交易日”。

### 14.3 密钥不能写入代码

webhook、secret、IM 回调 token、券商账号密码都不能硬编码。推荐使用环境变量或单独的本地配置文件，并避免提交到仓库。

### 14.4 通知应有频率控制

建议支持单笔交易通知、每日汇总通知、只通知买入、只通知卖出、大额交易通知、失败或异常优先通知。

### 14.5 实盘交易必须独立风控

模拟盘信号不能直接等于实盘下单。实盘阶段必须额外校验可用资金、当前持仓、单票最大仓位、单日最大交易金额、涨跌停状态、停牌状态、价格偏离和重复下单。

### 14.6 AI 不能使用未来数据

AI 评分的数据包必须按 `decision_date` 截断。K 线、指标、财务数据、指数数据、新闻摘要都要明确可见时间，不能把交易日之后才出现的数据传给 AI，否则评分会产生未来函数问题。

### 14.7 AI 输出必须可解释可回放

AI 结果不能只保存一句自然语言。必须保存输入摘要 hash、prompt 版本、模型名称、结构化输出、阈值比较和错误状态。后续调整提示词或模型后，历史交易仍要能解释当时为什么通过或拒绝。

### 14.8 AI gate 默认应保守关闭

第一阶段 AI 评分只用于辅助展示和通知，不建议直接改变交易结果。启用 gate 前应先在回测和模拟盘中对比“原策略收益”和“AI 过滤后收益”，并验证漏买、误卖、延迟、超时等问题。

### 14.9 通知不要堆砌过量数据

钉钉通知不是完整分析报告。通知应优先展示摘要总结、关键证据和风险提示，完整指标、长 K 线、完整 AI 输入输出应通过详情页查看。否则消息过长会降低可读性，也容易触发 IM 平台长度限制。

---

## 15. 推荐优先级

实际开发建议按以下顺序推进：

1. 新增通知 outbox 表和钉钉通知模块。
2. 在模拟交易成交落库后发送基础钉钉交易通知。
3. 扩展 `order_*` API 支持 `reason/decision`。
4. 新增交易信号和决策明细表。
5. 让一个典型策略先接入真实理由，例如 BOLL 下轨策略。
6. 通知模板展示阈值和实际值对比。
7. 新增 AI 配置和 AI 评分结果表，默认只留痕不拦截交易。
8. 在钉钉通知中展示 AI 评分摘要、关键证据和风险提示。
9. 模拟交易详情页读取同一套决策和 AI 评分数据。
10. 回测详情页迁移到同一套决策数据结构。
11. 增加通知配置和 AI 配置页面。
12. 最后再考虑企业微信、QQ、IM 指令和实盘连接。

---

## 16. 最小可交付版本

第一版建议交付以下能力：

1. 支持钉钉 webhook。
2. 支持钉钉加签、markdown 模板、失败重试。
3. 模拟交易成交后发送通知。
4. 通知包含成交信息和详情链接。
5. 新策略可传入 `reason/decision`。
6. 通知展示最多 5 条核心决策规则。
7. 通知事件落库，可查看发送成功或失败。
8. 重复运行不重复发送。
9. AI 配置和评分表先落库，支持禁用、启用但不 gate 两种模式。
10. 钉钉通知可展示 AI 评分、建议动作、关键证据和风险提示。

第一版暂不做：企业微信、QQ、个人微信、IM 交易指令、实盘下单、AI 自动实盘下单、完整通知配置 UI。

---

## 17. 关键结论

1. 即时消息通知在当前项目中完全可行，最佳入口在模拟交易成交落库之后。
2. 真正困难的不是发消息，而是保存“真实策略决策依据”。
3. 必须扩展策略下单 API，让策略在下单时提交 `reason/decision/indicators/selection`。
4. 数据库应新增通用交易信号、决策明细、指标快照、筛选快照、AI 配置、AI 评分结果、通知事件表。
5. 通知中的买卖理由必须标明来源，区分策略真实理由和系统兜底理由。
6. AI 综合评分应基于股票基础信息、常用指标、完整历史计算后的 K 线指标、策略筛选上下文和账户风控上下文。
7. AI 配置、提示词、模型参数、工具接入和阈值必须可配置且版本化。
8. 第一阶段 AI 评分只建议作为通知展示和人工复核依据，启用交易 gate 需要额外回测和模拟盘验证。
9. 回测和模拟交易应复用同一套决策结构、AI 评分结构和前端展示组件。
10. IM 接入第一阶段优先钉钉，企业微信、QQ 和个人微信不作为第一阶段重点。
11. IM 交易指令必须走确认、风控、审计队列，不能直接从聊天消息触发实盘下单。
12. 通知必须摘要总结优先展示，详情和原始参考数据随后展开。
13. 通知和 AI 的大部分业务参数应支持前端配置，但密钥和生产安全阈值必须留在后端或环境变量中。

---

## 18. 本轮审核结论

### 18.1 合理性结论

当前方案总体合理：通知、交易决策留痕、AI 研判、前端展示和未来 IM 指令被拆成独立模块，边界清晰；钉钉优先接入可以降低第一阶段复杂度；AI 评分默认只做辅助展示，避免过早影响交易结果；数据库表结构能覆盖信号、决策、指标快照、筛选快照、AI 配置、AI 评分、通知事件和 IM 指令。

### 18.2 已补强的严谨性要求

- 明确通知采用“摘要总结在前、详情在后”的结构。
- 明确 AI 评价依据和重要原始参考数据可以在通知中查看，但只展示摘要和关键切片。
- 明确完整 prompt、密钥、长 K 线原文、敏感账户信息不能进入通知。
- 明确通知详情链接应进入系统页面或详情 API，并需要权限控制。
- 明确通知开关、事件类型、摘要字段、详情字段、AI prompt、阈值、数据包范围等应支持前端配置。
- 明确 webhook、secret、AI API key、实盘风控硬阈值等不应在前端明文配置。
- 明确配置修改需要版本化，历史通知和 AI 评分不能被后续配置覆盖。

### 18.3 仍需实现时重点验证

- 前端配置保存后是否生成 `config_version`，并被后端运行快照引用。
- 钉钉通知是否在手机端也能先看到摘要，不被详情内容挤占重点信息。
- AI 证据是否都能追溯到 `input_summary`、指标快照或筛选快照，而不是模型自行编造。
- 权限控制是否覆盖信号详情、AI 评分详情、通知事件详情。
- AI gate 启用前是否完成回测/模拟盘对比验证，避免评分策略未经验证就改变交易行为。

