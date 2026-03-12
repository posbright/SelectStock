# 基础镜像
# https://hub.docker.com/_/python/tags
# 使用 python:3.11-slim 更通用，兼容各种Docker环境和镜像加速器
FROM python:3.11-slim

LABEL maintainer="InStock Team"
LABEL description="InStock - 股票数据分析系统（支持多数据源：新浪财经/腾讯财经/东方财富，支持增量缓存）"
LABEL version="2.2"

# 设置环境变量
ENV LANG=zh_CN.UTF-8
ENV LC_CTYPE=zh_CN.UTF-8
ENV LC_ALL=C
ENV PYTHONPATH=/data/InStock
ENV PYTHONUNBUFFERED=1

# 数据库连接配置（可通过docker-compose或docker run -e覆盖）
ENV db_host=localhost
ENV db_port=3306
ENV db_user=root
ENV db_password=root
ENV db_database=instockdb

# 数据源配置
ENV DATA_SOURCE_MAX_RETRIES=2
ENV DATA_SOURCE_RETRY_INTERVAL=30

# 历史数据配置
ENV HIST_DATA_DEFAULT_YEARS=10
ENV HIST_DATA_CACHE_EXPIRE_DAYS=60

EXPOSE 9988

# 配置国内镜像加速
# 兼容 Debian 11 (bullseye) 和 Debian 12 (bookworm) 两种源配置格式
# pip使用阿里云镜像
RUN set -eux; \
    # 检测并配置apt源（兼容新旧格式）
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
        sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list; \
        sed -i 's|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list; \
    fi; \
    # 配置pip镜像
    mkdir -p /root/.config/pip; \
    echo "[global]" > /root/.config/pip/pip.conf; \
    echo "index-url = https://mirrors.aliyun.com/pypi/simple/" >> /root/.config/pip/pip.conf; \
    echo "trusted-host = mirrors.aliyun.com" >> /root/.config/pip/pip.conf; \
    # 设置时区
    ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime; \
    echo "Asia/Shanghai" > /etc/timezone

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        cron \
        gcc \
        g++ \
        make \
        python3-dev \
        default-libmysqlclient-dev \
        build-essential \
        pkg-config \
        curl \
        wget \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装TA-Lib C库（使用固定版本提高稳定性）
# TA-Lib 0.4.0 是稳定版本
ARG TALIB_VERSION=0.4.0
RUN set -eux; \
    cd /tmp; \
    wget -q https://github.com/ta-lib/ta-lib/releases/download/v${TALIB_VERSION}/ta-lib-${TALIB_VERSION}-src.tar.gz \
        || wget -q https://prdownloads.sourceforge.net/ta-lib/ta-lib-${TALIB_VERSION}-src.tar.gz \
        || curl -SLO https://github.com/ta-lib/ta-lib/releases/download/v${TALIB_VERSION}/ta-lib-${TALIB_VERSION}-src.tar.gz; \
    tar -xzf ta-lib-${TALIB_VERSION}-src.tar.gz; \
    cd ta-lib/; \
    ./configure --prefix=/usr; \
    make -j$(nproc); \
    make install; \
    cd /; \
    rm -rf /tmp/ta-lib*; \
    ldconfig

# 升级pip并安装Python依赖
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
        supervisor \
        mysqlclient \
        requests \
        arrow \
        numpy \
        SQLAlchemy \
        PyMySQL \
        Logbook \
        python_dateutil \
        py_mini_racer \
        tqdm \
        beautifulsoup4 \
        bokeh \
        pandas \
        tornado \
        mini-racer \
        easytrader \
        pycryptodome \
        lxml \
        TA-Lib

# 清理构建依赖（保留curl用于健康检查）
RUN apt-get update && \
    apt-get purge -y --auto-remove \
        gcc \
        g++ \
        make \
        python3-dev \
        default-libmysqlclient-dev \
        build-essential \
        pkg-config \
        wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /root/.cache/*

WORKDIR /data

# 复制应用代码和定时任务配置
COPY stock /data/InStock
COPY cron/_common.sh /etc/cron/_common.sh
COPY cron/cron.hourly /etc/cron.hourly
COPY cron/cron.workdayly /etc/cron.workdayly
COPY cron/cron.monthly /etc/cron.monthly

# 配置定时任务
RUN set -eux; \
    chmod 755 /data/InStock/instock/bin/run_*.sh;
    chmod 755 /etc/cron/_common.sh; \
    find /etc/cron.hourly /etc/cron.workdayly /etc/cron.monthly -type f -exec chmod 755 {} \; 2>/dev/null || true; \
    # 创建crontab配置
    # 拆分模式：fetch → kline_cache → analysis 三阶段独立运行
    # 优势：每阶段可独立运行/重试，互不阻塞
    # 每个任务都有 flock 防并发 + 重试计划
    printf '%s\n' \
        'SHELL=/bin/sh' \
        'PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin' \
        'PYTHONPATH=/data/InStock' \
        '# min hour day month weekday command' \
        '# ── 盘中行情快照（轻量级，用于盘中监控）──' \
        '0 12 * * 1-5 flock -xn /tmp/instock_hourly.lock /etc/cron.hourly/run_hourly' \
        '18 15 * * 1-5 flock -xn /tmp/instock_hourly.lock /etc/cron.hourly/run_hourly' \
        '# ── 收盘后数据获取（API调用：行情+选股+资金流向）──' \
        '0 18 * * 1-5 flock -xn /tmp/instock_fetch.lock /etc/cron.workdayly/run_fetch' \
        '# ── 数据获取重试（如18:00仍在运行则flock跳过）──' \
        '0 1 * * 2-6 flock -xn /tmp/instock_fetch.lock /etc/cron.workdayly/run_fetch' \
        '# ── K线缓存增量更新（依赖 fetch 完成）──' \
        '0 20 * * 1-5 flock -xn /tmp/instock_kline.lock /etc/cron.workdayly/run_kline_cache' \
        '# ── K线缓存重试 ──' \
        '30 1 * * 2-6 flock -xn /tmp/instock_kline.lock /etc/cron.workdayly/run_kline_cache' \
        '# ── 数据分析（本地计算：指标+K线形态+策略+回测）──' \
        '0 22 * * 1-5 flock -xn /tmp/instock_analysis.lock /etc/cron.workdayly/run_analysis' \
        '# ── 数据分析重试 ──' \
        '30 2 * * 2-6 flock -xn /tmp/instock_analysis.lock /etc/cron.workdayly/run_analysis' \
        '# ── 月度缓存清理 ──' \
        '0 4 1 * * /etc/cron.monthly/run_monthly' \
    > /var/spool/cron/crontabs/root; \
    chmod 600 /var/spool/cron/crontabs/root

# 健康检查（使用curl检测Web服务）
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:9988/ || exit 1

ENTRYPOINT ["supervisord", "-n", "-c", "/data/InStock/supervisor/supervisord.conf"]