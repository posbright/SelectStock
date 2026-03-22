"""
A股历史财务数据采集脚本
数据来源：AkShare (https://akshare.akfamily.xyz)
目标数据库：stockbasedata (MySQL)

采集内容：
  1. stock_basic_info              - A股股票基础信息
  2. stock_financial_indicators    - 个股财务分析指标（新浪财经，含PB相关的每股净资产等）
  3. stock_financial_indicators_em - 个股财务分析指标（东方财富，含EPS/BPS/ROE等）
  4. stock_market_pb_history       - 全市场历史PB（中位数/等权均值，乐咕乐股）

用法：
  python stock_financial_data.py            # 全量采集
  python stock_financial_data.py --test 10  # 测试模式，仅采集前10只股票
  python stock_financial_data.py --skip-sina  # 跳过新浪接口
  python stock_financial_data.py --skip-em    # 跳过东方财富接口
"""

import akshare as ak
import pandas as pd
import pymysql
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import logging
import time
import warnings
import argparse
from datetime import datetime

warnings.filterwarnings("ignore")

# ─── 配置 ────────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "Dzm@ming&662",
    "database": "stockbasedata",
    "charset": "utf8mb4",
}

START_YEAR = "2015"          # 新浪接口起始年份
SLEEP_PER_STOCK = 3        # 每只股票采集间隔(秒)
RETRY_TIMES = 2              # 接口重试次数
RETRY_SLEEP = 5              # 重试间隔(秒)

# ─── 日志 ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("stock_financial_data.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ─── 数据库工具 ───────────────────────────────────────────────────────────────
def get_engine():
    pw = quote_plus(DB_CONFIG["password"])
    url = (
        f"mysql+pymysql://{DB_CONFIG['user']}:{pw}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        f"?charset={DB_CONFIG['charset']}"
    )
    return create_engine(url, pool_pre_ping=True)


