#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基本面数据提供层 — 实现聚宽 get_fundamentals / query / valuation API

提供与聚宽量化平台兼容的基本面数据查询接口，
用于在回测引擎中支持按市值、市盈率等基本面指标筛选股票。

实现原理：
1. 调用 stock_zh_a_spot_em() 获取当前全市场股票总市值
2. 估算总股本 = 总市值 / 最新价
3. 批量加载候选股票K线数据并缓存
4. 每日市值 = 总股本 × 当日收盘价 / 1亿
"""

import logging
import os
import time
import pickle
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

__author__ = 'InStock'
__date__ = '2026/03/16'

_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                          'cache', 'fundamental')


# ── 聚宽风格查询 API 对象 ──

class _FieldExpr:
    """表字段表达式，支持 .between() / .asc() / .desc() 等链式调用"""

    def __init__(self, table, name):
        self._table = table
        self._name = name

    def between(self, low, high):
        return ('between', self._name, low, high)

    def in_(self, values):
        """聚宽 .in_() 过滤 — 值在列表中"""
        return ('in_', self._name, list(values))

    def asc(self):
        return ('asc', self._name)

    def desc(self):
        return ('desc', self._name)

    def __gt__(self, other):
        return ('gt', self._name, other)

    def __lt__(self, other):
        return ('lt', self._name, other)

    def __ge__(self, other):
        return ('ge', self._name, other)

    def __le__(self, other):
        return ('le', self._name, other)

    def __repr__(self):
        return f"Field({self._table}.{self._name})"


class _ValuationTable:
    """聚宽 valuation 表对象 — 提供市值等估值指标字段"""
    code = _FieldExpr('valuation', 'code')
    name = _FieldExpr('valuation', 'name')
    market_cap = _FieldExpr('valuation', 'market_cap')
    pe_ratio = _FieldExpr('valuation', 'pe_ratio')
    pb_ratio = _FieldExpr('valuation', 'pb_ratio')
    circulating_market_cap = _FieldExpr('valuation', 'circulating_market_cap')


# 全局 valuation 实例（策略中直接引用）
valuation = _ValuationTable()


class _Query:
    """聚宽 query 对象"""

    def __init__(self, *fields):
        self._fields = fields
        self._filters = []
        self._order_by_clause = None
        self._limit_val = None

    def filter(self, *conditions):
        self._filters.extend(conditions)
        return self

    def order_by(self, clause):
        self._order_by_clause = clause
        return self

    def limit(self, n):
        self._limit_val = n
        return self


def query(*fields):
    """聚宽 query() 函数"""
    return _Query(*fields)


class OrderCost:
    """聚宽 OrderCost 对象"""

    def __init__(self, open_tax=0, close_tax=0.001,
                 open_commission=0.0003, close_commission=0.0003,
                 close_today_commission=0, min_commission=5):
        self.open_tax = open_tax
        self.close_tax = close_tax
        self.open_commission = open_commission
        self.close_commission = close_commission
        self.close_today_commission = close_today_commission
        self.min_commission = min_commission


# ── 基本面数据提供器 ──

class FundamentalDataProvider:
    """
    基本面数据提供器

    使用东方财富实时数据 + 历史K线重建每日市值。

    工作原理：
    1. 调用 stock_zh_a_spot_em() 获取所有A股当前总市值
    2. 估算总股本 = 总市值 / 最新价
    3. 批量加载候选股票K线数据（缓存的pickle文件或从东方财富在线获取）
    4. 每日市值 = 总股本 × 当日收盘价 / 1亿
    """

    # 候选市值范围（亿元），比实际查询范围更宽以覆盖历史波动
    CANDIDATE_MCAP_LOW = 10
    CANDIDATE_MCAP_HIGH = 80

    def __init__(self, engine):
        self._engine = engine
        self._stock_info = None         # DataFrame: code, name, total_shares, current_mcap
        self._price_lookup = {}         # {code: {date_str: close_price}}
        self._volume_lookup = {}        # {code: {date_str: volume}}
        self._daily_mcap_cache = {}     # {date_str: DataFrame}
        self._initialized = False
        self._candidate_codes = []

    def _init_data(self):
        """初始化：获取全市场数据并预加载候选股票K线"""
        if self._initialized:
            return
        self._initialized = True

        # 尝试加载缓存
        if self._load_fundamental_cache():
            return

        # 1. 获取全市场股票信息
        self._fetch_stock_info()
        if self._stock_info is None or len(self._stock_info) == 0:
            logging.error("[基本面] 无法获取股票信息")
            return

        # 2. 预筛选候选股票（当前市值在宽泛范围内）
        candidates = self._stock_info[
            (self._stock_info['current_mcap'] >= self.CANDIDATE_MCAP_LOW) &
            (self._stock_info['current_mcap'] <= self.CANDIDATE_MCAP_HIGH)
        ].copy()
        self._candidate_codes = candidates['code'].tolist()
        logging.info(f"[基本面] 候选股票: {len(self._candidate_codes)} 只 "
                     f"(当前市值 {self.CANDIDATE_MCAP_LOW}-{self.CANDIDATE_MCAP_HIGH}亿)")

        # 3. 批量加载候选股票K线数据
        self._batch_load_klines()

        # 4. 保存缓存
        self._save_fundamental_cache()

    def _fetch_stock_info(self):
        """获取全市场股票信息（优先DB，失败则在线API）"""
        # 方式1: 从数据库 cn_stock_spot 获取（快速、可靠）
        try:
            self._fetch_stock_info_from_db()
            if self._stock_info is not None and len(self._stock_info) > 0:
                return
        except Exception as e:
            logging.warning(f"[基本面] 从数据库获取失败: {e}")

        # 方式2: 从东方财富在线获取（push2his端点，代理加速）
        try:
            self._fetch_stock_info_from_push2his()
            if self._stock_info is not None and len(self._stock_info) > 0:
                return
        except Exception as e:
            logging.warning(f"[基本面] push2his获取失败: {e}")

        # 方式3: 老方式 spot_em（最慢，备用）
        try:
            self._fetch_stock_info_from_api()
        except Exception as e:
            logging.error(f"[基本面] 所有方式获取股票信息均失败: {e}")

    def _fetch_stock_info_from_db(self):
        """从数据库 cn_stock_spot 表获取股票信息（主要方式）"""
        from instock.lib.database import executeSqlFetch
        logging.info("[基本面] 正在从数据库获取全市场股票数据...")

        # 先获取最新日期（避免慢子查询）
        date_rows = executeSqlFetch('SELECT MAX(date) FROM cn_stock_spot')
        if not date_rows or date_rows[0][0] is None:
            logging.warning("[基本面] cn_stock_spot 表无数据")
            return
        max_date = date_rows[0][0]
        logging.info(f"[基本面] cn_stock_spot 最新日期: {max_date}")

        sql = """
            SELECT code, name, new_price, total_market_cap, pbnewmrq
            FROM cn_stock_spot
            WHERE date = %s
              AND new_price > 0
              AND total_market_cap > 0
        """
        rows = executeSqlFetch(sql, (max_date,))
        if not rows or len(rows) == 0:
            logging.warning("[基本面] cn_stock_spot 表无数据")
            return

        records = []
        for row in rows:
            code, name, price = row[0], row[1], float(row[2])
            mcap_wan = float(row[3])
            pb = float(row[4]) if row[4] is not None else 0
            # total_market_cap 单位是万元
            total_mv_yuan = mcap_wan * 10000
            total_shares = total_mv_yuan / price if price > 0 else 0
            current_mcap_yi = total_mv_yuan / 1e8
            records.append({
                'code': code, 'name': name.strip(),
                'total_shares': total_shares,
                'current_mcap': current_mcap_yi,
                'current_pb': pb,
                'current_price': price,
            })

        df = pd.DataFrame(records)

        # 过滤ST/退市股
        mask_st = df['name'].str.contains(r'ST|退', na=False)
        df = df[~mask_st].copy()

        # 只保留A股代码（6位数字，以0/3/6开头）
        mask_a = df['code'].str.match(r'^[036]\d{5}$')
        df = df[mask_a].copy()

        self._stock_info = df.reset_index(drop=True)
        logging.info(f"[基本面] 从数据库获取到 {len(self._stock_info)} 只A股信息")

    def _fetch_stock_info_from_push2his(self):
        """从东方财富 push2his 端点获取股票信息（可靠，使用代理）"""
        from instock.core.eastmoney_fetcher import eastmoney_fetcher
        logging.info("[基本面] 正在从 push2his 获取全市场股票数据...")

        fetcher = eastmoney_fetcher()
        url = 'https://push2his.eastmoney.com/api/qt/clist/get'
        all_data = []
        page = 1

        while True:
            params = {
                'pn': page, 'pz': 5000, 'po': '1', 'np': '1',
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                'fltt': '2', 'invt': '2', 'fid': 'f20',
                'fs': 'm:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048',
                'fields': 'f12,f14,f2,f20,f23',
                '_': str(int(time.time() * 1000)),
            }
            r = fetcher.make_request(url, params=params)
            d = r.json()
            # 防御：d.get('data') 可能返回 None 而非 {}
            data_obj = d.get('data') or {}
            rows = data_obj.get('diff') or []
            total = data_obj.get('total', 0)
            all_data.extend(rows)
            if len(rows) == 0 or len(all_data) >= total:
                break
            page += 1
            time.sleep(0.3)

        logging.info(f"[基本面] push2his 获取到 {len(all_data)} 条记录")

        records = []
        for item in all_data:
            code = str(item.get('f12', ''))
            name = str(item.get('f14', ''))
            price = float(item.get('f2') or 0)
            total_mv = float(item.get('f20') or 0)  # 总市值(元)
            pb = float(item.get('f23') or 0)  # 市净率
            if price > 0 and total_mv > 0:
                total_shares = total_mv / price
                current_mcap_yi = total_mv / 1e8
                records.append({
                    'code': code, 'name': name,
                    'total_shares': total_shares,
                    'current_mcap': current_mcap_yi,
                    'current_pb': pb,
                    'current_price': price,
                })

        df = pd.DataFrame(records)

        # 过滤ST/退市股
        mask_st = df['name'].str.contains(r'ST|退', na=False)
        df = df[~mask_st].copy()

        # 只保留A股代码（6位数字，以0/3/6开头）
        mask_a = df['code'].str.match(r'^[036]\d{5}$')
        df = df[mask_a].copy()

        cols = ['code', 'name', 'total_shares', 'current_mcap', 'current_pb', 'current_price']
        for c in cols:
            if c not in df.columns:
                df[c] = 0
        self._stock_info = df[cols].reset_index(drop=True)
        logging.info(f"[基本面] 从 push2his 获取到 {len(self._stock_info)} 只A股信息")

    def _fetch_stock_info_from_api(self):
        """从东方财富在线API获取股票信息（备用方式）"""
        try:
            from instock.core.crawling.stock_hist_em import stock_zh_a_spot_em
            logging.info("[基本面] 正在从东方财富API获取全市场股票数据...")
            df = stock_zh_a_spot_em()
            if df is None or len(df) == 0:
                return

            needed = ['代码', '名称', '最新价', '总市值']
            for c in needed:
                if c not in df.columns:
                    logging.error(f"[基本面] 缺少列: {c}")
                    return

            df = df[needed].copy()
            df.columns = ['code', 'name', 'price', 'total_mv']
            df['price'] = pd.to_numeric(df['price'], errors='coerce')
            df['total_mv'] = pd.to_numeric(df['total_mv'], errors='coerce')
            df = df[(df['price'] > 0) & (df['total_mv'] > 0)].copy()

            mask_st = df['name'].str.contains(r'ST|退', na=False)
            df = df[~mask_st].copy()
            mask_a = df['code'].str.match(r'^[036]\d{5}$')
            df = df[mask_a].copy()

            df['total_shares'] = df['total_mv'] / df['price']
            df['current_mcap'] = df['total_mv'] / 1e8
            df['current_pb'] = 0   # spot_em 不提供 PB，默认 0
            df['current_price'] = df['price']

            self._stock_info = df[['code', 'name', 'total_shares', 'current_mcap',
                                   'current_pb', 'current_price']].reset_index(drop=True)
            logging.info(f"[基本面] 从API获取到 {len(self._stock_info)} 只A股信息")

        except Exception as e:
            logging.error(f"[基本面] API获取股票数据失败: {e}")

    def _batch_load_klines(self):
        """批量加载候选股票K线数据（多线程并行，带重试）"""
        from .data_feed import _load_from_cache, _fetch_stock_from_eastmoney, _save_cache

        total = len(self._candidate_codes)
        loaded = 0
        fetched = 0
        failed = 0

        logging.info(f"[基本面] 正在加载 {total} 只候选股票K线数据...")

        # Phase 1: 从缓存加载
        need_fetch = []
        for code in self._candidate_codes:
            df = _load_from_cache(code)
            if df is not None and len(df) > 0:
                self._build_price_lookup(code, df)
                loaded += 1
            else:
                need_fetch.append(code)

        logging.info(f"[基本面] 缓存命中: {loaded}, 需在线获取: {len(need_fetch)}")

        # Phase 2: 从东方财富获取（多线程并行）
        if need_fetch:
            est_seconds = len(need_fetch) * 0.3
            logging.info(f"[基本面] 正在从东方财富获取 {len(need_fetch)} 只股票K线..."
                         f" (预计 {est_seconds:.0f} 秒)")

            def _fetch_one(code):
                for attempt in range(3):
                    try:
                        df = _fetch_stock_from_eastmoney(code, '20230101')
                        if df is not None and len(df) > 0:
                            _save_cache(code, df)
                            return (code, df)
                    except Exception:
                        if attempt < 2:
                            time.sleep(1 + attempt)
                return (code, None)

            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {executor.submit(_fetch_one, code): code for code in need_fetch}
                done_count = 0
                for future in as_completed(futures):
                    code, df = future.result()
                    done_count += 1
                    if df is not None:
                        self._build_price_lookup(code, df)
                        fetched += 1
                    else:
                        failed += 1
                    if done_count % 200 == 0:
                        logging.info(f"[基本面] 进度: {done_count}/{len(need_fetch)} "
                                     f"(成功={fetched}, 失败={failed})")

        total_loaded = loaded + fetched
        logging.info(f"[基本面] K线数据加载完成: {total_loaded}/{total} 只 "
                     f"(缓存={loaded}, 在线={fetched}, 失败={failed})")

    def _build_price_lookup(self, code, df):
        """构建价格和成交量快速查找字典"""
        prices = {}
        volumes = {}
        for _, row in df.iterrows():
            d = row['date']
            if hasattr(d, 'strftime'):
                d_str = d.strftime('%Y-%m-%d')
            else:
                d_str = str(d)[:10]
            prices[d_str] = float(row['close'])
            volumes[d_str] = int(row.get('volume', 0))
        self._price_lookup[code] = prices
        self._volume_lookup[code] = volumes

    def get_fundamentals(self, q, date=None):
        """
        执行聚宽风格基本面查询。

        Args:
            q: _Query 对象
            date: 查询日期（默认当前回测日期）

        Returns:
            DataFrame: 包含 'code', 'market_cap', 'pb_ratio' 等列
        """
        self._init_data()

        if date is None:
            date = self._engine.context.current_dt
        date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)[:10]

        # 确定需要查询的股票范围
        # 如果过滤条件中有 in_ 过滤 code，先提取该列表以确保加载数据
        in_codes = None
        for f in q._filters:
            if isinstance(f, tuple) and len(f) >= 3 and f[0] == 'in_' and f[1] == 'code':
                in_codes = set(f[2])
                break

        # 如果有 in_ code 过滤，确保这些股票的 K 线已加载
        if in_codes:
            self._ensure_stocks_loaded(in_codes)

        # 缓存 key = 日期 + 额外股票集（不同 in_codes 不能共用缓存）
        extra_key = ','.join(sorted(in_codes)) if in_codes else ''
        cache_key = f"{date_str}|{extra_key}"
        if cache_key in self._daily_mcap_cache:
            df = self._daily_mcap_cache[cache_key].copy()
        else:
            # 计算所有已知股票在该日的市值和 PB
            records = []
            if self._stock_info is not None:
                info_map = {}
                for _, row in self._stock_info.iterrows():
                    info_map[row['code']] = {
                        'total_shares': row['total_shares'],
                        'current_pb': row.get('current_pb', 0),
                        'current_price': row.get('current_price', 0),
                    }

                # 查询范围：候选股票 + in_ 过滤中的额外股票
                query_codes = set(self._candidate_codes)
                if in_codes:
                    query_codes = query_codes | in_codes

                for code in query_codes:
                    prices = self._price_lookup.get(code)
                    if prices is None:
                        continue
                    close = prices.get(date_str, 0)
                    if close <= 0:
                        continue
                    info = info_map.get(code)
                    if info is None:
                        continue
                    ts = info['total_shares']
                    if ts > 0:
                        mcap = ts * close / 1e8  # 亿元
                        # PB 估算：current_pb × (close / current_price)
                        # 原理：PB = 市值/净资产，净资产短期不变
                        # → historical_PB = current_PB × (historical_price / current_price)
                        cur_pb = info.get('current_pb', 0)
                        cur_price = info.get('current_price', 0)
                        if cur_pb > 0 and cur_price > 0:
                            pb_ratio = cur_pb * (close / cur_price)
                        else:
                            pb_ratio = 0
                        records.append({
                            'code': code,
                            'market_cap': mcap,
                            'pb_ratio': round(pb_ratio, 4),
                        })

            df = pd.DataFrame(records) if records else pd.DataFrame(
                columns=['code', 'market_cap', 'pb_ratio'])
            self._daily_mcap_cache[cache_key] = df

        if len(df) == 0:
            return df

        result = df.copy()

        # 应用过滤条件
        for f in q._filters:
            if isinstance(f, tuple) and len(f) >= 3:
                op, field = f[0], f[1]
                if field in result.columns:
                    if op == 'between' and len(f) >= 4:
                        result = result[(result[field] >= f[2]) & (result[field] <= f[3])]
                    elif op == 'gt':
                        result = result[result[field] > f[2]]
                    elif op == 'lt':
                        result = result[result[field] < f[2]]
                    elif op == 'ge':
                        result = result[result[field] >= f[2]]
                    elif op == 'le':
                        result = result[result[field] <= f[2]]
                    elif op == 'in_':
                        result = result[result[field].isin(f[2])]

        # 应用排序
        if q._order_by_clause is not None and isinstance(q._order_by_clause, tuple):
            direction, field = q._order_by_clause
            ascending = (direction == 'asc')
            if field in result.columns:
                result = result.sort_values(field, ascending=ascending)

        # 应用限制
        if q._limit_val is not None:
            result = result.head(q._limit_val)

        # 动态返回可用列
        out_cols = ['code']
        for c in ['market_cap', 'pb_ratio']:
            if c in result.columns:
                out_cols.append(c)
        return result[out_cols].reset_index(drop=True)

    def _ensure_stocks_loaded(self, codes):
        """确保指定股票的 K 线数据已加载（用于 in_ 过滤的非候选股）"""
        from .data_feed import _load_from_cache, _fetch_stock_from_eastmoney, _save_cache

        need_load = [c for c in codes
                     if c not in self._price_lookup
                     and (self._stock_info is not None
                          and c in self._stock_info['code'].values)]
        if not need_load:
            return

        logging.info(f"[基本面] 延迟加载 {len(need_load)} 只额外股票 K 线")
        newly_loaded = False
        for code in need_load:
            df = _load_from_cache(code)
            if df is not None and len(df) > 0:
                self._build_price_lookup(code, df)
                newly_loaded = True
                continue
            for attempt in range(3):
                try:
                    df = _fetch_stock_from_eastmoney(code, '20230101')
                    if df is not None and len(df) > 0:
                        _save_cache(code, df)
                        self._build_price_lookup(code, df)
                        newly_loaded = True
                        break
                except Exception:
                    if attempt < 2:
                        time.sleep(1 + attempt)
        # 把新加载的股票持久化到基本面缓存，避免下次重复请求 API
        if newly_loaded:
            self._save_fundamental_cache()

    def is_paused(self, code, date=None):
        """检查股票是否停牌（当日无成交量或无数据视为停牌）"""
        if date is None:
            date = self._engine.context.current_dt
        date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)[:10]

        volumes = self._volume_lookup.get(code)
        if volumes is None:
            return True  # 无数据 = 停牌
        vol = volumes.get(date_str, -1)
        if vol < 0:
            return True  # 当日无数据 = 停牌
        return vol == 0

    # ── 缓存管理 ──

    def _load_fundamental_cache(self):
        """加载基本面数据缓存"""
        cache_file = os.path.join(_CACHE_DIR, 'fundamental_v3.pickle')
        if not os.path.exists(cache_file):
            return False
        try:
            mtime = os.path.getmtime(cache_file)
            if time.time() - mtime > 7 * 86400:  # 7天过期
                logging.info("[基本面] 缓存已过期（>7天），重新获取")
                return False
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
            self._stock_info = data['stock_info']
            self._price_lookup = data['price_lookup']
            self._volume_lookup = data['volume_lookup']
            self._candidate_codes = data['candidate_codes']
            logging.info(f"[基本面] 从缓存加载: {len(self._candidate_codes)} 只候选股票，"
                         f"{len(self._price_lookup)} 只有K线数据")
            return True
        except Exception as e:
            logging.warning(f"[基本面] 缓存加载失败: {e}")
            return False

    def _save_fundamental_cache(self):
        """保存基本面数据缓存（原子写入：写临时文件后 os.replace，避免并发读到半写文件）"""
        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            cache_file = os.path.join(_CACHE_DIR, 'fundamental_v3.pickle')
            tmp_file = cache_file + '.tmp'
            data = {
                'stock_info': self._stock_info,
                'price_lookup': self._price_lookup,
                'volume_lookup': self._volume_lookup,
                'candidate_codes': self._candidate_codes,
            }
            with open(tmp_file, 'wb') as f:
                pickle.dump(data, f)
            os.replace(tmp_file, cache_file)
            size_mb = os.path.getsize(cache_file) / 1e6
            logging.info(f"[基本面] 缓存已保存 ({size_mb:.1f} MB)")
        except Exception as e:
            logging.warning(f"[基本面] 缓存保存失败: {e}")
            try:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
            except Exception:
                pass


# ── get_current_data() 代理对象 ──

class _CurrentDataProxy:
    """get_current_data() 返回的代理对象 — dict-like, proxy[code].paused"""

    def __init__(self, provider):
        self._provider = provider

    def __getitem__(self, code):
        return _CurrentStockInfo(code, self._provider)


class _CurrentStockInfo:
    """单只股票的当前数据"""

    def __init__(self, code, provider):
        self._code = code
        self._provider = provider

    @property
    def paused(self):
        """是否停牌"""
        return self._provider.is_paused(self._code)

    @property
    def is_st(self):
        """是否ST（简化实现：返回False）"""
        return False
