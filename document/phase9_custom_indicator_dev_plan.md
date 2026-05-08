# Phase 9 — 自定义复合指标 + 中长期 Alpha 落地开发计划

> **Status**: 🟡 待评审 (created 2026-05-08, branch `backTest_dev`)
> **基础**: V2/V3/V4/V5/V6 全部实证完成；本文档将所有结论落地为可执行的 PR。
> **请审核**：本文档定稿后才开始 PR-1 实施。所有"待实施"代码均未写入任何文件。

---

## 0. 实证结论汇总（V6 投资组合级回测最终数据）

`_compare_composite_winrate_v6_portfolio.py` — 1,000,000 起始资金，最多 8 仓并发，每仓 12.5%，扣 0.36% 双边成本，89 只基本面预筛股票，2020-01 ~ 2025-12，约 6 年。

### 60 天持仓窗口（止损 -8% / 止盈 +20%）

| 策略 | 笔数 | 胜率 | 总收益 | CAGR | 最大回撤 | Sharpe |
|---|---|---|---|---|---|---|
| **S12+T3 双信号** | **462** | **40.9%** | **+277.6%** | **24.79%** | **-29.0%** | **1.21** |
| T3 单独 | 439 | 40.1% | +225.2% | 21.72% | -30.4% | 1.13 |
| BH 60d 定投 | 398 | 35.9% | +70.8% | 9.33% | -25.6% | 0.59 |
| S12 单独 | 93 | 47.3% | +62.1% | 8.38% | -10.5% | **1.02** |
| M1 评分预警 | 647 | 34.2% | +43.4% | 6.19% | **-53.8%** | 0.38 |

### 120 天持仓窗口（止损 -12% / 止盈 +40%）

| 策略 | 笔数 | 胜率 | 总收益 | CAGR | 最大回撤 | Sharpe |
|---|---|---|---|---|---|---|
| **S12+T3 双信号** | **216** | **42.6%** | **+316.3%** | **26.83%** | -32.5% | **1.18** |
| M1 评分预警 | 298 | 34.2% | +194.0% | 19.69% | -40.2% | 0.84 |
| T3 单独 | 215 | 40.0% | +187.9% | 19.27% | -31.2% | 0.92 |
| **S12 单独** | **86** | **47.7%** | **+143.8%** | **16.01%** | **-19.6%** | **1.22** |
| BH 60d 定投 | 211 | 33.6% | +69.1% | 9.15% | -50.2% | 0.52 |

### 关键结论

1. **🏆 S12+T3 双信号在 120d 窗口 CAGR 26.8%、Sharpe 1.18 是绝对 Alpha 冠军**
2. **⚖️ S12 单独在 120d 窗口 Sharpe 1.22 + 回撤仅 -19.6% 是风险调整后的最佳策略**
3. **❌ M1 评分类指标在 60d 窗口最大回撤 -53.8% — 绝对禁止作为主交易信号**
4. ✅ 评分类指标 (M1) 仅适合做"今日值得关注"watchlist
5. ✅ 不择时定投 BH 在并发约束下 CAGR 仅 9.3%，远低于双信号策略 — 择时仍有价值

---

## 1. Phase 9 范围定义

### 1.1 必须交付（MVP）

| # | 功能 | 优先级 |
|---|---|---|
| F1 | 自定义复合指标（CRUD + 加权评分计算） | P0 |
| F2 | 触发模式：cross_down / cross_up / persistent / hard_AND_chain | P0 |
| F3 | 指标类型标签：`primary_entry` (硬规则) / `watchlist_alert` (评分类) | P0 |
| F4 | 单股历史回测视图（k 线 + 信号点 + 评分曲线） | P0 |
| F5 | 内置三档预设：稳健 (S12-60d) / 进攻 (S12+T3-120d) / 预警 (M1-watchlist) | P0 |
| F6 | 投资组合级回测 + 止损止盈参数 + 并发约束 | P1 |
| F7 | 指标范式守门（评分类禁止直接落库为 strategy_template） | P1 |

### 1.2 不在 Phase 9 范围（推到 Phase 10+）

- 实时推送 watchlist 到 IM（需要先做完 Phase 8 的安全收口）
- 多因子机器学习（XGBoost 选股）
- 期权 / 商品 / 美股扩展
- 实盘连接交易接口

---

## 2. 数据库 Schema 改动