def init_tables(engine):
    """建表（幂等）"""
    ddl_list = [
        # ── 表1：股票基础信息 ─────────────────────────────────────────────────
        """
        CREATE TABLE IF NOT EXISTS stock_basic_info (
            id          BIGINT AUTO_INCREMENT PRIMARY KEY,
            stock_code  VARCHAR(10) NOT NULL COMMENT '股票代码(6位)',
            stock_name  VARCHAR(50) COMMENT '股票简称',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_code (stock_code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='A股股票基础信息';
        """,

        # ── 表2：新浪财经个股财务分析指标 ────────────────────────────────────
        """
        CREATE TABLE IF NOT EXISTS stock_financial_indicators (
            id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
            stock_code              VARCHAR(10)   NOT NULL COMMENT '股票代码',
            report_date             DATE          NOT NULL COMMENT '报告期',
            eps                     DECIMAL(20,4) COMMENT '摊薄每股收益(元)',
            eps_weighted            DECIMAL(20,4) COMMENT '加权每股收益(元)',
            eps_ex_extra            DECIMAL(20,4) COMMENT '扣非每股收益(元)',
            bps_before              DECIMAL(20,4) COMMENT '每股净资产_调整前(元)',
            bps_after               DECIMAL(20,4) COMMENT '每股净资产_调整后(元)',
            ocfps                   DECIMAL(20,4) COMMENT '每股经营性现金流(元)',
            capital_reserve_ps      DECIMAL(20,4) COMMENT '每股资本公积金(元)',
            undistrib_profit_ps     DECIMAL(20,4) COMMENT '每股未分配利润(元)',
            roa                     DECIMAL(20,4) COMMENT '总资产利润率(%)',
            net_profit_margin       DECIMAL(20,4) COMMENT '销售净利率(%)',
            gross_margin            DECIMAL(20,4) COMMENT '销售毛利率(%)',
            roe                     DECIMAL(20,4) COMMENT '净资产收益率(%)',
            roe_weighted            DECIMAL(20,4) COMMENT '加权净资产收益率(%)',
            revenue_growth          DECIMAL(20,4) COMMENT '主营业务收入增长率(%)',
            netprofit_growth        DECIMAL(20,4) COMMENT '净利润增长率(%)',
            netasset_growth         DECIMAL(20,4) COMMENT '净资产增长率(%)',
            totalasset_growth       DECIMAL(20,4) COMMENT '总资产增长率(%)',
            current_ratio           DECIMAL(20,4) COMMENT '流动比率',
            quick_ratio             DECIMAL(20,4) COMMENT '速动比率',
            asset_liab_ratio        DECIMAL(20,4) COMMENT '资产负债率(%)',
            total_assets            DECIMAL(30,2) COMMENT '总资产(元)',
            inventory_turnover      DECIMAL(20,4) COMMENT '存货周转率(次)',
            receivable_turnover     DECIMAL(20,4) COMMENT '应收账款周转率(次)',
            total_asset_turnover    DECIMAL(20,4) COMMENT '总资产周转率(次)',
            cashflow_to_liab        DECIMAL(20,4) COMMENT '经营现金净流量对负债比率(%)',
            cashflow_to_revenue     DECIMAL(20,4) COMMENT '经营现金净流量对销售收入比率(%)',
            created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_stock_date (stock_code, report_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
          COMMENT='个股财务分析指标-新浪财经(含每股净资产/PB基础数据)';
        """,

        # ── 表3：东方财富个股财务分析指标 ────────────────────────────────────
        """
        CREATE TABLE IF NOT EXISTS stock_financial_indicators_em (
            id                   BIGINT AUTO_INCREMENT PRIMARY KEY,
            secucode             VARCHAR(15)   NOT NULL COMMENT '完整证券代码(如000001.SZ)',
            stock_code           VARCHAR(10)   NOT NULL COMMENT '股票代码',
            stock_name           VARCHAR(50)   COMMENT '股票简称',
            report_date          DATE          NOT NULL COMMENT '报告期',
            report_type          VARCHAR(20)   COMMENT '报告类型(年报/季报等)',
            report_date_name     VARCHAR(50)   COMMENT '报告期名称',
            notice_date          DATE          COMMENT '公告日期',
            currency             VARCHAR(10)   COMMENT '货币单位',
            eps                  DECIMAL(20,4) COMMENT '每股收益-基本(元)',
            eps_ex_extra         DECIMAL(20,4) COMMENT '每股收益-扣非(元)',
            bps                  DECIMAL(20,4) COMMENT '每股净资产(元)',
            capital_reserve_ps   DECIMAL(20,4) COMMENT '每股资本公积(元)',
            undistrib_profit_ps  DECIMAL(20,4) COMMENT '每股未分配利润(元)',
            ocfps                DECIMAL(20,4) COMMENT '每股经营现金流(元)',
            revenue              DECIMAL(30,2) COMMENT '营业总收入(元)',
            gross_margin         DECIMAL(20,4) COMMENT '毛利率(%)',
            net_profit           DECIMAL(30,2) COMMENT '归母净利润(元)',
            net_profit_ex        DECIMAL(30,2) COMMENT '扣非归母净利润(元)',
            revenue_growth       DECIMAL(20,4) COMMENT '营收同比增长(%)',
            netprofit_growth     DECIMAL(20,4) COMMENT '净利润同比增长(%)',
            roe                  DECIMAL(20,4) COMMENT 'ROE净资产收益率(%)',
            roe_ex               DECIMAL(20,4) COMMENT '扣非ROE(%)',
            roa                  DECIMAL(20,4) COMMENT '总资产净利率(%)',
            net_profit_margin    DECIMAL(20,4) COMMENT '净利率(%)',
            cash_flow_ratio      DECIMAL(20,4) COMMENT '现金流量比率(%)',
            asset_liab_ratio     DECIMAL(20,4) COMMENT '资产负债率(%)',
            current_ratio        DECIMAL(20,4) COMMENT '流动比率',
            quick_ratio          DECIMAL(20,4) COMMENT '速动比率',
            interest_coverage    DECIMAL(20,4) COMMENT '利息保障倍数',
            total_asset_turnover DECIMAL(20,4) COMMENT '总资产周转率(次)',
            inventory_turnover   DECIMAL(20,4) COMMENT '存货周转率(次)',
            receivable_turnover  DECIMAL(20,4) COMMENT '应收账款周转率(次)',
            bps_growth           DECIMAL(20,4) COMMENT '每股净资产增长率(%)',
            created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_stock_date (secucode, report_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
          COMMENT='个股财务分析指标-东方财富(含EPS/BPS/ROE/资产负债率等)';
        """,

        # ── 表4：全市场历史PB ─────────────────────────────────────────────────
        """
        CREATE TABLE IF NOT EXISTS stock_market_pb_history (
            id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
            trade_date              DATE          NOT NULL COMMENT '交易日期',
            middle_pb               DECIMAL(10,4) COMMENT 'PB中位数',
            equal_weight_avg_pb     DECIMAL(10,4) COMMENT 'PB等权均值',
            close                   DECIMAL(10,4) COMMENT '沪深全A收盘指数',
            quantile_all_middle_pb  DECIMAL(10,6) COMMENT '历史全区间中位数PB分位',
            quantile_10y_middle_pb  DECIMAL(10,6) COMMENT '近10年中位数PB分位',
            quantile_all_ewavg_pb   DECIMAL(10,6) COMMENT '历史全区间等权均值PB分位',
            quantile_10y_ewavg_pb   DECIMAL(10,6) COMMENT '近10年等权均值PB分位',
            created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_trade_date (trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
          COMMENT='全市场历史PB-乐咕乐股(2005年至今)';
        """,
    ]
    with engine.connect() as conn:
        for ddl in ddl_list:
            conn.execute(text(ddl))
        conn.commit()
    log.info("所有数据表初始化完成（4张表）")


