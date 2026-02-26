#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
代理池管理模块

功能：
1. 从多个免费代理源自动抓取代理IP
2. 验证代理可用性（针对东方财富API测试）
3. 后台定时刷新：定期获取新代理、移除不可用代理
4. 支持手动配置：proxy.txt 中的代理优先级最高
5. 线程安全：所有操作均加锁保护

使用方式不变：proxys().get_proxies() 返回可用代理或 None
"""

import os.path
import sys
import random
import time
import logging
import threading
import requests
from instock.lib.singleton_type import singleton_type

# 在项目运行时，临时将项目路径添加到环境变量
cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)
proxy_filename = os.path.join(cpath_current, 'config', 'proxy.txt')

__author__ = 'InStock'
__date__ = '2026/02/14'

# ── 配置 ──
PROXY_VALIDATE_URL = "http://datacenter.eastmoney.com/api/data/get"  # HTTP验证（免费代理多不支持HTTPS隧道）
PROXY_VALIDATE_TIMEOUT = 8          # 验证超时（秒）
PROXY_REFRESH_INTERVAL = 600        # 后台刷新间隔（秒），默认10分钟
PROXY_MIN_POOL_SIZE = 3             # 代理池最少保有量，低于此数触发紧急补充
PROXY_FETCH_WORKERS = 20            # 并发验证线程数
PROXY_MAX_FAIL_COUNT = 3            # 连续失败次数阈值，超过则移除


class proxys(metaclass=singleton_type):
    """
    代理池管理器（单例）

    生命周期：
    1. 首次 proxys() 时初始化：加载 proxy.txt + 抓取免费代理 + 启动后台刷新
    2. get_proxies() 随机返回一个已验证的可用代理
    3. report_failure(proxy) 报告代理失败，累积失败次数达阈值后自动移除
    4. 后台线程每 PROXY_REFRESH_INTERVAL 秒自动刷新
    """

    def __init__(self):
        self._lock = threading.RLock()
        # {proxy_url: {"fail_count": int, "last_verified": float}}
        self._pool = {}
        self._manual_proxies = []  # proxy.txt 中的手动配置代理
        self._running = False
        self._refresh_thread = None
        self._initialized = False

        # 初始加载
        self._load_manual_proxies()
        self._initial_fetch()
        self._start_background_refresh()

    def _load_manual_proxies(self):
        """从 proxy.txt 加载手动配置的代理"""
        try:
            with open(proxy_filename, "r") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                self._manual_proxies = list(set(lines))
                for proxy in self._manual_proxies:
                    self._pool[proxy] = {"fail_count": 0, "last_verified": time.time(), "manual": True}
                if self._manual_proxies:
                    logging.info(f"代理池：从 proxy.txt 加载了 {len(self._manual_proxies)} 个手动代理")
        except Exception:
            pass

    def _initial_fetch(self):
        """初始化时抓取免费代理（限制候选数量加速启动）"""
        logging.info("代理池：正在从免费代理源获取代理...")
        candidates = self._fetch_from_sources()
        if candidates:
            # 初始化时只验证前500个，加速启动；后台刷新时会验证更多
            batch = candidates[:500]
            verified = self._batch_validate(batch)
            logging.info(f"代理池：获取 {len(candidates)} 个候选代理，验证 {len(batch)} 个，通过 {len(verified)} 个")
        else:
            logging.warning("代理池：未能从免费代理源获取到候选代理")
        self._initialized = True

    # ══════════════════════════════════════════════
    # 公共接口（与旧版兼容）
    # ══════════════════════════════════════════════

    def get_data(self):
        """兼容旧接口：返回所有可用代理列表"""
        with self._lock:
            available = [p for p, info in self._pool.items() if info["fail_count"] < PROXY_MAX_FAIL_COUNT]
            return available if available else None

    @property
    def data(self):
        return self.get_data()

    def get_proxies(self):
        """
        随机返回一个可用代理。

        策略：
        - 30% 概率返回 None（直连），避免全部请求都走代理导致代理过载
        - 有 HTTPS 可用代理时，50% 概率选 HTTPS 代理（支持所有流量）
        - 否则返回 HTTP-only 代理（仅代理 HTTP 请求，HTTPS 走直连）

        返回：{"http": proxy, "https": proxy} 或 {"http": proxy} 或 None
        """
        with self._lock:
            all_available = [(p, info) for p, info in self._pool.items()
                             if info["fail_count"] < PROXY_MAX_FAIL_COUNT]

        if not all_available:
            return None

        # 30% 概率直连，分散请求压力
        if random.random() < 0.3:
            return None

        # 分离 HTTPS 可用和 HTTP-only 代理
        https_proxies = [p for p, info in all_available if info.get("https_ok")]
        http_only_proxies = [p for p, info in all_available if not info.get("https_ok")]

        # 如果有 HTTPS 代理，50% 概率优先用（避免少量HTTPS代理被过度使用）
        if https_proxies and (not http_only_proxies or random.random() < 0.5):
            proxy = random.choice(https_proxies)
            return {"http": proxy, "https": proxy}

        # 使用 HTTP-only 代理：仅代理 HTTP 流量，HTTPS 走直连
        all_http = [p for p, _ in all_available]
        if all_http:
            proxy = self._weighted_choice(all_http)
            return {"http": proxy}

        return None

    def _weighted_choice(self, available):
        """加权随机选择：失败次数越少权重越高"""
        weights = []
        for p in available:
            info = self._pool.get(p, {})
            fail = info.get("fail_count", 0)
            weights.append(max(1, PROXY_MAX_FAIL_COUNT - fail))
        return random.choices(available, weights=weights, k=1)[0]

    def report_failure(self, proxy_url):
        """
        报告代理失败（由调用方在请求失败时调用）
        累积失败次数达阈值后自动从池中移除
        """
        if proxy_url is None:
            return
        with self._lock:
            if proxy_url in self._pool:
                self._pool[proxy_url]["fail_count"] += 1
                if self._pool[proxy_url]["fail_count"] >= PROXY_MAX_FAIL_COUNT:
                    is_manual = self._pool[proxy_url].get("manual", False)
                    if not is_manual:
                        del self._pool[proxy_url]
                        logging.debug(f"代理池：移除失败代理 {proxy_url}")

    def report_success(self, proxy_url):
        """报告代理成功，重置失败计数"""
        if proxy_url is None:
            return
        with self._lock:
            if proxy_url in self._pool:
                self._pool[proxy_url]["fail_count"] = 0
                self._pool[proxy_url]["last_verified"] = time.time()

    def pool_size(self):
        """返回当前可用代理数量"""
        with self._lock:
            return len([p for p, info in self._pool.items() if info["fail_count"] < PROXY_MAX_FAIL_COUNT])

    def force_refresh(self):
        """手动触发刷新"""
        threading.Thread(target=self._refresh_cycle, daemon=True).start()

    # ══════════════════════════════════════════════
    # 免费代理源抓取
    # ══════════════════════════════════════════════

    def _fetch_from_sources(self):
        """从多个免费代理源抓取候选代理，返回去重列表"""
        candidates = set()
        fetchers = [
            ("proxylist.geonode.com", self._fetch_geonode),
            ("www.fate0.com/proxylist", self._fetch_fate0),
            ("raw.githubusercontent.com/proxifly", self._fetch_proxifly),
            ("raw.githubusercontent.com/TheSpeedX", self._fetch_thespeedx),
            ("raw.githubusercontent.com/monosans", self._fetch_monosans),
        ]

        for name, fetcher in fetchers:
            try:
                proxies = fetcher()
                if proxies:
                    candidates.update(proxies)
                    logging.debug(f"代理池：从 {name} 获取 {len(proxies)} 个候选")
            except Exception as e:
                logging.debug(f"代理池：从 {name} 获取失败: {e}")

        return list(candidates)

    def _fetch_geonode(self):
        """从 geonode.com 获取免费代理"""
        proxies = []
        try:
            url = "https://proxylist.geonode.com/api/proxy-list?limit=50&page=1&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps&anonymityLevel=elite%2Canonymous"
            r = requests.get(url, timeout=10, headers=self._ua_headers())
            if r.status_code == 200:
                data = r.json()
                for item in data.get("data", []):
                    ip = item.get("ip")
                    port = item.get("port")
                    protocols = item.get("protocols", [])
                    if ip and port:
                        proto = "https" if "https" in protocols else "http"
                        proxies.append(f"{proto}://{ip}:{port}")
        except Exception:
            pass
        return proxies

    def _fetch_fate0(self):
        """从 fate0 proxy list 获取"""
        proxies = []
        try:
            url = "http://proxylist.fate0.com/proxy.list"
            r = requests.get(url, timeout=10, headers=self._ua_headers())
            if r.status_code == 200:
                import json
                for line in r.text.strip().split("\n"):
                    try:
                        item = json.loads(line)
                        host = item.get("host")
                        port = item.get("port")
                        proto = item.get("type", "http")
                        if host and port:
                            proxies.append(f"{proto}://{host}:{port}")
                    except Exception:
                        continue
        except Exception:
            pass
        return proxies

    @staticmethod
    def _normalize_proxy(line, default_proto="http"):
        """规范化代理地址格式，确保有协议前缀且不重复"""
        line = line.strip()
        if not line or ":" not in line:
            return None
        # 已有协议前缀
        if line.startswith("http://") or line.startswith("https://") or line.startswith("socks"):
            return line
        # 纯 IP:PORT 格式
        return f"{default_proto}://{line}"

    def _fetch_proxifly(self):
        """从 proxifly GitHub 获取（返回格式：http://IP:PORT）"""
        proxies = []
        urls = [
            "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
            "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.txt",
        ]
        for url in urls:
            try:
                r = requests.get(url, timeout=10, headers=self._ua_headers())
                if r.status_code == 200:
                    for line in r.text.strip().split("\n"):
                        p = self._normalize_proxy(line)
                        if p:
                            proxies.append(p)
            except Exception:
                continue
        return proxies

    def _fetch_thespeedx(self):
        """从 TheSpeedX/PROXY-List GitHub 获取（返回格式：IP:PORT）"""
        proxies = []
        try:
            url = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
            r = requests.get(url, timeout=10, headers=self._ua_headers())
            if r.status_code == 200:
                lines = r.text.strip().split("\n")
                # 只取前200个，避免太多
                for line in lines[:200]:
                    p = self._normalize_proxy(line, "http")
                    if p:
                        proxies.append(p)
        except Exception:
            pass
        return proxies

    def _fetch_monosans(self):
        """从 monosans/proxy-list GitHub 获取（返回格式：IP:PORT）"""
        proxies = []
        try:
            url = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
            r = requests.get(url, timeout=10, headers=self._ua_headers())
            if r.status_code == 200:
                lines = r.text.strip().split("\n")
                for line in lines[:200]:
                    p = self._normalize_proxy(line, "http")
                    if p:
                        proxies.append(p)
        except Exception:
            pass
        return proxies

    # ══════════════════════════════════════════════
    # 代理验证
    # ══════════════════════════════════════════════

    def _validate_one(self, proxy_url):
        """
        验证单个代理是否可用
        1. 先测 HTTP 连通性（用东方财富 datacenter API）
        2. 再测 HTTPS 隧道支持（用 push2 API）
        返回 (http_ok, https_ok)
        """
        proxies = {"http": proxy_url, "https": proxy_url}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }

        # Step 1: HTTP 验证
        http_ok = False
        try:
            r = requests.get(
                PROXY_VALIDATE_URL,
                headers=headers,
                proxies=proxies,
                timeout=PROXY_VALIDATE_TIMEOUT,
                params={"type": "RPT_DAILYBILLBOARD_DETAILSNEW", "sty": "ALL", "p": "1", "ps": "3"}
            )
            if r.status_code == 200 and len(r.text) > 100:
                try:
                    data = r.json()
                    http_ok = data is not None
                except Exception:
                    pass
        except Exception:
            pass

        if not http_ok:
            return False, False

        # Step 2: HTTPS 隧道验证（可选，不通过也保留为 HTTP-only 代理）
        https_ok = False
        try:
            r2 = requests.get(
                "https://push2.eastmoney.com/api/qt/clist/get",
                headers={**headers, 'Referer': 'https://quote.eastmoney.com/'},
                proxies=proxies,
                timeout=PROXY_VALIDATE_TIMEOUT,
                params={"pn": "1", "pz": "3", "fields": "f2,f12,f14",
                        "fs": "m:0+t:6+f:!2", "ut": "fa5fd1943c7b386f172d6893dbfba10b"}
            )
            if r2.status_code == 200 and len(r2.text) > 50:
                https_ok = True
        except Exception:
            pass

        return http_ok, https_ok

    def _batch_validate(self, candidates, max_workers=None):
        """
        批量并发验证代理，将通过验证的加入池中
        返回通过验证的代理列表
        """
        if not candidates:
            return []

        if max_workers is None:
            max_workers = PROXY_FETCH_WORKERS

        # 排除已在池中的
        with self._lock:
            existing = set(self._pool.keys())
        new_candidates = [p for p in candidates if p not in existing]

        if not new_candidates:
            return []

        verified = []
        https_count = 0
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_proxy = {executor.submit(self._validate_one, p): p for p in new_candidates}
            for future in concurrent.futures.as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    http_ok, https_ok = future.result()
                    if http_ok:
                        with self._lock:
                            self._pool[proxy] = {
                                "fail_count": 0,
                                "last_verified": time.time(),
                                "manual": False,
                                "https_ok": https_ok,
                            }
                        verified.append(proxy)
                        if https_ok:
                            https_count += 1
                except Exception:
                    pass

        if https_count > 0:
            logging.info(f"代理池：其中 {https_count} 个支持 HTTPS 隧道")
        return verified

    def _revalidate_existing(self):
        """重新验证池中已有代理，移除不可用的"""
        with self._lock:
            to_check = list(self._pool.keys())

        if not to_check:
            return

        removed = 0
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=PROXY_FETCH_WORKERS) as executor:
            future_to_proxy = {executor.submit(self._validate_one, p): p for p in to_check}
            for future in concurrent.futures.as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    http_ok, https_ok = future.result()
                    with self._lock:
                        if proxy in self._pool:
                            if http_ok:
                                self._pool[proxy]["fail_count"] = 0
                                self._pool[proxy]["last_verified"] = time.time()
                                self._pool[proxy]["https_ok"] = https_ok
                            else:
                                is_manual = self._pool[proxy].get("manual", False)
                                if is_manual:
                                    self._pool[proxy]["fail_count"] = min(
                                        self._pool[proxy]["fail_count"] + 1,
                                        PROXY_MAX_FAIL_COUNT
                                    )
                                else:
                                    del self._pool[proxy]
                                    removed += 1
                except Exception:
                    pass

        if removed > 0:
            logging.info(f"代理池：重新验证完成，移除 {removed} 个失效代理，剩余 {self.pool_size()} 个")

    # ══════════════════════════════════════════════
    # 后台自动刷新
    # ══════════════════════════════════════════════

    def _start_background_refresh(self):
        """启动后台刷新线程"""
        if self._running:
            return
        self._running = True
        self._refresh_thread = threading.Thread(target=self._background_loop, daemon=True)
        self._refresh_thread.start()
        logging.info(f"代理池：后台刷新已启动（间隔 {PROXY_REFRESH_INTERVAL} 秒）")

    def _background_loop(self):
        """后台循环：定时刷新代理池"""
        while self._running:
            try:
                time.sleep(PROXY_REFRESH_INTERVAL)
                self._refresh_cycle()
            except Exception as e:
                logging.debug(f"代理池：后台刷新异常: {e}")

    def _refresh_cycle(self):
        """单次刷新：重新验证现有代理 + 补充新代理"""
        # Step 1: 重新验证现有代理
        self._revalidate_existing()

        # Step 2: 如果代理池不足，补充新代理
        current_size = self.pool_size()
        if current_size < PROXY_MIN_POOL_SIZE:
            logging.info(f"代理池：可用代理不足（{current_size}/{PROXY_MIN_POOL_SIZE}），正在补充...")
            candidates = self._fetch_from_sources()
            if candidates:
                verified = self._batch_validate(candidates)
                logging.info(f"代理池：补充完成，新增 {len(verified)} 个，当前可用 {self.pool_size()} 个")
        else:
            logging.debug(f"代理池：当前可用 {current_size} 个代理，状态健康")

        # Step 3: 重新加载 proxy.txt（支持运行时修改）
        self._load_manual_proxies()

    def stop(self):
        """停止后台刷新"""
        self._running = False

    @staticmethod
    def _ua_headers():
        """返回随机 User-Agent 请求头"""
        uas = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]
        return {"User-Agent": random.choice(uas)}
