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
  `bid_trust_amount` bigint DEFAULT NULL,
  `trust_amount_chg` float DEFAULT NULL,
  `bid_ratio` float DEFAULT NULL,
  `open_turnover` float DEFAULT NULL,
  `stock_holder_num` bigint DEFAULT NULL,
  `industry` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 8. 尾盘抢筹表
CREATE TABLE IF NOT EXISTS `cn_stock_chip_race_end` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `bid_trust_amount` bigint DEFAULT NULL,
  `trust_amount_chg` float DEFAULT NULL,
  `bid_ratio` float DEFAULT NULL,
  `close_turnover` float DEFAULT NULL,
  `stock_holder_num` bigint DEFAULT NULL,
  `industry` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 9. 涨停原因表
CREATE TABLE IF NOT EXISTS `cn_stock_limitup_reason` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `reason` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `limitup_times` int DEFAULT NULL,
  `first_limitup_time` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `last_limitup_time` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `open_times` int DEFAULT NULL,
  `order_amount` bigint DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `turnoverrate` float DEFAULT NULL,
  `free_cap` bigint DEFAULT NULL,
  `limit_height` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
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
  `lhb_net_buy` bigint DEFAULT NULL,
  `lhb_buy` bigint DEFAULT NULL,
  `lhb_sell` bigint DEFAULT NULL,
  `lhb_turnover` float DEFAULT NULL,
  `net_buy_ratio` float DEFAULT NULL,
  `deal_amount` bigint DEFAULT NULL,
  `turnoverrate` float DEFAULT NULL,
  `free_cap` bigint DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 12. 大宗交易表
CREATE TABLE IF NOT EXISTS `cn_stock_blocktrade` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `blocktrade_price` float DEFAULT NULL,
  `blocktrade_amount` bigint DEFAULT NULL,
  `blocktrade_volume` bigint DEFAULT NULL,
  `premium_rate` float DEFAULT NULL,
  `blocktrade_buyer` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `blocktrade_seller` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `blocktrade_tradenum` int DEFAULT NULL,
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
CREATE TABLE IF NOT EXISTS `cn_stock_selection` (
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
  `strategies` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 15. 股票指标表
CREATE TABLE IF NOT EXISTS `cn_stock_indicators` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `ma5` float DEFAULT NULL,
  `ma10` float DEFAULT NULL,
  `ma20` float DEFAULT NULL,
  `ma60` float DEFAULT NULL,
  `ma120` float DEFAULT NULL,
  `ma250` float DEFAULT NULL,
  `macd` float DEFAULT NULL,
  `macd_dea` float DEFAULT NULL,
  `macd_dif` float DEFAULT NULL,
  `kdj_k` float DEFAULT NULL,
  `kdj_d` float DEFAULT NULL,
  `kdj_j` float DEFAULT NULL,
  `rsi_6` float DEFAULT NULL,
  `rsi_12` float DEFAULT NULL,
  `rsi_24` float DEFAULT NULL,
  `boll_upper` float DEFAULT NULL,
  `boll_mid` float DEFAULT NULL,
  `boll_lower` float DEFAULT NULL,
  `cci` float DEFAULT NULL,
  `atr` float DEFAULT NULL,
  `sar` float DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 16. 指标买入选股表
CREATE TABLE IF NOT EXISTS `cn_stock_indicators_buy` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `indicators` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 17. 指标卖出选股表
CREATE TABLE IF NOT EXISTS `cn_stock_indicators_sell` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `indicators` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 18. K线形态表
CREATE TABLE IF NOT EXISTS `cn_stock_kline_pattern` (
  `date` date NOT NULL,
  `code` varchar(6) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `new_price` float DEFAULT NULL,
  `change_rate` float DEFAULT NULL,
  `patterns` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  PRIMARY KEY (`date`, `code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 19. 交易日历表
CREATE TABLE IF NOT EXISTS `cn_stock_trade_date` (
  `trade_date` date NOT NULL,
  PRIMARY KEY (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 完成提示
SELECT 'InStock 数据库初始化完成!' AS message;