# ─── 重试装饰器 ────────────────────────────────────────────────────────────────
def retry_call(fn, name="", retries=RETRY_TIMES, sleep=RETRY_SLEEP):
    for i in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            if i < retries:
                log.debug(f"{name} 第{i+1}次失败，{sleep}秒后重试: {e}")
                time.sleep(sleep)
            else:
                raise


# ─── 股票列表获取 ──────────────────────────────────────────────────────────────
def fetch_stock_list():
    """
    获取A股完整股票列表，多数据源容错。
    优先用深交所（稳定），补充沪市（有时不稳定），最后用内置列表兜底。
    """
    log.info("正在获取A股股票列表...")
    result_frames = []

    # ── 深交所 ────────────────────────────────────────────────────
    try:
        df_sz = ak.stock_info_sz_name_code(symbol="A股列表")
        df_sz = df_sz[["A股代码", "A股简称"]].copy()
        df_sz.columns = ["stock_code", "stock_name"]
        df_sz["stock_code"] = df_sz["stock_code"].astype(str).str.zfill(6)
        df_sz = df_sz.dropna(subset=["stock_code"])
        result_frames.append(df_sz)
        log.info(f"  深交所A股: {len(df_sz)} 只")
    except Exception as e:
        log.warning(f"  深交所接口失败: {e}")

    # ── 上交所主板 ─────────────────────────────────────────────────
    try:
        df_sh = ak.stock_info_sh_name_code(symbol="主板A股")
        df_sh = df_sh[["SECURITY_CODE_A", "SECURITY_ABBR_A"]].copy()
        df_sh.columns = ["stock_code", "stock_name"]
        df_sh["stock_code"] = df_sh["stock_code"].astype(str).str.zfill(6)
        df_sh = df_sh[df_sh["stock_code"].str.startswith("6")].copy()
        result_frames.append(df_sh)
        log.info(f"  上交所主板A股: {len(df_sh)} 只")
    except Exception as e:
        log.warning(f"  上交所接口失败: {e}，将通过代码范围补充沪市股票")
        # 补充：通过代码规律生成6字头（上交所主板）和688字头（科创板）
        sh_codes = [f"{i:06d}" for i in range(600000, 610000)] + \
                   [f"{i:06d}" for i in range(688000, 689000)]
        df_sh_fallback = pd.DataFrame({
            "stock_code": sh_codes,
            "stock_name": [""] * len(sh_codes)
        })
        result_frames.append(df_sh_fallback)
        log.info(f"  上交所代码范围兜底: {len(df_sh_fallback)} 个候选")

    # ── 北交所 ─────────────────────────────────────────────────────
    try:
        df_bj = ak.stock_info_bj_name_code()
        df_bj = df_bj[["证券代码", "证券简称"]].copy()
        df_bj.columns = ["stock_code", "stock_name"]
        df_bj["stock_code"] = df_bj["stock_code"].astype(str).str.zfill(6)
        result_frames.append(df_bj)
        log.info(f"  北交所: {len(df_bj)} 只")
    except Exception as e:
        log.warning(f"  北交所接口失败: {e}")

    if result_frames:
        df_all = pd.concat(result_frames, ignore_index=True)
        df_all = df_all.drop_duplicates(subset=["stock_code"])
        df_all = df_all[df_all["stock_code"].str.match(r"^\d{6}$")]
        df_all = df_all.reset_index(drop=True)
        log.info(f"A股股票列表合计: {len(df_all)} 只")
        return df_all

    # ── 最终兜底：akshare内置 ──────────────────────────────────────
    log.warning("所有在线接口失败，使用akshare内置股票列表")
    df = ak.stock_info_a_code_name()
    df.columns = ["stock_code", "stock_name"]
    return df.reset_index(drop=True)


