"""PR-1 Smoke verifier.

Run: python _verify_pr1_smoke.py
"""
from __future__ import annotations

import json

from instock.lib import database as mdb
from instock.web.customIndicatorHandler import bootstrap
from instock.core.composite import dynamic_universe as du


def main() -> None:
    print("=" * 60)
    print("PR-1 SMOKE VERIFY")
    print("=" * 60)

    print("\n[1] DDL + seed builtin presets ...")
    bootstrap()
    rows = mdb.executeSqlFetch(
        "SELECT indicator_id, name, kind FROM cn_stock_custom_indicator "
        "WHERE is_builtin = 1 ORDER BY id"
    )
    for r in rows:
        print(f"   - {r[0]:30s} | {r[1]} | kind={r[2]}")
    assert len(rows) >= 3, "expected 3 builtin presets"

    print("\n[2] fetch_universe (force refresh) ...")
    df = du.fetch_universe(top_n=10, force_refresh=True)
    print(f"   universe size = {len(df)}; cache = {du.CACHE_FILE}")
    if not df.empty:
        print(df[["code", "name", "industry", "score"]].head(10).to_string(index=False))

    print("\n[3] fundamentals_signal sample ...")
    if not df.empty:
        code = df.iloc[0]["code"]
        sig = du.fundamentals_signal(code)
        print(f"   {code}: {json.dumps(sig, ensure_ascii=False)}")

    print("\n[4] hard rules sandbox quick check ...")
    from instock.core.composite.hard_rules_engine import eval_hard_rules
    import pandas as pd
    d = pd.DataFrame({"rsi14": [25.0, 35.0], "close": [9.0, 10.0],
                      "boll_lower": [9.5, 9.5]})
    out = eval_hard_rules("(d['rsi14'] < 30) & (d['close'] < d['boll_lower'])", d)
    print(f"   eval result = {out.tolist()}  (expect [True, False])")
    assert out.tolist() == [True, False]

    print("\nALL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
