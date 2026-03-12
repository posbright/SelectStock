**InStock股票系统**

InStock股票系统，抓取每日股票、ETF关键数据，计算股票技术指标、筹码分布，识别K线各种形态，综合选股，内置多种选股策略，支持选股验证回测，支持自动交易，支持批量时间，运行高效，支持PC、平板、手机移动设备显示，同时提供Docker镜像方便安装，是量化投资的好帮手。

The stock system,Capture key data on daily stocks and ETFs, calculate stock technical indicators, chip distribution, Position Cost Distribution(CYQ), identify various K-line forms, comprehensive stock selection, built-in multiple stock selection strategies, support stock selection verification and backtesting, support automatic trading, and support batch time , runs efficiently, supports display on PCs, tablets, and mobile phones, and provides Docker images for easy installation, making it a good helper for quantitative investment.

ima知识库：myhhub/stock，每日提供全网最全面的股票数据，个股信息覆盖超 2200 多个栏目，是专业量化数据库级别的因子池，为优选个股提供优质数据支撑。
 https://ima.qq.com/wiki/?shareId=8b0da768c77bc863f1cad8eb9482e37a6eeb26ad7171523b687d48c1a67c8e2c 。

Docker镜像：https://hub.docker.com/r/mayanghua/instock 。

# 功能介绍

##  一：综合选股
综合选股支持股票范围、基本面、技术面、消息面、人气指标、行情数据等方面共200多个信息栏目进行自由组合选股。选股条件分为以下大类：
```
1.股票范围
市场、 行业、地区、 概念、 风格、指数成份、 上市时间。
2.基本面
估值指标、每股指标、盈利能力、成长能力、资本结构与偿债能力、股本股东。
3.技术面
MACD金叉、KDJ金叉、放量突破、低位资金净流入、高位资金净流出、向上突破均线、均线多头排列、均线空头排列、连涨放量、下跌无量、一根大阳线、两根大阳线、旭日东升、强势多方、炮拨云见日、七仙女下凡(七连阴)、八仙过海(八连阳)、九阳神功(九连阳)、四串阳、天量法则、放量上攻、穿头破脚、倒转锤头、射击之星、黄昏之星、曙光初现、身怀六甲、乌云盖顶、早晨之星、窄幅整理。
4.消息面
公告大事、机构关注情况、机构持股家数、机构持股比例。
5.人气指标
股吧人气排名、人气排名变化、人气排名连涨、人气排名连跌、人气排名创新高、人气排名创新低、新晋粉丝占比、铁杆粉丝占比、7日关注排名、今日浏览排名。
6.行情数据
股价表现、成交情况、资金流向、行情统计、沪深股通。
```
![](img/a3.jpg)
![](img/a1.jpg)

##  二：股票每日数据

包括每日股票数据、股票资金流向、股票分红配送、股票龙虎榜、股票大宗交易、股票基本面数据、行业资金流向、概念资金流向、早盘抢筹数据、尾盘抢筹数据、涨停原因揭密、每日ETF数据。

抓取A股票每日数据，主要为一些关键数据，同时封装抓取方法，方便扩展系统获取个人关注的数据。

![](img/00.jpg)
![](img/12.jpg)
## 三：股票指标计算
基于talib、pandas 计算指标，计算高效准确。调整个别指标公式，确保结果和同花顺、通信达结果一致。
指标：

```
1、MACD 2、KDJ 3、BOLL 4、TRIX，TRMA 5、CR 6、SMA 7、RSI 
8、VR，MAVR 9、ROC 10、DMI，+DI，-DI，DX，ADX，ADXR 11、W&R 
12、CCI 13、TR、ATR 14、DMA、AMA 15、OBV 16、SAR 17、PSY 
18、BRAR 19、EMV 20、BIAS 21、TEMA  22、MFI 23、VWMA
24、PPO 25、WT 26、Supertrend  27、DPO  28、VHF  29、RVI
30、FI 31、ENE 32、STOCHRSI
```

![](img/01.jpg)
![](img/06.jpg)

## 四：判断买入卖出的股票

根据指标判定可能买入卖出的股票，具体筛选条件如下：


```
KDJ:
1、超买区：K值在80以上，D值在70以上，J值大于90时为超买。一般情况下，股价有可能下跌。投资者应谨慎行事，局外人不应再追涨，局内人应适时卖出。
2、超卖区：K值在20以下，D值在30以下为超卖区。一般情况下，股价有可能上涨，反弹的可能性增大。局内人不应轻易抛出股票，局外人可寻机入场。
RSI:
1、当六日指标上升到达80时，表示股市已有超买现象，如果一旦继续上升，超过90以上时，则表示已到严重超买的警戒区，股价已形成头部，极可能在短期内反转回转。
2、当六日强弱指标下降至20时，表示股市有超卖现象，如果一旦继续下降至10以下时则表示已到严重超卖区域，股价极可能有止跌回升的机会。
CCI:
1、当CCI＞﹢100时，表明股价已经进入非常态区间——超买区间，股价的异动现象应多加关注。
2、当CCI＜﹣100时，表明股价已经进入另一个非常态区间——超卖区间，投资者可以逢低吸纳股票。
CR:
1、跌穿a、b、c、d四条线，再由低点向上爬升160时，为短线获利的一个良机，应适当卖出股票。
2、CR跌至40以下时，是建仓良机。
WR:
1、当％R线达到20时，市场处于超买状况，走势可能即将见顶。
2、当％R线达到80时，市场处于超卖状况，股价走势随时可能见底。
VR:
1、获利区域160－450根据情况获利了结。
2、低价区域40－70可以买进。
```

![](img/05.jpg)

## 五：K线形态识别

精准识别61种K线形态，支持用户自选形态识别。

识别形态:

```
1、两只乌鸦2、三只乌鸦3、三内部上涨和下跌4、三线打击5、三外部上涨和下跌6、南方三星7、三个白兵8、弃婴
9、大敌当前10、捉腰带线11、脱离12、收盘缺影线13、藏婴吞没14、反击线15、乌云压顶16、十字17、十字星
18、蜻蜓十字/T形十字19、吞噬模式20、十字暮星  21、暮星22、向上/下跳空并列阳线23、墓碑十字/倒T十字
24、锤头25、上吊线26、母子线27、十字孕线28、风高浪大线29、陷阱30、修正陷阱31、家鸽32、三胞胎乌鸦
33、颈内线34、倒锤头35、反冲形态36、由较长缺影线决定的反冲形态37、梯底38、长脚十字39、长蜡烛
40、光头光脚/缺影线 41、相同低价42、铺垫43、十字晨星44、晨星45、颈上线46、刺透形态47、黄包车夫
48、上升/下降三法49、分离线50、射击之星51、短蜡烛52、纺锤53、停顿形态54、条形三明治55、探水竿
56、跳空并列阴阳线57、插入58、三星59、奇特三河床60、向上跳空的两只乌鸦61、上升/下降跳空三法 
```
形态识别结果：
```
负：出现卖出信号
0：没有出现该形态
正：出现买入信号
```
![](img/09.jpg)
![](img/13.jpg)

## 六：筹码分布

筹码分布通过计算一定时间范围内股票的:最高价、最低价、成交数，输出对应价格成交数占整个流通盘比值的分布图形。计算高效准确，结果与东方财富等专业软件的一致，缺省计算210个交易日的成本，可以自行设定时间范围。
![](img/06.jpg)

## 七：策略选股

内置放量上涨、停机坪、回踩年线、突破平台、放量跌停等多种选股策略，同时封装了策略模板，方便扩展实现自己的策略。

策略分为两大类：**K线技术策略**（基于K线和成交量数据）和**策略选股**（含基本面策略）。

### K线技术策略
```
1、放量上涨
    1）当日比前一天上涨小于2%或收盘价小于开盘价。
    2）当日成交额不低于2亿。
    3）当日成交量/5日平均成交量>=2。
2、均线多头
    MA30向上
    1）30日前的30日均线<20日前的30日均线<10日前的30日均线<当日的30日均线。
    2）(当日的30日均线/30日前的30日均线)>1.2。
3、停机坪
    1）最近15日有涨幅大于9.5%，且必须是放量上涨。
    2）紧接的下个交易日必须高开，收盘价必须上涨，且与开盘价不能大于等于相差3%。
    3）接下2、3个交易日必须高开，收盘价必须上涨，且与开盘价不能大于等于相差3%，且每天涨跌幅在5%间。
4、回踩年线
    1）分2个时间段：前段=最近60交易日最高收盘价之前交易日(长度>0)，后段=最高价当日及后面的交易日。
    2）前段由年线(250日)以下向上突破。
    3）后段必须在年线以上运行，且后段最低价日与最高价日相差必须在10-50日间。
    4）回踩伴随缩量：最高价日交易量/后段最低价日交易量>2,后段最低价/最高价<0.8。
5、突破平台
    1）60日内某日收盘价>=60日均线>开盘价。
    2）且【1】放量上涨。
    3）且【1】间之前时间，任意一天收盘价与60日均线偏离在-5%~20%之间。
6、无大幅回撤
    1）当日收盘价比60日前的收盘价的涨幅小于0.6。
    2）最近60日，不能有单日跌幅超7%、高开低走7%、两日累计跌幅10%、两日高开低走累计10%。
```

