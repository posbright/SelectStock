#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import time
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.types import NVARCHAR
from sqlalchemy import inspect
from sqlalchemy.dialects.mysql import insert as mysql_insert
from urllib.parse import quote_plus

# 自动加载项目根目录下的 .env 文件（兼容方法 B）
# .env 中的变量不会覆盖已存在的环境变量（方法 A 优先）
try:
    from dotenv import load_dotenv as _load_dotenv
    # 向上查找到项目根目录（instock/lib/database.py → 项目根）
    _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    _env_path = os.path.join(_project_root, '.env')
    if os.path.isfile(_env_path):
        _load_dotenv(_env_path, override=False)
except ImportError:
    pass  # python-dotenv 未安装时静默跳过，仅使用环境变量

__author__ = 'InStock'
__date__ = '2026/02/14'

db_host = os.environ.get('db_host', '127.0.0.1')  # 数据库服务主机（默认本地）
db_user = os.environ.get('db_user', 'root')  # 数据库访问用户
db_password = os.environ.get('db_password', '')  # 数据库访问密码（生产环境务必通过环境变量配置）
db_database = os.environ.get('db_database', 'instockdb')  # 数据库名称
db_port = int(os.environ.get('db_port', '3306'))  # 数据库服务端口
db_charset = "utf8mb4"  # 数据库字符集

# 超时配置（秒），可通过环境变量覆盖（本地远程连接时适当放宽）
_connect_timeout = int(os.environ.get('INSTOCK_DB_CONNECT_TIMEOUT', '10'))
_read_timeout = int(os.environ.get('INSTOCK_DB_READ_TIMEOUT', '30'))
_write_timeout = int(os.environ.get('INSTOCK_DB_WRITE_TIMEOUT', '30'))

# 对密码进行URL编码，处理特殊字符
_encoded_password = quote_plus(db_password)
MYSQL_CONN_URL = "mysql+pymysql://%s:%s@%s:%s/%s?charset=%s" % (
    db_user, _encoded_password, db_host, db_port, db_database, db_charset)
logging.info(f"数据库链接信息：mysql+pymysql://{db_user}:***@{db_host}:{db_port}/{db_database}?charset={db_charset}")

MYSQL_CONN_DBAPI = {'host': db_host, 'user': db_user, 'password': db_password, 'database': db_database,
                    'charset': db_charset, 'port': db_port, 'autocommit': True,
                    'connect_timeout': _connect_timeout, 'read_timeout': _read_timeout, 'write_timeout': _write_timeout}

MYSQL_CONN_TORNDB = {'host': f'{db_host}:{str(db_port)}', 'user': db_user, 'password': db_password,
                     'database': db_database, 'charset': db_charset, 'max_idle_time': 3600, 'connect_timeout': 1000}


# 通过数据库链接 engine（单例模式，避免每次调用创建新连接池）
# 2核2G服务器优化：pool_size=2, max_overflow=3, 最多5个连接
_engine_instance = None


def engine():
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = create_engine(
            MYSQL_CONN_URL,
            pool_size=2,
            max_overflow=3,
            pool_recycle=600,
            pool_pre_ping=True,
            pool_timeout=30
        )
    return _engine_instance


def engine_to_db(to_db):
    _engine = create_engine(MYSQL_CONN_URL.replace(f'/{db_database}?', f'/{to_db}?'))
    return _engine


# DB Api -数据库连接对象connection
def get_connection():
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            return pymysql.connect(**MYSQL_CONN_DBAPI)
        except Exception as e:
            if attempt < max_retries and _is_retryable_error(e):
                logging.warning(f"database.get_connection瞬态错误（第{attempt}/{max_retries}次重试）：{type(e).__name__}")
                time.sleep(1 * attempt)
            else:
                logging.error(f"database.get_connection处理异常", exc_info=True)
                raise


# MySQL upsert方法：INSERT ... ON DUPLICATE KEY UPDATE
# 解决并发写入时的主键冲突、死锁等问题
def _mysql_upsert(table, conn, keys, data_iter):
    """pandas to_sql 的自定义 method，使用 INSERT ... ON DUPLICATE KEY UPDATE"""
    data = [dict(zip(keys, row)) for row in data_iter]
    if not data:
        return 0
    stmt = mysql_insert(table.table).values(data)
    # 主键冲突时，更新所有非主键列
    update_dict = {k: stmt.inserted[k] for k in keys}
    upsert_stmt = stmt.on_duplicate_key_update(**update_dict)
    result = conn.execute(upsert_stmt)
    return result.rowcount


# 判断是否为可重试的数据库瞬态错误（死锁、锁超时、连接异常等）
def _is_retryable_error(e):
    error_str = str(e)
    retryable_codes = ['1205', '1213', 'Deadlock', 'Lock wait timeout',
                       'Packet sequence', 'PendingRollbackError',
                       'Lost connection', 'Gone away', 'Can\'t connect',
                       'Connection refused', 'broken pipe']
    return any(code.lower() in error_str.lower() for code in retryable_codes)


# 定义通用方法函数，插入数据库表，并创建数据库主键，保证重跑数据的时候索引唯一。
def insert_db_from_df(data, table_name, cols_type, write_index, primary_keys, indexs=None):
    # 插入默认的数据库。
    insert_other_db_from_df(None, data, table_name, cols_type, write_index, primary_keys, indexs)


