@echo off
chcp 65001 >nul

REM ============================================================
REM 本地执行脚本 — 利用本地计算资源执行完整数据流水线
REM
REM 适用场景：
REM   - 服务器内存不足（1.6GB），分析任务频繁 OOM
REM   - 本地计算机资源充足，手动触发数据处理
REM   - 结果直接写入远程数据库，服务器前端即时可见
REM
REM 使用方式：
REM   1. 直接双击运行（当日数据）
REM   2. 命令行: run_local.bat 2026-03-09（指定日期）
REM   3. 命令行: run_local.bat 2026-03-01,2026-03-02（多日期）
REM   4. 命令行: run_local.bat 2026-03-01 2026-03-09（日期区间）
REM
REM 注意：
REM   - 所有任务幂等安全，重复执行不会产生重复数据
REM   - 服务器 cron 会自动检测本地是否已完成，避免重复执行
REM ============================================================

cd /d %~dp0
cd ..\..

REM === 激活虚拟环境 ===
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [警告] 未找到 .venv，将使用系统 Python
)

cd instock\job

REM === 高并发配置（利用本地充足的 CPU 和内存）===
REM 流式分析并发线程数（服务器默认 2，本地放大到 16）
set INSTOCK_ANALYSIS_WORKERS=16

REM 批量写入大小（服务器默认 50，本地放大到 1000）
set INSTOCK_BATCH_SIZE=1000

REM 回测内层并发线程数（服务器默认 2，本地放大到 4）
set INSTOCK_BACKTEST_INNER_WORKERS=4

REM === 数据库超时配置（远程连接适当放宽）===
set INSTOCK_DB_READ_TIMEOUT=60
set INSTOCK_DB_WRITE_TIMEOUT=60

echo ============================================================
echo  InStock 本地数据处理
echo ============================================================
echo.
echo  并发配置:
echo    分析线程: %INSTOCK_ANALYSIS_WORKERS%
echo    批量大小: %INSTOCK_BATCH_SIZE%
echo    回测线程: %INSTOCK_BACKTEST_INNER_WORKERS%
echo.
echo  执行参数: %*
echo ============================================================
echo.

if "%~1"=="" (
    echo [%date% %time%] 执行当日完整流水线...
    python execute_daily_job.py
) else (
    echo [%date% %time%] 执行指定日期流水线: %*
    python execute_daily_job.py %*
)

echo.
echo ============================================================
echo  执行完成！结果已写入远程数据库，服务器前端可查看。
echo ============================================================
pause