### 策略选股
```
7、海龟交易法则
    最后一个交易日收市价为指定区间内最高价。
    1）当日收盘价>=最近60日最高收盘价。
8、高而窄的旗形
    1）必须至少上市交易60日。
    2）当日收盘价/之前24~10日的最低价>=1.9。
    3）之前24~10日必须连续两天涨幅大于等于9.5%。
9、放量跌停。
    1）跌>9.5%。
    2）成交额不低于2亿。
    3）成交量至少是5日平均成交量的4倍。
10、低ATR成长
    1）必须至少上市交易250日。
    2）最近10个交易日的最高收盘价必须比最近10个交易日的最低收盘价高1.1倍。
11、趋势回调
    优质公司长期趋势向上时的回调买入机会。
12、超跌反弹
    市场恐慌但基本面未变时的超跌修复买入机会。
13、突破确认
    横盘整理后放量突破确认买入。
14、GPT综合选股（基本面策略）
    基于ChatGPT选股文档的基本面筛选策略，从综合选股数据中筛选：
    1）资产负债率 < 60%。
    2）每股经营现金流 > 0。
    3）ROE(加权) >= 15%。
    4）毛利率 >= 30%。
    5）净利率 >= 10%。
    6）营收3年CAGR > 10%。
    7）净利润3年CAGR > 10%。
    8）PE(TTM) 在 (0, 50] 之间。
```

![](img/04.jpg)

## 八：选股验证


对指标、策略等选出的股票进行回测，验证策略的成功率，是否可用。

在 Vue 前端中，选股验证模块提供：**回测看板**（跨策略总览、时间序列、单策略明细、收益分布、买入-卖出配对），并支持自定义收益周期（horizons/checkpoints）与日期区间（start_date/end_date）。


![](img/05.jpg)

## 九：自动交易

支持自动交易，内置自动打新股的策略及示例策略，由于**涉及金钱**，规避可能存在风险，没有提供其他交易策略。

具有交易日志，以及支持为每个交易策略配置交易日志。

**特别提醒**：交易日10:00点会触发打新，不想打新的删除stagging.py或不要启动“交易服务”。

![](img/11.jpg)

## 十：关注功能

支持股票关注，关注股票在各个模块(含有的)置顶、标红显示。

## 十一：支持批量


可以通过时间段、枚举时间、当前时间进行指标计算、策略选股及回测等。同时支持智能识别交易日，可以输入任意日期。

具体执行设置如下：
```
------整体作业，支持批量作业------
当前时间作业 python execute_daily_job.py
单个时间作业 python execute_daily_job.py 2022-03-01
枚举时间作业 python execute_daily_job.py 2022-01-01,2021-02-08,2022-03-12
区间时间作业 python execute_daily_job.py 2022-01-01 2022-03-01

------单功能作业，支持批量作业，回测数据自动填补到当前
数据获取作业 python fetch_data_job.py  (实时行情+历史K线+缓存清理)
基础数据实时作业 python basic_data_daily_job.py
基础数据非实时作业 python basic_data_other_daily_job.py
指标数据作业 python indicators_data_daily_job.py
K线形态作业 python klinepattern_data_daily_job.py
策略数据作业 python strategy_data_daily_job.py
GPT综合选股作业 python gpt_value_data_job.py
回测数据 python backtest_data_daily_job.py
```

## 十二’：手动拉取历史数据

当需要手动拉取或更新历史K线数据时，可以通过以下方式获取：

### 方式一：使用 fetch_data_job.py（推荐）
```
cd instock/job

# 拉取当前交易日的最新数据（增量更新）
python fetch_data_job.py

# 指定日期拉取
python fetch_data_job.py 2024-06-15
```
该脚本会自动清理过期缓存、拉取实时行情、增量更新历史K线。

数据源优先级：东方财富 → 腾讯财经 → 新浪财经，自动容错切换。

### 方式二：使用 Python 脚本自定义获取
```python
import datetime, os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import instock.core.stockfetch as stf

# 获取单只股票历史K线（默认10年）
df = stf.fetch_stock_hist((datetime.datetime.now(), '000001'))

# 自定义获取5年历史
df = stf.fetch_stock_hist((datetime.datetime.now(), '000001'), years=5)

# 指定日期范围
df = stf.fetch_stock_hist((datetime.datetime.now(), '000001'),
                          date_start='20230101', date_end='20231231')

# 不使用缓存，强制从API获取最新数据
df = stf.fetch_stock_hist((datetime.datetime.now(), '000001'), is_cache=False)
```

### 方式三：通过环境变量调整获取年数
```
# 默认10年，Docker默认3年，可自行调整
# Windows:
set HIST_DATA_DEFAULT_YEARS=10
# Linux/Mac:
export HIST_DATA_DEFAULT_YEARS=10

python fetch_data_job.py
```

### 方式四：强制重建全部缓存
```
# 先清空缓存目录（重新获取耗时较长）
# Windows:
rd /s /q instock\cache\hist
# Linux/Mac:
rm -rf instock/cache/hist

cd instock/job && python fetch_data_job.py
```

增量更新说明：首次运行需从API获取全量历史数据（耗时较长），后续运行只需补缺新增交易日数据（快速完成）。
## 十三：支持代理及Cookie

支持多代理获取数据。由于很多网站对大量请求有防护机制，使用单一IP地址频繁访问可能导致被封禁或限制访问。代理IP能够帮助分散请求来源，避免单一IP被封锁，从而保证爬虫程序的稳定运行。
支持注入Cookie，解决数据获取频率过高，限制数据获取。
## 十四：存储采用数据库设计

数据存储采用数据库设计，能保存历史数据，以及对数据进行扩展分析、统计、挖掘。系统实现自动创建数据库、数据表，封装了批量更新、插入数据，方便业务扩展。

![](img/07.jpg)

## 十五：展示采用web设计

采用web设计，可视化展示结果。对展示进行封装，添加新的业务表单，只需要配置视图字典就可自动出现业务可视化界面，方便业务功能扩展。

## 十六：运行高效


采用多线程、单例共享资源有效提高运算效率。1天数据的抓取、计算指标、形态识别、策略选股、回测等全部任务运行时间大概4分钟（普通笔记本），计算天数越多效率越高。


## 十七：方便调试

系统运行的重要日志记录在stock_execute_job.log(数据抓取、处理、分析)、stock_web.log(web服务)、stock_trade.log(交易服务)，方便调试发现问题。

![](img/08.jpg)

## 十八：定时任务 `run_fetch` 详细分析

### 概述

`run_fetch` 是工作日定时执行的**数据获取管道**，位于 `cron/cron.workdayly/run_fetch`，负责集中执行所有需要外部 API 调用的数据采集任务。它与 `run_analysis`（数据分析管道）配合使用，实现**获取与分析解耦**。

- **调用入口**：`instock/job/fetch_daily_job.py`
- **建议执行时间**：每个交易日 17:30~18:00（收盘后）
- **预计总耗时**：约 **30~90 分钟**（取决于网络状况和股票数量）
- **非交易日**：自动跳过（脚本内置交易日检测）

---

### 执行流程

`run_fetch` 脚本的执行流程如下：

```
run_fetch (Shell)
  ├── 加载 .env 环境变量
  ├── 交易日检测 → 非交易日直接退出
  └── 调用 fetch_daily_job.py
        ├── Phase 0: init_job — 数据库初始化
        ├── Phase 2: basic_data_daily_job — 实时行情入库
        ├── Phase 2: selection_data_daily_job — 综合选股入库
        ├── Phase 3: basic_data_other_daily_job (子进程) — 扩展数据
        ├── Phase 5: basic_data_after_close_daily_job (子进程) — 收盘后数据
        ├── 释放 stock_data 单例，回收内存
        └── Phase 1: fetch_data_job (子进程) — 历史K线缓存更新
```

> **设计原则**：轻量 API 调用优先于内存密集型操作。在 1.6GB 内存服务器上，K 线缓存更新可能因 OOM 被杀，放在最后确保不影响其他数据入库。

---

### 各阶段任务详解

#### Phase 0：数据库初始化

| 项目 | 说明 |
|------|------|
| **执行模块** | `init_job.py` → `init_job.main()` |
| **执行方式** | 进程内直接调用 |
| **功能** | 检查并创建数据库 `instockdb`、创建基础表（`cn_stock_attention`、`cn_stock_trade_date`） |
| **API 调用** | 无（纯数据库操作） |
| **预计耗时** | **< 1 秒** |
| **写入表** | `cn_stock_attention`、`cn_stock_trade_date`（仅首次运行时创建） |

