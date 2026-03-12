@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

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
set PROJECT_ROOT=%cd%

REM === 从 .env 加载数据库配置（连接远程服务器）===
if exist "%PROJECT_ROOT%\.env" (
    echo [信息] 加载 .env 配置...
    for /f "usebackq tokens=1,* delims==" %%A in ("%PROJECT_ROOT%\.env") do (
        set "_line=%%A"
        if not "!_line:~0,1!"=="#" if not "%%A"=="" (
            set "%%A=%%B"
        )
    )
) else (
    echo [警告] 未找到 .env 文件，将使用默认数据库配置（127.0.0.1）
)

REM === 激活虚拟环境 ===
if exist "%PROJECT_ROOT%\.venv\Scripts\activate.bat" (
    call "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
) else (
    echo [警告] 未找到 .venv，将使用系统 Python
)

cd instock\job

REM === 高并发配置（利用本地充足的 CPU 和内存）===
REM 流式分析并发线程数（服务器默认 2，本地放大到 16）
set INSTOCK_ANALYSIS_WORKERS=16

REM 批量写入大小（服务器默认 50，本地放大到 3000）
set INSTOCK_BATCH_SIZE=3000

REM 回测内层并发线程数（服务器默认 2，本地放大到 4）
set INSTOCK_BACKTEST_INNER_WORKERS=4

REM === 数据库超时配置（远程连接适当放宽）===
set INSTOCK_DB_CONNECT_TIMEOUT=30
set INSTOCK_DB_READ_TIMEOUT=60
set INSTOCK_DB_WRITE_TIMEOUT=60

REM === 重试配置（远程连接可能间歇性超时）===
set INSTOCK_DB_MAX_RETRIES=3
set INSTOCK_DB_RETRY_DELAY=10

REM === Python 编码配置（确保 cmd 中正确输出中文）===
set PYTHONIOENCODING=utf-8

echo ============================================================
echo  InStock 本地数据处理
echo ============================================================
echo.
echo  数据库: %db_host%:%db_port%/%db_database%
echo  超时: 连接%INSTOCK_DB_CONNECT_TIMEOUT%s 读%INSTOCK_DB_READ_TIMEOUT%s 写%INSTOCK_DB_WRITE_TIMEOUT%s
echo  重试: %INSTOCK_DB_MAX_RETRIES%次 间隔%INSTOCK_DB_RETRY_DELAY%s
echo.
echo  并发配置:
echo    分析线程: %INSTOCK_ANALYSIS_WORKERS%
echo    批量大小: %INSTOCK_BATCH_SIZE%
echo    回测线程: %INSTOCK_BACKTEST_INNER_WORKERS%
echo.
echo  执行参数: %*
echo ============================================================
echo.

REM === 启动前预检：测试数据库连接 ===
echo [%date% %time%] 测试数据库连接...
python -c "import sys,os;sys.path.insert(0,os.path.abspath('../..'));import instock.lib.database as m;import pymysql,time;t=time.time();c=pymysql.connect(**m.MYSQL_CONN_DBAPI);print(f'  连接成功 ({time.time()-t:.1f}s) MySQL {c.server_version}');c.close()" 2>&1
if errorlevel 1 (
    echo.
    echo [错误] 数据库连接失败！请检查：
    echo   1. 服务器 %db_host% 是否可达
    echo   2. 阿里云安全组是否放行了当前IP的3306端口
    echo   3. .env 中的密码是否正确
    echo.
    pause
    exit /b 1
)
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
