// 股票数据类型定义

export interface StockSpot {
  date: string
  code: string
  name: string
  new_price: number
  change_rate: number
  change_amount: number
  volume: number
  deal_amount: number
  amplitude: number
  high: number
  low: number
  open: number
  close: number
  turnover: number
  cdatetime?: string  // 关注时间，有值表示已关注
}

export interface StockIndicator {
  date: string
  code: string
  name: string
  macd: number
  macd_dea: number
  macd_dif: number
  kdj_k: number
  kdj_d: number
  kdj_j: number
  rsi_6: number
  rsi_12: number
  rsi_24: number
  boll_upper: number
  boll_mid: number
  boll_lower: number
  cci: number
  wr_6: number
  wr_10: number
  // ... 更多指标
}

export interface KlineData {
  date: string
  open: number
  close: number
  high: number
  low: number
  volume: number
  amount?: number
}

export interface KlinePattern {
  date: string
  code: string
  name: string
  pattern_name: string
  pattern_value: number  // 正: 买入信号, 负: 卖出信号, 0: 无信号
}

export interface StrategyResult {
  date: string
  code: string
  name: string
  strategy_name: string
  // ... 策略相关字段
}

export interface BacktestResult {
  date: string
  code: string
  name: string
  buy_date: string
  sell_date: string
  profit_rate: number
  success: boolean
}