---

#### Phase 2a：股票/ETF 实时行情入库

| 项目 | 说明 |
|------|------|
| **执行模块** | `basic_data_daily_job.py` → `hdj.main()` |
| **执行方式** | 进程内直接调用 |
| **功能** | 获取全市场 A 股 + ETF 实时行情数据并入库 |
| **数据内容** | A股：~5000 只股票的最新价、涨跌幅、涨跌额、成交量/额、开盘/最高/最低价、昨收、换手率、市盈率(PE)、市净率(PB)、每股收益、行业、上市时间等约 40 个字段；ETF：代码、名称、最新价、涨跌幅、成交量/额、总市值、流通市值等 |
| **API 数据源** | **东方财富**（主） → 腾讯财经 → 新浪财经 |
| **API 地址** | `https://push2.eastmoney.com/api/qt/clist/get` |
| **预计耗时** | **5~15 秒** |
| **写入表** | `cn_stock_spot`（A股实时行情）、`cn_etf_spot`（ETF实时行情） |

---

#### Phase 2b：综合选股数据入库

| 项目 | 说明 |
|------|------|
| **执行模块** | `selection_data_daily_job.py` → `sddj.main()` |
| **执行方式** | 进程内直接调用 |
| **功能** | 从东方财富选股器获取全市场综合选股数据 |
| **数据内容** | 200+ 字段：估值指标（PE/PB/PS）、财务指标（ROE/ROA/毛利率/净利率）、增长率（营收/净利润 CAGR）、机构持仓、技术指标（MACD/KDJ 金叉信号）、限售解禁、资产重组、股权质押、人气排名等 |
| **API 数据源** | **东方财富选股器**（主） → 新浪财经 |
| **API 地址** | `https://data.eastmoney.com/dataapi/xuangu/list`（分页获取，约 10 页） |
| **预计耗时** | **10~30 秒** |
| **写入表** | `cn_stock_selection` |
| **备注** | 获取失败时自动重试一次（10 秒延迟），该数据是后续 GPT 综合选股的数据源 |

---

#### Phase 3：扩展数据（子进程）

| 项目 | 说明 |
|------|------|
| **执行模块** | `basic_data_other_daily_job.py`（独立子进程） |
| **执行方式** | `subprocess.run()` 启动独立 Python 进程，超时 1800 秒 |
| **功能** | 获取龙虎榜、资金流向、分红配送、早盘抢筹、涨停原因等扩展市场数据 |
| **预计总耗时** | **3~8 分钟**（含子任务间 30 秒防限流延迟 × 5 = 2.5 分钟） |

Phase 3 内部包含 6 个子任务，按顺序串行执行（每个子任务之间有 30 秒防限流延迟）：

##### 子任务 3.1：龙虎榜（东方财富）

| 项目 | 说明 |
|------|------|
| **函数** | `save_nph_stock_lhb_data()` → `stf.fetch_stock_lhb_data()` |
| **数据内容** | 龙虎榜详情：上榜股票代码/名称、收盘价、涨跌幅、净买额、买入/卖出额、龙虎榜成交额、换手率、流通市值、上榜原因、上榜后 1/2/5/10 日涨跌幅 |
| **API 数据源** | **东方财富**（主） → 新浪财经 |
| **API 地址** | `https://datacenter-web.eastmoney.com/api/data/v1/get`（`RPT_DAILYBILLBOARD_DETAILSNEW`） |
| **预计耗时** | **3~10 秒** |
| **写入表** | `cn_stock_lhb` |
| **附带操作** | 自动执行 `stock_spot_buy()`（基本面选股：PE<20、PB<10、ROE>=15%），写入 `cn_stock_spot_buy` |

##### 子任务 3.2：股票分红配送

| 项目 | 说明 |
|------|------|
| **函数** | `save_nph_stock_bonus()` → `stf.fetch_stocks_bonus()` |
| **数据内容** | 分红送配数据：送转总比例、现金分红比例、股息率、每股收益/净资产/公积金/未分配利润、净利润同比、预案公告日、股权登记日、除权除息日、方案进度 |
| **API 数据源** | **东方财富** |
| **API 地址** | `https://datacenter-web.eastmoney.com/api/data/v1/get`（`RPT_SHAREBONUS_DET`） |
| **预计耗时** | **3~10 秒** |
| **写入表** | `cn_stock_bonus` |

##### 子任务 3.3：个股资金流向

| 项目 | 说明 |
|------|------|
| **函数** | `save_nph_stock_fund_flow_data()` → `stf.fetch_stocks_fund_flow()` |
| **数据内容** | 全市场个股资金流向排名（4 个周期合并）：今日/3 日/5 日/10 日的主力/超大单/大单/中单/小单净流入额及净占比 |
| **API 数据源** | **东方财富**（主） → 新浪财经 |
| **API 地址** | `https://push2.eastmoney.com/api/qt/clist/get`（资金流向排名，4 次 API 调用分别获取不同周期） |
| **预计耗时** | **10~30 秒**（4 个周期串行获取，每次含重试机制） |
| **写入表** | `cn_stock_fund_flow` |

##### 子任务 3.4：行业/概念板块资金流向

| 项目 | 说明 |
|------|------|
| **函数** | `save_nph_stock_sector_fund_flow_data()` → `stf.fetch_stocks_sector_fund_flow()` |
| **数据内容** | 行业板块 + 概念板块资金流向（各 3 个周期：今日/5 日/10 日）：板块名称、涨跌幅、主力/超大单/大单/中单/小单净流入额及占比、最大净流入个股 |
| **API 数据源** | **东方财富**（主） → 新浪财经 |
| **API 地址** | `https://push2.eastmoney.com/api/qt/clist/get`（板块资金流向） |
| **预计耗时** | **10~20 秒**（2 个板块类型 × 3 个周期 = 6 次 API 调用，多线程并发） |
| **写入表** | `cn_stock_fund_flow_industry`（行业）、`cn_stock_fund_flow_concept`（概念） |

##### 子任务 3.5：早盘竞价抢筹

| 项目 | 说明 |
|------|------|
| **函数** | `stock_chip_race_open_data()` → `stf.fetch_stock_chip_race_open()` |
| **数据内容** | 早盘集合竞价抢筹 TOP100：代码/名称、最新价、涨跌幅、昨收/今开、开盘金额、抢筹幅度、抢筹委托/成交金额、抢筹占比、连板天数 |
| **API 数据源** | **通达信** |
| **API 地址** | `http://excalc.icfqs.com:7616/TQLEX?Entry=HQServ.hq_nlp`（`funcId: 20`） |
| **预计耗时** | **2~5 秒** |
| **写入表** | `cn_stock_chip_race_open` |

##### 子任务 3.6：涨停原因揭密

| 项目 | 说明 |
|------|------|
| **函数** | `stock_imitup_reason_data()` → `stf.fetch_stock_limitup_reason()` |
| **数据内容** | 当日涨停股票的涨停原因：代码/名称、原因标题、详细原因、最新价、涨跌幅/额、换手率、成交量/额 |
| **API 数据源** | **同花顺** |
| **API 地址** | `http://zx.10jqka.com.cn/event/api/getharden/` |
| **预计耗时** | **2~5 秒** |
| **写入表** | `cn_stock_limitup_reason` |

---

#### Phase 5：收盘后数据（子进程）

| 项目 | 说明 |
|------|------|
| **执行模块** | `basic_data_after_close_daily_job.py`（独立子进程） |
| **执行方式** | `subprocess.run()` 启动独立 Python 进程，超时 1800 秒 |
| **功能** | 获取需要收盘后 1~2 小时才公布的数据 |
| **预计总耗时** | **1~2 分钟**（含 30 秒防限流延迟） |

Phase 5 内部包含 2 个子任务：

##### 子任务 5.1：大宗交易

| 项目 | 说明 |
|------|------|
| **函数** | `save_after_close_stock_blocktrade_data()` → `stf.fetch_stock_blocktrade_data()` |
| **数据内容** | 当日大宗交易：代码/名称、收盘价、涨跌幅、成交均价、折溢率、成交笔数、成交总量(万股)、成交总额(万元)、占流通市值比 |
| **API 数据源** | **东方财富** |
| **API 地址** | `https://datacenter-web.eastmoney.com/api/data/v1/get` |
| **预计耗时** | **3~10 秒** |
| **写入表** | `cn_stock_blocktrade` |

##### 子任务 5.2：尾盘竞价抢筹

