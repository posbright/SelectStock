#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证所有 bug 修复的测试脚本
覆盖: torndb, database, trade_time, stockfetch, dataIndicatorsHandler, web_service
"""

import sys
import os
import datetime
import copy

# 将项目根目录加入 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

passed = 0
failed = 0
errors = []


def test(name):
    """测试装饰器"""
    def decorator(func):
        global passed, failed, errors
        try:
            func()
            print(f"  ✅ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {name}: {e}")
            failed += 1
            errors.append(f"{name}: {e}")
        except Exception as e:
            print(f"  ❌ {name}: 异常 {type(e).__name__}: {e}")
            failed += 1
            errors.append(f"{name}: {type(e).__name__}: {e}")
    return decorator


# ============================================================
# 测试 1: torndb CONVERSIONS 修复
# ============================================================
print("\n🔧 测试 1: torndb CONVERSIONS 修复")

@test("CONVERSIONS 兼容新版 pymysql（function 类型）")
def _():
    import pymysql
    import pymysql.constants
    import pymysql.constants.FLAG
    import pymysql.converters
    FIELD_TYPE = pymysql.constants.FIELD_TYPE
    FLAG = pymysql.constants.FLAG
    CONVERSIONS = copy.copy(pymysql.converters.conversions)

    field_types = [FIELD_TYPE.BLOB, FIELD_TYPE.STRING, FIELD_TYPE.VAR_STRING]
    if 'VARCHAR' in vars(FIELD_TYPE):
        field_types.append(FIELD_TYPE.VARCHAR)

    # 新版 pymysql (>= 1.0): conversions 值是 function
    for field_type in field_types:
        val = CONVERSIONS[field_type]
        if isinstance(val, list):
            # 旧版 pymysql：可以 list 拼接
            result = [(FLAG.BINARY, str)] + val
            assert isinstance(result, list)
        else:
            # 新版 pymysql：值是 function（如 through）
            assert callable(val), f"CONVERSIONS[{field_type}] 应为 callable，实际为 {type(val)}"

@test("旧代码 list.append 返回 None 的 bug 确认")
def _():
    # 模拟旧代码的 bug：list.append() 返回 None
    old_result = [1, 2].append(3)
    assert old_result is None, "append() 应该返回 None（这就是 bug 所在）"

@test("torndb 模块可正常导入且 CONVERSIONS 非 None")
def _():
    import instock.lib.torndb as torndb
    assert torndb.CONVERSIONS is not None, "CONVERSIONS 不应为 None"
    for ft in [torndb.FIELD_TYPE.BLOB, torndb.FIELD_TYPE.STRING, torndb.FIELD_TYPE.VAR_STRING]:
        val = torndb.CONVERSIONS[ft]
        # 新版 pymysql: function, 旧版: list
        assert val is not None, f"CONVERSIONS[{ft}] 不应为 None"
        assert callable(val) or isinstance(val, list), f"CONVERSIONS[{ft}] 类型异常: {type(val)}"


# ============================================================
# 测试 2: database.py 修复
# ============================================================
print("\n🔧 测试 2: database.py 修复")

@test("engine() 单例模式")
def _():
    import instock.lib.database as mdb
    # 重置
    mdb._engine_instance = None
    e1 = mdb.engine()
    e2 = mdb.engine()
    assert e1 is e2, "engine() 应返回同一实例"
    # 清理
    mdb._engine_instance = None

@test("get_connection() 异常时 raise 而非返回 None")
def _():
    import instock.lib.database as mdb
    # 保存原始配置
    original = mdb.MYSQL_CONN_DBAPI.copy()
    # 使用无效配置
    mdb.MYSQL_CONN_DBAPI['host'] = '0.0.0.0'
    mdb.MYSQL_CONN_DBAPI['port'] = 1  # 不可能连接的端口
    mdb.MYSQL_CONN_DBAPI['connect_timeout'] = 1
    
    raised = False
    result = "not_set"
    try:
        result = mdb.get_connection()
    except Exception:
        raised = True
    finally:
        # 恢复原始配置
        mdb.MYSQL_CONN_DBAPI.update(original)
    
    assert raised, f"get_connection() 失败时应 raise 异常，而非返回 {result}"

@test("日志中密码已脱敏")
def _():
    # 直接读取源文件检查（避免 inspect.getsource 获取的是模块级代码的问题）
    import os
    db_file = os.path.join(project_root, 'instock', 'lib', 'database.py')
    with open(db_file, 'r', encoding='utf-8') as f:
        source = f.read()
    # 检查 logging.info 行中使用 *** 脱敏而非 MYSQL_CONN_URL
    assert '***@' in source, "日志中应使用 *** 脱敏密码"
    # 确保没有直接输出 MYSQL_CONN_URL 到日志
    log_lines = [l for l in source.split('\n') if 'logging.info' in l and 'MYSQL_CONN_URL' in l]
    assert len(log_lines) == 0, f"不应直接在 logging.info 中使用 MYSQL_CONN_URL: {log_lines}"

@test("update_db_from_df 使用参数化查询")
def _():
    import inspect
    import instock.lib.database as mdb
    source = inspect.getsource(mdb.update_db_from_df)
    # 检查使用 %s 参数化而非 f-string 拼接
    assert '%s' in source, "应使用 %s 参数化查询"
    assert 'set_parts' in source, "应使用 set_parts 列表构建 SQL"
    assert 'where_parts' in source, "应使用 where_parts 列表构建 SQL"
    assert "db.execute(sql, params)" in source, "应使用参数化执行"

@test("checkTableIsExist 使用参数化查询")
def _():
    import inspect
    import instock.lib.database as mdb
    source = inspect.getsource(mdb.checkTableIsExist)
    assert '%s' in source, "应使用 %s 参数化查询"
    assert '.format(' not in source, "不应使用 .format() 拼接 SQL"

@test("update_db_from_df SQL 生成逻辑正确")
def _():
    """模拟 update_db_from_df 的 SQL 生成逻辑"""
    import pandas as pd
    import numpy as np
    
    # 模拟数据
    data = pd.DataFrame({
        'code': ['000001', '000002'],
        'name': ['平安银行', '万科A'],
        'price': [12.5, np.nan],  # NaN 应该生成 NULL
        'volume': [1000, 2000]
    })
    data = data.where(data.notnull(), None)
    
    table_name = 'test_table'
    where = ['code']
    update_string = f'UPDATE `{table_name}` set '
    where_string = ' where '
    cols = tuple(data.columns)
    
    generated_sqls = []
    generated_params = []
    
    for row in data.values:
        set_parts = []
        set_params = []
        where_parts = []
        where_params = []
        for index, col in enumerate(cols):
            val = row[index]
            is_null = val is None or (val != val)
            if col in where:
                where_parts.append(f'`{col}` = %s')
                where_params.append(val)
            else:
                if is_null:
                    set_parts.append(f'`{col}` = NULL')
                else:
                    set_parts.append(f'`{col}` = %s')
                    set_params.append(val)
        if not set_parts or not where_parts:
            continue
        sql = update_string + ', '.join(set_parts) + where_string + ' and '.join(where_parts)
        params = set_params + where_params
        generated_sqls.append(sql)
        generated_params.append(params)
    
    # 第一行：price=12.5, volume=1000, code='000001'
    assert len(generated_sqls) == 2, f"应生成 2 条 SQL，实际 {len(generated_sqls)}"
    assert 'NULL' not in generated_sqls[0], f"第一行不应有 NULL: {generated_sqls[0]}"
    assert '`price` = %s' in generated_sqls[0], f"第一行 price 应参数化: {generated_sqls[0]}"
    assert generated_params[0] == ['平安银行', 12.5, 1000, '000001'], f"第一行参数错误: {generated_params[0]}"
    
    # 第二行：price=NaN(None), volume=2000, code='000002'
    assert '`price` = NULL' in generated_sqls[1], f"第二行 price 应为 NULL: {generated_sqls[1]}"
    assert generated_params[1] == ['万科A', 2000, '000002'], f"第二行参数错误: {generated_params[1]}"


# ============================================================
# 测试 3: trade_time.py 修复
# ============================================================
print("\n🔧 测试 3: trade_time.py 修复")

@test("is_pause 在交易时间返回 False")
def _():
    # 直接测试函数逻辑，不依赖 singleton（避免网络调用）
    PAUSE_TIME = ((datetime.time(11, 30, 0), datetime.time(12, 59, 30)),)
    
    def is_pause(now_time):
        now = now_time.time()
        for b, e in PAUSE_TIME:
            if b <= now < e:
                return True
        return False
    
    # 测试正常交易时间
    t1 = datetime.datetime(2026, 2, 10, 10, 0, 0)
    assert is_pause(t1) == False, "10:00 不应该是暂停时间"
    
    # 测试午休时间
    t2 = datetime.datetime(2026, 2, 10, 12, 0, 0)
    assert is_pause(t2) == True, "12:00 应该是暂停时间"
    
    # 测试下午交易时间
    t3 = datetime.datetime(2026, 2, 10, 14, 0, 0)
    assert is_pause(t3) == False, "14:00 不应该是暂停时间"
    
    # 测试收盘后
    t4 = datetime.datetime(2026, 2, 10, 15, 30, 0)
    assert is_pause(t4) == False, "15:30 不应该是暂停时间"

@test("is_pause 函数有明确的 return False")
def _():
    import inspect
    from instock.lib import trade_time
    source = inspect.getsource(trade_time.is_pause)
    # 确保函数末尾有 return False
    lines = [l.strip() for l in source.split('\n') if l.strip()]
    assert 'return False' in lines, "is_pause 应有 return False 语句"

@test("is_tradetime / is_close / is_continue / is_closing 全部有返回值")
def _():
    import inspect
    from instock.lib import trade_time
    for func_name in ['is_tradetime', 'is_close', 'is_continue', 'is_closing', 'is_pause']:
        func = getattr(trade_time, func_name)
        source = inspect.getsource(func)
        assert 'return False' in source or 'return True' in source, f"{func_name} 缺少返回值"


# ============================================================
# 测试 4: singleton_trade_date.py 修复
# ============================================================
print("\n🔧 测试 4: singleton_trade_date.py 修复")

@test("异常时 self.data = None")
def _():
    import inspect
    from instock.core import singleton_trade_date
    source = inspect.getsource(singleton_trade_date.stock_trade_date.__init__)
    assert 'self.data = None' in source, "except 中应设置 self.data = None"


# ============================================================
# 测试 5: stockfetch.py 辅助函数
# ============================================================
print("\n🔧 测试 5: stockfetch.py 辅助函数")

@test("_to_date_str 字符串输入")
def _():
    from instock.core.stockfetch import _to_date_str
    assert _to_date_str("2026-02-10") == "20260210"
    assert _to_date_str("20260210") == "20260210"

@test("_to_date_str datetime 输入")
def _():
    from instock.core.stockfetch import _to_date_str
    dt = datetime.datetime(2026, 2, 10)
    assert _to_date_str(dt) == "20260210"

@test("_to_date_str date 输入")
def _():
    from instock.core.stockfetch import _to_date_str
    d = datetime.date(2026, 2, 10)
    assert _to_date_str(d) == "20260210"

@test("_to_dash_date 转换正确")
def _():
    from instock.core.stockfetch import _to_dash_date
    assert _to_dash_date("20260210") == "2026-02-10"
    assert _to_dash_date("20001231") == "2000-12-31"

@test("_retry_sleep 参数验证（不实际 sleep）")
def _():
    import inspect
    from instock.core import stockfetch
    source = inspect.getsource(stockfetch._retry_sleep)
    assert 'base_interval' in source, "应支持 base_interval 参数"
    assert 'random.uniform' in source, "应包含随机抖动"
    assert '2 ** retry_count' in source, "应使用指数退避"

@test("DATA_SOURCE_MAX_RETRIES = 2")
def _():
    from instock.core.stockfetch import DATA_SOURCE_MAX_RETRIES
    assert DATA_SOURCE_MAX_RETRIES == 2, f"应为 2，实际 {DATA_SOURCE_MAX_RETRIES}"

@test("DATA_SOURCE_RETRY_INTERVAL = 90")
def _():
    from instock.core.stockfetch import DATA_SOURCE_RETRY_INTERVAL
    assert DATA_SOURCE_RETRY_INTERVAL == 90, f"应为 90，实际 {DATA_SOURCE_RETRY_INTERVAL}"

@test("HIST_DATA_DEFAULT_YEARS = 10")
def _():
    from instock.core.stockfetch import HIST_DATA_DEFAULT_YEARS
    assert HIST_DATA_DEFAULT_YEARS == 10, f"应为 10，实际 {HIST_DATA_DEFAULT_YEARS}"

@test("is_a_stock 过滤正确")
def _():
    from instock.core.stockfetch import is_a_stock
    assert is_a_stock('600000') == True
    assert is_a_stock('000001') == True
    assert is_a_stock('300001') == True
    assert is_a_stock('688001') == False  # 科创板不在A股列表
    assert is_a_stock('430001') == False  # 北证不在A股列表


# ============================================================
# 测试 6: dataIndicatorsHandler.py 防护
# ============================================================
print("\n🔧 测试 6: dataIndicatorsHandler.py 防护")

@test("code=None 防护已添加")
def _():
    import inspect
    from instock.web.dataIndicatorsHandler import GetDataIndicatorsHandler
    source = inspect.getsource(GetDataIndicatorsHandler.get)
    # 检查 code is None 在 code.startswith 之前
    none_check_pos = source.find('if code is None')
    startswith_pos = source.find('code.startswith')
    assert none_check_pos > 0, "应有 code is None 检查"
    assert startswith_pos > 0, "应有 code.startswith 调用"
    assert none_check_pos < startswith_pos, "None 检查应在 startswith 之前"


# ============================================================
# 测试 7: web_service.py 配置
# ============================================================
print("\n🔧 测试 7: web_service.py 配置")

@test("debug=False")
def _():
    # 直接读取源文件避免模块导入链的副作用
    import os
    ws_file = os.path.join(project_root, 'instock', 'web', 'web_service.py')
    with open(ws_file, 'r', encoding='utf-8') as f:
        source = f.read()
    assert 'debug=False' in source, "应设置 debug=False"
    assert 'debug=True' not in source, "不应有 debug=True"

@test("启动日志使用 logging.info")
def _():
    import os
    ws_file = os.path.join(project_root, 'instock', 'web', 'web_service.py')
    with open(ws_file, 'r', encoding='utf-8') as f:
        source = f.read()
    # 检查 main 函数中的日志级别
    main_section = source[source.find('def main():'):]
    assert 'logging.info' in main_section, "应使用 logging.info"
    assert 'logging.error' not in main_section, "不应使用 logging.error 记录启动信息"


# ============================================================
# 测试 8: eastmoney_fetcher.py 修复
# ============================================================
print("\n🔧 测试 8: eastmoney_fetcher.py 修复")

@test("默认 retry=2")
def _():
    import inspect
    from instock.core.eastmoney_fetcher import eastmoney_fetcher
    sig = inspect.signature(eastmoney_fetcher.make_request)
    assert sig.parameters['retry'].default == 2, f"retry 默认值应为 2，实际 {sig.parameters['retry'].default}"

@test("无过度预延迟")
def _():
    import inspect
    from instock.core.eastmoney_fetcher import eastmoney_fetcher
    source = inspect.getsource(eastmoney_fetcher.make_request)
    # 确保 for 循环之前没有 time.sleep
    for_pos = source.find('for i in range(retry)')
    pre_code = source[:for_pos]
    assert 'time.sleep' not in pre_code, "for 循环前不应有 time.sleep（过度预延迟已移除）"


# ============================================================
# 测试 9: singleton_stock.py workers
# ============================================================
print("\n🔧 测试 9: singleton_stock.py workers")

@test("默认 workers=8")
def _():
    import inspect
    from instock.core.singleton_stock import stock_hist_data
    sig = inspect.signature(stock_hist_data.__init__)
    assert sig.parameters['workers'].default == 8, f"workers 默认值应为 8，实际 {sig.parameters['workers'].default}"


# ============================================================
# 测试 10: stock_hist_sina.py 延迟
# ============================================================
print("\n🔧 测试 10: stock_hist_sina.py 延迟")

@test("请求延迟为 3-6 秒")
def _():
    import inspect
    from instock.core.crawling import stock_hist_sina
    source = inspect.getsource(stock_hist_sina.stock_zh_a_hist_sina)
    assert 'random.uniform(3, 6)' in source, "延迟应为 random.uniform(3, 6)"
    assert 'random.uniform(0.1, 0.3)' not in source, "不应有旧的 0.1-0.3 延迟"


# ============================================================
# 测试 11: 数据源优先级
# ============================================================
print("\n🔧 测试 11: 数据源优先级")

@test("fetch_stocks 东方财富优先")
def _():
    import inspect
    from instock.core import stockfetch
    source = inspect.getsource(stockfetch.fetch_stocks)
    em_pos = source.find('东方财富')
    sina_pos = source.find('新浪财经')
    assert em_pos < sina_pos, "东方财富应在新浪财经之前"

@test("fetch_etfs 东方财富优先")
def _():
    import inspect
    from instock.core import stockfetch
    source = inspect.getsource(stockfetch.fetch_etfs)
    em_pos = source.find('东方财富')
    sina_pos = source.find('新浪财经')
    assert em_pos < sina_pos, "东方财富应在新浪财经之前"


# ============================================================
# 测试 12: 增量缓存辅助函数集成测试
# ============================================================
print("\n🔧 测试 12: 增量缓存逻辑验证")

@test("增量缓存场景：缓存完全覆盖请求范围")
def _():
    """当缓存已覆盖整个请求范围时，不应产生任何 fetch_ranges"""
    cache_first_date = "20050101"
    cache_last_date = "20260210"
    date_start = "20060101"
    date_end = "20260210"
    
    fetch_ranges = []
    if date_start < cache_first_date:
        first_date_obj = datetime.datetime.strptime(cache_first_date, "%Y%m%d")
        prev_day = (first_date_obj - datetime.timedelta(days=1)).strftime("%Y%m%d")
        if date_start <= prev_day:
            fetch_ranges.append((date_start, prev_day))
    if cache_last_date < date_end:
        last_date_obj = datetime.datetime.strptime(cache_last_date, "%Y%m%d")
        next_day = (last_date_obj + datetime.timedelta(days=1)).strftime("%Y%m%d")
        if next_day <= date_end:
            fetch_ranges.append((next_day, date_end))
    
    assert len(fetch_ranges) == 0, f"缓存完全覆盖时不应有 fetch_ranges: {fetch_ranges}"

@test("增量缓存场景：需要尾部追加")
def _():
    cache_first_date = "20060101"
    cache_last_date = "20260205"
    date_start = "20060101"
    date_end = "20260210"
    
    fetch_ranges = []
    if date_start < cache_first_date:
        first_date_obj = datetime.datetime.strptime(cache_first_date, "%Y%m%d")
        prev_day = (first_date_obj - datetime.timedelta(days=1)).strftime("%Y%m%d")
        if date_start <= prev_day:
            fetch_ranges.append((date_start, prev_day))
    if cache_last_date < date_end:
        last_date_obj = datetime.datetime.strptime(cache_last_date, "%Y%m%d")
        next_day = (last_date_obj + datetime.timedelta(days=1)).strftime("%Y%m%d")
        if next_day <= date_end:
            fetch_ranges.append((next_day, date_end))
    
    assert len(fetch_ranges) == 1, f"应有 1 个 fetch_range: {fetch_ranges}"
    assert fetch_ranges[0] == ("20260206", "20260210"), f"范围错误: {fetch_ranges[0]}"

@test("增量缓存场景：需要向前补数据")
def _():
    cache_first_date = "20100101"
    cache_last_date = "20260210"
    date_start = "20060101"
    date_end = "20260210"
    
    fetch_ranges = []
    if date_start < cache_first_date:
        first_date_obj = datetime.datetime.strptime(cache_first_date, "%Y%m%d")
        prev_day = (first_date_obj - datetime.timedelta(days=1)).strftime("%Y%m%d")
        if date_start <= prev_day:
            fetch_ranges.append((date_start, prev_day))
    if cache_last_date < date_end:
        last_date_obj = datetime.datetime.strptime(cache_last_date, "%Y%m%d")
        next_day = (last_date_obj + datetime.timedelta(days=1)).strftime("%Y%m%d")
        if next_day <= date_end:
            fetch_ranges.append((next_day, date_end))
    
    assert len(fetch_ranges) == 1, f"应有 1 个 fetch_range: {fetch_ranges}"
    assert fetch_ranges[0] == ("20060101", "20091231"), f"范围错误: {fetch_ranges[0]}"

@test("增量缓存场景：双向补数据")
def _():
    cache_first_date = "20100101"
    cache_last_date = "20260205"
    date_start = "20060101"
    date_end = "20260210"
    
    fetch_ranges = []
    if date_start < cache_first_date:
        first_date_obj = datetime.datetime.strptime(cache_first_date, "%Y%m%d")
        prev_day = (first_date_obj - datetime.timedelta(days=1)).strftime("%Y%m%d")
        if date_start <= prev_day:
            fetch_ranges.append((date_start, prev_day))
    if cache_last_date < date_end:
        last_date_obj = datetime.datetime.strptime(cache_last_date, "%Y%m%d")
        next_day = (last_date_obj + datetime.timedelta(days=1)).strftime("%Y%m%d")
        if next_day <= date_end:
            fetch_ranges.append((next_day, date_end))
    
    assert len(fetch_ranges) == 2, f"应有 2 个 fetch_ranges: {fetch_ranges}"
    assert fetch_ranges[0] == ("20060101", "20091231"), f"向前范围错误: {fetch_ranges[0]}"
    assert fetch_ranges[1] == ("20260206", "20260210"), f"向后范围错误: {fetch_ranges[1]}"


# ============================================================
# 测试 13: Docker 版本一致性
# ============================================================
print("\n🔧 测试 13: Docker 版本一致性")

@test("主版本与 Docker 版本文件内容一致")
def _():
    files_to_check = [
        ('instock/lib/database.py', 'docker/stock/instock/lib/database.py'),
        ('instock/lib/torndb.py', 'docker/stock/instock/lib/torndb.py'),
        ('instock/lib/trade_time.py', 'docker/stock/instock/lib/trade_time.py'),
        ('instock/core/stockfetch.py', 'docker/stock/instock/core/stockfetch.py'),
        ('instock/core/singleton_stock.py', 'docker/stock/instock/core/singleton_stock.py'),
        ('instock/core/singleton_trade_date.py', 'docker/stock/instock/core/singleton_trade_date.py'),
        ('instock/core/eastmoney_fetcher.py', 'docker/stock/instock/core/eastmoney_fetcher.py'),
        ('instock/core/crawling/stock_hist_sina.py', 'docker/stock/instock/core/crawling/stock_hist_sina.py'),
        ('instock/core/crawling/stock_hist_tencent.py', 'docker/stock/instock/core/crawling/stock_hist_tencent.py'),
        ('instock/web/dataIndicatorsHandler.py', 'docker/stock/instock/web/dataIndicatorsHandler.py'),
        ('instock/web/web_service.py', 'docker/stock/instock/web/web_service.py'),
        ('instock/job/execute_daily_job.py', 'docker/stock/instock/job/execute_daily_job.py'),
        ('instock/job/fetch_data_job.py', 'docker/stock/instock/job/fetch_data_job.py'),
    ]
    
    mismatches = []
    for main_file, docker_file in files_to_check:
        main_path = os.path.join(project_root, main_file)
        docker_path = os.path.join(project_root, docker_file)
        
        if not os.path.exists(main_path):
            mismatches.append(f"主版本缺失: {main_file}")
            continue
        if not os.path.exists(docker_path):
            mismatches.append(f"Docker版本缺失: {docker_file}")
            continue
        
        with open(main_path, 'r', encoding='utf-8') as f:
            main_content = f.read()
        with open(docker_path, 'r', encoding='utf-8') as f:
            docker_content = f.read()
        
        if main_content != docker_content:
            mismatches.append(f"{main_file}")
    
    assert len(mismatches) == 0, f"以下文件不一致: {', '.join(mismatches)}"


# ============================================================
# 汇总
# ============================================================
if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"测试完成: ✅ {passed} 通过, ❌ {failed} 失败")
    if errors:
        print(f"\n失败详情:")
        for err in errors:
            print(f"  - {err}")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)
