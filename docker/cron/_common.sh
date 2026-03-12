#!/bin/bash
# ═══════════════════════════════════════════════════════════
# Cron 脚本公共库（Docker 版）
# 与 cron/_common.sh 保持同步，仅部署路径不同
# ═══════════════════════════════════════════════════════════

# ─── 环境初始化 ───
init_env() {
    export PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin:$PATH
    export PYTHONIOENCODING=utf-8
    export LANG=zh_CN.UTF-8
    export LC_CTYPE=zh_CN.UTF-8
    export PYTHONPATH=$PROJECT_ROOT

    if [ -f "$PROJECT_ROOT/.env" ]; then
        set -a; source "$PROJECT_ROOT/.env"; set +a
    fi

    LOG_DIR=$PROJECT_ROOT/instock/log
    mkdir -p "$LOG_DIR"
}

# ─── 日志工具 ───
_ts() { date '+%Y-%m-%d %H:%M:%S'; }

log_info()  { echo "[$(_ts)] [INFO]  $*" >> "$LOG_FILE"; }
log_warn()  { echo "[$(_ts)] [WARN]  $*" >> "$LOG_FILE"; }
log_error() { echo "[$(_ts)] [ERROR] $*" >> "$LOG_FILE"; }

elapsed_fmt() {
    local s=$1
    if [ "$s" -ge 3600 ] 2>/dev/null; then
        printf "%dh%02dm%02ds" $((s/3600)) $((s%3600/60)) $((s%60))
    elif [ "$s" -ge 60 ] 2>/dev/null; then
        printf "%dm%02ds" $((s/60)) $((s%60))
    else
        printf "%ds" "$s"
    fi
}

# ─── 交易日检测 ───
check_trade_day() {
    local task_name="${1:-任务}"
    local is_trade
    is_trade=$(python3 -c "
import sys; sys.path.insert(0, '$PROJECT_ROOT')
try:
    import instock.lib.trade_time as trd
    print('1' if trd.is_trade_date() else '0')
except Exception:
    print('1')
" 2>/dev/null)

    if [ "$is_trade" = "0" ]; then
        log_info "非交易日，跳过${task_name}"
        exit 0
    fi
}

# ─── 运行 Python 作业 ───
run_job() {
    local label="$1"
    local script="$2"
    local timeout="${3:-0}"
    local start_ts rc end_ts dur dur_str

    start_ts=$(date +%s)
    log_info "────── ${label} 开始 ──────"

    if [ "$timeout" -gt 0 ] 2>/dev/null; then
        timeout "$timeout" python3 "$PROJECT_ROOT/$script" >> "$LOG_FILE" 2>&1
    else
        python3 "$PROJECT_ROOT/$script" >> "$LOG_FILE" 2>&1
    fi
    rc=$?

    end_ts=$(date +%s)
    dur=$((end_ts - start_ts))
    dur_str=$(elapsed_fmt $dur)

    if [ $rc -eq 0 ]; then
        log_info "────── ${label} 完成 ✓ (${dur_str}) ──────"
    elif [ $rc -eq 124 ]; then
        log_error "────── ${label} 超时 ✗ (限制 ${timeout}s, 已用 ${dur_str}) ──────"
    else
        log_error "────── ${label} 失败 ✗ (退出码 ${rc}, ${dur_str}) ──────"
    fi

    return $rc
}

# ─── 运行 Shell 子脚本 ───
run_sub() {
    local label="$1"
    local script="$2"
    local start_ts rc end_ts dur dur_str

    start_ts=$(date +%s)
    log_info "══════ ${label} 开始 ══════"

    bash "$script"
    rc=$?

    end_ts=$(date +%s)
    dur=$((end_ts - start_ts))
    dur_str=$(elapsed_fmt $dur)

    if [ $rc -eq 0 ]; then
        log_info "══════ ${label} 完成 ✓ (${dur_str}) ══════"
    else
        log_warn "══════ ${label} 异常 ✗ (退出码 ${rc}, ${dur_str}) ══════"
    fi

    return $rc
}
