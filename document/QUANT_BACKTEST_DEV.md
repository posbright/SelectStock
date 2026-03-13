# 聚宽量化回测 & 模拟交易 — 开发文档

> **分支**: `backTest_dev`
> **日期**: 2026-03-13
> **状态**: 设计阶段

---

## 一、项目目标

基于 InStock 现有数据基础设施，复刻聚宽量化平台的两大核心功能：

1. **回测引擎**（Portfolio Backtest Engine）— 支持组合级别的策略回测
2. **模拟交易系统**（Paper Trading System）— 支持策略的实时模拟运行

前后端各为独立模块，不修改原有代码逻辑。

---

## 二、聚宽核心功能分析

### 2.1 策略编程框架

聚宽策略的核心是**事件驱动的生命周期函数**：

```python
def initialize(context):          # 初始化（仅执行一次）
    set_benchmark('000300.XSHG')  # 设定基准
    set_order_cost(OrderCost(...)) # 设定交易成本
    run_daily(market_open, time='every_bar')

def before_trading_start(context):  # 每日开盘前
    pass

def market_open(context):           # 盘中（每bar执行）
    if 买入条件:
        order(security, amount)     # 下单
    if 卖出条件:
        order_target(security, 0)   # 目标持仓

def after_trading_end(context):     # 收盘后
    pass
```

### 2.2 核心对象

| 对象 | 作用 | InStock 对应 |
|------|------|-------------|
| `context.portfolio` | 账户信息（总资产/可用现金/持仓） | 无（需新建） |
| `context.portfolio.positions` | 持仓字典（code→Position） | 无（需新建） |
| `g` | 全局变量容器 | 无（需新建） |
| `data` | 当前 Bar 的数据快照 | 需适配 |
| `Order` | 订单信息 | trade/ 有基础 |
| `Position` | 持仓信息（数量/成本价/市值） | 无（需新建） |

### 2.3 交易函数

| 聚宽 API | 作用 | 实现难度 |
|----------|------|---------|
| `order(code, amount)` | 按股数下单 | 中 |
| `order_target(code, amount)` | 目标持仓 | 中 |
| `order_value(code, value)` | 按金额下单 | 中 |
| `order_target_value(code, value)` | 目标金额 | 中 |
| `cancel_order(order_id)` | 撤单 | 低 |
| `get_open_orders()` | 查询未完成订单 | 低 |

### 2.4 数据获取函数

| 聚宽 API | 作用 | InStock 数据源 |
|----------|------|---------------|
| `attribute_history(code, N, '1d', fields)` | 单股历史 | `cache/hist/` K线缓存 |
| `history(N, '1d', field, stocks)` | 多股历史 | 同上 |
| `get_price(code, start, end, fields)` | 区间数据 | 同上 |
| `get_current_data()` | 当前快照 | `cn_stock_spot` |
| `get_index_stocks(index)` | 指数成分 | 需新增 |
| `get_industry_stocks(industry)` | 行业成分 | `cn_stock_spot.industry` |

### 2.5 回测结果报告

| 指标 | 说明 | 实现方式 |
|------|------|---------|
| 累计收益 | 策略 vs 基准收益曲线 | 每日 NAV 计算 |
| 年化收益 | 年化总回报 | NAV 序列计算 |
| 最大回撤 | 最大峰谷跌幅 | NAV 序列计算 |
| 夏普比率 | 风险调整收益 | 日收益率序列 |
| Alpha/Beta | 相对基准的超额/系统风险 | 日收益率回归 |
| 日胜率 | 正收益天数占比 | 日收益率统计 |
| 持仓分析 | 持仓变化时间线 | 交易记录聚合 |
| 交易明细 | 每笔买卖记录 | 订单日志 |

### 2.6 模拟交易功能

| 功能 | 说明 |
|------|------|
| 策略实时运行 | 每日收盘后按策略逻辑执行 |
| 状态持久化 | 持仓/订单/全局变量保存到 DB |
| 修改策略 | 热更新策略代码 |
| 暂停/恢复 | 暂停策略运行 |
| 多策略并行 | 同时运行多个模拟盘 |

---

## 三、InStock 现有资源盘点

### 3.1 可直接复用

| 资源 | 说明 |
|------|------|
| K 线缓存 `cache/hist/*.gzip.pickle` | 全市场 ~5000 只股票的日 K 线历史（10年） |
| `cn_stock_spot` 表 | 当日实时行情（OHLCV + 40 字段） |
| `cn_stock_selection` 表 | 综合选股数据（200+ 字段，含估值/财务） |
| `cn_stock_trade_date` 表 | 交易日历 |
| 13 种策略 | 已有 `check()` 函数，可转为信号 |
| TA-Lib 指标 | 32 项技术指标，已封装 |
| Backtrader 适配器 | `bt_engine.py`（391 行，未集成到生产） |
| 交易费用计算 | `rate_stats.py`（佣金/印花税/滑点） |