| 项目 | 说明 |
|------|------|
| **函数** | `save_after_close_stock_chip_race_end_data()` → `stf.fetch_stock_chip_race_end()` |
| **数据内容** | 尾盘集合竞价抢筹 TOP100：代码/名称、最新价、涨跌幅、收盘金额、抢筹幅度、抢筹委托/成交金额、抢筹占比、连板天数 |
| **API 数据源** | **通达信** |
| **API 地址** | `http://excalc.icfqs.com:7616/TQLEX?Entry=HQServ.hq_nlp`（`funcId: 21`） |
| **预计耗时** | **2~5 秒** |
| **写入表** | `cn_stock_chip_race_end` |

---

#### Phase 1：历史 K 线缓存增量更新（子进程，内存密集型）

| 项目 | 说明 |
|------|------|
| **执行模块** | `fetch_data_job.py`（独立子进程） |
| **执行方式** | `subprocess.run()` 启动独立 Python 进程，超时 **36000 秒（10 小时）** |
| **功能** | 批量更新全市场 ~5000 只股票的历史 K 线缓存文件 |
| **预计总耗时** | 首次运行 **2~6 小时**；增量更新 **20~60 分钟** |

Phase 1 内部分为 3 个步骤：

##### Step 1/3：清理过期缓存

| 项目 | 说明 |
|------|------|
| **函数** | `stf.clean_expired_cache()` |
| **功能** | ①删除退市股票缓存 ②刷新近 35 天内除权除息股票的前复权缓存 ③删除损坏的 `.meta` 文件 |
| **API 调用** | 无（纯本地文件操作） |
| **预计耗时** | **1~5 秒** |

##### Step 2/3：预加载实时行情

| 项目 | 说明 |
|------|------|
| **函数** | `stock_data(date).get_data()` |
| **功能** | 加载 `stock_data` 单例获取全市场股票列表，作为后续 K 线更新的股票清单 |
| **API 数据源** | **东方财富** → 腾讯财经 → 新浪财经 |
| **预计耗时** | **3~10 秒**（若前面 Phase 2a 已加载单例则直接使用缓存，0 秒） |

##### Step 3/3：批量更新 K 线缓存

| 项目 | 说明 |
|------|------|
| **函数** | `stf.update_all_caches()` |
| **功能** | 对每只股票调用 `stock_hist_cache_incremental()` 进行增量缓存更新 |
| **数据内容** | 日 K 线数据：日期、开盘价、收盘价、最高价、最低价、成交量(手)、成交额(元)、振幅、涨跌幅、涨跌额、换手率 |
| **API 数据源** | **东方财富**（主） → **腾讯财经** → **新浪财经**（按健康度动态排序，自动降级切换） |
| **API 地址** | 东方财富：`https://push2his.eastmoney.com/api/qt/stock/kline/get`<br>腾讯：`https://web.ifzq.gtimg.cn/appstock/app/fqkline/`<br>新浪：`https://finance.sina.com.cn/realstock/company/` |
| **并发策略** | 2 线程并发，请求间隔 1~3 秒 |
| **缓存跳过** | 预检查 `.meta` 文件的 `last_date`，若已 >= 当日则跳过（零 API 调用） |
| **缓存文件** | `instock/cache/hist/{code}.gzip.pickle` + `{code}.meta` |
| **默认年数** | 本地 10 年，Docker 3 年（可通过 `HIST_DATA_DEFAULT_YEARS` 环境变量调整） |
| **防限流策略** | 5 层防护：①2 线程并发限制 ②请求间隔 1~3 秒 ③每 100 只暂停 8~15 秒 ④连续 3 次失败触发限流暂停（120s→240s→480s 指数退避） ⑤累计 3 次限流触发熔断终止 |
| **预计耗时** | 首次全量：**2~6 小时**（~5000 只 × 单次 1~3 秒）；增量更新：**20~60 分钟**（大部分股票已有缓存直接跳过） |

---

### 执行时间汇总

| 阶段 | 模块 | 执行方式 | 预计耗时 | API 数据源 |
|------|------|---------|---------|-----------|
| Phase 0 | `init_job` | 进程内 | < 1 秒 | 无 |
| Phase 2a | `basic_data_daily_job` | 进程内 | 5~15 秒 | 东方财富 |
| Phase 2b | `selection_data_daily_job` | 进程内 | 10~30 秒 | 东方财富选股器 |
| Phase 3.1 | 龙虎榜 + 基本面选股 | 子进程 | 3~10 秒 | 东方财富/新浪 |
| *延迟* | | | *30 秒* | |
| Phase 3.2 | 股票分红配送 | 子进程 | 3~10 秒 | 东方财富 |
| *延迟* | | | *30 秒* | |
| Phase 3.3 | 个股资金流向 (4周期) | 子进程 | 10~30 秒 | 东方财富 |
| *延迟* | | | *30 秒* | |
| Phase 3.4 | 行业/概念板块资金流向 | 子进程 | 10~20 秒 | 东方财富 |
| *延迟* | | | *30 秒* | |
| Phase 3.5 | 早盘竞价抢筹 | 子进程 | 2~5 秒 | 通达信 |
| *延迟* | | | *30 秒* | |
| Phase 3.6 | 涨停原因揭密 | 子进程 | 2~5 秒 | 同花顺 |
| Phase 5.1 | 大宗交易 | 子进程 | 3~10 秒 | 东方财富 |
| *延迟* | | | *30 秒* | |
| Phase 5.2 | 尾盘竞价抢筹 | 子进程 | 2~5 秒 | 通达信 |
| Phase 1.1 | 清理过期缓存 | 子进程 | 1~5 秒 | 无 |
| Phase 1.2 | 预加载实时行情 | 子进程 | 0~10 秒 | 东方财富 |
| Phase 1.3 | K线缓存增量更新 | 子进程 | 20~60 分钟 | 东方财富/腾讯/新浪 |
| **总计** | | | **约 30~90 分钟** | |

> **说明**：轻量级任务（Phase 0/2/3/5）合计约 5~10 分钟，总耗时主要取决于 Phase 1（K 线缓存更新）。增量更新时大部分股票缓存已为最新会自动跳过，耗时显著缩短。

---

### 数据写入表汇总

| 数据库表 | 数据类型 | 来源阶段 | 更新策略 |
|---------|---------|---------|---------|
| `cn_stock_spot` | A 股实时行情 | Phase 2a | 按日期删除后重新插入 |
| `cn_etf_spot` | ETF 实时行情 | Phase 2a | 按日期删除后重新插入 |
| `cn_stock_selection` | 综合选股数据 | Phase 2b | 按日期删除后重新插入 |
| `cn_stock_lhb` | 龙虎榜 | Phase 3.1 | 按日期删除后重新插入 |
| `cn_stock_spot_buy` | 基本面选股 | Phase 3.1 | 按日期删除后重新插入 |
| `cn_stock_bonus` | 分红配送 | Phase 3.2 | 按日期删除后重新插入 |
| `cn_stock_fund_flow` | 个股资金流向 | Phase 3.3 | 按日期删除后重新插入 |
| `cn_stock_fund_flow_industry` | 行业资金流向 | Phase 3.4 | 按日期删除后重新插入 |
| `cn_stock_fund_flow_concept` | 概念资金流向 | Phase 3.4 | 按日期删除后重新插入 |
| `cn_stock_chip_race_open` | 早盘竞价抢筹 | Phase 3.5 | 按日期删除后重新插入 |
| `cn_stock_limitup_reason` | 涨停原因 | Phase 3.6 | 按日期删除后重新插入 |
| `cn_stock_blocktrade` | 大宗交易 | Phase 5.1 | 按日期删除后重新插入 |
| `cn_stock_chip_race_end` | 尾盘竞价抢筹 | Phase 5.2 | 按日期删除后重新插入 |
| 本地缓存文件 `cache/hist/*.gzip.pickle` | 历史日 K 线 | Phase 1.3 | 增量追加新交易日数据 |

---

### API 数据源汇总

| 数据源 | 使用场景 | 备注 |
|-------|---------|------|
| **东方财富** | 实时行情、选股器、龙虎榜、资金流向、分红配送、大宗交易、历史 K 线 | 主要数据源，支持 Cookie 注入防限流 |
| **腾讯财经** | 实时行情（备用）、历史 K 线（备用） | 东方财富不可用时自动降级 |
| **新浪财经** | 实时行情（备用）、龙虎榜统计（补充）、资金流向（备用）、历史 K 线（备用） | 第三优先级数据源 |
| **通达信** | 早盘抢筹、尾盘抢筹 | 独占数据源，无备用 |
| **同花顺** | 涨停原因揭密 | 独占数据源，无备用 |

---

### 容错与隔离机制

