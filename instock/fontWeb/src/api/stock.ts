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
 * 获取股票指标详情（备用：通过后端 HTML 接口获取指标数据）
 * 注意：当前前端使用 getKlineData + indicator/index.vue 渲染指标详情，
 * 此函数保留以兼容未来可能的 JSON 格式指标 API。
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

// ============= 组合回测 & 策略管理 API =============

/** 获取内置策略模板 */
export function getStrategyTemplates() {
  return request({ url: '/api/strategy/templates', method: 'get' })
}

/** 获取策略列表 */
export function getStrategyCodeList() {
  return request({ url: '/api/strategy/code/list', method: 'get' })
}

/** 获取策略详情 */
export function getStrategyCodeDetail(id: number) {
  return request({ url: '/api/strategy/code/detail', method: 'get', params: { id } })
}

/** 保存策略代码 */
export function saveStrategyCode(data: {
  id?: number
  name: string
  code: string
  description?: string
  initial_cash?: number
  benchmark?: string
  commission_rate?: number
  stamp_tax_rate?: number
  slippage?: number
}) {
  return request({ url: '/api/strategy/code', method: 'post', data })
}

/** 删除策略 */
export function deleteStrategyCode(id: number) {
  return request({ url: '/api/strategy/code/delete', method: 'post', data: { id } })
}

/** 运行组合回测 */
export function runPortfolioBacktest(data: {
  code: string
  start_date: string
  end_date: string
  initial_cash?: number
  benchmark?: string
  commission_rate?: number
  stamp_tax_rate?: number
  slippage?: number
}) {
  return request({ url: '/api/backtest/portfolio/run', method: 'post', data })
}

/** 获取回测历史列表 */
export function getPortfolioBacktestList() {
  return request({ url: '/api/backtest/portfolio/list', method: 'get' })
}

// ============= 模拟交易 API =============

/** 创建模拟盘 */
export function createPaperTrading(data: { strategy_id: number; name?: string; initial_cash?: number }) {
  return request({ url: '/api/paper/create', method: 'post', data })
}

/** 模拟盘操作（暂停/恢复/停止） */
export function paperTradingAction(data: { id: number; action: 'pause' | 'resume' | 'stop' }) {
  return request({ url: '/api/paper/action', method: 'post', data })
}

/** 获取模拟盘列表 */
export function getPaperTradingList() {
  return request({ url: '/api/paper/list', method: 'get' })
}

/** 获取模拟盘详情 */
export function getPaperTradingDetail(id: number) {
  return request({ url: '/api/paper/detail', method: 'get', params: { id } })
}

/** 手动触发模拟盘执行 */
export function runPaperTrading(id: number) {
  return request({ url: '/api/paper/run', method: 'post', data: { id } })
}