### 3.2 需要新建

| 组件 | 说明 |
|------|------|
| **回测引擎** | 组合级别的事件驱动引擎 |
| **Portfolio/Position 对象** | 资金/持仓追踪 |
| **撮合引擎** | 模拟订单成交（涨跌停/成交量限制） |
| **策略运行时** | 安全执行用户 Python 策略代码 |
| **基准对比** | 沪深300等指数数据 |
| **风险指标计算** | Sharpe/MaxDrawdown/Alpha/Beta |
| **数据适配层** | 统一接口供策略调用历史数据 |
| **策略管理** | CRUD + 版本管理 |
| **模拟盘引擎** | 定时执行 + 状态持久化 |
| **前端页面** | 策略编辑器 + 回测报告 + 模拟盘面板 |

---

## 四、技术架构设计

### 4.1 模块划分

```
instock/
├── backtest/                    ← 新增：回测引擎模块
│   ├── engine.py               # 回测引擎主逻辑
│   ├── context.py              # Context/Portfolio/Position 对象
│   ├── matching.py             # 撮合引擎（涨跌停/成交量限制）
│   ├── data_proxy.py           # 数据代理层（统一接口）
│   ├── risk_metrics.py         # 风险指标计算
│   ├── strategy_runner.py      # 策略运行时（安全沙箱）
│   ├── api.py                  # 策略可调用的 API 函数
│   └── recorder.py             # 交易/持仓/净值记录
│
├── paper_trading/               ← 新增：模拟交易模块
│   ├── paper_engine.py         # 模拟交易引擎
│   ├── scheduler.py            # 定时调度（每日触发）
│   ├── state_manager.py        # 状态持久化（持仓/资金/g 对象）
│   └── strategy_manager.py     # 策略 CRUD + 版本管理
│
├── web/
│   ├── backtestEngineHandler.py  ← 新增：回测引擎 API
│   └── paperTradingHandler.py    ← 新增：模拟交易 API
│
└── fontWeb/src/
    ├── views/
    │   ├── quant-backtest/        ← 新增：回测前端模块
    │   │   ├── index.vue          # 策略编辑器 + 参数配置
    │   │   ├── result.vue         # 回测结果展示
    │   │   └── components/        # 图表组件
    │   └── paper-trading/         ← 新增：模拟交易前端模块
    │       ├── index.vue          # 模拟盘管理面板
    │       ├── detail.vue         # 单策略详情
    │       └── components/        # 图表/持仓组件
    └── api/
        └── quant.ts               # 回测 + 模拟交易 API
```

### 4.2 数据库新增表