# ─── 全市场PB历史数据 ──────────────────────────────────────────────────────────
def fetch_market_pb_all(engine):
    """采集全市场历史PB（2005年至今，乐咕乐股）"""
    log.info("正在采集全市场历史PB数据 (stock_a_all_pb)...")
    try:
        df = retry_call(ak.stock_a_all_pb, "stock_a_all_pb")
        df = df.rename(columns={
            "date":                                        "trade_date",
            "middlePB":                                    "middle_pb",
            "equalWeightAveragePB":                        "equal_weight_avg_pb",
            "close":                                       "close",
            "quantileInAllHistoryMiddlePB":                "quantile_all_middle_pb",
            "quantileInRecent10YearsMiddlePB":             "quantile_10y_middle_pb",
            "quantileInAllHistoryEqualWeightAveragePB":    "quantile_all_ewavg_pb",
            "quantileInRecent10YearsEqualWeightAveragePB": "quantile_10y_ewavg_pb",
        })
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        rows = _clean_nan(df.to_dict(orient="records"))

        with engine.connect() as conn:
            conn.execute(text("""
                INSERT IGNORE INTO stock_market_pb_history
                  (trade_date, middle_pb, equal_weight_avg_pb, close,
                   quantile_all_middle_pb, quantile_10y_middle_pb,
                   quantile_all_ewavg_pb, quantile_10y_ewavg_pb)
                VALUES
                  (:trade_date, :middle_pb, :equal_weight_avg_pb, :close,
                   :quantile_all_middle_pb, :quantile_10y_middle_pb,
                   :quantile_all_ewavg_pb, :quantile_10y_ewavg_pb)
            """), rows)
            conn.commit()
        log.info(f"全市场PB数据入库完成，共 {len(df)} 条")
        return len(df)
    except Exception as e:
        log.error(f"全市场PB数据采集失败: {e}")
        return 0


