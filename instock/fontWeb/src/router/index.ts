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
    path: '/selection',
    component: Layout,
    redirect: '/selection/all',
    meta: { title: '综合选股', icon: 'Monitor' },
    children: [
      {
        path: 'all',
        name: 'StockSelection',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '综合选股', tableName: 'cn_stock_selection', isRealtime: false }
      },
      {
        path: 'gpt-value',
        name: 'GptValue',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: 'GPT综合选股', tableName: 'cn_stock_strategy_gpt_value', isRealtime: false }
      },
      {
        path: 'fundamental',
        name: 'FundamentalBuy',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '基本面选股', tableName: 'cn_stock_spot_buy', isRealtime: false }
      }
    ]
  },
  {
    path: '/basic',
    component: Layout,
    redirect: '/basic/spot',
    meta: { title: '股票数据', icon: 'Document' },
    children: [
      {
        path: 'spot',
        name: 'StockSpot',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '每日股票数据', tableName: 'cn_stock_spot', isRealtime: true }
      },
      {
        path: 'etf',
        name: 'ETFSpot',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '每日ETF数据', tableName: 'cn_etf_spot', isRealtime: true }
      },
      {
        path: 'index',
        name: 'IndexSpot',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '每日指数数据', tableName: 'cn_index_spot', isRealtime: true }
      },
      {
        path: 'bonus',
        name: 'StockBonus',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '股票分红配送', tableName: 'cn_stock_bonus', isRealtime: true }
      },
      {
        path: 'lhb',
        name: 'StockLHB',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '股票龙虎榜', tableName: 'cn_stock_lhb', isRealtime: true }
      },
      {
        path: 'blocktrade',
        name: 'BlockTrade',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '股票大宗交易', tableName: 'cn_stock_blocktrade', isRealtime: true }
      },
      {
        path: 'limitup-reason',
        name: 'LimitUpReason',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '涨停原因揭密', tableName: 'cn_stock_limitup_reason', isRealtime: true }
      },
      {
        path: 'chip-race-open',
        name: 'ChipRaceOpen',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '早盘抢筹数据', tableName: 'cn_stock_chip_race_open', isRealtime: true }
      },
      {
        path: 'chip-race-end',
        name: 'ChipRaceEnd',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '尾盘抢筹数据', tableName: 'cn_stock_chip_race_end', isRealtime: false }
      }
    ]
  },
  {
    path: '/fund-flow',
    component: Layout,
    redirect: '/fund-flow/individual',
    meta: { title: '资金流向', icon: 'Money' },
    children: [
      {
        path: 'individual',
        name: 'FundFlow',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '个股资金流向', tableName: 'cn_stock_fund_flow', isRealtime: true }
      },
      {
        path: 'industry',
        name: 'FundFlowIndustry',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '行业资金流向', tableName: 'cn_stock_fund_flow_industry', isRealtime: true }
      },
      {
        path: 'concept',
        name: 'FundFlowConcept',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '概念资金流向', tableName: 'cn_stock_fund_flow_concept', isRealtime: true }
      }
    ]
  },
  {
    path: '/indicator',
    component: Layout,
    redirect: '/indicator/list',
    meta: { title: '技术指标', icon: 'TrendCharts' },
    children: [
      {
        path: 'list',
        name: 'IndicatorList',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '股票指标', tableName: 'cn_stock_indicators', isRealtime: false }
      },
      {
        path: 'buy',
        name: 'IndicatorBuy',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '指标买入信号', tableName: 'cn_stock_indicators_buy', isRealtime: false }
      },
      {
        path: 'sell',
        name: 'IndicatorSell',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '指标卖出信号', tableName: 'cn_stock_indicators_sell', isRealtime: false }
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
        meta: { title: 'K线形态识别', tableName: 'cn_stock_kline_pattern', isRealtime: false }
      }
    ]
  },
  {
    path: '/strategy',
    component: Layout,
    redirect: '/strategy/enter',
    meta: { title: '策略选股', icon: 'Aim' },
    children: [
      {
        path: 'enter',
        name: 'StrategyEnter',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '放量上涨', tableName: 'cn_stock_strategy_enter', isRealtime: false }
      },
      {
        path: 'keep-increasing',
        name: 'StrategyKeepIncreasing',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '均线多头', tableName: 'cn_stock_strategy_keep_increasing', isRealtime: false }
      },
      {
        path: 'parking-apron',
        name: 'StrategyParkingApron',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '停机坪', tableName: 'cn_stock_strategy_parking_apron', isRealtime: false }
      },
      {
        path: 'backtrace-ma250',
        name: 'StrategyBacktraceMa250',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '回踩年线', tableName: 'cn_stock_strategy_backtrace_ma250', isRealtime: false }
      },
      {
        path: 'breakthrough-platform',
        name: 'StrategyBreakthroughPlatform',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '突破平台', tableName: 'cn_stock_strategy_breakthrough_platform', isRealtime: false }
      },
      {
        path: 'low-backtrace-increase',
        name: 'StrategyLowBacktraceIncrease',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '无大幅回撤', tableName: 'cn_stock_strategy_low_backtrace_increase', isRealtime: false }
      },
      {
        path: 'turtle-trade',
        name: 'StrategyTurtleTrade',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '海龟交易法则', tableName: 'cn_stock_strategy_turtle_trade', isRealtime: false }
      },
      {
        path: 'high-tight-flag',
        name: 'StrategyHighTightFlag',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '高而窄的旗形', tableName: 'cn_stock_strategy_high_tight_flag', isRealtime: false }
      },
      {
        path: 'climax-limitdown',
        name: 'StrategyClimaxLimitdown',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '放量跌停', tableName: 'cn_stock_strategy_climax_limitdown', isRealtime: false }
      },
      {
        path: 'low-atr',
        name: 'StrategyLowAtr',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '低ATR成长', tableName: 'cn_stock_strategy_low_atr', isRealtime: false }
      },
      {
        path: 'trend-pullback',
        name: 'StrategyTrendPullback',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '趋势回调', tableName: 'cn_stock_strategy_trend_pullback', isRealtime: false }
      },
      {
        path: 'oversold-rebound',
        name: 'StrategyOversoldRebound',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '超跌反弹', tableName: 'cn_stock_strategy_oversold_rebound', isRealtime: false }
      },
      {
        path: 'breakout-confirm',
        name: 'StrategyBreakoutConfirm',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '突破确认', tableName: 'cn_stock_strategy_breakout_confirm', isRealtime: false }
      }
    ]
  },
  {
    path: '/config',
    component: Layout,
    redirect: '/config/strategy',
    meta: { title: '参数配置', icon: 'Setting' },
    children: [
      {
        path: 'strategy',
        name: 'StrategyConfig',
        component: () => import('@/views/strategy/StrategyConfig.vue'),
        meta: { title: '策略参数配置', icon: 'Operation', defaultStrategy: 'gpt_value' }
      },
      {
        path: 'ai-model',
        name: 'AIModelConfig',
        component: () => import('@/views/strategy/StrategyConfig.vue'),
        meta: { title: 'AI模型设置', icon: 'Cpu', defaultStrategy: 'ai_model' }
      }
    ]
  },
  {
    path: '/algo',
    component: Layout,
    redirect: '/algo/list',
    meta: { title: '策略回测', icon: 'DataLine' },
    children: [
      {
        path: 'list',
        name: 'AlgoList',
        component: () => import('@/views/algo/list.vue'),
        meta: { title: '策略列表' }
      },
      {
        path: 'edit/:id',
        name: 'AlgoEdit',
        component: () => import('@/views/algo/edit.vue'),
        meta: { title: '策略编辑', hidden: true }
      },
      {
        path: 'backtests',
        name: 'BacktestHistory',
        component: () => import('@/views/algo/backtest-list.vue'),
        meta: { title: '回测列表' }
      },
      {
        path: 'backtest-detail/:id',
        name: 'BacktestDetail',
        component: () => import('@/views/algo/backtest-detail.vue'),
        meta: { title: '回测详情', hidden: true }
      },
      {
        path: 'backtest-compare',
        name: 'BacktestCompare',
        component: () => import('@/views/algo/backtest-compare.vue'),
        meta: { title: '回测对比', hidden: true }
      },
      {
        path: 'paper',
        name: 'PaperTrading',
        component: () => import('@/views/paper-trading/index.vue'),
        meta: { title: '模拟交易' }
      }
    ]
  },
  {
    path: '/backtest',
    component: Layout,
    redirect: '/backtest/custom',
    meta: { title: '选股验证', icon: 'DataAnalysis' },
    children: [
      {
        path: 'dashboard',
        name: 'BacktestDashboard',
        component: () => import('@/views/backtest/dashboard.vue'),
        meta: { title: '回测看板' }
      },
      {
        path: 'custom',
        name: 'BacktestCustom',
        component: () => import('@/views/backtest/index.vue'),
        meta: { title: '自定义回测' }
      },
      {
        path: 'list',
        name: 'BacktestList',
        component: () => import('@/views/stock/StockData.vue'),
        meta: { title: '回测汇总', tableName: 'cn_stock_backtest', isRealtime: false, noDateFilter: true }
      }
    ]
  },
  // 兼容旧版 /stock/ 前缀路径：自动去掉前缀并重定向到正确路由
  // 例如 /stock/selection → /selection, /stock/basic/spot → /basic/spot
  {
    path: '/stock/:pathMatch(.*)*',
    redirect: (to) => {
      const rest = to.path.replace(/^\/stock\/?/, '')
      return `/${rest}`
    },
    meta: { hidden: true }
  },
  // 404 catch-all：放在最后，匹配所有未定义路径
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: Layout,
    meta: { hidden: true },
    children: [
      {
        path: '',
        component: () => import('@/views/error/NotFound.vue'),
        meta: { title: '页面不存在', hidden: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
