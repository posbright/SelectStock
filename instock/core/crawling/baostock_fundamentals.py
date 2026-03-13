#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baostock 基本面数据补充器

当主数据源（东方财富）降级到腾讯/新浪后，PE/PB/ROE 等基本面字段会为 0。
本模块通过 Baostock 免费 API 批量补充这些缺失字段。

接口特点：
- 免费，无需 Token/Cookie
- 提供 peTTM、pbMRQ（日频，逐只查询）
- 提供 roeAvg、epsTTM、gpMargin（季频报告期数据）
- 单只约 500ms，5000 只约 40 分钟（可通过线程池加速）

使用方式：
    from instock.core.crawling.baostock_fundamentals import patch_spot_fundamentals
    patch_spot_fundamentals('2026-03-12')  # 补充 cn_stock_spot 中缺失的 PE/ROE
"""

import logging
import time
from collections import defaultdict

__author__ = 'InStock'
__date__ = '2026/03/13'

# Baostock 延迟导入（可能未安装）
_bs = None


def _ensure_baostock():
    """延迟导入并登录 Baostock"""
    global _bs
    if _bs is not None:
        return True
    try:
        import baostock as bs
        lg = bs.login()
        if lg.error_code != '0':
            logging.warning(f"Baostock 登录失败: {lg.error_msg}")
            return False
        _bs = bs
        return True
    except ImportError:
        logging.warning("baostock 未安装，无法补充基本面数据。pip install baostock")
        return False
    except Exception as e:
        logging.warning(f"Baostock 初始化异常: {e}")
        return False


def _to_bs_code(code):
    """将 6 位股票代码转为 Baostock 格式：sh.600519 / sz.000001"""
    if code.startswith(('6', '9')):
        return f"sh.{code}"
    else:
        return f"sz.{code}"


def _fetch_pe_pb(bs_code, date_str):
    """查询单只股票的 peTTM / pbMRQ（日频）"""
    try:
        rs = _bs.query_history_k_data_plus(
            bs_code,
            'date,code,peTTM,pbMRQ',
            start_date=date_str, end_date=date_str,
            frequency='d'
        )
        while rs.error_code == '0' and rs.next():
            row = rs.get_row_data()
            pe = float(row[2]) if row[2] else 0.0
            pb = float(row[3]) if row[3] else 0.0
            return pe, pb
    except Exception:
        pass
    return 0.0, 0.0


def _fetch_roe_eps(bs_code, year, quarter):
    """查询单只股票的 ROE / EPS / 毛利率（季频）"""
    try:
        rs = _bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
        while rs.error_code == '0' and rs.next():
            row = rs.get_row_data()
            # fields: code, pubDate, statDate, roeAvg, npMargin, gpMargin,
            #         netProfit, epsTTM, MBRevenue, totalShare, liqaShare
            roe = float(row[3]) if row[3] else 0.0
            gp_margin = float(row[5]) if row[5] else 0.0
            eps = float(row[7]) if row[7] else 0.0
            return roe * 100, eps, gp_margin * 100  # 转为百分比
    except Exception:
        pass
    return 0.0, 0.0, 0.0


def _get_latest_report_quarter(date_str):
    """根据日期推算最近的财报季度"""
    from datetime import date
    d = date.fromisoformat(date_str)
    year, month = d.year, d.month
    # 财报滞后：Q1(4月底), Q2(8月底), Q3(10月底), Q4(次年4月底)
    if month <= 4:
        return year - 1, 3  # 去年Q3（Q4可能还没出）
    elif month <= 8:
        return year, 1      # 今年Q1
    elif month <= 10:
        return year, 2      # 今年Q2
    else:
        return year, 3      # 今年Q3


def fetch_fundamentals_batch(codes, date_str, workers=None):
    """
    批量获取股票基本面数据（PE/PB/ROE/EPS/毛利率）

    注意：Baostock 内部使用单一 TCP 连接，不支持并发。
    此函数顺序查询所有股票，约 300-500ms/只。

    Args:
        codes: 股票代码列表 ['600519', '000001', ...]
        date_str: 日期字符串 'YYYY-MM-DD'
        workers: 保留参数（Baostock 不支持并发，忽略）

    Returns:
        dict: {code: {'pe9': float, 'pbnewmrq': float, 'roe_weight': float,
                       'basic_eps': float, 'sale_gpr': float}}
    """
    if not _ensure_baostock():
        return {}

    report_year, report_quarter = _get_latest_report_quarter(date_str)
    results = {}
    total = len(codes)
    start = time.time()

    for i, code in enumerate(codes):
        bs_code = _to_bs_code(code)
        pe, pb = _fetch_pe_pb(bs_code, date_str)
        roe, eps, gp_margin = _fetch_roe_eps(bs_code, report_year, report_quarter)

        if pe != 0.0 or roe != 0.0:
            results[code] = {
                'pe9': pe,
                'pbnewmrq': pb,
                'roe_weight': roe,
                'basic_eps': eps,
                'sale_gpr': gp_margin,
            }

        done = i + 1
        if done % 500 == 0 or done == total:
            elapsed = time.time() - start
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            logging.info(f"Baostock 基本面数据: {done}/{total} ({rate:.0f}/s, ETA {eta:.0f}s)")

    elapsed = time.time() - start
    logging.info(f"Baostock 基本面数据获取完成: {len(results)}/{total} 只有数据，耗时 {elapsed:.0f}s")
    return results


def patch_spot_fundamentals(date_str, force=False):
    """
    补充 cn_stock_spot 表中缺失的 PE/PB/ROE 等基本面字段。

    仅在检测到当日数据的 pe9 字段全为 0 时执行（说明主数据源降级了）。
    设置 force=True 可强制补充。

    Args:
        date_str: 日期字符串 'YYYY-MM-DD'
        force: 是否强制补充（跳过检测）

    Returns:
        int: 补充的股票数量（0 表示无需补充或补充失败）
    """
    import instock.lib.database as mdb

    # 检查是否需要补充
    if not force:
        try:
            row = mdb.executeSqlFetch(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN pe9 IS NOT NULL AND pe9 != 0 THEN 1 ELSE 0 END) as has_pe "
                "FROM cn_stock_spot WHERE date = %s", (date_str,)
            )
            if not row or row[0][0] == 0:
                logging.info(f"Baostock: cn_stock_spot 无 {date_str} 数据，跳过补充")
                return 0
            total, has_pe = row[0]
            if has_pe > 0:
                logging.info(f"Baostock: cn_stock_spot {date_str} PE 数据正常 ({has_pe}/{total})，无需补充")
                return 0
            logging.info(f"Baostock: 检测到 {date_str} PE/ROE 全为 0（{total} 条），开始补充")
        except Exception as e:
            logging.warning(f"Baostock: 检查 cn_stock_spot 异常: {e}")
            return 0

    # 获取所有股票代码
    try:
        rows = mdb.executeSqlFetch(
            'SELECT code FROM cn_stock_spot WHERE date = %s', (date_str,)
        )
        codes = [r[0] for r in rows] if rows else []
        if not codes:
            return 0
    except Exception as e:
        logging.warning(f"Baostock: 获取股票列表异常: {e}")
        return 0

    # 批量获取基本面数据
    import instock.lib.envconfig as _cfg
    workers = _cfg.get_int('INSTOCK_BAOSTOCK_WORKERS', 10)
    fundamentals = fetch_fundamentals_batch(codes, date_str, workers=workers)
    if not fundamentals:
        logging.warning("Baostock: 未获取到任何基本面数据")
        return 0

    # 批量更新数据库
    updated = 0
    batch_size = 100
    codes_list = list(fundamentals.keys())

    for i in range(0, len(codes_list), batch_size):
        batch = codes_list[i:i + batch_size]
        for code in batch:
            data = fundamentals[code]
            try:
                mdb.executeSql(
                    'UPDATE cn_stock_spot SET pe9=%s, pbnewmrq=%s, roe_weight=%s, '
                    'basic_eps=%s, sale_gpr=%s '
                    'WHERE date=%s AND code=%s',
                    (data['pe9'], data['pbnewmrq'], data['roe_weight'],
                     data['basic_eps'], data['sale_gpr'],
                     date_str, code)
                )
                updated += 1
            except Exception as e:
                logging.debug(f"Baostock: 更新 {code} 异常: {e}")

    logging.info(f"Baostock: 已补充 {updated} 只股票的 PE/PB/ROE 数据 ({date_str})")

    # 清理 Baostock 连接
    try:
        if _bs is not None:
            _bs.logout()
    except Exception:
        pass

    return updated


def cleanup():
    """清理 Baostock 连接"""
    global _bs
    if _bs is not None:
        try:
            _bs.logout()
        except Exception:
            pass
        _bs = None
