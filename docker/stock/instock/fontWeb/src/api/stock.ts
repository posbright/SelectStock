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
