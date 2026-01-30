# InStock 快速入门指南

本文档帮助您快速上手 InStock 股票数据分析系统。

---

## 🚀 五分钟快速开始

### 1. 安装依赖

```bash
# 克隆项目
git clone https://github.com/your-repo/SelectStock.git
cd SelectStock

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置数据库

编辑 `instock/lib/database.py`：

```python
db_host = "localhost"
db_user = "root"
db_password = "your_password"  # 修改为您的MySQL密码
db_database = "instockdb"
```

### 3. 运行数据作业

```bash
cd instock/job
python execute_daily_job.py
```

### 4. 启动Web服务

```bash
cd instock/bin
# Windows:
run_web.bat
# Linux/Mac:
./run_web.sh
```

### 5. 访问系统

打开浏览器访问: http://localhost:9988

---

## 📊 常用操作

### 获取今日股票数据

```bash
cd instock/job
python basic_data_daily_job.py
```

### 计算技术指标

```bash
python indicators_data_daily_job.py
```

### 运行策略选股

```bash
python strategy_data_daily_job.py
```

### 批量处理历史数据

```bash
# 指定日期
python execute_daily_job.py 2024-01-15

# 日期范围
python execute_daily_job.py 2024-01-01 2024-01-31
```

---

## 🐳 Docker 快速部署

```bash
cd docker

# 完整部署（包含MySQL）
docker-compose up -d

# 仅应用（使用外部MySQL）
docker-compose -f docker-compose.remote-db.yml up -d
```

---

## 📁 核心目录说明

| 目录 | 说明 |
|-----|------|
| `instock/job/` | 数据作业脚本 |
| `instock/core/` | 核心业务逻辑 |
| `instock/web/` | Web服务 |
| `instock/config/` | 配置文件 |
| `instock/log/` | 日志文件 |

---

## 🔧 常见问题

### Q: 数据获取失败？

A: 系统已配置多数据源（新浪→腾讯→东方财富），会自动切换。如果仍失败：
1. 检查网络连接
2. 配置代理：编辑 `instock/config/proxy.txt`

### Q: 数据库连接失败？

A: 检查数据库配置和MySQL服务是否运行：
```bash
mysql -u root -p -e "SELECT 1"
```

### Q: 如何更新历史数据？

A: 历史数据采用增量更新机制，只需运行：
```bash
python execute_daily_job.py
```

---

## 📖 更多文档

- [完整项目文档](PROJECT_DOCUMENTATION.md)
- [数据库设计文档](document/database_schema.md)
- [Docker部署说明](docker/DOCKER_DEPLOY.md)
- [历史数据缓存说明](document/hist_cache_incremental.md)