| 机制 | 说明 |
|------|------|
| **子进程隔离** | Phase 3、Phase 5、Phase 1 均以独立子进程运行，防止 OOM 波及主进程 |
| **顺序容错** | 每个阶段独立 `try/except`，某阶段失败不影响后续阶段继续执行 |
| **API 重试** | 每个 API 调用自带重试机制（1 次重试 + 10 秒延迟），降低瞬时网络问题的影响 |
| **防限流延迟** | Phase 3 子任务之间有 30 秒延迟，避免高频调用触发 API 限流 |
| **智能换源** | K 线数据获取支持三数据源自动切换（健康度排序 + 连续失败降级 + 指数退避） |
| **缓存预检** | K 线更新前检查 `.meta` 文件，缓存已为最新则跳过（零 API 调用） |
| **OOM 安全** | 轻量任务优先执行，即使 K 线更新因内存不足被杀，关键数据已安全入库 |

---

### 与其他定时任务的关系

```
run_fetch  ──→  数据获取（API调用）  ──→  写入数据库表 + 更新本地K线缓存
                                              │
run_analysis  ──→  数据分析（零API调用）  ──→  读取K线缓存 → 计算指标/形态/策略 → 写入分析表
                                              │
run_workdayly  ──→  完整任务  ──→  run_fetch + run_analysis 的组合（自动检测跳过已完成的分析）
```

- `run_fetch` + `run_analysis` 可独立运行，实现**获取与分析解耦**
- `run_workdayly` 是两者的组合，适合单机部署
- 多机部署时可让一台机器运行 `run_fetch`（API 调用），另一台运行 `run_analysis`（计算密集）

---

## 十九：定时任务 `run_analysis` 详细分析

### 概述

`run_analysis` 是工作日定时执行的**数据分析管道**，位于 `cron/cron.workdayly/run_analysis`，负责执行所有本地计算任务（技术指标、K线形态、策略选股、回测验证）。与 `run_fetch`（数据获取管道）配合使用，实现**获取与分析解耦**。

- **调用入口**：`instock/job/analysis_daily_job.py`
- **建议执行时间**：每个交易日 `run_fetch` 完成后（约 19:00~20:00）
- **预计总耗时**：约 **3~10 分钟**（取决于 CPU 性能和股票数量）
- **非交易日**：自动跳过（脚本内置交易日检测）
- **零 API 调用**：所有数据来源为本地磁盘缓存 + 数据库，不发起任何外部网络请求
- **峰值内存**：< 100 MB（流式处理架构）

---

### 执行流程

```
run_analysis (Shell)
  ├── 加载 .env 环境变量
  ├── 交易日检测 → 非交易日直接退出
  └── 调用 analysis_daily_job.py
        ├── 跳过检查 → 分析数据已完成则直接退出
        ├── Step 1: gpt_value_data_job — GPT综合选股（纯DB读取+筛选）
        ├── Step 2: streaming_analysis_job — 流式分析
        │     ├── 2a: 获取股票列表（从DB读取，零API）
        │     ├── 2b: 逐只股票流式处理（从缓存读取K线数据）
        │     │     ├── 技术指标计算（32项指标，77个字段）
        │     │     ├── K线形态识别（61种形态）
        │     │     └── 策略选股检测（13种策略）
        │     ├── 2c: 批量写入数据库（每50只一批）
        │     └── 2d: 指标二次筛选（买入/卖出信号）
        ├── Step 3: backtest_data_daily_job — 策略回测
        │     ├── 3a: 逐表扫描待回测记录（backtest列为NULL）
        │     ├── 3b: 从缓存按需读取历史K线计算收益率
        │     └── 3c: 汇总回测结果到 cn_stock_backtest 表
        └── 释放单例 + GC 回收内存
```

---

### 跳过已完成检查（本地优先模式）

`run_analysis` 内置**智能跳过机制**，适用于多机部署场景：

| 项目 | 说明 |
|------|------|
| **检查目标** | `cn_stock_indicators` 表中当日数据行数 |
| **跳过阈值** | 默认 1000 条（正常交易日约 4800+ 条，该阈值避免误跳过部分完成的情况） |
| **强制执行** | 设置环境变量 `INSTOCK_FORCE_ANALYSIS=1` 可绕过跳过检查 |
| **阈值调整** | 环境变量 `INSTOCK_ANALYSIS_DONE_THRESHOLD`（默认 1000） |
| **应用场景** | 本地计算机已执行完分析并写入 DB → 服务器 cron 触发时自动跳过，节省低内存环境的计算资源 |

---

### 各步骤任务详解

#### Step 1：GPT 综合选股

| 项目 | 说明 |
|------|------|
| **执行模块** | `gpt_value_data_job.py` → `gptj.main()` |
| **执行方式** | 进程内直接调用 |
| **API 调用** | **无**（纯数据库读取 + 内存筛选） |
| **数据来源** | 从 `cn_stock_selection` 表读取综合选股数据（由 `run_fetch` 的 `selection_data_daily_job` 入库） |
| **功能** | 基于基本面指标执行多条件筛选 |
| **预计耗时** | **1~5 秒** |
| **写入表** | `cn_stock_strategy_gpt_value` |

**筛选条件（全部满足）**：

| 指标 | 条件 |
|------|------|
| 资产负债率 | < 60% |
| 每股经营现金流 | > 0 |
| ROE（加权） | >= 15% |
| 毛利率 | >= 30% |
| 净利率 | >= 10% |
| 营收 3 年 CAGR | > 10% |
| 净利润 3 年 CAGR | > 10% |
| PE（TTM） | 在 (0, 50] 之间 |

**特性**：
- 支持日期回退：若当天 `cn_stock_selection` 无数据，自动查找最近 7 天内有数据的交易日
- 筛选结果按 `gpt_score` 综合评分降序排序
- 输出包含评分和各项指标原值，便于前端展示

---

#### Step 2：流式分析（核心计算模块）

| 项目 | 说明 |
|------|------|
| **执行模块** | `streaming_analysis_job.py` → `saj.main()` |
| **执行方式** | 进程内直接调用 |
| **API 调用** | **无**（股票列表从 DB 读取，K 线从磁盘缓存读取） |
| **数据来源** | 股票列表：`cn_stock_spot` 表；K线历史：`instock/cache/hist/*.gzip.pickle` 缓存文件 |
| **功能** | 单次遍历全市场 ~4900 只股票，同时完成三大计算任务 |
| **预计耗时** | **2~8 分钟** |
| **峰值内存** | < 100 MB（vs 旧版独立作业 ~1670 MB） |

##### 核心架构：单次遍历 + 按需读取 + 及时释放

```
对每只股票（~4900只）:
  1. 从磁盘缓存读取历史K线（~350 KB/只）
  2. 同时执行三大计算：
     ├── 技术指标计算 → 结果暂存内存
     ├── K线形态识别 → 结果暂存内存
     └── 策略选股检测 → 结果暂存内存
  3. 释放该股票的DataFrame
  4. 每50只股票批量写入数据库 + GC回收
```

> **效率对比**：原架构 3+13=16 次遍历 × 4900 = **78,400 次 I/O**；流式架构 1 次遍历 × 4900 = **4,900 次 I/O**（减少 93%）

##### 2a. 技术指标计算（32 项指标，77 个数据字段）

基于 TA-Lib 和 pandas 计算，结果与同花顺、通信达一致。

| 指标类别 | 具体指标 |
|---------|---------|
| 趋势指标 | MACD（DIF/DEA/柱状）、TRIX/TRMA、TEMA、CR（及 CR-MA1/2/3）、DMA/AMA、SAR、Supertrend、DPO/MADPO |
| 动量指标 | KDJ（K/D/J）、RSI（6/12/14/24日）、ROC/ROCMA/ROCEMA、CCI（14/84日）、W&R（6/10/14日）、PSY/PSYMA、StochRSI（K/D） |
| 波动指标 | BOLL（上/中/下轨）、TR/ATR、VHF、RVI/RVIS、ENE（上/中/下轨） |
| 成交量指标 | VR/MAVR、OBV、EMV/EMVA、MFI/MFISMA、VWMA/MVWMA、FI（Force Index 2/13日） |
| 能量指标 | BRAR（BR/AR）、BIAS、PPO/PPOS/PPOH、WT（WT1/WT2） |

| 项目 | 说明 |
|------|------|
| **写入表** | `cn_stock_indicators`（77 列） |

##### 2b. K 线形态识别（61 种形态）

基于 TA-Lib 的形态识别函数（`CDL` 系列），对每只股票的最新 K 线进行 61 种形态匹配。

| 结果值 | 含义 |
|-------|------|
| 正数 | 出现买入信号 |
| 0 | 未出现该形态 |
| 负数 | 出现卖出信号 |

**识别形态举例**：两只乌鸦、三只乌鸦、乌云压顶、十字星、锤头、上吊线、射击之星、暮星、晨星、吞噬模式、十字孕线、刺透形态、三线打击、母子线等共 61 种。

| 项目 | 说明 |
|------|------|
| **写入表** | `cn_stock_kline_pattern`（61 列） |

##### 2c. 策略选股检测（13 种策略）

对每只股票逐一检测是否满足各策略的买入/卖出条件。