# ─── 新浪财经财务指标 ──────────────────────────────────────────────────────────
SINA_COL_MAP = {
    "日期": "report_date",
    "摊薄每股收益(元)": "eps",
    "加权每股收益(元)": "eps_weighted",
    "扣除非经常性损益后的每股收益(元)": "eps_ex_extra",
    "每股净资产_调整前(元)": "bps_before",
    "每股净资产_调整后(元)": "bps_after",
    "每股经营性现金流(元)": "ocfps",
    "每股资本公积金(元)": "capital_reserve_ps",
    "每股未分配利润(元)": "undistrib_profit_ps",
    "总资产利润率(%)": "roa",
    "销售净利率(%)": "net_profit_margin",
    "销售毛利率(%)": "gross_margin",
    "净资产收益率(%)": "roe",
    "加权净资产收益率(%)": "roe_weighted",
    "主营业务收入增长率(%)": "revenue_growth",
    "净利润增长率(%)": "netprofit_growth",
    "净资产增长率(%)": "netasset_growth",
    "总资产增长率(%)": "totalasset_growth",
    "流动比率": "current_ratio",
    "速动比率": "quick_ratio",
    "资产负债率(%)": "asset_liab_ratio",
    "总资产(元)": "total_assets",
    "存货周转率(次)": "inventory_turnover",
    "应收账款周转率(次)": "receivable_turnover",
    "总资产周转率(次)": "total_asset_turnover",
    "经营现金净流量对负债比率(%)": "cashflow_to_liab",
    "经营现金净流量对销售收入比率(%)": "cashflow_to_revenue",
}

SINA_DB_FIELDS = [
    "stock_code", "report_date", "eps", "eps_weighted", "eps_ex_extra",
    "bps_before", "bps_after", "ocfps", "capital_reserve_ps", "undistrib_profit_ps",
    "roa", "net_profit_margin", "gross_margin", "roe", "roe_weighted",
    "revenue_growth", "netprofit_growth", "netasset_growth", "totalasset_growth",
    "current_ratio", "quick_ratio", "asset_liab_ratio", "total_assets",
    "inventory_turnover", "receivable_turnover", "total_asset_turnover",
    "cashflow_to_liab", "cashflow_to_revenue",
]


def fetch_sina_financial_indicators(engine, stock_list_df):
    """采集新浪财经个股财务分析指标"""
    total = len(stock_list_df)
    success, fail, skip = 0, 0, 0
    log.info(f"开始采集新浪财经财务指标，共 {total} 只股票...")

    for _, row in stock_list_df.iterrows():
        code = str(row["stock_code"]).zfill(6)
        name = row.get("stock_name", "")
        try:
            df = retry_call(
                lambda c=code: ak.stock_financial_analysis_indicator(symbol=c, start_year=START_YEAR),
                name=f"sina_{code}"
            )
            if df is None or df.empty:
                skip += 1
                continue

            df = df.rename(columns=SINA_COL_MAP)
            keep = ["report_date"] + [v for v in SINA_COL_MAP.values() if v != "report_date"]
            df = df[[c for c in keep if c in df.columns]].copy()
            df["stock_code"] = code
            df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce").dt.date
            df = df.dropna(subset=["report_date"])
            if df.empty:
                skip += 1
                continue

            for c in df.columns:
                if c not in ("stock_code", "report_date"):
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            _upsert_sina(engine, _clean_nan(df.to_dict(orient="records")))
            success += 1
            if success % 100 == 0:
                log.info(f"  新浪进度: {success}/{total} 成功, {fail} 失败, {skip} 跳过")

        except Exception as e:
            fail += 1
            log.debug(f"  [{code}]{name} 新浪财务指标失败: {e}")

        time.sleep(SLEEP_PER_STOCK)

    log.info(f"新浪财务指标完成: 成功={success}, 跳过={skip}, 失败={fail}")
    return success, fail


def _upsert_sina(engine, rows):
    if not rows:
        return
    defaults = {f: None for f in SINA_DB_FIELDS}
    rows = [{**defaults, **r} for r in rows]
    placeholders = ", ".join([f":{f}" for f in SINA_DB_FIELDS])
    updates = ", ".join([f"{f}=VALUES({f})" for f in SINA_DB_FIELDS
                         if f not in ("stock_code", "report_date")])
    sql = text(f"""
        INSERT INTO stock_financial_indicators ({', '.join(SINA_DB_FIELDS)})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {updates}, updated_at=CURRENT_TIMESTAMP
    """)
    with engine.connect() as conn:
        conn.execute(sql, rows)
        conn.commit()


