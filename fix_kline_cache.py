#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K线缓存数据清理脚本

修复已知的缓存污染问题：
- 5只股票的日线缓存中混入了月度聚合数据行
- 受影响股票: 002024, 002371, 002916, 300760, 600809
- 异常特征: 月末日期的OHLC价格与前后数据偏离>50%

使用方法:
    python fix_kline_cache.py           # 扫描并修复所有缓存
    python fix_kline_cache.py --scan    # 仅扫描，不修复
    python fix_kline_cache.py --delete  # 删除受影响的缓存文件（下次获取时重建）
"""
import os
import sys
import glob
import argparse
import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 缓存目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, 'instock', 'cache', 'hist')

# 已知受影响的股票
KNOWN_AFFECTED = ['002024', '002371', '002916', '300760', '600809']


def filter_ohlc_outliers(data, code=''):
    """
    过滤OHLC异常行。使用滚动中位数检测价格异常。
    与 stockfetch.py 中的 _filter_ohlc_outliers() 保持一致。
    """
    if data is None or data.empty or len(data) < 10:
        return data, 0

    try:
        close_col = 'close' if 'close' in data.columns else None
        if close_col is None:
            return data, 0

        close = data[close_col].astype(float)
        rolling_med = close.rolling(window=5, center=True, min_periods=2).median()
        ratio = close / rolling_med

        outlier_mask = (ratio < 0.5) | (ratio > 2.0)
        outlier_count = outlier_mask.sum()

        if outlier_count > 0 and outlier_count < len(data) * 0.1:
            removed_dates = data.loc[outlier_mask, 'date'].tolist() if 'date' in data.columns else []
            logger.info(f"  [{code}] 检测到 {outlier_count} 行异常数据")
            for d in removed_dates[:5]:
                idx = data[data['date'] == d].index[0]
                row = data.loc[idx]
                logger.info(f"    日期={d}, open={row.get('open','?')}, close={row.get('close','?')}, "
                          f"high={row.get('high','?')}, low={row.get('low','?')}, volume={row.get('volume','?')}")
            if len(removed_dates) > 5:
                logger.info(f"    ... 及其他 {len(removed_dates) - 5} 行")
            cleaned = data[~outlier_mask].reset_index(drop=True)
            return cleaned, outlier_count
        elif outlier_count >= len(data) * 0.1:
            logger.warning(f"  [{code}] 异常行占比过高 ({outlier_count}/{len(data)})，跳过过滤")
            return data, 0
    except Exception as e:
        logger.error(f"  [{code}] 过滤异常时出错: {e}")

    return data, 0


def scan_cache_files(cache_dir):
    """扫描所有缓存文件，返回受影响的文件列表"""
    affected = []
    total = 0

    if not os.path.exists(cache_dir):
        logger.error(f"缓存目录不存在: {cache_dir}")
        return affected

    pattern = os.path.join(cache_dir, '**', '*qfq.gzip.pickle')
    files = glob.glob(pattern, recursive=True)
    logger.info(f"找到 {len(files)} 个缓存文件")

    for filepath in sorted(files):
        filename = os.path.basename(filepath)
        code = filename.replace('qfq.gzip.pickle', '')
        total += 1

        try:
            data = pd.read_pickle(filepath, compression='gzip')
            if data is None or data.empty or len(data) < 10:
                continue

            _, outlier_count = filter_ohlc_outliers(data.copy(), code)
            if outlier_count > 0:
                affected.append({
                    'code': code,
                    'path': filepath,
                    'rows': len(data),
                    'outliers': outlier_count,
                })
        except Exception as e:
            logger.warning(f"  读取缓存失败 [{code}]: {e}")

    logger.info(f"\n扫描完成: 共 {total} 个文件，{len(affected)} 个受影响")
    return affected


def fix_cache_files(affected_list):
    """修复受影响的缓存文件（删除异常行后重新保存）"""
    fixed = 0
    for item in affected_list:
        code = item['code']
        filepath = item['path']
        logger.info(f"修复 [{code}] ...")

        try:
            data = pd.read_pickle(filepath, compression='gzip')
            cleaned, removed = filter_ohlc_outliers(data, code)

            if removed > 0:
                # 备份原文件
                backup_path = filepath + '.bak'
                if not os.path.exists(backup_path):
                    os.rename(filepath, backup_path)
                    logger.info(f"  已备份到 {backup_path}")
                else:
                    os.remove(filepath)

                # 保存清理后的数据
                cleaned.to_pickle(filepath, compression='gzip')
                logger.info(f"  已修复: {len(data)} -> {len(cleaned)} 行 (删除 {removed} 行)")
                fixed += 1
            else:
                logger.info(f"  无需修复")
        except Exception as e:
            logger.error(f"  修复失败 [{code}]: {e}")

    logger.info(f"\n修复完成: {fixed}/{len(affected_list)} 个文件已修复")
    return fixed


def delete_cache_files(codes, cache_dir):
    """删除指定股票的缓存文件（下次数据获取时会自动重建）"""
    deleted = 0
    for code in codes:
        cache_path = os.path.join(cache_dir, code[:3], f"{code}qfq.gzip.pickle")
        meta_path = os.path.join(cache_dir, code[:3], f"{code}qfq.meta")

        for path in [cache_path, meta_path]:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"  已删除: {path}")
                deleted += 1
            else:
                logger.info(f"  文件不存在: {path}")

    logger.info(f"\n删除完成: {deleted} 个文件")
    return deleted


def main():
    parser = argparse.ArgumentParser(description='K线缓存数据清理脚本')
    parser.add_argument('--scan', action='store_true', help='仅扫描，不修复')
    parser.add_argument('--delete', action='store_true', help='删除受影响的缓存文件')
    parser.add_argument('--cache-dir', default=CACHE_DIR, help=f'缓存目录 (默认: {CACHE_DIR})')
    parser.add_argument('--codes', nargs='*', help='指定股票代码 (默认: 扫描全部)')
    args = parser.parse_args()

    cache_dir = args.cache_dir
    logger.info(f"缓存目录: {cache_dir}")

    if args.delete:
        codes = args.codes or KNOWN_AFFECTED
        logger.info(f"删除模式: 将删除 {codes} 的缓存文件")
        delete_cache_files(codes, cache_dir)
        return

    # 扫描
    logger.info("开始扫描缓存文件...")
    affected = scan_cache_files(cache_dir)

    if not affected:
        logger.info("未发现异常数据，所有缓存正常。")
        return

    for item in affected:
        logger.info(f"  {item['code']}: {item['outliers']} 行异常 / {item['rows']} 行总计")

    if args.scan:
        logger.info("扫描模式，不执行修复。使用不带 --scan 参数运行以执行修复。")
        return

    # 修复
    logger.info("\n开始修复...")
    fix_cache_files(affected)


if __name__ == '__main__':
    main()