### 2.1 新增表 `cn_stock_custom_indicator`

```sql
CREATE TABLE IF NOT EXISTS `cn_stock_custom_indicator` (
  `id`           INT AUTO_INCREMENT PRIMARY KEY,
  `indicator_id` VARCHAR(64)  NOT NULL UNIQUE COMMENT '业务 ID, e.g. user_001_master',
  `name`         VARCHAR(128) NOT NULL,
  `kind`         ENUM('primary_entry','watchlist_alert') NOT NULL,
  `description`  TEXT,
  `weights`      JSON         NOT NULL COMMENT '加权评分组件 e.g. {"n_rsi14":0.1,...}',
  `smooth_ema`   TINYINT      DEFAULT 0,
  `buy_th`       FLOAT        DEFAULT 50,
  `direction`    ENUM('low','high') NOT NULL DEFAULT 'high',
  `extra_filter` TEXT         COMMENT 'Python 表达式字符串, eval 在受限作用域',
  `hard_rules`   TEXT         COMMENT '可选: AND 链规则 (Python 表达式), kind=primary_entry 必填',
  `risk_profile` JSON         NOT NULL COMMENT '{"stop":-0.08,"target":0.2,"max_hold":60}',
  `owner`        VARCHAR(64)  NOT NULL DEFAULT 'system',
  `is_builtin`   TINYINT      DEFAULT 0,
  `created_at`   DATETIME     DEFAULT CURRENT_TIMESTAMP,
  `updated_at`   DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX `ix_kind` (`kind`),
  INDEX `ix_owner` (`owner`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 2.2 自动迁移

- 沿用现有约定：在 `instock/web/portfolioBacktestHandler.py` 新增 `_ensure_custom_indicator_table()`，在模块加载时调用
- 不使用 Alembic（项目历史风格），保持一致

### 2.3 内置数据

启动时 `_seed_builtin_indicators()` 写入三条记录（如果不存在）：

| indicator_id | name | kind | 来源 |
|---|---|---|---|
| `builtin_s12_steady` | 稳健·S12 超跌反弹 | primary_entry | V4-V6 实证 PF 1.81~3.63 |
| `builtin_s12_t3_aggressive` | 进攻·S12+T3 双信号 | primary_entry | V6 CAGR 26.8% |
| `builtin_m1_watchlist` | 预警·M1 综合评分 | watchlist_alert | V5 范式守门示例 |

---

## 3. 后端代码改动

### 3.1 新增模块 `instock/core/composite/`

```
instock/core/composite/
├── __init__.py
├── normalizers.py      # n_lin / n_rank / n_wr / n_supertrend / n_cci ... (从 _v2.py 抽出)
├── indicators_enrich.py # enrich(df) -> 加 n_* 列 (从 _v2.py 抽出)
├── composite_engine.py  # Composite 数据类 + .value(d) + .signal(d) (从 _v2.py 抽出)
├── hard_rules_engine.py # 解析 hard_rules 表达式 -> bool Series
├── risk_simulator.py    # simulate(code, df, sig, sl, tp, max_hold) (从 _v3.py 抽出)
└── builtins.py          # S12 / T3 / E1-3 / MASTER / M1 等可复用函数
```

**职责分离原则**：
- `_v2/_v3/_v4/_v5/_v6` 这些根目录脚本**不动**（实证存档）
- 所有生产代码从这些脚本"提炼"到 `instock/core/composite/`
- 单元测试覆盖：normalizers 数值正确性、composite_engine 触发方向、hard_rules eval 沙箱安全

### 3.2 新增 Web Handler

文件：`instock/web/customIndicatorHandler.py`（新建）

```python
class ListCustomIndicatorHandler(...)        # GET  /instock/api/custom_indicator/list
class GetCustomIndicatorHandler(...)         # GET  /instock/api/custom_indicator/detail?id=
class SaveCustomIndicatorHandler(...)        # POST /instock/api/custom_indicator/save
class DeleteCustomIndicatorHandler(...)      # POST /instock/api/custom_indicator/delete
class BacktestCustomIndicatorHandler(...)    # POST /instock/api/custom_indicator/backtest
class WatchlistTodayHandler(...)             # GET  /instock/api/custom_indicator/watchlist?id=
```

### 3.3 路由注册

在 `instock/web/web_service.py` 第 ~110 行处增 6 条路由

### 3.4 范式守门 (F7)

`SaveCustomIndicatorHandler` 的校验逻辑：
- `kind=primary_entry` ⇒ 必须有 `hard_rules` 表达式且通过 sandbox 解析
- `kind=watchlist_alert` ⇒ 允许只有 weights，但 UI 上始终标红色 "仅供参考，禁止实盘"
- 评分类指标的 `direction` 强制 `high`（V5 实证唯一有效改动）

### 3.5 表达式 Sandbox

`hard_rules_engine.py` 使用 `compile(..., mode='eval') + eval(..., {'__builtins__': {}}, safe_locals)`，
`safe_locals` 只暴露 `d`（DataFrame）+ pandas/numpy 子集。
**禁止** `import / open / __` 关键字（白名单 AST 节点检查）。

---

## 4. 前端改动

### 4.1 新增页面 `/customIndicator.html`

复用 `portfolioBacktest.html` 的 Vue 3 + Element Plus 框架：

- 左侧：指标列表 + 新建按钮
- 右侧编辑面板：
  - 基本信息：name / kind (radio: 主信号 / 预警类) / description
  - **kind=primary_entry**：硬规则编辑器（多行表达式，支持快速插入：`d['ma5']>d['ma20']` 等）
  - **kind=watchlist_alert**：权重表格（可加减行，组件下拉选择，权重数字输入）
  - 触发参数：smooth_ema / buy_th / direction
  - 风控参数：stop_loss / take_profit / max_hold
  - 实时回测按钮 → 显示单股回测结果 (PF / CAGR / DD / 净值曲线)
- **顶部红色横幅**：当 kind=watchlist_alert 时显示「⚠️ 评分类指标，仅做今日值得关注列表，禁止直接驱动交易」

### 4.2 文件清单

```
instock/web/static/customIndicator.html              # 新建 ~80 行
instock/web/static/js/custom_indicator.js            # 新建 ~600 行 Vue 组件
instock/web/static/css/custom_indicator.css          # 新建 ~80 行
instock/web/static/index.html                        # 加导航菜单项
```

### 4.3 在投资组合回测页加"导入自定义指标"

`portfolioBacktest.html`：策略下拉框旁加按钮「从自定义指标导入」→ 弹窗只列出 `kind=primary_entry` 的项 → 选中后自动生成对应 strategy code。

---

## 5. 测试计划

### 5.1 单元测试

| 文件 | 用例数 | 覆盖范围 |
|---|---|---|
| `tests/test_composite_normalizers.py` | ~12 | n_lin / n_rank / n_wr / n_supertrend 边界与 NaN |
| `tests/test_composite_engine.py` | ~8 | direction='low'/'high' 触发、smooth_ema、extra_filter |
| `tests/test_hard_rules_engine.py` | ~10 | sandbox 安全（拒绝 import/open）、eval 正确性 |
| `tests/test_risk_simulator.py` | ~6 | stop/target/time-exit 三路径、T+1 进场 |
| `tests/test_custom_indicator_handler.py` | ~14 | CRUD、kind 守门、内置 seed |

总计 ~50 个新测试，加在现有 325 个之后保持全绿。

### 5.2 集成回归

- 确保 `pytest tests/ -q` 全部通过
- 用内置 `builtin_s12_steady` 在 UI 上跑一遍 89 股 6 年回测，验证 CAGR ≈ V6 数据 ±2% 内（容许并发实现差异）

### 5.3 Sandbox 安全测试

```python
def test_hard_rules_blocks_import():
    with pytest.raises(SecurityError):
        parse_hard_rules("__import__('os').system('rm -rf /')")
