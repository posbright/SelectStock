#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志配置模块

使用方法：
    from instock.lib.log_config import setup_logging
    setup_logging('fetch')     # → instock/log/stock_fetch.log + stock_error.log
    setup_logging('analysis')  # → instock/log/stock_analysis.log + stock_error.log
    setup_logging('web')       # → instock/log/stock_web.log + stock_error.log

日志文件说明：
    stock_{name}.log   — 该脚本的全量日志（INFO+）
    stock_error.log    — 所有脚本的错误日志汇总（ERROR+，含完整堆栈）

日志格式：
    2026-02-14 18:30:05 [INFO] fetch_data_job: 数据获取开始
    2026-02-14 18:30:10 [ERROR] stockfetch: 获取失败
    Traceback (most recent call last):
      File "stockfetch.py", line 100, in _fetch_from_sources
        ...
    ConnectionError: Remote end closed connection
"""

import logging
import os

__author__ = 'InStock'
__date__ = '2026/02/14'

_LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
_LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def setup_logging(name='execute', level=logging.INFO):
    """
    配置日志系统（三路输出：全量文件 + 错误文件 + 控制台）
    
    Args:
        name: 日志名称，会生成 stock_{name}.log 文件
        level: 日志级别，默认 INFO
    """
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 避免重复添加 handler
    if root_logger.handlers:
        return
    
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)
    
    # 1. 全量日志文件 — stock_{name}.log（INFO+）
    full_handler = logging.FileHandler(
        os.path.join(log_dir, f'stock_{name}.log'), encoding='utf-8')
    full_handler.setLevel(level)
    full_handler.setFormatter(formatter)
    root_logger.addHandler(full_handler)
    
    # 2. 错误日志文件 — stock_error.log（ERROR+，所有脚本共享）
    error_handler = logging.FileHandler(
        os.path.join(log_dir, 'stock_error.log'), encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # 3. 控制台 — WARNING+（避免大量 INFO 刷屏）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    ))
    root_logger.addHandler(console_handler)
