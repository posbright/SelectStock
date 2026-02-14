#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志配置模块

使用方法：
    from instock.lib.log_config import setup_logging
    setup_logging('fetch')     # → instock/log/stock_fetch.log
    setup_logging('analysis')  # → instock/log/stock_analysis.log
    setup_logging('web')       # → instock/log/stock_web.log

日志格式：
    2026-02-14 18:30:05 [INFO] fetch_data_job: 数据获取开始
    2026-02-14 18:30:10 [ERROR] stockfetch: 获取失败
    Traceback (most recent call last):
      File "stockfetch.py", line 100, in _fetch_from_sources
        ...
    ConnectionError: Remote end closed connection

日志文件按脚本分类：
    stock_execute.log  — execute_daily_job（一体模式）
    stock_fetch.log    — fetch_daily_job（拆分模式：数据获取）
    stock_analysis.log — analysis_daily_job（拆分模式：数据分析）
    stock_web.log      — web_service
"""

import logging
import os

__author__ = 'InStock'
__date__ = '2026/02/14'


def setup_logging(name='execute', level=logging.INFO):
    """
    配置日志系统
    
    Args:
        name: 日志名称，会生成 stock_{name}.log 文件
        level: 日志级别，默认 INFO
    """
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f'stock_{name}.log')
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 避免重复添加 handler（多次调用 setup_logging 时）
    if root_logger.handlers:
        return
    
    # 文件 handler — 完整日志
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    root_logger.addHandler(file_handler)
    
    # 控制台 handler — 仅 WARNING 及以上（避免大量 INFO 刷屏）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    ))
    root_logger.addHandler(console_handler)
