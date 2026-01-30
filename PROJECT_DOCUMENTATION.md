# InStock 股票数据分析系统

> 一个功能强大的量化投资辅助系统，支持A股股票和ETF数据抓取、技术指标计算、K线形态识别、策略选股、回测验证和自动交易。

---

## 📑 目录

- [功能概述](#功能概述)
- [系统架构](#系统架构)
- [目录结构](#目录结构)
- [模块详解](#模块详解)
- [安装部署](#安装部署)
- [使用指南](#使用指南)
- [配置说明](#配置说明)
- [API接口](#api接口)
- [扩展开发](#扩展开发)

---

## 功能概述

### 核心功能

| 功能模块 | 描述 |
|---------|------|
| **综合选股** | 支持200+信息栏目自由组合选股，包括股票范围、基本面、技术面、消息面等 |
| **每日数据** | 自动抓取股票/ETF日数据、资金流向、龙虎榜、大宗交易、分红配送等 |
| **指标计算** | 基于TA-Lib计算32种技术指标（MACD、KDJ、BOLL、RSI等） |
| **K线形态** | 精准识别61种K线形态（锤头、十字星、吞噬模式等） |
| **策略选股** | 内置11种选股策略（放量上涨、停机坪、突破平台等） |
| **回测验证** | 对选股策略进行历史回测，验证成功率 |
| **自动交易** | 支持自动交易，内置打新策略，可扩展交易策略 |
| **筹码分布** | 计算并可视化股票筹码分布图 |

### 技术特点

- **多数据源支持**：新浪财经 → 腾讯财经 → 东方财富，自动容错切换
- **增量缓存**：历史数据以天为单位增量更新，提高效率
- **多线程处理**：采用并发处理，提高数据抓取和计算效率
- **Web可视化**：Tornado + Bootstrap实现的Web界面
- **前端Vue版本**：提供现代化的Vue 3 + TypeScript前端
- **Docker支持**：提供Docker镜像，一键部署
- **代理支持**：支持多代理IP，应对反爬虫限制

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                                │
├─────────────────────────────────────────────────────────────────┤
│   Web Service (Tornado)    │    Vue Frontend (TypeScript)       │
│   端口: 9988               │    开发端口: 5173                   │
└─────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────┐
│                         业务逻辑层                                │
├─────────────────────────────────────────────────────────────────┤
│  策略选股  │  指标计算  │  K线形态  │  筹码分布  │  回测验证      │
│  strategy/ │ indicator/ │  pattern/ │   kline/   │  backtest/    │
└─────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────┐
│                         数据服务层                                │
├─────────────────────────────────────────────────────────────────┤
│               stockfetch.py (多数据源调度)                        │
│  ┌─────────────┬─────────────┬─────────────┐                    │
│  │  新浪财经    │   腾讯财经   │   东方财富   │                    │
│  │ (优先级: 1)  │  (优先级: 2) │  (优先级: 3) │                    │
│  └─────────────┴─────────────┴─────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────┐
│                         数据存储层                                │
├─────────────────────────────────────────────────────────────────┤
│   MySQL Database (instockdb)    │    File Cache (cache/hist/)   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 目录结构

```
SelectStock/
├── README.md                    # 项目说明文档
├── requirements.txt             # Python依赖包
├── LICENSE                      # 开源许可证
│
├── instock/                     # 📦 核心代码目录
│   ├── __init__.py
│   │
│   ├── bin/                     # 🚀 启动脚本
│   │   ├── run_web.sh/.bat     # 启动Web服务
│   │   ├── run_job.sh/.bat     # 启动数据作业
│   │   ├── run_trade.bat       # 启动交易服务
│   │   └── run_cron.sh         # 启动定时任务
│   │
│   ├── config/                  # ⚙️ 配置文件
│   │   ├── proxy.txt           # 代理IP配置
│   │   ├── eastmoney_cookie.txt # 东方财富Cookie
│   │   └── trade_client.json   # 交易客户端配置
│   │
│   ├── core/                    # 🧠 核心业务模块
│   │   ├── stockfetch.py       # 数据获取核心（多数据源调度）
│   │   ├── tablestructure.py   # 数据库表结构定义
│   │   ├── singleton_stock.py  # 股票数据单例
│   │   ├── singleton_trade_date.py # 交易日历单例
│   │   ├── web_module_data.py  # Web模块数据配置
│   │   │
│   │   ├── crawling/           # 🕷️ 数据爬取模块
│   │   │   ├── stock_sina.py       # 新浪财经-股票实时行情
│   │   │   ├── stock_tencent.py    # 腾讯财经-股票实时行情
│   │   │   ├── stock_hist_em.py    # 东方财富-历史K线
│   │   │   ├── stock_hist_sina.py  # 新浪财经-历史K线
│   │   │   ├── stock_fund_em.py    # 东方财富-资金流向
│   │   │   ├── stock_fund_sina.py  # 新浪财经-资金流向
│   │   │   ├── stock_lhb_em.py     # 东方财富-龙虎榜
│   │   │   ├── stock_lhb_sina.py   # 新浪财经-龙虎榜
│   │   │   ├── stock_dzjy_em.py    # 大宗交易
│   │   │   ├── stock_fhps_em.py    # 分红配送
│   │   │   ├── stock_selection.py  # 综合选股
│   │   │   ├── stock_chip_race.py  # 早盘/尾盘抢筹
│   │   │   ├── stock_limitup_reason.py # 涨停原因
│   │   │   ├── fund_etf_em.py      # ETF数据
│   │   │   ├── etf_sina.py         # 新浪财经-ETF
│   │   │   ├── etf_tencent.py      # 腾讯财经-ETF
│   │   │   └── trade_date_hist.py  # 交易日历
│   │   │
│   │   ├── indicator/          # 📊 指标计算模块
│   │   │   └── calculate_indicator.py  # 32种技术指标计算
│   │   │
│   │   ├── pattern/            # 📈 K线形态识别
│   │   │   └── pattern_recognitions.py # 61种K线形态
│   │   │
│   │   ├── strategy/           # 💡 选股策略
│   │   │   ├── enter.py              # 策略入口/工具
│   │   │   ├── backtrace_ma250.py    # 回踩年线
│   │   │   ├── breakthrough_platform.py # 突破平台
│   │   │   ├── keep_increasing.py    # 放量上涨
│   │   │   ├── parking_apron.py      # 停机坪
│   │   │   ├── turtle_trade.py       # 海龟交易法则
│   │   │   ├── high_tight_flag.py    # 高而窄的旗形
│   │   │   ├── climax_limitdown.py   # 放量跌停
│   │   │   ├── low_atr.py            # 低ATR成长
│   │   │   └── low_backtrace_increase.py # 无大幅回撤
│   │   │
│   │   ├── kline/              # 📉 K线可视化
│   │   │   ├── cyq.py          # 筹码分布计算
│   │   │   ├── cyq.js          # 筹码分布JS
│   │   │   ├── visualization.py # K线可视化
│   │   │   └── indicator_web_dic.py # 指标字典
│   │   │
│   │   └── backtest/           # 🔄 回测模块
│   │       └── rate_stats.py   # 收益率统计
│   │
│   ├── job/                     # ⏰ 定时作业
│   │   ├── execute_daily_job.py    # 整体作业调度
│   │   ├── init_job.py             # 初始化（创建数据库）
│   │   ├── basic_data_daily_job.py # 基础数据实时作业
│   │   ├── basic_data_other_daily_job.py # 其他基础数据
│   │   ├── basic_data_after_close_daily_job.py # 收盘后数据
│   │   ├── selection_data_daily_job.py # 综合选股数据
│   │   ├── indicators_data_daily_job.py # 指标数据作业
│   │   ├── klinepattern_data_daily_job.py # K线形态作业
│   │   ├── strategy_data_daily_job.py # 策略选股作业
│   │   └── backtest_data_daily_job.py # 回测数据作业
│   │
│   ├── web/                     # 🌐 Web服务
│   │   ├── web_service.py      # Tornado主服务
│   │   ├── base.py             # 基础Handler
│   │   ├── dataTableHandler.py # 数据表Handler
│   │   ├── dataIndicatorsHandler.py # 指标Handler
│   │   ├── templates/          # HTML模板
│   │   └── static/             # 静态资源
│   │
│   ├── trade/                   # 💹 自动交易
│   │   ├── trade_service.py    # 交易服务主程序
│   │   ├── usage.md            # 交易使用说明
│   │   ├── robot/              # 交易机器人引擎
│   │   └── strategies/         # 交易策略
│   │
│   ├── lib/                     # 📚 公共库
│   │   ├── database.py         # 数据库连接
│   │   ├── torndb.py           # Tornado数据库封装
│   │   ├── trade_time.py       # 交易时间工具
│   │   ├── run_template.py     # 运行模板
│   │   ├── singleton_type.py   # 单例类型
│   │   ├── crypto_aes.py       # AES加密
│   │   └── version.py          # 版本信息
│   │
│   ├── fontWeb/                 # 🎨 Vue前端（新版）
│   │   ├── package.json        # 前端依赖
│   │   ├── vite.config.ts      # Vite配置
│   │   ├── tsconfig.json       # TypeScript配置
│   │   └── src/                # Vue源代码
│   │       ├── api/            # API接口
│   │       ├── views/          # 页面视图
│   │       ├── router/         # 路由配置
│   │       ├── stores/         # Pinia状态管理
│   │       └── types/          # TypeScript类型
│   │
│   ├── cache/                   # 💾 缓存目录
│   │   └── hist/               # 历史数据缓存
│   │
│   └── log/                     # 📝 日志目录
│       ├── stock_execute_job.log # 作业日志
│       ├── stock_web.log       # Web服务日志
│       └── stock_trade.log     # 交易服务日志
│
├── docker/                      # 🐳 Docker配置
│   ├── Dockerfile              # Docker镜像构建
│   ├── docker-compose.yml      # 完整部署配置
│   ├── docker-compose.remote-db.yml # 远程数据库配置
│   ├── .env.example            # 环境变量示例
│   ├── build.sh/.bat           # 构建脚本
│   └── DOCKER_DEPLOY.md        # Docker部署说明
│
├── cron/                        # ⏲️ 定时任务配置
│   ├── cron.hourly/            # 每小时任务
│   ├── cron.workdayly/         # 每工作日任务
│   └── cron.monthly/           # 每月任务
│
├── supervisor/                  # 🔧 进程管理
│   └── supervisord.conf        # Supervisor配置
│
├── document/                    # 📖 文档目录
│   ├── database_schema.md      # 数据库设计文档
│   └── hist_cache_incremental.md # 增量缓存说明
│
└── img/                         # 🖼️ 截图资源
```

---

## 模块详解

### 1. 数据获取模块 (crawling/)

支持多数据源自动切换，确保数据可用性：

| 数据类型 | 优先数据源 | 备选数据源 | 说明 |
|---------|-----------|-----------|------|
| 股票实时行情 | 新浪财经 | 腾讯财经 → 东方财富 | 包含40+字段 |
| ETF实时行情 | 新浪财经 | 腾讯财经 → 东方财富 | 含规模、换手率等 |
| 历史K线 | 新浪财经 | 东方财富 | 支持增量更新 |
| 资金流向 | 新浪财经 | 东方财富 | 主力/散户资金 |
| 龙虎榜 | 新浪财经 | 东方财富 | 机构买卖数据 |
| 综合选股 | 东方财富 | - | 200+筛选条件 |

### 2. 技术指标模块 (indicator/)

基于TA-Lib实现的32种技术指标：

```
趋势指标: MACD, SMA, TRIX, DMA, TEMA, Supertrend, ENE
动量指标: KDJ, RSI, ROC, CCI, WR, MFI, STOCHRSI
波动指标: BOLL, ATR, VHF
成交量指标: OBV, VR, VWMA
其他指标: CR, DMI, SAR, PSY, BRAR, EMV, BIAS, PPO, WT, DPO, RVI, FI
```

### 3. K线形态识别 (pattern/)

精准识别61种K线形态，包括：

- **反转形态**: 锤头、吊颈线、倒锤头、射击之星、早晨之星、黄昏之星
- **持续形态**: 三白兵、三乌鸦、上升三法、下降三法
- **中性形态**: 十字星、纺锤、高浪线

### 4. 选股策略 (strategy/)

| 策略名称 | 核心逻辑 |
|---------|---------|
| 放量上涨 | 成交量/5日均量≥2，涨幅<2% |
| 停机坪 | 涨停后连续3日高开小涨 |
| 回踩年线 | 突破250日均线后回踩确认 |
| 突破平台 | 放量突破60日均线 |
| 海龟交易 | 收盘价创60日新高 |
| 高而窄的旗形 | 24日内涨幅≥90%，连续两日涨停 |
| 放量跌停 | 跌>9.5%，量≥5日均量×4 |
| 低ATR成长 | 10日内振幅>10% |

### 5. Web服务 (web/)

基于Tornado的Web服务，端口9988：

- **首页路由**: `/instock/`
- **数据API**: `/instock/api_data`
- **页面渲染**: `/instock/data`
- **指标图表**: `/instock/data/indicators`
- **关注管理**: `/instock/control/attention`

---

## 安装部署

### 方式一：常规安装

#### 1. 环境要求

- Python 3.11+
- MySQL 8.0+
- TA-Lib C/C++库

#### 2. 安装步骤

```bash
# 克隆项目
git clone https://github.com/your-repo/SelectStock.git
cd SelectStock

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置数据库 (编辑 instock/lib/database.py)
db_host = "localhost"
db_user = "root"
db_password = "your_password"
db_database = "instockdb"
```

#### 3. 启动服务

```bash
# Windows
cd instock\bin
run_web.bat      # 启动Web服务
run_job.bat      # 运行数据作业

# Linux/Mac
cd instock/bin
./run_web.sh     # 启动Web服务
./run_job.sh     # 运行数据作业
```

### 方式二：Docker部署

```bash
cd docker

# 使用本地数据库
docker-compose up -d

# 使用远程数据库
docker-compose -f docker-compose.remote-db.yml up -d
```

详见 [Docker部署文档](docker/DOCKER_DEPLOY.md)

---

## 使用指南

### 1. 运行数据作业

```bash
cd instock/job

# 整体作业（包含所有数据处理）
python execute_daily_job.py

# 指定日期
python execute_daily_job.py 2024-01-15

# 日期范围
python execute_daily_job.py 2024-01-01 2024-01-31

# 多个日期
python execute_daily_job.py 2024-01-01,2024-01-15,2024-01-31
```

### 2. 单独运行模块

```bash
# 基础数据（实时行情）
python basic_data_daily_job.py

# 综合选股数据
python selection_data_daily_job.py

# 技术指标计算
python indicators_data_daily_job.py

# K线形态识别
python klinepattern_data_daily_job.py

# 策略选股
python strategy_data_daily_job.py

# 回测数据
python backtest_data_daily_job.py
```

### 3. 访问Web界面

启动Web服务后访问: http://localhost:9988

### 4. 自动交易

```bash
cd instock/bin
run_trade.bat  # Windows

# 配置交易账户
# 编辑 instock/config/trade_client.json
```

⚠️ **警告**: 交易日10:00会自动打新，不需要请删除相关策略。

---

## 配置说明

### 数据库配置

编辑 `instock/lib/database.py`:

```python
db_host = "localhost"      # 数据库主机
db_user = "root"           # 用户名
db_password = "password"   # 密码
db_database = "instockdb"  # 数据库名
db_port = 3306             # 端口
```

或使用环境变量（Docker推荐）:

```bash
export db_host=localhost
export db_password=your_password
```

### 代理配置

编辑 `instock/config/proxy.txt`:

```
# 格式: ip:port 或 username:password@ip:port
127.0.0.1:7890
user:pass@192.168.1.100:8080
```

### 数据源配置

编辑 `instock/core/stockfetch.py`:

```python
DATA_SOURCE_MAX_RETRIES = 2      # 最大重试次数
DATA_SOURCE_RETRY_INTERVAL = 30  # 重试间隔(秒)
HIST_DATA_DEFAULT_YEARS = 3      # 历史数据年数
HIST_DATA_CACHE_EXPIRE_DAYS = 7  # 缓存过期天数
```

---

## API接口

### 获取股票数据

```
GET /instock/api_data?table_name=cn_stock_spot&date=2024-01-15
```

### 获取指标图表

```
GET /instock/data/indicators?code=000001&date=2024-01-15
```

### 管理关注

```
POST /instock/control/attention
Body: {"code": "000001", "action": "add"}
```

---

## 扩展开发

### 添加新数据源

1. 在 `instock/core/crawling/` 创建新模块
2. 在 `stockfetch.py` 中添加导入和调用逻辑
3. 遵循现有数据源的返回格式

### 添加新策略

1. 在 `instock/core/strategy/` 创建策略文件
2. 实现策略函数（参考 `enter.py` 模板）
3. 在 `tablestructure.py` 注册策略

### 添加新指标

1. 在 `calculate_indicator.py` 添加指标计算
2. 在 `tablestructure.py` 添加字段定义
3. 更新 `indicator_web_dic.py` 用于Web显示

---

## 日志文件

| 文件 | 位置 | 说明 |
|-----|------|-----|
| stock_execute_job.log | instock/log/ | 数据作业日志 |
| stock_web.log | instock/log/ | Web服务日志 |
| stock_trade.log | instock/log/ | 交易服务日志 |

---

## 技术栈

| 类别 | 技术 |
|-----|------|
| 后端框架 | Python 3.11+, Tornado |
| 数据库 | MySQL 8.0+, SQLAlchemy, PyMySQL |
| 数据处理 | Pandas, NumPy, TA-Lib |
| 前端(新) | Vue 3, TypeScript, Vite, Element Plus |
| 前端(旧) | Bootstrap, jQuery, DataTables |
| 可视化 | Bokeh, ECharts |
| 部署 | Docker, Supervisor |

---

## 许可证

本项目采用开源许可证，详见 [LICENSE](LICENSE) 文件。

---

## 致谢

感谢所有贡献者和开源社区的支持！

如有问题，请提交 Issue 或 Pull Request。