# 增加一个插入到其他数据库的方法。
def insert_other_db_from_df(to_db, data, table_name, cols_type, write_index, primary_keys, indexs=None):
    # 定义engine
    if to_db is None:
        engine_mysql = engine()
    else:
        engine_mysql = engine_to_db(to_db)
    # 使用 http://docs.sqlalchemy.org/en/latest/core/reflection.html
    # 使用检查检查数据库表是否有主键。
    ipt = inspect(engine_mysql)
    col_name_list = data.columns.tolist()
    # 如果有索引，把索引增加到varchar上面。
    if write_index:
        # 插入到第一个位置：
        col_name_list.insert(0, data.index.name)

    # 检查表是否已存在主键，决定是否使用upsert模式
    has_primary_key = False
    try:
        pk_cols = ipt.get_pk_constraint(table_name)['constrained_columns']
        has_primary_key = bool(pk_cols)
    except Exception:
        logging.debug(f"检查主键约束异常（表可能不存在，首次创建）：{table_name}", exc_info=True)

    # 选择插入方法：有主键时使用upsert避免重复插入错误，否则普通append
    insert_method = _mysql_upsert if has_primary_key else None

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            if cols_type is None:
                data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                            index=write_index, method=insert_method)
            elif not cols_type:
                data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                            dtype={col_name: NVARCHAR(255) for col_name in col_name_list},
                            index=write_index, method=insert_method)
            else:
                data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                            dtype=cols_type, index=write_index, method=insert_method)
            break  # 成功则跳出重试循环
        except Exception as e:
            if attempt < max_retries and _is_retryable_error(e):
                logging.warning(f"database.insert_other_db_from_df瞬态错误（第{attempt}/{max_retries}次重试）：{table_name}表 - {type(e).__name__}")
                # 清理连接池中可能损坏的连接
                try:
                    engine_mysql.dispose()
                except Exception:
                    logging.debug(f"database.insert_other_db_from_df: dispose引擎异常", exc_info=True)
                # 重新获取engine（单例模式下dispose后需要重建）
                if to_db is None:
                    global _engine_instance
                    _engine_instance = None
                    engine_mysql = engine()
                else:
                    engine_mysql = engine_to_db(to_db)
                time.sleep(2 * attempt)  # 递增等待时间
            else:
                logging.error(f"database.insert_other_db_from_df处理异常：{table_name}表", exc_info=True)
                return

    # 判断是否存在主键（仅在首次创建表时添加）
    try:
        pk_exists = ipt.get_pk_constraint(table_name)['constrained_columns']
    except Exception as e:
        logging.error(f"database.insert_other_db_from_df检查主键异常：{table_name}表", exc_info=True)
        return
    if not pk_exists:
        try:
            # 执行数据库插入数据。
            with get_connection() as conn:
                with conn.cursor() as db:
                    db.execute(f'ALTER TABLE `{table_name}` ADD PRIMARY KEY ({primary_keys});')
                    if indexs is not None:
                        for k in indexs:
                            db.execute(f'ALTER TABLE `{table_name}` ADD INDEX IN{k}({indexs[k]});')
        except Exception as e:
            logging.error(f"database.insert_other_db_from_df处理异常：{table_name}表", exc_info=True)


# 更新数据
def update_db_from_df(data, table_name, where):
    data = data.where(data.notnull(), None)
    update_string = f'UPDATE `{table_name}` set '
    where_string = ' where '
    cols = tuple(data.columns)
    try:
        with get_connection() as conn:
            with conn.cursor() as db:
                for row in data.values:
                    set_parts = []
                    set_params = []
                    where_parts = []
                    where_params = []
                    for index, col in enumerate(cols):
                        val = row[index]
                        # 检测 None 和 NaN（NaN != NaN）
                        is_null = val is None or (val != val)
                        if col in where:
                            if is_null:
                                where_parts.append(f'`{col}` IS NULL')
                            else:
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
                    db.execute(sql, params)
    except Exception as e:
        logging.error(f"database.update_db_from_df处理异常：{table_name}表", exc_info=True)


# 检查表是否存在
def checkTableIsExist(tableName):
    try:
        with get_connection() as conn:
            with conn.cursor() as db:
                db.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                    """, (db_database, tableName))
                if db.fetchone()[0] >= 1:
                    return True
    except Exception as e:
        logging.error(f"database.checkTableIsExist处理异常", exc_info=True)
    return False

# 增删改数据
def executeSql(sql, params=()):
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            with get_connection() as conn:
                with conn.cursor() as db:
                    db.execute(sql, params)
                    return
        except Exception as e:
            if attempt < max_retries and _is_retryable_error(e):
                logging.warning(f"database.executeSql瞬态错误（第{attempt}/{max_retries}次重试）：{type(e).__name__}")
                time.sleep(1 * attempt)
            else:
                logging.error(f"database.executeSql处理异常：{sql}", exc_info=True)
                raise


# 查询数据
def executeSqlFetch(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as db:
            try:
                db.execute(sql, params)
                return db.fetchall()
            except Exception as e:
                logging.error(f"database.executeSqlFetch处理异常：{sql}", exc_info=True)
    return None


# 计算数量
def executeSqlCount(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as db:
            try:
                db.execute(sql, params)
                result = db.fetchall()
                if len(result) == 1:
                    return int(result[0][0])
                else:
                    return 0
            except Exception as e:
                logging.error(f"database.select_count计算数量处理异常", exc_info=True)
    return 0
