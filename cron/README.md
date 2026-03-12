# Cron 定时任务说明

本目录包含用于定时执行数据采集任务的脚本。

## 脚本概览

| 脚本 | 执行频率 | 作用 |
|------|---------|------|
| `cron.hourly/run_hourly` | 每小时 | 执行基础数据采集 |
| `cron.workdayly/run_workdayly` | 每个工作日 | 执行完整的每日任务（获取+K线缓存+分析一体） |
| `cron.workdayly/run_fetch` | 每个工作日 | **仅数据获取**（API调用，含数据新鲜度检查） |
| `cron.workdayly/run_kline_cache` | 每个工作日 | **K线缓存增量更新**（需 run_fetch 完成后执行） |
| `cron.workdayly/run_analysis` | 每个工作日 | **仅数据分析**（本地计算，含基本面选股） |
| `cron.monthly/run_monthly` | 每月 | 清理历史缓存数据 |

---

## 1. run_hourly - 每小时任务

**调用**: `instock/job/basic_data_daily_job.py`

**作用**: 采集实时股票基础数据（最新价、涨跌幅、成交量等）

**适用场景**: 收盘后（16:00-17:00）更新当日收盘行情数据，也可在交易时间内每小时执行获取盘中快照

---

## 2. run_workdayly - 每日任务（完整）

**调用**: `instock/job/execute_daily_job.py`

**执行步骤**（采用 5 阶段流水线架构，轻量任务优先，重量级操作放后）:

**Phase 0: 初始化**
1. **init_job** - 创建/初始化数据库

**Phase 1: 轻量级数据入库**（优先执行，确保关键数据不受后续 OOM 影响）
2. **Phase 1a** - 实时行情预加载（stock_data 单例）
3. **Phase 1b** - basic_data_daily_job - 股票/ETF实时行情入库（含数据新鲜度检查）
4. **Phase 1c** - selection_data_daily_job - 综合选股数据入库（含数据新鲜度检查）
5. **Phase 1d** - basic_data_other_daily_job - 资金流向、龙虎榜等扩展数据
6. **Phase 1e** - gpt_value_data_job - GPT综合选股（纯DB读取）
7. **Phase 1e2** - stock_spot_buy - 基本面选股（PE/PB/ROE筛选）
8. **Phase 1f** - basic_data_after_close_daily_job - 收盘后数据（大宗交易等）

**Phase 2: 重量级数据获取 — K线缓存批量更新**
9. **kline_cache_daily_job** - 历史K线缓存增量更新（~5000只股票，内存密集型）
   - 在1.6GB内存服务器上可能因OOM被杀，因此放在轻量级任务之后
   - 即使此步骤失败，Phase 1的关键数据已安全入库

**Phase 3: 数据分析**（流式处理，无 API 调用，峰值内存 < 100 MB）
10. **streaming_analysis_job** - 单次遍历所有股票，同时计算：
    - 技术指标（MACD/KDJ/RSI等）
    - K线形态识别（锤子线/十字星等）
    - 策略选股（放量突破/均线金叉等）
    - 指标二次筛选（买入/卖出信号）
    - 内置跳过检查：如果分析数据已由其他节点完成则自动跳过

**Phase 4: 回测与收尾**
11. **backtest_data_daily_job** - 策略回测数据（从缓存按需读取）
12. **数据健康检查** - 检查各核心表是否有当日数据

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

# 执行每日完整任务（获取+K线缓存+分析一体）
./cron/cron.workdayly/run_workdayly

# 仅执行数据获取（API调用部分，含数据新鲜度检查）
./cron/cron.workdayly/run_fetch

# 仅执行K线缓存增量更新（需 run_fetch 完成后执行）
./cron/cron.workdayly/run_kline_cache

# 仅执行数据分析（本地计算部分，含基本面选股）
./cron/cron.workdayly/run_analysis

# 执行月度清理（清理过期缓存）
./cron/cron.monthly/run_monthly

# 执行月度清理（全量清除所有缓存）
./cron/cron.monthly/run_monthly --all
```

### 配置 Crontab 自动执行

推荐使用**拆分模式**（获取、K线缓存、分析独立调度），避免数据获取阻塞分析任务：

```bash
# 编辑 crontab
crontab -e

# 添加以下内容（假设项目在 /root/SelectStock）：

# 盘中快照
30 12 * * 1-5 flock -xn /tmp/instock_hourly.lock /root/SelectStock/cron/cron.hourly/run_hourly
18 15 * * 1-5 flock -xn /tmp/instock_hourly.lock /root/SelectStock/cron/cron.hourly/run_hourly

# 数据获取 + 重试
0 18 * * 1-5 flock -xn /tmp/instock_fetch.lock /root/SelectStock/cron/cron.workdayly/run_fetch
0 1 * * 2-6 flock -xn /tmp/instock_fetch.lock /root/SelectStock/cron/cron.workdayly/run_fetch

# K线缓存更新（run_fetch 完成后自动检查前置条件）
30 18 * * 1-5 flock -xn /tmp/instock_kline.lock /root/SelectStock/cron/cron.workdayly/run_kline_cache
30 1 * * 2-6 flock -xn /tmp/instock_kline.lock /root/SelectStock/cron/cron.workdayly/run_kline_cache

