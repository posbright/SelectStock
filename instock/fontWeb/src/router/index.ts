import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import Layout from '@/layout/index.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: Layout,
    redirect: '/home',
    children: [
      {
        path: 'home',
        name: 'Home',
        component: () => import('@/views/home/index.vue'),
        meta: { title: '首页', icon: 'HomeFilled' }
      }
    ]
  },
  {
    path: '/stock',
    component: Layout,
    redirect: '/stock/selection',
    meta: { title: '综合选股', icon: 'Monitor' },
    children: [
      {
        path: 'selection',
        name: 'StockSelection',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '综合选股', tableName: 'cn_stock_selection' }
      }
    ]
  },
  {
    path: '/basic',
    component: Layout,
    redirect: '/basic/spot',
    meta: { title: '股票基本数据', icon: 'Document' },
    children: [
      {
        path: 'spot',
        name: 'StockSpot',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '每日股票数据', tableName: 'cn_stock_spot' }
      },
      {
        path: 'fund-flow',
        name: 'FundFlow',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '股票资金流向', tableName: 'cn_stock_fund_flow' }
      },
      {
        path: 'bonus',
        name: 'StockBonus',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '股票分红配送', tableName: 'cn_stock_bonus' }
      },
      {
        path: 'lhb',
        name: 'StockLHB',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '股票龙虎榜', tableName: 'cn_stock_lhb' }
      },
      {
        path: 'blocktrade',
        name: 'BlockTrade',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '股票大宗交易', tableName: 'cn_stock_blocktrade' }
      },
      {
        path: 'limitup-reason',
        name: 'LimitUpReason',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '涨停原因揭密', tableName: 'cn_stock_limitup_reason' }
      },
      {
        path: 'chip-race-open',
        name: 'ChipRaceOpen',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '早盘抢筹数据', tableName: 'cn_stock_chip_race_open' }
      },
      {
        path: 'chip-race-end',
        name: 'ChipRaceEnd',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '尾盘抢筹数据', tableName: 'cn_stock_chip_race_end' }
      },
      {
        path: 'fund-flow-industry',
        name: 'FundFlowIndustry',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '行业资金流向', tableName: 'cn_stock_fund_flow_industry' }
      },
      {
        path: 'fund-flow-concept',
        name: 'FundFlowConcept',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '概念资金流向', tableName: 'cn_stock_fund_flow_concept' }
      },
      {
        path: 'etf',
        name: 'ETFSpot',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '每日ETF数据', tableName: 'cn_etf_spot' }
      }
    ]
  },
  {
    path: '/indicator',
    component: Layout,
    redirect: '/indicator/list',
    meta: { title: '股票指标数据', icon: 'TrendCharts' },
    children: [
      {
        path: 'list',
        name: 'IndicatorList',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '股票指标', tableName: 'cn_stock_indicators' }
      },
      {
        path: 'buy',
        name: 'IndicatorBuy',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '指标买入', tableName: 'cn_stock_indicators_buy' }
      },
      {
        path: 'sell',
        name: 'IndicatorSell',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '指标卖出', tableName: 'cn_stock_indicators_sell' }
      },
      {
        path: 'detail',
        name: 'IndicatorDetail',
        component: () => import('@/views/indicator/index.vue'),
        meta: { title: '指标详情', hidden: true }
      }
    ]
  },
  {
    path: '/kline',
    component: Layout,
    redirect: '/kline/pattern',
    meta: { title: 'K线形态', icon: 'PriceTag' },
    children: [
      {
        path: 'pattern',
        name: 'KlinePattern',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: 'K线形态识别', tableName: 'cn_stock_kline_pattern' }
      }
    ]
  },
  {
    path: '/strategy',
    component: Layout,
    redirect: '/strategy/list',
    meta: { title: '策略选股', icon: 'Aim' },
    children: [
      {
        path: 'enter',
        name: 'StrategyEnter',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '放量上涨', tableName: 'cn_stock_strategy_enter' }
      },
      {
        path: 'keep-increasing',
        name: 'StrategyKeepIncreasing',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '均线多头', tableName: 'cn_stock_strategy_keep_increasing' }
      },
      {
        path: 'parking-apron',
        name: 'StrategyParkingApron',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '停机坪', tableName: 'cn_stock_strategy_parking_apron' }
      },
      {
        path: 'backtrace-ma250',
        name: 'StrategyBacktraceMa250',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '回踩年线', tableName: 'cn_stock_strategy_backtrace_ma250' }
      },
      {
        path: 'breakthrough-platform',
        name: 'StrategyBreakthroughPlatform',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '突破平台', tableName: 'cn_stock_strategy_breakthrough_platform' }
      },
      {
        path: 'low-backtrace-increase',
        name: 'StrategyLowBacktraceIncrease',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '无大幅回撤', tableName: 'cn_stock_strategy_low_backtrace_increase' }
      },
      {
        path: 'turtle-trade',
        name: 'StrategyTurtleTrade',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '海龟交易法则', tableName: 'cn_stock_strategy_turtle_trade' }
      },
      {
        path: 'high-tight-flag',
        name: 'StrategyHighTightFlag',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '高而窄的旗形', tableName: 'cn_stock_strategy_high_tight_flag' }
      },
      {
        path: 'climax-limitdown',
        name: 'StrategyClimaxLimitdown',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '放量跌停', tableName: 'cn_stock_strategy_climax_limitdown' }
      },
      {
        path: 'low-atr',
        name: 'StrategyLowAtr',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '低ATR成长', tableName: 'cn_stock_strategy_low_atr' }
      }
    ]
  },
  {
    path: '/backtest',
    component: Layout,
    redirect: '/backtest/list',
    meta: { title: '选股验证', icon: 'DataAnalysis' },
    children: [
      {
        path: 'list',
        name: 'BacktestList',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '回测验证', tableName: 'cn_stock_backtest' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