```sql
-- 策略定义表
CREATE TABLE cn_quant_strategy (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code TEXT NOT NULL,                    -- Python 策略代码
    description TEXT,
    initial_cash DECIMAL(15,2) DEFAULT 1000000,
    benchmark VARCHAR(20) DEFAULT '000300',
    frequency ENUM('1d','1m') DEFAULT '1d',
    commission_rate DECIMAL(8,6) DEFAULT 0.000300,
    stamp_tax_rate DECIMAL(8,6) DEFAULT 0.001000,
    slippage DECIMAL(8,6) DEFAULT 0.000500,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('draft','active','archived') DEFAULT 'draft'
);

-- 回测任务表
CREATE TABLE cn_quant_backtest (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_cash DECIMAL(15,2),
    status ENUM('pending','running','completed','failed') DEFAULT 'pending',
    started_at DATETIME,
    completed_at DATETIME,
    error_message TEXT,
    -- 汇总指标（完成后写入）
    total_return DECIMAL(10,6),
    annual_return DECIMAL(10,6),
    max_drawdown DECIMAL(10,6),
    sharpe_ratio DECIMAL(10,6),
    alpha DECIMAL(10,6),
    beta DECIMAL(10,6),
    win_rate DECIMAL(10,6),
    trade_count INT,
    FOREIGN KEY (strategy_id) REFERENCES cn_quant_strategy(id)
);

-- 每日净值表（回测结果）
CREATE TABLE cn_quant_daily_nav (
    id INT AUTO_INCREMENT PRIMARY KEY,
    backtest_id INT NOT NULL,
    date DATE NOT NULL,
    nav DECIMAL(15,6) NOT NULL,            -- 单位净值
    benchmark_nav DECIMAL(15,6),           -- 基准净值
    cash DECIMAL(15,2),                    -- 当日现金
    market_value DECIMAL(15,2),            -- 持仓市值
    total_value DECIMAL(15,2),             -- 总资产
    daily_return DECIMAL(10,6),            -- 日收益率
    benchmark_return DECIMAL(10,6),        -- 基准日收益率
    UNIQUE KEY (backtest_id, date),
    FOREIGN KEY (backtest_id) REFERENCES cn_quant_backtest(id)
);

-- 交易记录表
CREATE TABLE cn_quant_trade (
    id INT AUTO_INCREMENT PRIMARY KEY,
    backtest_id INT,                       -- 回测 ID（回测时非空）
    paper_id INT,                          -- 模拟盘 ID（模拟时非空）
    date DATE NOT NULL,
    code VARCHAR(6) NOT NULL,
    name VARCHAR(20),
    direction ENUM('buy','sell') NOT NULL,
    price DECIMAL(10,3) NOT NULL,
    amount INT NOT NULL,                   -- 成交股数
    value DECIMAL(15,2),                   -- 成交金额
    commission DECIMAL(10,2),              -- 佣金
    tax DECIMAL(10,2),                     -- 印花税
    slippage_cost DECIMAL(10,2),           -- 滑点成本
    INDEX (backtest_id, date),
    INDEX (paper_id, date)
);

-- 持仓快照表
CREATE TABLE cn_quant_position_snapshot (
    id INT AUTO_INCREMENT PRIMARY KEY,
    backtest_id INT,
    paper_id INT,
    date DATE NOT NULL,
    code VARCHAR(6) NOT NULL,
    name VARCHAR(20),
    amount INT NOT NULL,                   -- 持仓股数
    avg_cost DECIMAL(10,3),               -- 持仓均价
    close_price DECIMAL(10,3),            -- 当日收盘价
    market_value DECIMAL(15,2),           -- 市值
    profit DECIMAL(15,2),                 -- 浮动盈亏
    profit_rate DECIMAL(10,6),            -- 浮动盈亏率
    weight DECIMAL(10,6),                 -- 持仓权重
    INDEX (backtest_id, date),
    INDEX (paper_id, date)
);

-- 模拟交易实例表
CREATE TABLE cn_quant_paper_trading (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_id INT NOT NULL,
    initial_cash DECIMAL(15,2) DEFAULT 1000000,
    status ENUM('running','paused','stopped') DEFAULT 'running',
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_run_date DATE,
    -- 当前状态序列化（g 对象 + 持仓等）
    state_json LONGTEXT,
    FOREIGN KEY (strategy_id) REFERENCES cn_quant_strategy(id)
);
```

### 4.3 API 端点设计

#### 回测 API

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/quant/strategy` | 创建/保存策略 |
| GET | `/api/quant/strategy` | 获取策略列表 |
| GET | `/api/quant/strategy/:id` | 获取策略详情 |
| PUT | `/api/quant/strategy/:id` | 更新策略代码 |
| DELETE | `/api/quant/strategy/:id` | 删除策略 |
| POST | `/api/quant/backtest/run` | 启动回测 |
| GET | `/api/quant/backtest/:id` | 获取回测结果 |
| GET | `/api/quant/backtest/:id/nav` | 获取净值曲线 |
| GET | `/api/quant/backtest/:id/trades` | 获取交易记录 |
| GET | `/api/quant/backtest/:id/positions` | 获取持仓快照 |
| GET | `/api/quant/backtest/list` | 获取回测任务列表 |

#### 模拟交易 API

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/quant/paper/create` | 创建模拟盘 |
| POST | `/api/quant/paper/:id/pause` | 暂停 |
| POST | `/api/quant/paper/:id/resume` | 恢复 |
| POST | `/api/quant/paper/:id/stop` | 停止 |
| GET | `/api/quant/paper/:id` | 获取状态 |
| GET | `/api/quant/paper/:id/trades` | 交易记录 |
| GET | `/api/quant/paper/:id/positions` | 当前持仓 |
| GET | `/api/quant/paper/list` | 模拟盘列表 |

---

## 五、实现计划（分阶段）

### Phase 1: 回测引擎核心（2-3 周）

**目标**: 能运行简单的买卖策略并输出收益曲线

1. `context.py` — Portfolio / Position / Context 对象
2. `data_proxy.py` — 数据代理层（读取 K 线缓存）
3. `matching.py` — 基础撮合引擎（市价单 + 涨跌停检测）
4. `api.py` — `order()` / `order_target()` / `order_value()` / `history()` 等
5. `engine.py` — 回测主循环（逐日遍历 + 事件触发）
6. `risk_metrics.py` — Sharpe / MaxDrawdown / Alpha / Beta
7. 单元测试覆盖

### Phase 2: 回测 Web 集成（1-2 周）

