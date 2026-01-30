# 历史数据增量缓存功能说明

## 功能概述

本功能实现了股票历史K线数据的增量更新缓存机制，主要特点：

1. **增量更新**：以天为单位追加更新历史数据，避免每次全量获取
2. **多数据源**：优先使用新浪财经，备选东方财富
3. **自定义范围**：用户可以指定历史数据的获取年数或日期范围
4. **自动清理**：支持定期清理过期缓存数据

## 核心函数

### 1. `stock_hist_cache_incremental(code, date_start, date_end, is_cache=True, adjust='')`

增量更新的股票历史数据缓存函数。

**参数：**
- `code`: 股票代码，如 "000001"
- `date_start`: 起始日期，格式 YYYYMMDD
- `date_end`: 结束日期，格式 YYYYMMDD
- `is_cache`: 是否使用缓存，默认 True
- `adjust`: 复权类型，"qfq"前复权，"hfq"后复权，""不复权

**工作流程：**
1. 检查缓存是否存在
2. 如果有缓存，读取缓存中的最后日期
3. 只获取缓存最后日期之后的增量数据
4. 合并增量数据到缓存
5. 保存更新后的缓存

**数据源优先级：**
1. 新浪财经 (`stock_hist_sina.py`)
2. 东方财富 (`stock_hist_em.py`)

### 2. `fetch_stock_hist(data_base, date_start=None, date_end=None, is_cache=True, years=None)`

获取股票历史数据的高级接口。

**参数：**
- `data_base`: 元组 (日期, 股票代码)
- `date_start`: 起始日期，默认根据 years 计算
- `date_end`: 结束日期，默认当前日期
- `is_cache`: 是否使用缓存
- `years`: 历史数据年数，默认 3 年

### 3. `clean_expired_cache(expire_days=None)`

清理过期的缓存文件。

**参数：**
- `expire_days`: 过期天数，默认 7 天

## 配置参数

在 `stockfetch.py` 中可配置：

```python
# 数据源重试配置
DATA_SOURCE_MAX_RETRIES = 2      # 最大重试次数
DATA_SOURCE_RETRY_INTERVAL = 30  # 重试间隔（秒）

# 历史数据配置
HIST_DATA_DEFAULT_YEARS = 3      # 默认获取历史数据年数
HIST_DATA_CACHE_EXPIRE_DAYS = 7  # 缓存过期天数
```

## 缓存目录结构

```
instock/cache/hist/
├── 000/                    # 按股票代码前3位分组
│   ├── 000001.gzip.pickle  # 压缩的缓存数据
│   ├── 000001.meta         # 缓存元数据（最后更新日期）
│   ├── 000002.gzip.pickle
│   └── 000002.meta
├── 600/
│   ├── 600000.gzip.pickle
│   └── 600000.meta
└── ...
```

## 使用示例

```python
import datetime
import instock.core.stockfetch as stf

# 示例1: 使用默认配置（3年历史数据）
data_base = (datetime.datetime.now(), '000001')
df = stf.fetch_stock_hist(data_base)

# 示例2: 自定义日期范围
df = stf.fetch_stock_hist(data_base, date_start='20230101', date_end='20231231')

# 示例3: 自定义年数
df = stf.fetch_stock_hist(data_base, years=5)

# 示例4: 直接使用增量缓存函数
df = stf.stock_hist_cache_incremental('000001', '20240101', '20240630')

# 示例5: 清理过期缓存
cleaned = stf.clean_expired_cache(expire_days=30)
print(f'清理了 {cleaned} 个过期缓存文件')
```

## 数据源模块

### 新浪财经历史数据 (`stock_hist_sina.py`)

```python
from instock.core.crawling.stock_hist_sina import stock_zh_a_hist_sina

df = stock_zh_a_hist_sina(
    symbol="000001",
    period="daily",      # daily, weekly, monthly
    start_date="20240101",
    end_date="20240630",
    adjust=""            # "", "qfq", "hfq"
)
```

## 性能优势

1. **减少网络请求**：增量更新只获取新数据，减少API调用
2. **提高响应速度**：缓存命中时直接返回本地数据
3. **数据源容错**：多数据源自动切换，提高可用性
4. **存储优化**：使用gzip压缩，节省磁盘空间

## 注意事项

1. 缓存数据按股票代码组织，而非按日期
2. 增量更新以天为单位，每次只获取缺失的交易日数据
3. 元数据文件记录最后更新时间，用于缓存过期判断
4. 建议定期调用 `clean_expired_cache()` 清理过期缓存