| 策略名称 | 策略逻辑 | 写入表 |
|---------|---------|--------|
| 放量上涨 | 涨幅<2%且收阳、成交额≥2亿、量比≥2 | `cn_stock_strategy_enter` |
| 均线多头 | MA30 连续30日向上、涨幅>20% | `cn_stock_strategy_keep_increasing` |
| 停机坪 | 15日内涨停+放量上涨，后续高开缩量整理 | `cn_stock_strategy_parking_apron` |
| 回踩年线 | 突破250日均线后回踩不破+缩量 | `cn_stock_strategy_backtrace_ma250` |
| 突破平台 | 收盘价穿越60日均线+放量 | `cn_stock_strategy_breakthrough_platform` |
| 无大幅回撤 | 60日涨幅<60%、无单日跌7%或两日跌10% | `cn_stock_strategy_low_backtrace_increase` |
| 海龟交易法则 | 收盘价为近60日最高价 | `cn_stock_strategy_turtle_trade` |
| 高而窄的旗形 | 24~10日前涨幅≥90%+连续两日涨停 | `cn_stock_strategy_high_tight_flag` |
| 放量跌停 | 跌幅>9.5%、成交额≥2亿、量比≥4 | `cn_stock_strategy_climax_limitdown` |
| 低ATR成长 | 上市≥250日、近10日最高/最低价比≥1.1 | `cn_stock_strategy_low_atr` |
| 趋势回调 | 长期趋势向上时的回调买入机会 | `cn_stock_strategy_trend_pullback` |
| 超跌反弹 | 基本面未变、市场恐慌时超跌修复机会 | `cn_stock_strategy_oversold_rebound` |
| 突破确认 | 横盘整理后放量突破确认 | `cn_stock_strategy_breakout_confirm` |

> **注意**：「高而窄的旗形」策略需要龙虎榜数据（`cn_stock_lhb` 表），该数据由 `run_fetch` 入库，若无数据则此策略自动跳过。

##### 2d. 指标二次筛选（买入/卖出信号）

基于已入库的 `cn_stock_indicators` 数据进行二次 SQL 筛选。

| 信号类型 | 筛选条件 | 写入表 |
|---------|---------|--------|
| **买入信号** | KDJ-K≥80、KDJ-D≥70、KDJ-J≥100、RSI6≥80、CCI≥100、CR≥300、WR6≥-20、VR≥160 | `cn_stock_indicators_buy` |
| **卖出信号** | KDJ-K<20、KDJ-D<30、KDJ-J<10、RSI6<20、CCI<-100、CR<40、WR6<-80、VR<40 | `cn_stock_indicators_sell` |

| 项目 | 说明 |
|------|------|
| **预计耗时** | **< 1 秒**（纯 SQL 查询，不读取缓存） |

---

#### Step 3：策略回测

| 项目 | 说明 |
|------|------|
| **执行模块** | `backtest_data_daily_job.py` → `bdj.main()` |
| **执行方式** | 进程内直接调用 |
| **API 调用** | **无**（从磁盘缓存按需读取历史 K 线） |
| **功能** | 对各策略选出的股票进行历史收益率回测验证 |
| **预计耗时** | **1~3 分钟** |
| **峰值内存** | ~50 MB（流式读取，每批 50 只） |

##### 3a. 回测数据计算

| 项目 | 说明 |
|------|------|
| **回测对象** | 所有策略表中 backtest 列为 NULL 的记录（仅补算未回测的） |
| **覆盖策略表** | 指标买入、指标卖出、13 种 K 线策略、GPT 综合选股 = 共 **16 个表** |
| **计算方式** | 从磁盘缓存读取该股票历史 K 线 → 计算选出日后 1/3/5/10/20/30/60/90/120 日收益率 |
| **并发策略** | 外层逐表顺序处理（默认 1 线程），内层每批 50 只 × 2 线程并发读取缓存 |
| **写入方式** | UPDATE 更新原策略表的 `rate_1` ~ `rate_120` 等回测字段 |

**回测收益率字段**（共 9 个 horizon）:

| 字段 | 含义 |
|------|------|
| `rate_1` | 选出后 1 个交易日收益率 |
| `rate_3` | 选出后 3 个交易日收益率 |
| `rate_5` | 选出后 5 个交易日收益率 |
| `rate_10` | 选出后 10 个交易日收益率 |
| `rate_20` | 选出后 20 个交易日收益率 |
| `rate_30` | 选出后 30 个交易日收益率 |
| `rate_60` | 选出后 60 个交易日收益率 |
| `rate_90` | 选出后 90 个交易日收益率 |
| `rate_120` | 选出后 120 个交易日收益率 |

##### 3b. 回测汇总

| 项目 | 说明 |
|------|------|
| **功能** | 汇总各策略表的回测结果，按日期 × 策略维度统计 |
| **统计指标** | 选股数量、已回测数量、成功数量（rate>0）、成功率、各 horizon 平均收益率 |
| **成功率算法** | 优先使用 `rate_5`，不存在时降级 `rate_3` → `rate_1`，判断 > 0 的比例 |
| **写入表** | `cn_stock_backtest`（回测汇总表） |
| **预计耗时** | **1~5 秒** |

---

### 执行时间汇总

| 步骤 | 模块 | 主要计算内容 | 预计耗时 |
|------|------|------------|---------|
| 跳过检查 | `_is_analysis_done()` | 查询 DB 行数 | < 1 秒 |
| Step 1 | `gpt_value_data_job` | GPT 综合选股 | 1~5 秒 |
| Step 2a | `streaming_analysis_job` | 获取股票列表 | < 1 秒 |
| Step 2b | `streaming_analysis_job` | 流式分析（指标+形态+策略） | 2~8 分钟 |
| Step 2d | `streaming_analysis_job` | 指标二次筛选 | < 1 秒 |
| Step 3a | `backtest_data_daily_job` | 策略回测计算 | 1~3 分钟 |
| Step 3b | `backtest_data_daily_job` | 回测汇总统计 | 1~5 秒 |
| 清理 | 释放单例 + GC | 内存回收 | < 1 秒 |
| **总计** | | | **约 3~10 分钟** |

> **说明**：总耗时主要取决于 Step 2b（流式分析，~4900 只股票逐只处理）和 Step 3a（回测计算，仅处理 backtest 为 NULL 的记录）。首次运行回测量最大，后续每日仅补算新增选股记录。

---

### 数据写入表汇总

| 数据库表 | 数据类型 | 数据量级 | 来源步骤 |
|---------|---------|---------|---------|
| `cn_stock_strategy_gpt_value` | GPT 综合选股结果 | ~50~200 条/日 | Step 1 |
| `cn_stock_indicators` | 技术指标（77 列） | ~4800 条/日 | Step 2b |
| `cn_stock_kline_pattern` | K 线形态识别（61 列） | ~4800 条/日 | Step 2b |
| `cn_stock_strategy_enter` | 放量上涨策略 | ~10~100 条/日 | Step 2b |
| `cn_stock_strategy_keep_increasing` | 均线多头策略 | ~10~50 条/日 | Step 2b |
| `cn_stock_strategy_parking_apron` | 停机坪策略 | ~0~20 条/日 | Step 2b |
| `cn_stock_strategy_backtrace_ma250` | 回踩年线策略 | ~0~30 条/日 | Step 2b |
| `cn_stock_strategy_breakthrough_platform` | 突破平台策略 | ~5~50 条/日 | Step 2b |
| `cn_stock_strategy_low_backtrace_increase` | 无大幅回撤策略 | ~50~200 条/日 | Step 2b |
| `cn_stock_strategy_turtle_trade` | 海龟交易法则 | ~10~50 条/日 | Step 2b |
| `cn_stock_strategy_high_tight_flag` | 高而窄的旗形 | ~0~10 条/日 | Step 2b |
| `cn_stock_strategy_climax_limitdown` | 放量跌停策略 | ~0~30 条/日 | Step 2b |
| `cn_stock_strategy_low_atr` | 低 ATR 成长 | ~10~50 条/日 | Step 2b |
| `cn_stock_strategy_trend_pullback` | 趋势回调策略 | ~10~50 条/日 | Step 2b |
| `cn_stock_strategy_oversold_rebound` | 超跌反弹策略 | ~10~50 条/日 | Step 2b |
| `cn_stock_strategy_breakout_confirm` | 突破确认策略 | ~5~30 条/日 | Step 2b |
| `cn_stock_indicators_buy` | 买入信号筛选 | ~0~20 条/日 | Step 2d |
| `cn_stock_indicators_sell` | 卖出信号筛选 | ~0~20 条/日 | Step 2d |
| `cn_stock_backtest` | 回测汇总统计 | ~16 × 日期数 条 | Step 3b |

---

### 数据依赖关系

`run_analysis` 的所有数据来源均为本地，不发起任何外部 API 请求。

