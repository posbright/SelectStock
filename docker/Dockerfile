# 基础镜像
# https://hub.docker.com/_/python/tags?page=1&name=3.11-slim-bullseye
FROM docker.io/python:3.11-slim-bullseye

LABEL maintainer="InStock Team"
LABEL description="InStock - 股票数据分析系统（支持多数据源：新浪财经/腾讯财经/东方财富，支持增量缓存）"
LABEL version="2.1"

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
ENV HIST_DATA_DEFAULT_YEARS=3
ENV HIST_DATA_CACHE_EXPIRE_DAYS=7

EXPOSE 9988

# 使用国内镜像地址加速。修改debian apt更新地址，pip地址，设置时区
# https://opsx.alibaba.com/mirror
# https://mirrors.tuna.tsinghua.edu.cn/help/pypi/
# cat /etc/apt/sources.list 参考原始地址，再确定怎么样替换
# 安装依赖库
# apt-get autoremove -y 删除没有用的依赖lib
# apt-get --purge remove 软件包名称 , 删除已安装包（不保留配置文件)
RUN sed -i "s@http://\(deb\|security\).debian.org@https://mirrors.aliyun.com@g" /etc/apt/sources.list && \
    echo  "[global]\n\
index-url = https://mirrors.aliyun.com/pypi/simple\n\
trusted-host = mirrors.aliyun.com" > /etc/pip.conf && \
    ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone && \
    apt-get update && \
    apt-get install -y cron gcc make python3-dev default-libmysqlclient-dev build-essential pkg-config curl && \
    pip install --upgrade pip && \
    pip install supervisor && \
    pip install mysqlclient && \
    pip install requests && \
    pip install arrow && \
    pip install numpy && \
    pip install SQLAlchemy && \
    pip install PyMySQL && \
    pip install Logbook && \
    pip install python_dateutil && \
    pip install py_mini_racer && \
    pip install tqdm && \
    pip install beautifulsoup4 && \
    pip install bokeh && \
    pip install pandas && \
    pip install tornado && \
    pip install mini-racer && \
    pip install easytrader && \
    pip install pycryptodome && \
    pip install lxml && \
    mkdir ta-lib && \
    curl -SL $(curl -s https://api.github.com/repos/ta-lib/ta-lib/releases/latest | grep browser_download_url | cut -d'"' -f4 |grep -E 'tar.gz$') | tar -xz --strip-components=1 -C ./ta-lib && \
    cd ta-lib/ && \
    ./configure && \
    make && \
    make install && \
    cd .. && \
    pip install TA-Lib && \
    rm -rf ta-lib* && \
    apt-get --purge remove -y gcc make python3-dev default-libmysqlclient-dev curl && \
    rm -rf /root/.cache/* && rm -rf /var/lib/apt/lists/* && apt-get clean && apt-get autoclean && apt-get autoremove -y

WORKDIR /data
# InStock软件
COPY stock /data/InStock
COPY cron/cron.hourly /etc/cron.hourly
COPY cron/cron.workdayly /etc/cron.workdayly
COPY cron/cron.monthly /etc/cron.monthly

# add cron service.
# 任务调度
RUN chmod 755 /data/InStock/instock/bin/run_*.sh && \
    chmod 755 /etc/cron.hourly/* && chmod 755 /etc/cron.workdayly/* && chmod 755 /etc/cron.monthly/* && \
    echo "SHELL=/bin/sh \n\
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin \n\
# min hour day month weekday command \n\
*/30 9,10,11,13,14,15 * * 1-5 /bin/run-parts /etc/cron.hourly \n\
30 17 * * 1-5 /bin/run-parts /etc/cron.workdayly \n\
30 10 * * 3,6 /bin/run-parts /etc/cron.monthly \n" > /var/spool/cron/crontabs/root && \
    chmod 600 /var/spool/cron/crontabs/root

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:9988/ || exit 1

ENTRYPOINT ["supervisord","-n","-c","/data/InStock/supervisor/supervisord.conf"]