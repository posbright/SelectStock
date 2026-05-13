# AGENTS.md — InStock 量化选股系统

Quantitative A-stock / ETF analysis platform. Tornado backend + Vue 3 frontend, MySQL storage, multi-source crawlers (EastMoney → Tencent → Sina), TA-Lib indicators, Backtrader backtests, paper trading.

For background, prefer linking over re-reading:
- Architecture, data-source strategy, module map: [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)
- Setup / common commands: [QUICKSTART.md](QUICKSTART.md)
- API surface: [document/API_REFERENCE.md](document/API_REFERENCE.md)
- DB schema: [document/database_schema.md](document/database_schema.md)
- Domain plans (read on demand): [document/](document/)

## Build & test

Python (run from repo root, venv activated):
- Install: `pip install -r requirements.txt`
- Full suite: `pytest -q` (≈1700+ tests; some require MySQL — see env below)
- Single test: `pytest tests/test_<name>.py -q`
- Note: [tests/conftest.py](tests/conftest.py) already ignores script-style files (`test_bugfixes.py`, `test_data_fixes.py`, `test_data_source_consistency.py`, `test_pagination.py`, `test_sector_api.py`). Don't add them back to runs.
- Smoke verifiers (top-level `_verify_*.py`) are runnable scripts, not pytest tests.

Frontend (in [instock/fontWeb](instock/fontWeb)):
- `npm install` then `npm run dev` (or `npm run dev:mock`)
- Type-check + build: `npm run build`
- Unit tests: `npm test`
- Production: copy `instock/fontWeb/dist/**` into [instock/web/static](instock/web/static) — Tornado serves from there. Vite build alone is not enough.

Web service:
- Start: [instock/bin/run_web.sh](instock/bin/run_web.sh) / `run_web.bat` → http://localhost:9988
- After ANY backend Python change, restart `web_service.py` (long-running process; modules are cached). Remote: `/root/SelectStock/instock/bin/restart_web.sh`.

Env: copy `.env` template; required keys are `db_host/db_user/db_password/db_database`. AI provider keys (`INSTOCK_AI_PROVIDER_*`) are only needed for AI features. `INSTOCK_LOCAL_MODE=1` enables higher concurrency.

## Architecture rules (do not violate)

1. **Fetch / Analysis / Web separation** — only the Fetch pipeline ([instock/job/fetch_*](instock/job), `instock/core/stockfetch.py`, `instock/core/crawling/`) may call external APIs. Analysis and Web pipelines must read from MySQL + `cache/hist/` only. Never add `requests`/`akshare` calls inside `instock/web/*Handler.py` or analysis jobs.
2. **Table metadata** lives in [instock/core/tablestructure.py](instock/core/tablestructure.py). Do **not** import `instock.lib.tablestructure` for stock metadata — it is not the source of truth.
3. **Index codes** (`000300`, `399xxx`, …) in backtests must go through `load_benchmark_data`, not `load_stock_data`. Routing them to `load_stock_data` makes EastMoney `secid=0.000300` → HTTP 500.
4. **Index cache invariant** — `cache/hist/index/{code}.gzip.pickle` holds the *full* history. `instock/core/backtest/data_feed.py::_save_index_cache` MERGES new rows (drop_duplicates by date, keep='last'). Never blind-overwrite with a date-bounded slice. Source of truth for repair: `akshare.stock_zh_index_daily(symbol='sh000300')`.
5. **Dynamic universe strategies** (fundamental selectors) discover candidates after preload. Backtest and paper-trading `history` / `attribute_history` paths require lazy K-line loading + normalized daily timestamps for order price lookup.
6. **Paper-trading display truth**: latest `cn_stock_paper_nav` row is authoritative for current asset/cash/profit. `cn_stock_paper_trading.current_value/current_cash` may be stale. Use `initial_cash` (not first NAV) as full-life baseline for metrics/charts.

## DB write hygiene

- All `df.to_sql` writes must pass `chunksize=500` (constant `_DB_INSERT_CHUNKSIZE` in [instock/lib/database.py](instock/lib/database.py)). Without it, `_mysql_upsert` builds one giant INSERT and OOM-kills the 1.6 GB server. (Regression history: commit bba51731.)
- MySQL/PyMySQL rejects NaN/inf (`inf can not be used with MySQL`). Sanitize at the source AND rely on the guard in `instock/lib/database.py` before write. Do not silently fillna in handlers.
- Strategy ratio math: keep finite at compute time — don't push the burden onto the DB layer.

## Frontend / template sync

- Built-in strategy source changes are synced to DB by `portfolioBacktestHandler.sync_strategy_templates_to_db()` on Web service startup, and by `POST /instock/api/strategy/sync_templates`. Algo list "导入示例策略" uses the same endpoint.
- Sync tracks `template_id`, `template_hash`, `user_modified`. Frontend-saved built-ins are protected from overwrite when their code differs from official templates.
- If you change a template's code, restart the web service so sync runs (or hit the sync endpoint) — otherwise frontend edit / backtest pages keep the old code.

## Memory efficiency

Streaming analysis ([instock/job/streaming_analysis_job.py]) processes 4900+ stocks with <100 MB peak memory by single-pass iteration. Don't materialize full universe DataFrames in handlers or jobs.

## Key directories

| Path | Purpose |
| --- | --- |
| [instock/core/stockfetch.py](instock/core/stockfetch.py) | Multi-source data scheduler + incremental cache |
| [instock/core/crawling/](instock/core/crawling) | Per-source HTTP crawlers (EastMoney/Tencent/Sina) |
| [instock/core/strategy/](instock/core/strategy) | 14 built-in selection strategies |
| [instock/core/indicator/](instock/core/indicator), [instock/core/pattern/](instock/core/pattern), [instock/core/kline/](instock/core/kline) | TA-Lib indicators, 61 K-line patterns, K-line utils |
| [instock/core/backtest/](instock/core/backtest) | Backtrader feeds, runners, metrics |
| [instock/core/composite/](instock/core/composite) | Phase 9 自定义综合指标 (normalizers, hard-rule AST sandbox, risk simulator, dynamic universe) |
| [instock/job/](instock/job) | Daily / hourly batch jobs (fetch + analysis pipelines) |
| [instock/web/](instock/web) | Tornado handlers + Jinja templates + static assets |
| [instock/paper_trading/](instock/paper_trading), [instock/live/](instock/live), [instock/trade/](instock/trade) | Paper / live / brokerage trading |
| [instock/ai_decision/](instock/ai_decision) | AI assistant + multi-provider LLM integration |
| [instock/auth/](instock/auth), [instock/notification/](instock/notification), [instock/im/](instock/im) | Auth, notifications, DingTalk/IM |
| [cron/](cron) | Cron entry scripts (hourly / workdayly / monthly) |

## Pitfalls quick list

- Don't add API calls to handlers / analysis jobs (rule 1).
- Don't import `instock.lib.tablestructure` for stock metadata (rule 2).
- Don't route index codes through `load_stock_data` (rule 3).
- Don't `to_pickle` blind-overwrite the index cache (rule 4).
- Don't omit `chunksize=500` in `to_sql`.
- Don't forget to restart the web service after backend edits.
- Don't forget to copy Vite `dist/` into `instock/web/static` for prod.
- Hard-rule expressions (composite): AST sandbox blocks `__import__`, dunders, lambda, file ops, exec/eval, attribute access on dicts. Don't try to "improve" the sandbox by relaxing these.
