-- InStock 数据库初始化脚本
-- 版本: 2.2
-- 用途: 创建所有必需的数据库表

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS `instockdb` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `instockdb`;

-- 1. 我的关注表
CREATE TABLE IF NOT EXISTS `cn_stock_attention` (
  `datetime` datetime DEFAULT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  PRIMARY KEY (`code`),
  KEY `INIX_DATETIME` (`datetime`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 2. 每日股票数据表
CREATE TABLE IF NOT EXISTS `cn_stock_spot` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `ups_downs` float DEFAULT NULL,
  `volume` bigint DEFAULT NULL,
  `deal_amount` bigint DEFAULT NULL,
  `amplitude` float DEFAULT NULL,
  `turnoverrate` float DEFAULT NULL,
  `volume_ratio` float DEFAULT NULL,
  `open_price` float DEFAULT NULL,
  `high_price` float DEFAULT NULL,
  `low_price` float DEFAULT NULL,
  `pre_close_price` float DEFAULT NULL,
  `speed_increase` float DEFAULT NULL,
  `speed_increase_5` float DEFAULT NULL,
  `speed_increase_60` float DEFAULT NULL,
  `speed_increase_all` float DEFAULT NULL,
  `dtsyl` float DEFAULT NULL,
  `pe9` float DEFAULT NULL,
  `pe` float DEFAULT NULL,
  `pbnewmrq` float DEFAULT NULL,
  `basic_eps` float DEFAULT NULL,
  `bvps` float DEFAULT NULL,
  `per_capital_reserve` float DEFAULT NULL,
  `per_unassign_profit` float DEFAULT NULL,
  `roe_weight` float DEFAULT NULL,
  `sale_gpr` float DEFAULT NULL,
  `debt_asset_ratio` float DEFAULT NULL,
  `total_operate_income` bigint DEFAULT NULL,
  `toi_yoy_ratio` float DEFAULT NULL,
  `parent_netprofit` bigint DEFAULT NULL,
  `netprofit_yoy_ratio` float DEFAULT NULL,
  `report_date` date DEFAULT NULL,
  `total_shares` bigint DEFAULT NULL,
  `free_shares` bigint DEFAULT NULL,
  `total_market_cap` bigint DEFAULT NULL,
  `free_cap` bigint DEFAULT NULL,
  `industry` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `listing_date` date DEFAULT NULL,
  PRIMARY KEY (`date`, `code`),
  KEY `idx_code` (`code`),
  KEY `idx_date` (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 3. 基本面选股表
CREATE TABLE IF NOT EXISTS `cn_stock_spot_buy` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `ups_downs` float DEFAULT NULL,
  `volume` bigint DEFAULT NULL,
  `deal_amount` bigint DEFAULT NULL,
  `amplitude` float DEFAULT NULL,
  `turnoverrate` float DEFAULT NULL,
  `volume_ratio` float DEFAULT NULL,
  `open_price` float DEFAULT NULL,
  `high_price` float DEFAULT NULL,
  `low_price` float DEFAULT NULL,
  `pre_close_price` float DEFAULT NULL,
  `speed_increase` float DEFAULT NULL,
  `speed_increase_5` float DEFAULT NULL,
  `speed_increase_60` float DEFAULT NULL,
  `speed_increase_all` float DEFAULT NULL,
  `dtsyl` float DEFAULT NULL,
  `pe9` float DEFAULT NULL,
  `pe` float DEFAULT NULL,
  `pbnewmrq` float DEFAULT NULL,
  `basic_eps` float DEFAULT NULL,
  `bvps` float DEFAULT NULL,
  `per_capital_reserve` float DEFAULT NULL,
  `per_unassign_profit` float DEFAULT NULL,
  `roe_weight` float DEFAULT NULL,
  `sale_gpr` float DEFAULT NULL,
  `debt_asset_ratio` float DEFAULT NULL,
  `total_operate_income` bigint DEFAULT NULL,
  `toi_yoy_ratio` float DEFAULT NULL,
  `parent_netprofit` bigint DEFAULT NULL,
  `netprofit_yoy_ratio` float DEFAULT NULL,
  `report_date` date DEFAULT NULL,
  `total_shares` bigint DEFAULT NULL,
  `free_shares` bigint DEFAULT NULL,
  `total_market_cap` bigint DEFAULT NULL,
  `free_cap` bigint DEFAULT NULL,
  `industry` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `listing_date` date DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 4. 股票资金流向表
CREATE TABLE IF NOT EXISTS `cn_stock_fund_flow` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `fund_amount` bigint DEFAULT NULL,
  `fund_rate` float DEFAULT NULL,
  `fund_amount_super` bigint DEFAULT NULL,
  `fund_rate_super` float DEFAULT NULL,
  `fund_amount_large` bigint DEFAULT NULL,
  `fund_rate_large` float DEFAULT NULL,
  `fund_amount_medium` bigint DEFAULT NULL,
  `fund_rate_medium` float DEFAULT NULL,
  `fund_amount_small` bigint DEFAULT NULL,
  `fund_rate_small` float DEFAULT NULL,
  `change_rate_3` float DEFAULT NULL,
  `fund_amount_3` bigint DEFAULT NULL,
  `fund_rate_3` float DEFAULT NULL,
  `fund_amount_super_3` bigint DEFAULT NULL,
  `fund_rate_super_3` float DEFAULT NULL,
  `fund_amount_large_3` bigint DEFAULT NULL,
  `fund_rate_large_3` float DEFAULT NULL,
  `fund_amount_medium_3` bigint DEFAULT NULL,
  `fund_rate_medium_3` float DEFAULT NULL,
  `fund_amount_small_3` bigint DEFAULT NULL,
  `fund_rate_small_3` float DEFAULT NULL,
  `change_rate_5` float DEFAULT NULL,
  `fund_amount_5` bigint DEFAULT NULL,
  `fund_rate_5` float DEFAULT NULL,
  `fund_amount_super_5` bigint DEFAULT NULL,
  `fund_rate_super_5` float DEFAULT NULL,
  `fund_amount_large_5` bigint DEFAULT NULL,
  `fund_rate_large_5` float DEFAULT NULL,
  `fund_amount_medium_5` bigint DEFAULT NULL,
  `fund_rate_medium_5` float DEFAULT NULL,
  `fund_amount_small_5` bigint DEFAULT NULL,
  `fund_rate_small_5` float DEFAULT NULL,
  `change_rate_10` float DEFAULT NULL,
  `fund_amount_10` bigint DEFAULT NULL,
  `fund_rate_10` float DEFAULT NULL,
  `fund_amount_super_10` bigint DEFAULT NULL,
  `fund_rate_super_10` float DEFAULT NULL,
  `fund_amount_large_10` bigint DEFAULT NULL,
  `fund_rate_large_10` float DEFAULT NULL,
  `fund_amount_medium_10` bigint DEFAULT NULL,
  `fund_rate_medium_10` float DEFAULT NULL,
  `fund_amount_small_10` bigint DEFAULT NULL,
  `fund_rate_small_10` float DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 5. 行业资金流向表
CREATE TABLE IF NOT EXISTS `cn_stock_fund_flow_industry` (
  `date` date NOT NULL,
  `name` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `change_rate` float DEFAULT NULL,
  `fund_amount` bigint DEFAULT NULL,
  `fund_rate` float DEFAULT NULL,
  `fund_amount_super` bigint DEFAULT NULL,
  `fund_rate_super` float DEFAULT NULL,
  `fund_amount_large` bigint DEFAULT NULL,
  `fund_rate_large` float DEFAULT NULL,
  `fund_amount_medium` bigint DEFAULT NULL,
  `fund_rate_medium` float DEFAULT NULL,
  `fund_amount_small` bigint DEFAULT NULL,
  `fund_rate_small` float DEFAULT NULL,
  `stock_name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `change_rate_5` float DEFAULT NULL,
  `fund_amount_5` bigint DEFAULT NULL,
  `fund_rate_5` float DEFAULT NULL,
  `fund_amount_super_5` bigint DEFAULT NULL,
  `fund_rate_super_5` float DEFAULT NULL,
  `fund_amount_large_5` bigint DEFAULT NULL,
  `fund_rate_large_5` float DEFAULT NULL,
  `fund_amount_medium_5` bigint DEFAULT NULL,
  `fund_rate_medium_5` float DEFAULT NULL,
  `fund_amount_small_5` bigint DEFAULT NULL,
  `fund_rate_small_5` float DEFAULT NULL,
  `stock_name_5` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `change_rate_10` float DEFAULT NULL,
  `fund_amount_10` bigint DEFAULT NULL,
  `fund_rate_10` float DEFAULT NULL,
  `fund_amount_super_10` bigint DEFAULT NULL,
  `fund_rate_super_10` float DEFAULT NULL,
  `fund_amount_large_10` bigint DEFAULT NULL,
  `fund_rate_large_10` float DEFAULT NULL,
  `fund_amount_medium_10` bigint DEFAULT NULL,
  `fund_rate_medium_10` float DEFAULT NULL,
  `fund_amount_small_10` bigint DEFAULT NULL,
  `fund_rate_small_10` float DEFAULT NULL,
  `stock_name_10` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`date`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 6. 概念资金流向表
CREATE TABLE IF NOT EXISTS `cn_stock_fund_flow_concept` (
  `date` date NOT NULL,
  `name` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `change_rate` float DEFAULT NULL,
  `fund_amount` bigint DEFAULT NULL,
  `fund_rate` float DEFAULT NULL,
  `fund_amount_super` bigint DEFAULT NULL,
  `fund_rate_super` float DEFAULT NULL,
  `fund_amount_large` bigint DEFAULT NULL,
  `fund_rate_large` float DEFAULT NULL,
  `fund_amount_medium` bigint DEFAULT NULL,
  `fund_rate_medium` float DEFAULT NULL,
  `fund_amount_small` bigint DEFAULT NULL,
  `fund_rate_small` float DEFAULT NULL,
  `stock_name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `change_rate_5` float DEFAULT NULL,
  `fund_amount_5` bigint DEFAULT NULL,
  `fund_rate_5` float DEFAULT NULL,
  `fund_amount_super_5` bigint DEFAULT NULL,
  `fund_rate_super_5` float DEFAULT NULL,
  `fund_amount_large_5` bigint DEFAULT NULL,
  `fund_rate_large_5` float DEFAULT NULL,
  `fund_amount_medium_5` bigint DEFAULT NULL,
  `fund_rate_medium_5` float DEFAULT NULL,
  `fund_amount_small_5` bigint DEFAULT NULL,
  `fund_rate_small_5` float DEFAULT NULL,
  `stock_name_5` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `change_rate_10` float DEFAULT NULL,
  `fund_amount_10` bigint DEFAULT NULL,
  `fund_rate_10` float DEFAULT NULL,
  `fund_amount_super_10` bigint DEFAULT NULL,
  `fund_rate_super_10` float DEFAULT NULL,
  `fund_amount_large_10` bigint DEFAULT NULL,
  `fund_rate_large_10` float DEFAULT NULL,
  `fund_amount_medium_10` bigint DEFAULT NULL,
  `fund_rate_medium_10` float DEFAULT NULL,
  `fund_amount_small_10` bigint DEFAULT NULL,
  `fund_rate_small_10` float DEFAULT NULL,
  `stock_name_10` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`date`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 7. 早盘抢筹表
CREATE TABLE IF NOT EXISTS `cn_stock_chip_race_open` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `pre_close_price` float DEFAULT NULL,
  `open_price` float DEFAULT NULL,
  `deal_amount` bigint DEFAULT NULL,
  `bid_rate` float DEFAULT NULL,
  `bid_trust_amount` bigint DEFAULT NULL,
  `bid_deal_amount` bigint DEFAULT NULL,
  `bid_ratio` float DEFAULT NULL,
  `limitup_day` smallint DEFAULT NULL,
  `limitup_board` smallint DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 8. 尾盘抢筹表
CREATE TABLE IF NOT EXISTS `cn_stock_chip_race_end` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `pre_close_price` float DEFAULT NULL,
  `open_price` float DEFAULT NULL,
  `deal_amount` bigint DEFAULT NULL,
  `bid_rate` float DEFAULT NULL,
  `bid_trust_amount` bigint DEFAULT NULL,
  `bid_deal_amount` bigint DEFAULT NULL,
  `bid_ratio` float DEFAULT NULL,
  `limitup_day` smallint DEFAULT NULL,
  `limitup_board` smallint DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 9. 涨停原因表
CREATE TABLE IF NOT EXISTS `cn_stock_limitup_reason` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `reason` varchar(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `ups_downs` float DEFAULT NULL,
  `turnoverrate` float DEFAULT NULL,
  `volume` bigint DEFAULT NULL,
  `deal_amount` bigint DEFAULT NULL,
  `dde` bigint DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 10. 股票分红配送表
CREATE TABLE IF NOT EXISTS `cn_stock_bonus` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `convertible_total_rate` float DEFAULT NULL,
  `convertible_rate` float DEFAULT NULL,
  `convertible_transfer_rate` float DEFAULT NULL,
  `bonusaward_rate` float DEFAULT NULL,
  `bonusaward_yield` float DEFAULT NULL,
  `basic_eps` float DEFAULT NULL,
  `bvps` float DEFAULT NULL,
  `per_capital_reserve` float DEFAULT NULL,
  `per_unassign_profit` float DEFAULT NULL,
  `netprofit_yoy_ratio` float DEFAULT NULL,
  `total_shares` bigint DEFAULT NULL,
  `plan_date` date DEFAULT NULL,
  `record_date` date DEFAULT NULL,
  `ex_dividend_date` date DEFAULT NULL,
  `progress` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `report_date` date DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 11. 股票龙虎榜表
CREATE TABLE IF NOT EXISTS `cn_stock_lhb` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `ranking_times` date DEFAULT NULL,
  `interpret` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `net_amount_buy` float DEFAULT NULL,
  `sum_buy` float DEFAULT NULL,
  `sum_sell` float DEFAULT NULL,
  `lhb_amount` float DEFAULT NULL,
  `market_amount` float DEFAULT NULL,
  `net_amount_rate` float DEFAULT NULL,
  `sum_rate` float DEFAULT NULL,
  `turnoverrate` float DEFAULT NULL,
  `free_cap` bigint DEFAULT NULL,
  `reason` varchar(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `ranking_after_1` float DEFAULT NULL,
  `ranking_after_2` float DEFAULT NULL,
  `ranking_after_5` float DEFAULT NULL,
  `ranking_after_10` float DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 12. 大宗交易表
CREATE TABLE IF NOT EXISTS `cn_stock_blocktrade` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `average_price` float DEFAULT NULL,
  `overflow_rate` float DEFAULT NULL,
  `trade_number` float DEFAULT NULL,
  `sum_volume` float DEFAULT NULL,
  `sum_turnover` float DEFAULT NULL,
  `turnover_market_rate` float DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 13. 每日ETF数据表
CREATE TABLE IF NOT EXISTS `cn_etf_spot` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `ups_downs` float DEFAULT NULL,
  `volume` bigint DEFAULT NULL,
  `deal_amount` bigint DEFAULT NULL,
  `open_price` float DEFAULT NULL,
  `high_price` float DEFAULT NULL,
  `low_price` float DEFAULT NULL,
  `pre_close_price` float DEFAULT NULL,
  `turnoverrate` float DEFAULT NULL,
  `total_market_cap` bigint DEFAULT NULL,
  `free_cap` bigint DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 14. 综合选股表
-- 注意: 该表列数较多(140+列)，由代码自动创建。
-- 如需手动创建，请参考 instock/core/tablestructure.py 中 TABLE_CN_STOCK_SELECTION 的定义。
-- 代码在表不存在时会通过 SQLAlchemy 自动创建正确的表结构。

-- 15. 股票指标表
-- 注意: 该表列70+列，由代码自动创建。
-- 如需手动创建，请参考 instock/core/tablestructure.py 中 TABLE_CN_STOCK_INDICATORS 的定义。
-- 代码在表不存在时会通过 SQLAlchemy 自动创建正确的表结构。

-- 16. 指标买入选股表
-- 注意: 该表包含 date/code/name + rate_1到rate_100 共103列，由代码自动创建。
-- 代码在表不存在时会通过 SQLAlchemy 自动创建正确的表结构。

-- 17. 指标卖出选股表
-- 同上，由代码自动创建。

-- 18. K线形态表
-- 注意: 该表包含 date/code/name + 63个形态列 共66列，由代码自动创建。
-- 代码在表不存在时会通过 SQLAlchemy 自动创建正确的表结构。

-- 19. 交易日历表
CREATE TABLE IF NOT EXISTS `cn_stock_trade_date` (
  `trade_date` date NOT NULL,
  PRIMARY KEY (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 20-29. 策略选股表（包含回测数据列）
-- 通用策略表结构：基础信息 + 100日收益率
-- 注意: 该表包含 date/code/name + rate_1到rate_100 共103列，由代码自动创建。
-- 代码在表不存在时会通过 SQLAlchemy 自动创建正确的表结构。
-- 包括以下策略表:
-- cn_stock_strategy_enter (放量上涨)
-- cn_stock_strategy_keep_increasing (均线多头)
-- cn_stock_strategy_parking_apron (停机坪)
-- cn_stock_strategy_backtrace_ma250 (回踩年线)
-- cn_stock_strategy_breakthrough_platform (突破平台)
-- cn_stock_strategy_low_backtrace_increase (无大幅回撤)
-- cn_stock_strategy_turtle_trade (海龟交易法则)
-- cn_stock_strategy_high_tight_flag (高而窄的旗形)
-- cn_stock_strategy_climax_limitdown (放量跌停)
-- cn_stock_strategy_low_atr (低ATR成长)
-- cn_stock_strategy_trend_pullback (趋势回调)
-- cn_stock_strategy_oversold_rebound (超跌反弹)
-- cn_stock_strategy_breakout_confirm (突破确认)
-- cn_stock_strategy_gpt_value (GPT综合选股)

-- 30. 回测汇总表
CREATE TABLE IF NOT EXISTS `cn_stock_backtest` (
  `date` date NOT NULL,
  `strategy_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `stock_count` int DEFAULT NULL,
  `success_count` int DEFAULT NULL,
  `success_rate` float DEFAULT NULL,
  `avg_rate_1` float DEFAULT NULL,
  `avg_rate_3` float DEFAULT NULL,
  `avg_rate_5` float DEFAULT NULL,
  `avg_rate_10` float DEFAULT NULL,
  `avg_rate_20` float DEFAULT NULL,
  PRIMARY KEY (`date`, `strategy_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 完成提示
SELECT 'InStock 数据库初始化完成!' AS message;
