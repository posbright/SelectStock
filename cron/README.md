# Cron 定时任务说明

本目录包含用于定时执行数据采集任务的脚本。

## 脚本概览

| 脚本 | 执行频率 | 作用 |
|------|---------|------|
| `cron.hourly/run_hourly` | 每小时 | 执行基础数据采集 |
| `cron.workdayly/run_workdayly` | 每个工作日 | 执行完整的每日任务 |
| `cron.monthly/run_monthly` | 每月 | 清理历史缓存数据 |

---

## 1. run_hourly - 每小时任务

**调用**: `instock/job/basic_data_daily_job.py`

**作用**: 采集实时股票基础数据（最新价、涨跌幅、成交量等）

**适用场景**: 交易时间内（9:30-15:00）每小时更新数据

---

## 2. run_workdayly - 每日任务（完整）

**调用**: `instock/job/execute_daily_job.py`

**执行步骤**:

1. **init_job** - 创建/初始化数据库
2. **basic_data_daily_job** - 股票基础数据
3. **selection_data_daily_job** - 综合选股数据
4. **basic_data_other_daily_job** - 分红、龙虎榜、大宗交易等（并行）
5. **indicators_data_daily_job** - 技术指标数据（并行）
6. **klinepattern_data_daily_job** - K线形态识别（并行）
7. **strategy_data_daily_job** - 策略选股数据（并行）
8. **gpt_value_data_job** - GPT综合选股（并行）
9. **backtest_data_daily_job** - 策略回测数据
10. **basic_data_after_close_daily_job** - 收盘后数据

**适用场景**: 每个交易日收盘后运行（建议18:00后执行）

---

## 3. run_monthly - 每月任务

**作用**: 智能清理 `instock/cache/hist/` 目录下的历史K线缓存

**清理策略**:
- 默认模式（智能清理）：
  - 删除已退市股票的缓存（不在当前活跃股票列表中的）
  - 刷新近期有除权除息股票的前复权缓存（除权后历史价格需要重算）
  - 清理损坏的缓存文件
  - **保留**活跃股票、停牌股票、长假期间的缓存（历史数据不可变，不因未更新而误删）
- 全量模式：使用 `--all` 参数删除所有缓存（下次运行将全量重新拉取，耗时较长）

**适用场景**: 定期清理退市/除权缓存，释放磁盘空间

---

## 使用方法

### 手动执行

```bash
# 执行每小时任务
./cron/cron.hourly/run_hourly

# 执行每日完整任务
./cron/cron.workdayly/run_workdayly

# 执行月度清理（清理过期缓存）
./cron/cron.monthly/run_monthly

# 执行月度清理（全量清除所有缓存）
./cron/cron.monthly/run_monthly --all
```

### 配置 Crontab 自动执行

```bash
# 编辑 crontab
crontab -e

# 添加以下内容（假设项目在 /root/SelectStock）：

# 每小时执行（交易日9:30-15:00）
#30 9-15 * * 1-5 /root/SelectStock/cron/cron.hourly/run_hourly

# 每个工作日18:00执行完整任务
0 18 * * 1-5 /root/SelectStock/cron/cron.workdayly/run_workdayly

# 每月1日凌晨2点清理缓存
0 2 1 * * /root/SelectStock/cron/cron.monthly/run_monthly
```

---

## 注意事项

1. **执行权限**: 脚本需要可执行权限
   ```bash
   chmod +x cron/cron.hourly/run_hourly
   chmod +x cron/cron.workdayly/run_workdayly
   chmod +x cron/cron.monthly/run_monthly
   ```

2. **Python 环境**: 确保系统 Python3 已安装所需依赖
   ```bash
   pip3 install -r requirements.txt
   ```

3. **数据库配置**: 数据库连接配置在 `instock/lib/database.py` 中

4. **日志位置**: 任务执行日志保存在 `instock/log/` 目录下

5. **交易日判断**: 系统会自动判断是否为交易日，非交易日不会采集数据

---

## 异常恢复与数据完整性

### 数据写入机制

所有 Job 使用 **先删后插（DELETE + INSERT）** 模式写入数据库，保证重跑时数据不会重复。但 DELETE 和 INSERT 不在同一个事务中（`autocommit=True`），如果 DELETE 执行后程序崩溃，当次数据会暂时缺失，需要下次重跑恢复。

### K线缓存增量更新

- 缓存使用 gzip 压缩的 pickle 文件（`.gzip.pickle` + `.meta`）
- 增量逻辑：读取缓存最后日期 → 只从数据源拉取新增数据 → 合并写入
- **缓存损坏**（如写入时崩溃导致文件截断）：下次读取时自动检测异常，触发全量重拉，不会永久丢失数据
- **API 拉取失败**：返回已有缓存数据，不覆盖写入，下次重试即可恢复

### 各 Job 异常恢复能力

| Job | 异常后重跑 | 可否补历史数据 | 说明 |
|-----|-----------|--------------|------|
| basic_data_daily_job | ✅ 恢复 | ❌ 仅当天 | 实时行情快照，数据源不提供历史回查 |
| selection_data_daily_job | ✅ 恢复 | ❌ 仅当天 | 同上，综合选股为实时快照 |
| basic_data_other_daily_job | ✅ 恢复 | ⚠️ 部分可 | 龙虎榜/资金流为实时，早盘抢筹/涨停原因可补 |
| indicators_data_daily_job | ✅ 恢复 | ✅ 可补跑 | 基于K线缓存计算，支持日期参数 |
| klinepattern_data_daily_job | ✅ 恢复 | ✅ 可补跑 | 基于K线缓存计算，支持日期参数 |
| strategy_data_daily_job | ✅ 恢复 | ✅ 可补跑 | 基于K线缓存计算，支持日期参数 |
| gpt_value_data_job | ✅ 恢复 | ⚠️ 需数据 | 依赖 `cn_stock_selection` 表有对应日期数据 |
| backtest_data_daily_job | ✅ 恢复 | ✅ 自动补 | 查询 NULL 字段自动补填，天然幂等 |
| basic_data_after_close_daily_job | ✅ 恢复 | ✅ 可补跑 | 大宗交易等，支持日期参数 |

### 补跑历史数据

对于支持日期参数的 Job，可以手动补跑指定日期：

```bash
cd /root/SelectStock

# 补跑单个日期
python3 instock/job/strategy_data_daily_job.py 2026-02-06

# 补跑日期区间
python3 instock/job/strategy_data_daily_job.py 2026-02-01 2026-02-06

# 补跑多个指定日期
python3 instock/job/indicators_data_daily_job.py 2026-02-03,2026-02-05
```

> **注意**：`save_nph_*` 前缀的函数（实时快照类数据）不支持历史日期参数，补跑时会自动跳过。

---

## 单独执行各任务

如果只需要执行特定任务，可以直接运行对应的 Python 脚本：

```bash
cd /root/SelectStock

# 初始化数据库
python3 instock/job/init_job.py

# 基础数据采集
python3 instock/job/basic_data_daily_job.py

# 综合选股数据
python3 instock/job/selection_data_daily_job.py

# 分红、龙虎榜等数据
python3 instock/job/basic_data_other_daily_job.py

# 技术指标数据
python3 instock/job/indicators_data_daily_job.py

# K线形态识别
python3 instock/job/klinepattern_data_daily_job.py

# 策略选股数据
python3 instock/job/strategy_data_daily_job.py

# 策略回测数据
python3 instock/job/backtest_data_daily_job.py

# 收盘后数据
python3 instock/job/basic_data_after_close_daily_job.py
```