# 数据分析 + 重试
0 22 * * 1-5 flock -xn /tmp/instock_analysis.lock /root/SelectStock/cron/cron.workdayly/run_analysis
30 0 * * 2-6 flock -xn /tmp/instock_analysis.lock /root/SelectStock/cron/cron.workdayly/run_analysis

# 月度清理
0 4 1 * * /root/SelectStock/cron/cron.monthly/run_monthly
```

> **说明**：
> - **拆分模式优势**：数据获取（5~15分钟）、K线缓存（20~60分钟）、分析（~10分钟）三者独立调度，互不阻塞
> - `flock -xn` 参数：`-x` 排他锁，`-n` 非阻塞（如果锁被占用则立即退出，不等待）
> - 获取、K线缓存、分析使用**不同的锁文件**，互不阻塞；`run_hourly` 也用独立锁文件避免与 `run_fetch` 写同一张表冲突
> - `run_kline_cache` 安排在 18:30，给 `run_fetch` 留 30 分钟完成时间；若 `run_fetch` 未完成，`run_kline_cache` 会自动跳过
> - 分析安排在22:00，给K线缓存更新留充足时间（后续增量更新速度很快）
> - 重试服务安排在凌晨（周二到周六），对应周一到周五的交易日数据

### Docker 环境 Cron 配置


Docker 容器内使用与上述相同的拆分模式，定时任务在 Dockerfile 中配置：

```crontab
# 盘中行情快照
0 12 * * 1-5 flock -xn /tmp/instock_hourly.lock /etc/cron.hourly/run_hourly
18 15 * * 1-5 flock -xn /tmp/instock_hourly.lock /etc/cron.hourly/run_hourly

# 收盘后数据获取 + 凌晨重试
0 18 * * 1-5 flock -xn /tmp/instock_fetch.lock /etc/cron.workdayly/run_fetch
0 1 * * 2-6 flock -xn /tmp/instock_fetch.lock /etc/cron.workdayly/run_fetch

# K线缓存更新 + 凌晨重试
30 18 * * 1-5 flock -xn /tmp/instock_kline.lock /etc/cron.workdayly/run_kline_cache
30 1 * * 2-6 flock -xn /tmp/instock_kline.lock /etc/cron.workdayly/run_kline_cache

# 数据分析 + 凌晨重试
0 22 * * 1-5 flock -xn /tmp/instock_analysis.lock /etc/cron.workdayly/run_analysis
30 2 * * 2-6 flock -xn /tmp/instock_analysis.lock /etc/cron.workdayly/run_analysis

# 月度缓存清理
0 4 1 * * /etc/cron.monthly/run_monthly
```

> **Docker 环境注意事项**：
> - 脚本路径为 `/etc/cron.*`（由 Dockerfile COPY 部署）
> - `PROJECT_ROOT=/data/InStock` 硬编码在脚本中（Docker 固定路径）
> - `PYTHONPATH=/data/InStock` 在 crontab 中设置

---

## 重试安全性（幂等性保证）

所有定时任务均设计为**可安全重试**，不会因重复执行导致数据冗余或资源浪费：

### 数据写入幂等性

| 操作 | 机制 | 重试安全 |
|------|------|---------|
| DB 数据入库 | `DELETE WHERE date=X` → `INSERT`（先删后插） | ✅ 重跑覆盖旧数据 |
| 并发写入 | `INSERT ... ON DUPLICATE KEY UPDATE`（Upsert） | ✅ 主键冲突自动更新 |
| K线缓存更新 | 增量模式：读 `.meta` 最后日期 → 只拉新数据 | ✅ 已有数据不重拉 |
| 回测计算 | 只处理 `backtest IS NULL` 的记录 | ✅ 已回测的不重算 |

### 防重复执行机制

| 机制 | 说明 |
|------|------|
| `flock -xn` | 排他锁+非阻塞：同类任务只能有一个在运行，后来者立即退出 |
| `is_trade_date()` | 非交易日自动跳过（节假日、周末） |
| `is_job_completed()` | `run_fetch` 整体完成检查（`cn_job_status` 表），避免重复获取 |
| `is_data_fresh()` | 各表数据新鲜度检查，已有完整数据时跳过该阶段 |
| `_is_analysis_done()` | 分析数据已存在（≥1000条）时自动跳过，避免低内存环境重复计算 |
| `_check_fetch_completed()` | `run_kline_cache` 检查 `run_fetch` 是否完成，未完成则跳过 |

### 资源消耗

- **重试时的 API 调用**：实时行情 API 返回最新快照（无历史累积），重试只是覆盖同一天的数据
- **K线缓存重试**：增量模式下，如果上次已成功更新，重试几乎零 I/O（`.meta` 显示已是最新）
- **分析重试**：如果上次已完成，`_is_analysis_done()` 检查通过后直接跳过，耗时<1秒

---

## 注意事项

1. **执行权限**: 脚本需要可执行权限
   ```bash
   chmod +x cron/cron.hourly/run_hourly
   chmod +x cron/cron.workdayly/run_workdayly
   chmod +x cron/cron.workdayly/run_fetch
   chmod +x cron/cron.workdayly/run_kline_cache
   chmod +x cron/cron.workdayly/run_analysis
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