1. `backtestEngineHandler.py` — 回测 API Handler
2. `quant.ts` — 前端 API 函数
3. `quant-backtest/index.vue` — 策略编辑器（Monaco Editor）
4. `quant-backtest/result.vue` — 回测结果（ECharts 曲线）
5. 路由注册 + 导航菜单

### Phase 3: 模拟交易（1-2 周）

1. `paper_engine.py` — 模拟交易引擎
2. `scheduler.py` — 定时触发（复用 cron 框架）
3. `state_manager.py` — 状态序列化/恢复
4. `paperTradingHandler.py` — 模拟交易 API
5. `paper-trading/*.vue` — 前端管理面板

### Phase 4: 增强功能（持续迭代）

1. 策略模板库（内置经典策略）
2. 因子分析 / 归因分析
3. 多策略组合优化
4. 自定义指标
5. 分钟级回测支持

---

## 六、可行性分析

### 6.1 数据可行性 ✅

| 需求 | 现状 | 评估 |
|------|------|------|
| 日 K 线历史 | `cache/hist/` 10年数据 | ✅ 完全满足 |
| 实时行情 | `cn_stock_spot` 每日更新 | ✅ 满足 |
| 交易日历 | `cn_stock_trade_date` | ✅ 满足 |
| 基本面数据 | `cn_stock_selection` 200+ 字段 | ✅ 满足 |
| 指数基准 | 需新增沪深300等指数日 K 线 | ⚠️ 需从数据源获取 |
| 涨跌停价格 | K 线数据含开高低收 | ✅ 可计算 |

### 6.2 技术可行性 ✅

| 需求 | 方案 | 评估 |
|------|------|------|
| 策略执行 | Python `exec()` + 受限命名空间 | ✅ 可行 |
| 回测性能 | 逐日遍历 5年 ≈ 1250 个交易日 | ✅ 秒级 |
| 数据加载 | 从 cache 读取 pickle | ✅ 已有 |
| 撮合引擎 | 模拟成交逻辑 | ✅ 较简单 |
| 前端编辑器 | Monaco Editor（VS Code 同款） | ✅ 成熟方案 |
| 图表展示 | 复用 ECharts | ✅ 已有 |

### 6.3 风险点

| 风险 | 影响 | 缓解 |
|------|------|------|
| 策略代码安全 | 用户代码可能执行危险操作 | 受限命名空间 + 超时机制 |
| 回测性能 | 大量股票 × 长时间可能慢 | 按需加载 + 缓存 |
| 指数数据缺失 | 无法计算 Alpha/Beta | 从 AkShare 获取沪深300 |
| 前端复杂度 | 策略编辑器 + 图表较复杂 | 分阶段实现 |

---

## 七、与现有系统的隔离策略

| 原则 | 说明 |
|------|------|
| 新增不修改 | 所有新功能在新目录/新文件中实现 |
| 数据只读 | 回测引擎只读 K 线缓存和 DB，不修改原有表 |
| 新增表 | 所有新表以 `cn_quant_` 前缀区分 |
| API 路径隔离 | 新 API 统一使用 `/api/quant/` 前缀 |
| 前端路由隔离 | 新页面在 `/quant-backtest/` 和 `/paper-trading/` 下 |
| 测试覆盖 | 每个模块配套单元测试 |
| 分支隔离 | 在 `backTest_dev` 分支开发，验证后再合并 |

---

## 八、聚宽 vs InStock 功能对比（MVP 范围）

| 聚宽功能 | MVP 是否包含 | 说明 |
|----------|------------|------|
| `initialize` + `handle_data` | ✅ | 核心策略框架 |
| `order/order_target/order_value` | ✅ | 基础下单 |
| `set_benchmark` | ✅ | 基准设定 |
| `set_order_cost` | ✅ | 交易成本 |
| `history/attribute_history` | ✅ | 历史数据 |
| `get_current_data` | ✅ | 当前数据 |
| 收益曲线 + 基准对比 | ✅ | 核心报告 |
| 风险指标（Sharpe等） | ✅ | 核心报告 |
| 交易明细 | ✅ | 核心报告 |
| 持仓分析 | ✅ | 核心报告 |
| 模拟交易 | ✅ | 日频版 |
| 分钟级回测 | ❌ Phase 4 | 数据量大 |
| Tick 级回测 | ❌ | 无 Tick 数据 |
| 期货交易 | ❌ | 仅 A 股 |
| 融资融券 | ❌ | 仅现金账户 |
| 投资组合优化器 | ❌ Phase 4 | 高级功能 |
| 因子分析 | ❌ Phase 4 | 高级功能 |
| Brinson 归因 | ❌ Phase 4 | 高级功能 |
