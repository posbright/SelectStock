"""PR-2 Smoke verifier — 启动 web，逐个 API 跑一次 happy path。

用法：
    # 终端 A：启动 web（自动 bootstrap）
    python -m instock.bin.run_web

    # 终端 B：跑此脚本
    python _verify_pr2_smoke.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

BASE_URL = "http://localhost:9988"


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(path: str, body: dict) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    print("=" * 60)
    print("PR-2 SMOKE VERIFY (需先启动 web 服务于 :9988)")
    print("=" * 60)

    # 1. /list
    print("\n[1] GET /custom_indicator/list ...")
    r = _get("/instock/api/custom_indicator/list")
    assert r["code"] == 0, r
    print(f"   total = {len(r['data'])}")
    for it in r["data"][:5]:
        print(f"   - {it['indicator_id']:30s} | {it['name']:20s} | kind={it['kind']} | builtin={it['is_builtin']}")
    assert any(it["indicator_id"] == "steady_oversold_rebound" for it in r["data"])

    # 2. /detail
    print("\n[2] GET /custom_indicator/detail?indicator_id=steady_oversold_rebound ...")
    r = _get("/instock/api/custom_indicator/detail?indicator_id=steady_oversold_rebound")
    assert r["code"] == 0, r
    d = r["data"]
    print(f"   name={d['name']}  hard_rules length={len(d['hard_rules'] or '')}")
    assert d["kind"] == "primary_entry"

    # 3. /save (新增)
    print("\n[3] POST /custom_indicator/save ...")
    r = _post("/instock/api/custom_indicator/save", {
        "indicator_id": "smoke_test_pr2",
        "name": "PR-2 烟雾测试",
        "kind": "primary_entry",
        "description": "automated smoke verifier",
        "weights": {},
        "smooth_ema": 0,
        "buy_th": 0,
        "direction": "high",
        "hard_rules": "(d['rsi14'] < 30) & (d['close'] > d['boll_lower'])",
        "risk_profile": {"stop": -0.08, "target": 0.20, "max_hold": 30},
    })
    assert r["code"] == 0, r
    print(f"   saved indicator_id = {r['data']['indicator_id']}")

    # 4. /save 沙箱注入 — 必须拒绝
    print("\n[4] POST /save with __import__ ...（必须被拒绝）")
    r = _post("/instock/api/custom_indicator/save", {
        "indicator_id": "smoke_attack_pr2",
        "name": "attack",
        "kind": "primary_entry",
        "hard_rules": "__import__('os').system('whoami')",
    })
    assert r["code"] == -1 and "解析失败" in r["msg"], r
    print(f"   rejected: {r['msg']}")

    # 5. /save 内置预设 — 必须拒绝修改
    print("\n[5] POST /save 修改内置预设 ...（必须被拒绝）")
    r = _post("/instock/api/custom_indicator/save", {
        "indicator_id": "steady_oversold_rebound",
        "name": "试图覆盖内置",
        "kind": "primary_entry",
        "hard_rules": "d['rsi14'] < 30",
    })
    assert r["code"] == -1 and "内置" in r["msg"], r
    print(f"   rejected: {r['msg']}")

    # 6. /backtest
    print("\n[6] POST /custom_indicator/backtest ...")
    r = _post("/instock/api/custom_indicator/backtest", {
        "indicator_id": "smoke_test_pr2",
        "code": "000001",
        "start": "2023-01-01",
        "end": "2024-12-31",
    })
    if r["code"] == 0:
        s = r["data"]["summary"]
        print(f"   {s.get('strategy')}: trades={s.get('trades')}  win%={s.get('win%')}  PF={s.get('PF')}")
    else:
        print(f"   ⚠ {r['msg']}（数据缺失可忽略）")

    # 7. /series
    print("\n[7] GET /custom_indicator/series ...")
    r = _get("/instock/api/custom_indicator/series?indicator_id=smoke_test_pr2&code=000001&start=2024-01-01&end=2024-12-31")
    if r["code"] == 0:
        print(f"   signal_points = {len(r['data']['signal_points'])}; "
              f"score_series = {len(r['data']['score_series'])}")
    else:
        print(f"   ⚠ {r['msg']}（数据缺失可忽略）")

    # 8. /watchlist (评分类)
    print("\n[8] GET /custom_indicator/watchlist?id=score_alert_watchlist&top_n=10 ...")
    r = _get("/instock/api/custom_indicator/watchlist?indicator_id=score_alert_watchlist&top_n=10")
    if r["code"] == 0:
        items = r["data"]["items"]
        print(f"   评分榜共 {len(items)} 只；warning={r['data'].get('warning')}")
        for it in items[:5]:
            print(f"   - {it['code']} {it.get('name')} score={it.get('latest_score')}")
    else:
        print(f"   ⚠ {r['msg']}")

    # 9. /delete
    print("\n[9] POST /custom_indicator/delete ...")
    r = _post("/instock/api/custom_indicator/delete",
              {"indicator_id": "smoke_test_pr2"})
    assert r["code"] == 0, r
    print("   deleted ok")

    # 10. /delete 内置 — 必须拒绝
    print("\n[10] POST /delete 内置预设 ...（必须被拒绝）")
    r = _post("/instock/api/custom_indicator/delete",
              {"indicator_id": "steady_oversold_rebound"})
    assert r["code"] == -1 and "内置" in r["msg"], r
    print(f"   rejected: {r['msg']}")

    print("\nALL PR-2 API SMOKE CHECKS PASSED")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ FAILED: {e}", file=sys.stderr)
        sys.exit(1)