# ─── 东方财富财务指标 ──────────────────────────────────────────────────────────
EM_COL_MAP = {
    "SECUCODE": "secucode",
    "SECURITY_CODE": "stock_code",
    "SECURITY_NAME_ABBR": "stock_name",
    "REPORT_DATE": "report_date",
    "REPORT_TYPE": "report_type",
    "REPORT_DATE_NAME": "report_date_name",
    "NOTICE_DATE": "notice_date",
    "CURRENCY": "currency",
    "EPSJB": "eps",
    "EPSKCJB": "eps_ex_extra",
    "BPS": "bps",
    "MGZBGJ": "capital_reserve_ps",
    "MGWFPLR": "undistrib_profit_ps",
    "MGJYXJJE": "ocfps",
    "TOTALOPERATEREVE": "revenue",
    "XSMLL": "gross_margin",
    "PARENTNETPROFIT": "net_profit",
    "KCFJCXSYJLR": "net_profit_ex",
    "TOTALOPERATEREVETZ": "revenue_growth",
    "PARENTNETPROFITTZ": "netprofit_growth",
    "ROEJQ": "roe",
    "ROEKCJQ": "roe_ex",
    "ZZCJLL": "roa",
    "XSJLL": "net_profit_margin",
    "XJLLB": "cash_flow_ratio",
    "ZCFZL": "asset_liab_ratio",
    "LD": "current_ratio",
    "SD": "quick_ratio",
    "INTEREST_COVERAGE_RATIO": "interest_coverage",
    "TOAZZL": "total_asset_turnover",
    "CHZZL": "inventory_turnover",
    "YSZKZZL": "receivable_turnover",
    "BPSTZ": "bps_growth",
}

EM_STR_FIELDS = {"secucode", "stock_code", "stock_name", "report_type",
                 "report_date_name", "currency"}
EM_DATE_FIELDS = {"report_date", "notice_date"}
EM_DB_FIELDS = [
    "secucode", "stock_code", "stock_name", "report_date", "report_type",
    "report_date_name", "notice_date", "currency",
    "eps", "eps_ex_extra", "bps", "capital_reserve_ps", "undistrib_profit_ps", "ocfps",
    "revenue", "gross_margin", "net_profit", "net_profit_ex",
    "revenue_growth", "netprofit_growth", "roe", "roe_ex", "roa",
    "net_profit_margin", "cash_flow_ratio", "asset_liab_ratio",
    "current_ratio", "quick_ratio", "interest_coverage",
    "total_asset_turnover", "inventory_turnover", "receivable_turnover", "bps_growth",
]


def _code_to_secucode(code):
    code = str(code).zfill(6)
    if code.startswith("6") or code.startswith("5"):
        return f"{code}.SH"
    elif code.startswith(("0", "3", "2")):
        return f"{code}.SZ"
    elif code.startswith(("4", "8", "9")):
        return f"{code}.BJ"
    else:
        return f"{code}.SZ"


def fetch_em_financial_indicators(engine, stock_list_df):
    """采集东方财富个股财务分析指标"""
    total = len(stock_list_df)
    success, fail, skip = 0, 0, 0
    log.info(f"开始采集东方财富财务指标，共 {total} 只股票...")

    for _, row in stock_list_df.iterrows():
        code = str(row["stock_code"]).zfill(6)
        secucode = _code_to_secucode(code)
        name = row.get("stock_name", "")
        try:
            df = retry_call(
                lambda s=secucode: ak.stock_financial_analysis_indicator_em(
                    symbol=s, indicator="按报告期"),
                name=f"em_{secucode}"
            )
            if df is None or df.empty:
                skip += 1
                continue

            df = df.rename(columns=EM_COL_MAP)
            keep = [v for v in EM_DB_FIELDS if v in df.columns]
            df = df[keep].copy()

            # 日期处理
            for dcol in EM_DATE_FIELDS:
                if dcol in df.columns:
                    df[dcol] = pd.to_datetime(df[dcol], errors="coerce").dt.date
            df = df.dropna(subset=["report_date"])
            if df.empty:
                skip += 1
                continue

            # 数值处理
            for c in df.columns:
                if c not in EM_STR_FIELDS and c not in EM_DATE_FIELDS:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            _upsert_em(engine, _clean_nan(df.to_dict(orient="records")))
            success += 1
            if success % 100 == 0:
                log.info(f"  东方财富进度: {success}/{total} 成功, {fail} 失败, {skip} 跳过")

        except Exception as e:
            fail += 1
            log.debug(f"  [{secucode}]{name} 东方财富财务指标失败: {e}")

        time.sleep(SLEEP_PER_STOCK)

    log.info(f"东方财富财务指标完成: 成功={success}, 跳过={skip}, 失败={fail}")
    return success, fail


