#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


import json
import logging
from abc import ABC
from tornado import gen
import datetime
import instock.lib.trade_time as trd
import instock.core.singleton_stock_web_module_data as sswmd
import instock.web.base as webBase
from instock.lib.query_cache import stock_data_cache

__author__ = 'myh '
__date__ = '2023/3/10 '


class MyEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, bytes):
            return "是" if ord(obj) == 1 else "否"
        elif isinstance(obj, datetime.datetime):
            # datetime 对象转为 ISO 格式字符串
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(obj, datetime.date):
            # date 对象转为 YYYY-MM-DD 格式字符串
            return obj.strftime("%Y-%m-%d")
        else:
            return json.JSONEncoder.default(self, obj)


# 获得页面数据。
class GetStockHtmlHandler(webBase.BaseHandler, ABC):
    @gen.coroutine
    def get(self):
        name = self.get_argument("table_name", default=None, strip=False)
        web_module_data = sswmd.stock_web_module_data().get_data(name)
        if web_module_data is None:
            self.set_status(404)
            self.write(f"未找到数据模块: {name}")
            return
        run_date, run_date_nph = trd.get_trade_date_last()
        if web_module_data.is_realtime:
            date_now_str = run_date_nph.strftime("%Y-%m-%d")
        else:
            date_now_str = run_date.strftime("%Y-%m-%d")
        self.render("stock_web.html", web_module_data=web_module_data, date_now=date_now_str,
                    leftMenu=webBase.GetLeftMenu(self.request.uri))


# 获得股票数据内容。
class GetStockDataHandler(webBase.BaseHandler, ABC):
    def get(self):
        name = self.get_argument("name", default=None, strip=False)
        date = self.get_argument("date", default=None, strip=False)
        page = self.get_argument("page", default=None, strip=True)
        page_size = self.get_argument("page_size", default=None, strip=True)
        keyword = self.get_argument("keyword", default=None, strip=True)
        self.set_header('Content-Type', 'application/json;charset=UTF-8')
        
        # 参数验证
        if name is None:
            self.set_status(400)
            self.write(json.dumps({"error": "缺少必要参数 name", "code": 400}))
            return
        
        web_module_data = sswmd.stock_web_module_data().get_data(name)
        if web_module_data is None:
            self.set_status(404)
            self.write(json.dumps({"error": f"未找到数据模块: {name}", "code": 404}))
            return

        query_params = []
        conditions = []
        if date is not None:
            conditions.append("`date` = %s")
            query_params.append(date)

        # 关键词搜索（代码/名称模糊匹配）
        if keyword is not None and keyword.strip():
            keyword_like = f"%{keyword.strip()}%"
            has_code = 'code' in web_module_data.columns
            has_name = 'name' in web_module_data.columns
            if has_code and has_name:
                conditions.append("(`code` LIKE %s OR `name` LIKE %s)")
                query_params.append(keyword_like)
                query_params.append(keyword_like)
            elif has_code:
                conditions.append("`code` LIKE %s")
                query_params.append(keyword_like)
            elif has_name:
                conditions.append("`name` LIKE %s")
                query_params.append(keyword_like)

        where = ""
        if conditions:
            where = " WHERE " + " AND ".join(conditions)

        order_by = ""
        if web_module_data.order_by is not None:
            order_by = f" ORDER BY {web_module_data.order_by}"

        order_columns = ""
        if web_module_data.order_columns is not None:
            order_columns = f",{web_module_data.order_columns}"

        # 分页参数处理
        use_pagination = page is not None and page_size is not None
        limit_clause = ""
        if use_pagination:
            try:
                page_int = max(1, int(page))
                page_size_int = max(1, min(500, int(page_size)))
                offset = (page_int - 1) * page_size_int
                limit_clause = f" LIMIT {page_size_int} OFFSET {offset}"
            except (ValueError, TypeError):
                use_pagination = False

        # 先查询总数
        count_sql = f"SELECT COUNT(*) AS cnt FROM `{web_module_data.table_name}`{where}"
        data_sql = f"SELECT *{order_columns} FROM `{web_module_data.table_name}`{where}{order_by}{limit_clause}"
        
        try:
            # 尝试从缓存获取总数
            cache_params = tuple(query_params) if query_params else None
            hit, cached_total = stock_data_cache.get(count_sql, cache_params)
            if hit:
                total = cached_total
            else:
                if query_params:
                    total_result = self.db.query(count_sql, *query_params)
                else:
                    total_result = self.db.query(count_sql)
                total = total_result[0]["cnt"] if total_result else 0
                stock_data_cache.put(count_sql, cache_params, total)
            
            # 尝试从缓存获取数据
            hit, cached_data = stock_data_cache.get(data_sql, cache_params)
            if hit:
                data = cached_data
            else:
                if query_params:
                    data = self.db.query(data_sql, *query_params)
                else:
                    data = self.db.query(data_sql)
                stock_data_cache.put(data_sql, cache_params, data)
        except Exception as e:
            error_msg = str(e)
            # 表不存在时返回空数据，而非500错误
            if "doesn't exist" in error_msg or "not found" in error_msg.lower():
                data = []
                total = 0
            else:
                logging.error(f"GetStockDataHandler查询异常：{web_module_data.table_name} {e}")
                self.set_status(500)
                self.write(json.dumps({"error": f"查询数据异常: {error_msg}", "code": 500}))
                return

        # 返回包含列定义和数据的响应
        response = {
            "columns": web_module_data.column_names,
            "data": data,
            "total": total
        }
        self.write(json.dumps(response, cls=MyEncoder))
