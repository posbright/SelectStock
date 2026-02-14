#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import pymysql
from sqlalchemy import create_engine
from sqlalchemy.types import NVARCHAR
from sqlalchemy import inspect
from urllib.parse import quote_plus

__author__ = 'myh '
__date__ = '2023/3/10 '

db_host = "115.29.213.22"  # 数据库服务主机
db_user = "root"  # 数据库访问用户
db_password = "Dzm@ming&662"  # 数据库访问密码
db_database = "instockdb"  # 数据库名称
db_port = 3306  # 数据库服务端口
db_charset = "utf8mb4"  # 数据库字符集

# 使用环境变量获得数据库,docker -e 传递
_db_host = os.environ.get('db_host')
if _db_host is not None:
    db_host = _db_host
_db_user = os.environ.get('db_user')
if _db_user is not None:
    db_user = _db_user
_db_password = os.environ.get('db_password')
if _db_password is not None:
    db_password = _db_password
_db_database = os.environ.get('db_database')
if _db_database is not None:
    db_database = _db_database
_db_port = os.environ.get('db_port')
if _db_port is not None:
    db_port = int(_db_port)

# 对密码进行URL编码，处理特殊字符
_encoded_password = quote_plus(db_password)
MYSQL_CONN_URL = "mysql+pymysql://%s:%s@%s:%s/%s?charset=%s" % (
    db_user, _encoded_password, db_host, db_port, db_database, db_charset)
logging.info(f"数据库链接信息：mysql+pymysql://{db_user}:***@{db_host}:{db_port}/{db_database}?charset={db_charset}")

MYSQL_CONN_DBAPI = {'host': db_host, 'user': db_user, 'password': db_password, 'database': db_database,
                    'charset': db_charset, 'port': db_port, 'autocommit': True}

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
            pool_recycle=1800,
            pool_pre_ping=True
        )
    return _engine_instance


def engine_to_db(to_db):
    _engine = create_engine(MYSQL_CONN_URL.replace(f'/{db_database}?', f'/{to_db}?'))
    return _engine


# DB Api -数据库连接对象connection
def get_connection():
    try:
        return pymysql.connect(**MYSQL_CONN_DBAPI)
    except Exception as e:
        logging.error(f"database.get_connection处理异常", exc_info=True)
        raise


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
    try:
        if cols_type is None:
            data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                        index=write_index, )
        elif not cols_type:
            data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                        dtype={col_name: NVARCHAR(255) for col_name in col_name_list}, index=write_index, )
        else:
            data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                        dtype=cols_type, index=write_index, )
    except Exception as e:
        logging.error(f"database.insert_other_db_from_df处理异常：{table_name}表", exc_info=True)
        return

    # 判断是否存在主键
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
                    WHERE table_name = %s
                    """, (tableName,))
                if db.fetchone()[0] == 1:
                    return True
    except Exception as e:
        logging.error(f"database.checkTableIsExist处理异常", exc_info=True)
    return False

# 增删改数据
def executeSql(sql, params=()):
    with get_connection() as conn:
        with conn.cursor() as db:
            try:
                db.execute(sql, params)
            except Exception as e:
                logging.error(f"database.executeSql处理异常：{sql}", exc_info=True)


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
