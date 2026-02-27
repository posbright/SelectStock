import request from './request'

export interface StockDataParams {
  name: string
  date?: string
  page?: number
  page_size?: number
  keyword?: string
}

export interface StockIndicatorParams {
  code: string
  date: string
  name?: string
}

export interface AttentionParams {
  code: string
  otype: '0' | '1'  // 0: 添加关注, 1: 取消关注
}

/**
 * 获取股票数据列表
 * @param params 
 */
export function getStockData(params: StockDataParams) {
  return request({
    url: '/api_data',
    method: 'get',
    params
  })
}

/**
 * 获取股票指标详情
 * @param params 
 */
export function getStockIndicators(params: StockIndicatorParams) {
  return request({
    url: '/data/indicators',
    method: 'get',
    params
  })
}

/**
 * 添加/取消关注股票
 * @param params 
 */
export function toggleAttention(params: AttentionParams) {
  return request({
    url: '/control/attention',
    method: 'get',
    params
  })
}

/**
 * 获取最近交易日期
 * 返回 { run_date: 'YYYY-MM-DD', run_date_nph: 'YYYY-MM-DD' }
 * run_date: 最近已收盘的交易日
 * run_date_nph: 当前交易日（含未收盘）
 */
export function getTradeDate() {
  return request({
    url: '/api/trade_date',
    method: 'get'
  })
}

// ============= 回测相关 API =============

export interface BacktestParams {
  code?: string
  strategy?: string
  period?: string
  start_date?: string
  end_date?: string
  /** 回测输出点（逗号分隔，如 1,3,5,10,20） */
  checkpoints?: string
}

export interface BatchBacktestParams {
  strategy: string
  period?: string
  limit?: number
  /** 批量汇总使用的持有天数列表（逗号分隔，如 1,3,5,10,20） */
  horizons?: string
  /** 成功定义使用的持有天数（对应 rate_N > 0） */
  success_days?: number
}

/** 获取回测配置（可选周期、策略列表） */
export function getBacktestConfig() {
  return request({ url: '/api/backtest/config', method: 'get' })
}

/** 执行单只股票回测 */
export function runBacktest(params: BacktestParams) {
  return request({ url: '/api/backtest/run', method: 'get', params })
}

/** 批量回测（策略历史验证） */
export function runBatchBacktest(params: BatchBacktestParams) {
  return request({ url: '/api/backtest/batch', method: 'get', params })
}

// ============= 回测看板 API =============

export interface DashboardOverviewParams {
  days?: number
  metric?: number
  start_date?: string
  end_date?: string
}

export function getBacktestDashboardOverview(params: DashboardOverviewParams) {
  return request({ url: '/api/backtest/dashboard/overview', method: 'get', params })
}

export interface DashboardTimelineParams {
  strategies?: string
  days?: number
  horizon?: number
  start_date?: string
  end_date?: string
}

export function getBacktestDashboardTimeline(params: DashboardTimelineParams) {
  return request({ url: '/api/backtest/dashboard/timeline', method: 'get', params })
}

export interface DashboardStrategyDetailParams {
  strategy: string
  days?: number
  horizons?: string
  page?: number
  page_size?: number
  start_date?: string
  end_date?: string
}

export function getBacktestDashboardStrategyDetail(params: DashboardStrategyDetailParams) {
  return request({ url: '/api/backtest/dashboard/strategy_detail', method: 'get', params })
}

export interface DashboardDistributionParams {
  strategy: string
  days?: number
  horizon?: number
  start_date?: string
  end_date?: string
}

export function getBacktestDashboardDistribution(params: DashboardDistributionParams) {
  return request({ url: '/api/backtest/dashboard/distribution', method: 'get', params })
}

export interface DashboardTradePairsParams {
  strategy: string
  days?: number
  page?: number
  page_size?: number
  max_hold?: number
  start_date?: string
  end_date?: string
}

export function getBacktestDashboardTradePairs(params: DashboardTradePairsParams) {
  return request({ url: '/api/backtest/dashboard/trade_pairs', method: 'get', params })
}

// ============= K线数据 API =============

export interface KlineParams {
  code: string
  date?: string
  period?: string   // daily / weekly / monthly / quarterly / yearly
  days?: number
  name?: string
}

/** 获取K线数据（含技术指标：MA/BOLL/RSI/MACD） */
export function getKlineData(params: KlineParams) {
  return request({ url: '/api/kline', method: 'get', params })
}
