# 选股策略模块

## 目录结构

```
instock/core/strategy/
├── __init__.py           # 模块入口,导出所有策略
├── base.py               # 策略基类和注册表
├── technical/            # 技术指标策略
│   ├── __init__.py
│   └── ma_strategies.py  # 均线相关策略
├── volume/               # 成交量策略
│   ├── __init__.py
│   └── volume_strategies.py
├── pattern/              # 形态策略
│   ├── __init__.py
│   └── pattern_strategies.py
└── [旧策略文件...]       # 保留兼容性
```

## 策略分类

### 技术指标策略 (technical)

| 策略类名 | 中文名 | 表名 | 说明 |
|---------|-------|------|------|
| `MABullishStrategy` | 均线多头 | cn_stock_strategy_keep_increasing | MA30均线持续上涨超20% |
| `MA250PullbackStrategy` | 回踩年线 | cn_stock_strategy_backtrace_ma250 | 突破年线后回踩不破 |
| `TurtleTradingStrategy` | 海龟交易法则 | cn_stock_strategy_turtle_trade | 突破60日新高 |
| `LowATRGrowthStrategy` | 低ATR成长 | cn_stock_strategy_low_atr | 低波动稳健上涨 |

### 成交量策略 (volume)

| 策略类名 | 中文名 | 表名 | 说明 |
|---------|-------|------|------|
| `VolumeIncreaseStrategy` | 放量上涨 | cn_stock_strategy_enter | 放量上涨超2%,量比超2 |
| `ClimaxLimitdownStrategy` | 放量跌停 | cn_stock_strategy_climax_limitdown | 放量跌停,可能恐慌抛售 |

### 形态策略 (pattern)

| 策略类名 | 中文名 | 表名 | 说明 |
|---------|-------|------|------|
| `BreakthroughPlatformStrategy` | 突破平台 | cn_stock_strategy_breakthrough_platform | 放量突破60日均线 |
| `ParkingApronStrategy` | 停机坪 | cn_stock_strategy_parking_apron | 涨停后横盘整理 |
| `HighTightFlagStrategy` | 高而窄的旗形 | cn_stock_strategy_high_tight_flag | 快速上涨后窄幅整理 |
| `LowBacktraceIncreaseStrategy` | 无大幅回撤 | cn_stock_strategy_low_backtrace_increase | 稳健上涨无大幅回撤 |

## 使用方法

### 1. 使用新的类方式（推荐）

```python
from instock.core.strategy import VolumeIncreaseStrategy

# 创建策略实例
strategy = VolumeIncreaseStrategy(threshold=60)

# 检查股票是否符合条件
result = strategy.check(code_name, data, date)
```

### 2. 使用策略注册表

```python
from instock.core.strategy.base import get_strategy, get_all_strategies

# 获取单个策略
strategy_cls = get_strategy('enter')
strategy = strategy_cls()
result = strategy.check(code_name, data, date)

# 获取所有策略
all_strategies = get_all_strategies()
for name, cls in all_strategies.items():
    print(f"{name}: {cls.cn_name}")
```

### 3. 使用兼容性函数（旧接口）

```python
from instock.core.strategy import enter

# 旧接口仍可用
result = enter.check_volume(code_name, data, date, threshold=60)
```

## 创建新策略

### 继承基类

```python
from instock.core.strategy.base import TechnicalStrategy, register_strategy

@register_strategy
class MyNewStrategy(TechnicalStrategy):
    name = "my_new_strategy"
    cn_name = "我的新策略"
    default_threshold = 60
    description = "策略描述"
    
    def check(self, code_name, data, date=None, **kwargs):
        data = self.prepare_data(code_name, data, date)
        if data is None:
            return False
        
        # 策略逻辑...
        
        return True
```

### 基类可用方法

- `TechnicalStrategy`:
  - `calc_ma(data, column, period)` - 计算移动平均
  - `calc_ema(data, column, period)` - 计算指数移动平均
  - `calc_atr(data, period)` - 计算ATR

- `VolumeStrategy`:
  - `calc_vol_ma(data, period)` - 计算成交量移动平均
  - `calc_amount(data, row_index)` - 计算成交额

## Backtrader 回测集成

### 使用回测引擎

```python
from instock.core.backtest import BacktestEngine, BACKTRADER_AVAILABLE

if BACKTRADER_AVAILABLE:
    # 创建回测引擎
    engine = BacktestEngine(initial_cash=100000)
    
    # 添加数据
    engine.add_data(stock_data)
    
    # 添加信号策略
    engine.add_signal_strategy(
        signal_dates=['2024-01-15', '2024-02-20'],
        hold_days=5,
        position_pct=0.1
    )
    
    # 运行回测
    results = engine.run()
    print(f"总收益: {results['total_return']:.2f}%")
    
    # 绘制图表
    engine.plot()
```

### 使用策略回测器

```python
from instock.core.backtest import StrategyBacktester

backtester = StrategyBacktester(initial_cash=100000)
results = backtester.backtest_strategy(
    strategy_name='enter',
    stocks_data=stocks_data,
    hold_days=5
)
```

## 安装依赖

```bash
pip install backtrader>=1.9.76
```

或者使用 requirements.txt:

```bash
pip install -r requirements.txt
```