数据写入采用 **Upsert（INSERT ... ON DUPLICATE KEY UPDATE）** 模式，保证重跑时数据不会重复，且并发写入不会因主键冲突而失败。同时数据库操作内置了重试机制（死锁、锁超时、连接异常等瞬态错误最多重试3次），提高了写入成功率。

### K线缓存增量更新

- 缓存使用 gzip 压缩的 pickle 文件（`.gzip.pickle` + `.meta`）
- 增量逻辑：读取缓存最后日期 → 只从数据源拉取新增数据 → 合并写入
- **缓存损坏**（如写入时崩溃导致文件截断）：下次读取时自动检测异常，触发全量重拉，不会永久丢失数据
- **API 拉取失败**：返回已有缓存数据，不覆盖写入，下次重试即可恢复

### 各 Job 异常恢复能力

| Job | 异常后重跑 | 可否补历史数据 | 说明 |
|-----|-----------|--------------|------|
| fetch_data_job | ✅ 恢复 | ✅ 增量更新 | 缓存机制，首次全量，后续补缺新增数据（低内存模式） |
| basic_data_daily_job | ✅ 恢复 | ❌ 仅当天 | 实时行情快照，数据源不提供历史回查 |
| selection_data_daily_job | ✅ 恢复 | ❌ 仅当天 | 同上，综合选股为实时快照 |
| basic_data_other_daily_job | ✅ 恢复 | ⚠️ 部分可 | 龙虎榜/资金流为实时，早盘抢筹/涨停原因可补 |
| indicators/kline/strategy | ✅ 恢复 | ✅ 可补跑 | 基于K线缓存计算，支持日期参数（流式处理，峰值内存<100MB） |
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

## 获取历史K线数据

系统默认获取 **10 年** 历史K线数据（可通过环境变量 `HIST_DATA_DEFAULT_YEARS` 调整）。
数据源优先级：东方财富 → 腾讯财经 → 新浪财经，自动容错切换。

### 方式一：使用 fetch_data_job.py（推荐）

```bash
cd /root/SelectStock/instock/job

# 拉取当前交易日的最新数据（增量更新，自动补缺）
python3 fetch_data_job.py

# 指定日期拉取
python3 fetch_data_job.py 2026-02-12
```

该脚本会自动执行：
1. 清理过期缓存（退市股票、除权除息数据）
2. 预加载全部股票的实时行情数据
3. 批量更新全部股票的历史K线缓存（低内存模式：每只股票处理完即释放，不保留在内存中）

> 首次运行需从 API 获取全量 10 年历史数据，耗时较长；后续运行只需补缺新增交易日数据，快速完成。

### 方式二：通过环境变量调整获取年数

```bash
# 默认 10 年，Docker 默认 3 年，可自行调整
export HIST_DATA_DEFAULT_YEARS=10
python3 fetch_data_job.py
```

### 方式三：使用 Python 脚本自定义获取

```python
import datetime, sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import instock.core.stockfetch as stf

# 获取单只股票历史K线（默认 10 年）
df = stf.fetch_stock_hist((datetime.datetime.now(), '000001'))

# 自定义年数
df = stf.fetch_stock_hist((datetime.datetime.now(), '000001'), years=5)

# 指定日期范围
df = stf.fetch_stock_hist((datetime.datetime.now(), '000001'),
                          date_start='20200101', date_end='20231231')

# 不使用缓存，强制从 API 获取最新数据
df = stf.fetch_stock_hist((datetime.datetime.now(), '000001'), is_cache=False)
```

### 方式四：强制重建全部缓存

```bash
# ⚠️ 清空缓存后重新获取（耗时较长）
rm -rf /root/SelectStock/instock/cache/hist
cd /root/SelectStock/instock/job
python3 fetch_data_job.py
```

### Docker 环境手动拉取

```bash
docker exec -it InStock bash
cd /data/InStock/instock/job

# 拉取最新数据
python3 fetch_data_job.py

# 临时调整历史年数
HIST_DATA_DEFAULT_YEARS=5 python3 fetch_data_job.py
```

---

## 单独执行各任务

如果只需要执行特定任务，可以直接运行对应的 Python 脚本：

```bash
cd /root/SelectStock

# 初始化数据库
python3 instock/job/init_job.py

# 数据获取（实时行情 + 历史K线 + 缓存清理）
python3 instock/job/fetch_data_job.py

# 基础数据采集
python3 instock/job/basic_data_daily_job.py

# 综合选股数据
python3 instock/job/selection_data_daily_job.py

# 分红、龙虎榜等数据
python3 instock/job/basic_data_other_daily_job.py

# 技术指标 + K线形态 + 策略选股（流式处理，低内存）
python3 instock/job/streaming_analysis_job.py

# 也可单独运行旧版独立脚本（会加载全量历史数据到内存，内存需求大）
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
