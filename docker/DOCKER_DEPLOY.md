# InStock Docker 部署指南

## 概述

InStock 是一个股票数据分析系统，支持多数据源（新浪财经、腾讯财经、东方财富），支持历史数据增量缓存。

**版本**: 2.2

## 新功能

- ✅ 多数据源自动切换（新浪 → 腾讯 → 东方财富）
- ✅ 历史数据增量更新（以天为单位）
- ✅ 可配置历史数据年数（1-20年）
- ✅ 自动清理过期缓存
- ✅ 环境变量灵活配置
- ✅ 兼容 Debian 11/12 (bullseye/bookworm)
- ✅ MySQL 8.0 官方镜像

## 快速开始

### 1. 构建镜像

**Linux/Mac:**
```bash
cd docker
chmod +x build.sh
./build.sh
```

**Windows:**
```cmd
cd docker
build.bat
```

### 2. 启动服务

#### 方式一：使用本地数据库（推荐新手）

```bash
# 复制环境配置文件
cp .env.example .env

# 编辑.env文件，修改配置（可选）
# vim .env

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

#### 方式二：连接远程数据库

```bash
# 编辑远程数据库配置
export REMOTE_DB_HOST=your-db-host
export REMOTE_DB_PASSWORD=your-password

# 启动服务
docker-compose -f docker-compose.remote-db.yml up -d
```

## 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `db_host` | localhost | 数据库主机 |
| `db_port` | 3306 | 数据库端口 |
| `db_user` | root | 数据库用户 |
| `db_password` | root | 数据库密码 |
| `db_database` | instockdb | 数据库名称 |
| `WEB_PORT` | 9988 | Web服务端口 |
| `SUPERVISOR_PORT` | 9001 | Supervisor管理端口 |
| `DATA_SOURCE_MAX_RETRIES` | 2 | 数据源最大重试次数 |
| `DATA_SOURCE_RETRY_INTERVAL` | 30 | 数据源基础重试间隔（秒，指数退避） |
| `HIST_DATA_DEFAULT_YEARS` | 3 | 默认获取历史数据年数（裸机部署默认20年） |

> 注意：Docker 环境默认获取3年历史数据以加快首次启动，裸机部署默认20年。可通过环境变量自行调整。
> `HIST_DATA_CACHE_EXPIRE_DAYS` 已废弃，缓存清理现由 `clean_expired_cache()` 智能管理（清理已退市股票、除权除息股票缓存）。

### 数据源配置

系统支持三个数据源，优先级顺序为：
1. **东方财富** - 首选数据源（更稳定）
2. **腾讯财经** - 备选数据源
3. **新浪财经** - 最后备选

当某个数据源获取失败时，会自动切换到下一个数据源。

- 最大重试次数：2次
- 重试间隔：30秒（Docker默认，指数退避；裸机部署默认90秒）

## 端口说明

| 端口 | 服务 | 说明 |
|------|------|------|
| 9988 | Web服务 | 股票数据查看界面 |
| 9001 | Supervisor | 进程管理界面 |
| 3306 | MySQL | 数据库（仅本地数据库模式） |

## 常用命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 查看日志
docker-compose logs -f instock

# 重启服务
docker-compose restart instock

# 进入容器
docker exec -it instock-app bash

# 查看运行状态
docker-compose ps
```

## 数据持久化

以下目录会自动持久化：
- `instock_db_data` - MySQL数据
- `instock_logs` - 应用日志
- `instock_cache` - 缓存数据

## 定时任务

系统内置以下定时任务：

| 时间 | 任务 | 说明 |
|------|------|------|
| 每30分钟 (9-15点) | hourly任务 | 交易时段数据更新 |
| 17:30 (工作日) | workdayly任务 | 收盘后数据汇总 |
| 10:30 (周三、六) | monthly任务 | 月度数据统计 |

## 历史数据缓存

### 缓存目录结构
```
/data/InStock/instock/cache/hist/
├── 000/                    # 按股票代码前3位分组
│   ├── 000001.gzip.pickle  # 压缩的缓存数据
│   └── 000001.meta         # 元数据（最后更新日期）
├── 600/
└── ...
```

### 缓存机制
- **增量更新**: 以天为单位追加数据，避免全量获取
- **智能清理**: 自动清理已退市股票、除权除息后需重算的前复权缓存、损坏文件
- **多数据源**: 优先使用东方财富，失败时自动切换腾讯财经/新浪财经

### 配置建议
```bash
# 获取更长历史数据（20年为默认值，可根据需要调整）
HIST_DATA_DEFAULT_YEARS=20
```

### 存储空间估算
| 数据范围 | 压缩后大小 |
|---------|-----------|
| 单只股票3年 | ~30 KB |
| 单只股票10年 | ~80 KB |
| 全部A股3年 | ~150 MB |
| 全部A股10年 | ~400 MB |

## 故障排查

### 1. 数据库连接失败
```bash
# 检查数据库容器状态
docker-compose ps instockdb

# 查看数据库日志
docker-compose logs instockdb
```

### 2. Web服务无法访问
```bash
# 检查服务状态
docker exec -it instock-app supervisorctl status

# 重启Web服务
docker exec -it instock-app supervisorctl restart run_web
```

### 3. 数据获取失败
查看日志确认数据源状态：
```bash
docker-compose logs -f instock | grep -E "新浪|腾讯|东方"
```

## 更新升级

```bash
# 拉取最新代码
git pull

# 重新构建
./build.sh

# 重启服务
docker-compose down
docker-compose up -d
```