def _upsert_em(engine, rows):
    if not rows:
        return
    defaults = {f: None for f in EM_DB_FIELDS}
    rows = [{**defaults, **r} for r in rows]
    placeholders = ", ".join([f":{f}" for f in EM_DB_FIELDS])
    updates = ", ".join([f"{f}=VALUES({f})" for f in EM_DB_FIELDS
                         if f not in ("secucode", "report_date")])
    sql = text(f"""
        INSERT INTO stock_financial_indicators_em ({', '.join(EM_DB_FIELDS)})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {updates}, updated_at=CURRENT_TIMESTAMP
    """)
    with engine.connect() as conn:
        conn.execute(sql, rows)
        conn.commit()


# ─── 工具函数 ─────────────────────────────────────────────────────────────────
def _clean_nan(rows):
    """将 dict 列表中的 float('nan') 替换为 None（MySQL 不接受 NaN）"""
    cleaned = []
    for r in rows:
        cleaned.append({k: (None if (isinstance(v, float) and v != v) else v)
                        for k, v in r.items()})
    return cleaned


def save_stock_basic(engine, stock_list_df):
    """保存股票基础信息"""
    rows = stock_list_df.rename(columns={"code": "stock_code", "name": "stock_name"}
                                ).to_dict(orient="records")
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO stock_basic_info (stock_code, stock_name)
            VALUES (:stock_code, :stock_name)
            ON DUPLICATE KEY UPDATE stock_name=VALUES(stock_name),
                                    updated_at=CURRENT_TIMESTAMP
        """), rows)
        conn.commit()
    log.info(f"股票基础信息入库完成，共 {len(rows)} 条")


# ─── 主流程 ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="A股历史财务数据采集")
    parser.add_argument("--test", type=int, default=0,
                        help="测试模式：仅采集前N只股票")
    parser.add_argument("--skip-sina", action="store_true",
                        help="跳过新浪财经接口")
    parser.add_argument("--skip-em", action="store_true",
                        help="跳过东方财富接口")
    parser.add_argument("--skip-pb", action="store_true",
                        help="跳过全市场PB数据")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("A股历史财务数据采集开始")
    log.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.test:
        log.info(f"[测试模式] 仅采集前 {args.test} 只股票")
    log.info("=" * 60)

    # 1. 数据库初始化
    engine = get_engine()
    init_tables(engine)

    # 2. 获取股票列表
    stock_df = fetch_stock_list()
    if args.test:
        stock_df = stock_df.head(args.test)

    # 3. 保存基础信息
    save_stock_basic(engine, stock_df)

    # 4. 全市场历史PB
    pb_count = 0
    if not args.skip_pb:
        pb_count = fetch_market_pb_all(engine)

    # 5. 新浪财经财务指标
    sina_ok, sina_fail = 0, 0
    if not args.skip_sina:
        sina_ok, sina_fail = fetch_sina_financial_indicators(engine, stock_df)

    # 6. 东方财富财务指标
    em_ok, em_fail = 0, 0
    if not args.skip_em:
        em_ok, em_fail = fetch_em_financial_indicators(engine, stock_df)

    log.info("=" * 60)
    log.info("采集完成汇总:")
    log.info(f"  股票基础信息: {len(stock_df)} 条")
    log.info(f"  全市场PB历史: {pb_count} 条")
    log.info(f"  新浪财务指标: 成功={sina_ok}, 失败={sina_fail}")
    log.info(f"  东方财富财务指标: 成功={em_ok}, 失败={em_fail}")
    log.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
