# InStock API 接口文档

本文档描述 InStock 系统提供的 Web API 接口。

---

## 基础信息

- **Base URL**: `http://localhost:9988`
- **响应格式**: JSON / HTML
- **端口**: 9988

---

## 接口列表

### 1. 首页

#### 请求

```
GET /instock/
```

#### 响应

返回系统首页 HTML 页面。

---

### 2. 获取数据表数据 (API)

#### 请求

```
GET /instock/api_data
```

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| table_name | string | 是 | 数据表名称 |
| date | string | 否 | 日期 (YYYY-MM-DD) |
| columns | string | 否 | 指定返回列 |
| order | string | 否 | 排序字段 |
| search | string | 否 | 搜索关键字 |
| start | int | 否 | 分页起始位置 |
| length | int | 否 | 每页数量 |

#### 支持的表名

| table_name | 说明 |
|-----------|------|
| cn_stock_spot | 每日股票数据 |
| cn_etf_spot | 每日ETF数据 |
| cn_stock_fund_flow | 股票资金流向 |
| cn_stock_fund_flow_industry | 行业资金流向 |
| cn_stock_fund_flow_concept | 概念资金流向 |
| cn_stock_bonus | 股票分红配送 |
| cn_stock_top | 股票龙虎榜(新浪) |
| cn_stock_lhb | 股票龙虎榜 |
| cn_stock_blocktrade | 股票大宗交易 |
| cn_stock_spot_buy | 基本面选股 |
| cn_stock_indicators | 股票指标数据 |
| cn_stock_strategy_* | 策略选股结果 |
| cn_stock_kline_pattern_* | K线形态识别 |

#### 响应示例

```json
{
    "draw": 1,
    "recordsTotal": 5000,
    "recordsFiltered": 5000,
    "data": [
        {
            "date": "2024-01-15",
            "code": "000001",
            "name": "平安银行",
            "new_price": 10.50,
            "change_rate": 1.25,
            ...
        }
    ]
}
```

---

### 3. 获取数据表页面 (HTML)

#### 请求

```
GET /instock/data
```

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| table_name | string | 是 | 数据表名称 |
| date | string | 否 | 日期 (YYYY-MM-DD) |

#### 响应

返回带有 DataTables 的 HTML 页面。

---

### 4. 获取股票指标图表

#### 请求

```
GET /instock/data/indicators
```

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| code | string | 是 | 股票代码 (如: 000001) |
| date | string | 否 | 日期 (YYYY-MM-DD) |
| type | string | 否 | 图表类型 |

#### 响应

返回包含 K线图、指标图、筹码分布图的 HTML 页面。

#### 图表内容

- K线图（日K线）
- 成交量图
- MACD 指标
- KDJ 指标
- RSI 指标
- BOLL 指标
- 筹码分布图

---

### 5. 添加/删除关注

#### 请求

```
POST /instock/control/attention
```

#### 请求体

```json
{
    "code": "000001",
    "action": "add"  // 或 "remove"
}
```

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| code | string | 是 | 股票代码 |
| action | string | 是 | 操作类型: add(添加) / remove(删除) |

#### 响应

```json
{
    "status": "success",
    "message": "关注添加成功"
}
```

---

## 数据表字段说明

### cn_stock_spot (每日股票数据)

| 字段 | 类型 | 说明 |
|-----|------|------|
| date | DATE | 日期 |
| code | VARCHAR(6) | 股票代码 |
| name | VARCHAR(20) | 股票名称 |
| new_price | FLOAT | 最新价 |
| change_rate | FLOAT | 涨跌幅(%) |
| ups_downs | FLOAT | 涨跌额 |
| volume | BIGINT | 成交量(股) |
| deal_amount | BIGINT | 成交额(元) |
| amplitude | FLOAT | 振幅(%) |
| turnoverrate | FLOAT | 换手率(%) |
| volume_ratio | FLOAT | 量比 |
| open_price | FLOAT | 今开 |
| high_price | FLOAT | 最高 |
| low_price | FLOAT | 最低 |
| pre_close_price | FLOAT | 昨收 |
| pe | FLOAT | 市盈率(静) |
| pbnewmrq | FLOAT | 市净率 |
| total_market_cap | BIGINT | 总市值 |
| free_cap | BIGINT | 流通市值 |
| industry | VARCHAR(20) | 所属行业 |

### cn_stock_indicators (技术指标数据)

| 字段 | 类型 | 说明 |
|-----|------|------|
| date | DATE | 日期 |
| code | VARCHAR(6) | 股票代码 |
| macd | FLOAT | MACD值 |
| macds | FLOAT | MACD信号线 |
| macdh | FLOAT | MACD柱 |
| kdjk | FLOAT | KDJ-K值 |
| kdjd | FLOAT | KDJ-D值 |
| kdjj | FLOAT | KDJ-J值 |
| rsi | FLOAT | RSI(14) |
| rsi_6 | FLOAT | RSI(6) |
| boll | FLOAT | BOLL中轨 |
| boll_ub | FLOAT | BOLL上轨 |
| boll_lb | FLOAT | BOLL下轨 |
| cr | FLOAT | CR指标 |
| wr | FLOAT | 威廉指标 |
| cci | FLOAT | CCI指标 |
| atr | FLOAT | ATR指标 |
| pdi | FLOAT | +DI |
| mdi | FLOAT | -DI |
| adx | FLOAT | ADX |

---

## 错误处理

### 错误响应格式

```json
{
    "error": true,
    "message": "错误描述信息"
}
```

### 常见错误码

| 错误 | 说明 |
|-----|------|
| 400 | 参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 使用示例

### Python 示例

```python
import requests

# 获取股票数据
response = requests.get(
    'http://localhost:9988/instock/api_data',
    params={
        'table_name': 'cn_stock_spot',
        'date': '2024-01-15',
        'length': 100
    }
)
data = response.json()
print(f"获取到 {len(data['data'])} 条数据")

# 添加关注
response = requests.post(
    'http://localhost:9988/instock/control/attention',
    json={'code': '000001', 'action': 'add'}
)
print(response.json())
```

### JavaScript 示例

```javascript
// 获取股票数据
fetch('/instock/api_data?table_name=cn_stock_spot&date=2024-01-15')
    .then(response => response.json())
    .then(data => {
        console.log(`获取到 ${data.data.length} 条数据`);
    });

// 添加关注
fetch('/instock/control/attention', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({code: '000001', action: 'add'})
})
    .then(response => response.json())
    .then(data => console.log(data));
```

### cURL 示例

```bash
# 获取股票数据
curl "http://localhost:9988/instock/api_data?table_name=cn_stock_spot&date=2024-01-15"

# 添加关注
curl -X POST "http://localhost:9988/instock/control/attention" \
    -H "Content-Type: application/json" \
    -d '{"code":"000001","action":"add"}'
```

---

## 注意事项

1. 所有日期参数格式为 `YYYY-MM-DD`
2. 股票代码为6位数字字符串
3. API 返回数据量较大时建议使用分页
4. 关注功能需要先运行数据作业创建相关表