```

---

## 6. PR 拆分（每个 PR 独立可合）

### PR-1 — 后端核心抽取（无 UI）

**Scope**：建表迁移 + `instock/core/composite/` 全套模块 + 单元测试 + 三条内置指标 seed
**预计变更**：~1500 行新代码 + ~50 个测试
**完成后可独立运行**：`pytest tests/test_composite_*.py` 全绿；REST API 用 curl 验证

### PR-2 — Web Handler + REST API

**Scope**：`customIndicatorHandler.py` + 路由 + handler 单元测试
**依赖**：PR-1 已合并
**预计变更**：~600 行
**完成后可独立运行**：所有 6 个 API 用 curl 通过；UI 暂未对接

### PR-3 — 前端编辑器 + 内置预设浏览

**Scope**：`customIndicator.html` 三页面 + 导航菜单
**依赖**：PR-2 已合并
**预计变更**：~800 行 Vue + CSS
**完成后可独立运行**：UI 上完成 CRUD + 单股回测预览

### PR-4 — 投资组合集成 + 范式守门 UI

**Scope**：`portfolioBacktest.html` 加"导入自定义指标"+ watchlist 红色警告横幅 + watchlist 今日列表页面
**依赖**：PR-3 已合并
**预计变更**：~400 行
**完成后可独立运行**：在投资组合回测页能选中 `builtin_s12_t3_aggressive` 跑出 V6 量级的 CAGR

---

## 7. 时间盒 / 里程碑

> 不给具体时间估算（按 instructions 要求）。但定义检查点：

| 检查点 | 进入条件 |
|---|---|
| **CP1** | PR-1 通过本地 pytest 全绿；3 条内置指标在 MySQL 落库 |
| **CP2** | PR-2 通过 curl 测试 6 个 API；范式守门拒绝错误 kind |
| **CP3** | PR-3 在浏览器手动操作完成 CRUD + 回测预览；watchlist 红色横幅显示 |
| **CP4** | PR-4 在投资组合回测页跑通 `builtin_s12_t3_aggressive`，CAGR 偏差 < 5% |

每个检查点完成后用户确认 → 进入下一 PR。

---

## 8. 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| Sandbox 表达式逃逸 | AST 白名单 + ban `__` 前缀 + ban 关键 builtins |
| 评分类指标被滥用为实盘信号 | DB 层 ENUM 约束 + Handler 校验 + UI 红色横幅三重防线 |
| 投资组合回测性能（89 股 × 6 年） | V6 实测 89 股 ~30 秒，可接受；UI 加 progress bar |
| MASTER 调参陷阱（V5 教训） | 内置预设固定参数 + UI 上写"此为实证最优，慎修改" |
| 基本面预筛前视偏差 | 预设说明文字标明，并在 PR-5 (后续阶段) 接入历史财报快照 |
| 现有 325 测试回归 | 每个 PR 跑全量回归 |

---

## 9. 文档同步

每个 PR 合并时同步更新：

- `document/QUANT_BACKTEST_DEV.md` — 加 §10 自定义指标 API 说明
- `document/API_REFERENCE.md` — 加 6 个新 endpoint
- `README.md` — 在功能列表加一条
- `/memories/repo/` — 创建 `phase9_custom_indicator.md` 记录 schema + 关键约束

---

## 10. 实施前的最后核对项（请用户确认）

请用户确认以下决策点后开始 PR-1：

- [ ] **核对 1**：内置预设是否就用 `builtin_s12_steady` / `builtin_s12_t3_aggressive` / `builtin_m1_watchlist` 三个？还是用其他名字？
- [ ] **核对 2**：股票池是否依然用基本面预筛 89 只 (`_phase9_top100.pkl`)？还是改成动态从 `cn_stock_selection` 实时取 Top 100？
- [ ] **核对 3**：`max_concurrent` 仓位数是否就 8（V6 实测值）？用户实盘资金量是多少？
- [ ] **核对 4**：UI 是否需要支持用户编辑硬规则（kind=primary_entry）？还是仅允许查看 + 复制内置？
- [ ] **核对 5**：是否同意"评分类禁止直接驱动交易"的强约束？这会限制部分用户期望的灵活性
- [ ] **核对 6**：PR-1~PR-4 是否一次性合并到 `backTest_dev`？还是每个 PR 等用户体验确认？

---

## 11. 文档关联

- V2 报告：[document/custom_indicator_winrate_analysis.md](custom_indicator_winrate_analysis.md)
- V3 报告：[document/custom_indicator_winrate_analysis_v3_fundamentals_sl_tp.md](custom_indicator_winrate_analysis_v3_fundamentals_sl_tp.md)
- V4/V5 报告：[document/medium_long_term_holding_analysis.md](medium_long_term_holding_analysis.md)
- 指标百科：[document/technical_indicators_guide_and_optimal_combo.md](technical_indicators_guide_and_optimal_combo.md)
- V6 投资组合回测脚本：[_compare_composite_winrate_v6_portfolio.py](../_compare_composite_winrate_v6_portfolio.py)
- 本文：[document/phase9_custom_indicator_dev_plan.md](phase9_custom_indicator_dev_plan.md)