| 数据依赖 | 来源 | 提供方 | 缺失时行为 |
|---------|------|--------|-----------|
| `cn_stock_spot` 股票列表 | 数据库 | `run_fetch` → `basic_data_daily_job` | 降级为 `stock_data` 单例（可能发起 API） |
| `cn_stock_selection` 选股数据 | 数据库 | `run_fetch` → `selection_data_daily_job` | GPT 选股跳过，自动回退 7 天 |
| `cn_stock_lhb` 龙虎榜数据 | 数据库 | `run_fetch` → `basic_data_other_daily_job` | 高而窄旗形策略跳过 |
| `cache/hist/*.gzip.pickle` K 线缓存 | 磁盘文件 | `run_fetch` → `fetch_data_job` | 该股票跳过分析 |

> **重要**：即使 `run_fetch` 未执行或部分失败，`run_analysis` 仍可基于历史缓存数据运行（结果可能不包含当日行情）。

---

### 可调参数

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `INSTOCK_FORCE_ANALYSIS` | 空 | 设为 `1` 强制执行分析（跳过完成检查） |
| `INSTOCK_ANALYSIS_DONE_THRESHOLD` | `1000` | 分析完成判断阈值（`cn_stock_indicators` 行数） |
| `INSTOCK_BATCH_SIZE` | `50` | 流式分析每批处理股票数（越大内存越高） |
| `INSTOCK_ANALYSIS_WORKERS` | `2` | 流式分析并发线程数（适配 ≤2GB 服务器） |
| `INSTOCK_BACKTEST_OUTER_WORKERS` | `1` | 回测外层并发（逐表处理，默认顺序执行） |
| `INSTOCK_BACKTEST_INNER_WORKERS` | `2` | 回测内层并发（每批 50 只股票的读取线程数） |

---

### 容错机制

| 机制 | 说明 |
|------|------|
| **跳过已完成** | 检查 `cn_stock_indicators` 行数，已有足够数据则直接跳过 |
| **延迟删除** | 不在开头一次性 DELETE 所有表的当日数据，而是首次写入某表时才清理，避免中途崩溃丢数据 |
| **单只容错** | 单只股票处理失败不影响其他股票，错误计数记录到日志 |
| **表 Schema 自动修复** | 旧版数据库表列数不足时自动 DROP + 重建（如旧版 26 列 → 新版 77 列） |
| **缓存降级** | K 线缓存未覆盖当日时仍基于历史缓存计算（标记为 stale，日志告警） |
| **缓存过期检测** | 过期率 > 80% 时发出告警，提示 Phase 2（K 线缓存更新）可能 OOM 失败 |
| **GC 回收** | 每个 Step 完成后执行 `gc.collect()`，每批写入后也触发 GC，控制内存增长 |
| **日期回退** | GPT 选股支持 7 天日期回退，选股数据某天缺失不影响筛选 |

---

### 与 `run_fetch` 的协作关系

```
run_fetch（数据获取）                  run_analysis（数据分析）
─────────────────────                ──────────────────────
Phase 0: DB初始化                     
Phase 2: 实时行情 → cn_stock_spot  ─→  读取股票列表
Phase 2: 选股数据 → cn_stock_selection ─→  GPT综合选股
Phase 3: 龙虎榜   → cn_stock_lhb  ─→  高而窄旗形策略
Phase 1: K线缓存  → cache/hist/    ─→  流式分析 + 回测
```

- **独立运行**：`run_analysis` 可在 `run_fetch` 完成后任意时间运行
- **数据隔离**：获取和分析通过数据库表 + 缓存文件解耦，无进程间依赖
- **多机部署**：`run_fetch` 在高带宽机器运行（API 密集），`run_analysis` 在高 CPU 机器运行（计算密集）
- **容错降级**：即使 `run_fetch` 部分失败，`run_analysis` 仍可基于历史数据运行


# 安装说明

本系统支持Windows、Linux、MacOS，同时本系统创建了Docker镜像，按自己需要选择安装方式。

下面按分常规安装方式、docker镜像安装方式进行一一说明。

## 一：常规安装方式

建议windows下安装，方便操作及使用系统，同时安装也非常简单。

以下安装及运行以windows为例进行介绍。

### 1.安装python

项目开发使用python 3.11，建议最新版。

```
（1）在官网 https://www.python.org/downloads/ 下载安装包，一键安装即可，安装切记勾选自动设置环境变量。
（2）配置永久全局国内镜像库（因为有墙，无法正常安装库文件），执行如下dos命令：
python pip config --global set  global.index-url https://mirrors.aliyun.com/pypi/simple/
# 如果你只想为当前用户设置，你也可以去掉下面的"--global"选项
```
### 2.安装mysql

建议最新版。

```
在官网 https://dev.mysql.com/downloads/mysql/ 下载安装包，一键安装即可。
```
### 3.安装 TA-Lib 共享静态库和头文件

安装 TA-Lib C/C++ 共享静态库和头文件

```
https://ta-lib.org/install/ 下载最新 ta-lib 共享静态库和头文件，按照说明进行安装。
安装方式按官方建议，会更简单：
Windows Executable Installer
macOS Homebrew
Linux Debian packages
```

### 4.安装依赖库

依赖库都是目前最新版本。

a.安装依赖库：

```
#dos切换到本系统的根目录，执行下面命令：
python -m pip install -r requirements.txt
```
b.若想升级项目依赖库至最新版，可以通过下面方法：

先打开requirements.txt，然后修改文件中的“==”为“>=”，接着执行下面命令：

```
python -m pip install -r requirements.txt --upgrade
```

c.若扩展了本项目，可以通过下面方法生成项目依赖：

```
#使用pipreqs生成项目相关依赖的requirements.txt

python -m pip install pipreqs
# 安装pipreqs，若有安装可跳过

python -m pipreqs --encoding utf-8 --force ./ 
# 本项目是utf-8编码
```


### 5.安装 Navicat（可选）

Navicat可以方便管理数据库，以及可以手工对数据进行查看、处理、分析、挖掘。

Navicat是一套可创建多个连接的数据库管理工具，用以方便管理 MySQL、Oracle、PostgreSQL、SQLite、SQL Server、MariaDB 和 MongoDB 等不同类型的数据库

```
（1）在官网 https://www.navicat.com.cn/download/navicat-premium 下载安装包，一键安装即可。

（2）然后下载破解补丁: https://pan.baidu.com/s/18XpTHrm9OiLEl3u6z_uxnw 提取码: 8888 ，破解即可。
```
### 6.配置数据库

一般可能会修改的信息是”数据库访问密码“。

修改database.py相关信息:

```
db_host = "localhost"  # 数据库服务主机
db_user = "root"  # 数据库访问用户
db_password = "root"  # 数据库访问密码
db_port = 3306  # 数据库服务端口
db_charset = "utf8mb4"  # 数据库字符集
```

### 7.配置代理
不使用代理，跳过本步。

具体设置如下：
编辑proxy.txt，添加有效代理，格式为：ip:port，带认证代理username:password@ip:port，每个代理占一行。当不使用代理时清空该文件。
编辑保存完代理文件，若本系统已经启动，需要重启本系统，才能生效。
示例代理：
```
127.0.0.1:7860
52.13.248.29:3128
35.178.104.4:80
abc:123456@65.1.244.232:3128
13.126.79.133:80
54.212.22.168:3128
```
注意：以上均为无效代理。

### 8.设置东方财富网Cookie
东方财富数据获取频率过高，会限制获取数据，可以通过注入cookie解决。
以下是详细的操作步骤：
```
1、获取Cookie
    打开浏览器，访问东方财富网行情页面：https://quote.eastmoney.com/center/gridlist.html#hs_a_board
    登录账号（如果有东方财富网账号，建议登录以获取更稳定的Cookie）
    打开开发者工具：
    切换到Network（网络）选项卡
    刷新页面（按 F5 或点击浏览器刷新按钮）
    选择任意请求：在网络请求列表中，选择任意一个请求（建议选择URL包含 push2.eastmoney.com 的请求）
    查看Cookie：在请求详情中，找到 Request Headers（请求头）部分，复制完整的 Cookie 值
    保存Cookie：将复制的Cookie值保存下来，稍后使用
2、设置Cookie的两种方式
    方式一：通过环境变量设置（推荐）
    Windows系统：
    cmd命令： setx EAST_MONEY_COOKIE "你的Cookie值"
    重启Python环境：设置环境变量后，需要重启Python IDE或命令提示符窗口
    Linux/macOS系统：
    bash命令：export EAST_MONEY_COOKIE="你的Cookie值"
    注意：这种方式只在当前终端会话有效，若要永久设置，需要编辑 ~/.bashrc 或 ~/.zshrc 文件
    方式二：通过文件设置
    编辑eastmoney_cookie.txt文件，替换Cookie。
3、注意事项
    Cookie有效期：东方财富网的Cookie通常会在一段时间后过期（一般为几天到几周），如突然无法正常工作，可能是Cookie过期了，需要重新获取并设置
    定期更新：建议每隔一段时间（如每周）更新一次Cookie，以确保爬取的稳定性
    多账号轮换：如果有多个东方财富网账号，可以轮换使用不同账号的Cookie，进一步降低被限制的风险
```
### 9.安装自动交易（可选）

```
1.安装交易软件
    1.1 通用同花顺客户端券商的客户
        通用同花顺客户端:
        https://activity.ths123.com/acmake/cache/1361.html
    1.2 专用同花顺客户端券商的客户
        自行去券商官网找同花顺专用版
        例如：广发的下载核新独立委托端(同花顺版):
        http://www.gf.com.cn/softdownload/index?tab=1
2.安装tesseract(自动识别验证码)
    第一种方法.下载编译好的
        在下面链接页，根据操作系统选择相应版本
        https://digi.bib.uni-mannheim.de/tesseract/
    第二种方法.用源码编译
        下载源码：https://github.com/tesseract-ocr/tesseract
    注意：
        安装完要将安装路径设置到PATH环境变量里。
        下面提供dos命令设置，以管理员身份运行cmd，输入:
        setx /m PATH "%PATH%;C:\Program Files\Tesseract-OCR"
3.设置交易配置   
    3.1.修改trade_client.json
        "user": "888888888888",               #交易账号
        "password": "888888",                 #交易密码
        "exe_path": "C:/gfzqrzrq/xiadan.exe"  #交易软件路径
    3.2.修改trade_service.py
        broker = 'gf_client' #这是广发
        详情参阅usage.md，配置对应券商
```

### 10.运行说明

#### 10.1.执行数据抓取、处理、分析、识别

支持批量作业，具体参见run_job.bat中的注释说明。

建议将其加入到任务计划中，工作日的每天17：00执行。

**数据抓取、处理原则：**

1).开盘即有且无历史数据的：综合选股、每日股票数据、股票资金流向、股票分红配送、龙虎榜、每日ETF数据；

2).收盘即有且有历史数据的：股票指标数据、股票K线形态、股票策略数据；

3).收盘后1~2小时才有且有历史数据的：大宗交易。

运行run_job.bat，会依据上面原则获取各模块当前或前个交易日的数据。

```

运行 run_job.bat
```
若想看开盘后的当前实时数据，可以运行下面，很快大概1秒：

```
#基础数据作业 
python basic_data_daily_job.py
```
#### 10.2.启动web服务

```
运行 run_web.bat
```
启动服务后，打开浏览器，输入：http://localhost:9988/ ，即可使用本系统的可视化功能。

#### 10.3.启动交易服务

```
运行 run_trade.bat
```

## 二：docker镜像安装方式

没有docker环境，可以参考：[VirtualBox虚拟机安装Ubuntu](https://www.ljjyy.com/archives/2019/10/100590.html)，里面也介绍了python、docker等常用软件的安装，若想在Windows下安装docker自行百度。

### 1.配置代理
不使用代理，跳过本步。

系统安装完成后，可以通过编辑宿主机的代理文件，来配置代理。

具体设置如下：
编辑宿主的代理文件，添加有效代理，格式为：ip:port，带认证代理username:password@ip:port，每个代理占一行。当不使用代理时清空该文件。
编辑完代理文件，若本系统已经启动，需要重启本系统，才能生效。
示例创建代理：
```
sudo sh -c 'echo "127.0.0.1:7860" > /data/instockproxy.txt'
#创建代理文件，会自动替换掉原代理文件

sudo sh -c 'echo "52.13.248.29:3128" >> /data/instockproxy.txt'
#追加代理

sudo sh -c 'echo "abc:123456@35.178.104.4:80" >> /data/instockproxy.txt'
#追加代理
```
注意：以上均为无效代理。

### 2.配置东方财富网Cookie
不使用Cookie，跳过本步。

系统安装完成后，可以通过编辑宿主机的代理文件，来配置Cookie。
详细请参阅：常规安装方式，设置东方财富网Cookie。

```
sudo sh -c 'echo "你的Cookie值" > /data/eastmoneycookie.txt'
#创建代理文件，会自动替换掉原代理文件

```

### 3.安装数据库镜像

如果已经有Mysql、mariadb数据库可以跳过本步。

运行下面命令：

**特别提醒：执行命令的用户要有root权限，其他命令也如此。例如：ubuntu系统在命令前加上sudo** ，sudo docker......

```
docker network create InStockService

docker run -d --name InStockDbService \
    --network InStockService \
    -v /data/mariadb/data:/var/lib/instockdb \
    -e MYSQL_ROOT_PASSWORD=root \
    library/mariadb:latest
```

### 4.安装本系统镜像

a.若按上面【1.安装数据库镜像】装的数据库，运行下面命令：

```
docker run -dit --name InStock --network=InStockService \
    -p 9988:9988 \
    -v /data/instockproxy.txt:/data/InStock/instock/config/proxy.txt \
    -v /data/eastmoneycookie.txt:/data/InStock/instock/config/eastmoney_cookie.txt \
    -e db_host=InStockDbService \
    mayanghua/instock:latest
```

b.已经有Mysql、mariadb数据库，运行下面命令：

```
docker run -dit --name InStock \
    -p 9988:9988 \
    -v /data/instockproxy.txt:/data/InStock/instock/config/proxy.txt \
    -v /data/eastmoneycookie.txt:/data/InStock/instock/config/eastmoney_cookie.txt \
    -e db_host=localhost \
    -e db_user=root \
    -e db_password=root \
    -e db_database=instockdb \
    -e db_port=3306 \
    mayanghua/instock:latest
```

docker -e 参数说明：
```
db_host       # 数据库服务主机
db_user       # 数据库访问用户
db_password   # 数据库访问密码
db_database   # 数据库名称
db_port       # 数据库服务端口
```
按自己数据库实际情况配置参数。

### 5. 系统运行

启动容器后，会自动运行，首先会初始化数据、启动web服务。然后每小时执行“基础数据抓取”，每天17:30执行所有的数据抓取、处理、分析、识别、回测。

打开浏览器，输入：http://localhost:9988/ ，即可使用本系统的可视化功能。

### 6.历史数据

历史数据抓取、处理、分析、识别、回测，运行下面命令：

```
docker exec -it InStock bash 
cat InStock/instock/bin/run_job.sh
#查看run_job.sh注释,自己选择作业
------整体作业，支持批量作业------
当前时间作业 python execute_daily_job.py
单个时间作业 python execute_daily_job.py 2022-03-01
枚举时间作业 python execute_daily_job.py 2022-01-01,2021-02-08,2022-03-12
区间时间作业 python execute_daily_job.py 2022-01-01 2022-03-01
------单功能作业，支持批量作业，回测数据自动填补到当前
数据获取管道 python fetch_daily_job.py  (Phase 1-3 + 收盘后，包含所有API调用)
数据分析管道 python analysis_daily_job.py  (GPT + 流式分析 + 回测，零API调用)
数据获取作业 python fetch_data_job.py  (实时行情+历史K线+缓存清理)
基础数据实时作业 python basic_data_daily_job.py
基础数据非实时作业 python basic_data_other_daily_job.py
综合选股作业 python selection_data_daily_job.py
GPT综合选股作业 python gpt_value_data_job.py
流式分析作业 python streaming_analysis_job.py  (指标+K线+策略，替代旧版三个独立作业)
回测数据 python backtest_data_daily_job.py
基础数据收盘2小时后 python basic_data_after_close_daily_job.py
------旧版独立作业（仍可运行但内存较高，已被streaming_analysis_job替代）
指标数据作业 python indicators_data_daily_job.py
K线形态作业 python klinepattern_data_daily_job.py
策略数据作业 python strategy_data_daily_job.py
第一种方法：
python execute_daily_job.py 2023-03-01,2023-03-02
第二种方法：
修改run_job.sh，然后运行 bash InStock/instock/bin/run_job.sh
```

### 7.查看日志

运行下面命令：

```
docker exec -it InStock bash 
cat InStock/instock/log/stock_execute_job.log
cat InStock/instock/log/stock_web.log
```

### 8.docker常用命令

```
docker container stop InStock InStockDbService
#停止容器
docker container prune
#回收容器
docker rmi mayanghua/instock:latest library/mariadb:latest
#删除镜像
```

具体参见：[Docker基础之 二.镜像及容器的基本操作](https://www.ljjyy.com/archives/2018/06/100208.html)

### 9.自动交易

目前只支持windows。参考常规安装方式,只需安装python、依赖库，**不需安装mysql、talib等**。

# 特别声明

股市有风险投资需谨慎，本系统只能用于学习、股票分析，投资盈亏概不负责。

本系统中的表格为第三方商业控件，仅使用了评估版进行学习及测试。
