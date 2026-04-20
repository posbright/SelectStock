<template>
  <div class="bt-detail" v-loading="loading">
    <!-- ── Header ── -->
    <div class="detail-header">
      <el-button text @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
      <h3>回测详情 #{{ btId }}</h3>
      <span class="header-sub" v-if="info">
        {{ info.strategy_name }} &nbsp;|&nbsp; {{ info.start_date }} ~ {{ info.end_date }}
        &nbsp;|&nbsp; 初始资金 {{ Number(info.initial_cash || 0).toLocaleString() }} 元
      </span>
    </div>

    <!-- ═══════════  收益概述（聚宽双列表格风格）═══════════ -->
    <div class="jq-summary" v-if="info?.metrics">
      <table class="jq-table">
        <tbody>
          <tr>
            <td class="jq-lbl">策略收益</td>
            <td class="jq-val" :class="pctCls(M.total_return)">{{ fmtPct(M.total_return) }}</td>
            <td class="jq-lbl">策略年化收益</td>
            <td class="jq-val" :class="pctCls(M.annual_return)">{{ fmtPct(M.annual_return) }}</td>
            <td class="jq-lbl">超额收益</td>
            <td class="jq-val" :class="pctCls(M.excess_return)">{{ fmtPct(M.excess_return) }}</td>
          </tr>
          <tr>
            <td class="jq-lbl">基准收益</td>
            <td class="jq-val" :class="pctCls(M.benchmark_return)">{{ fmtPct(M.benchmark_return) }}</td>
            <td class="jq-lbl">阿尔法</td>
            <td class="jq-val">{{ fmtNum(M.alpha) }}</td>
            <td class="jq-lbl">贝塔</td>
            <td class="jq-val">{{ fmtNum(M.beta) }}</td>
          </tr>
          <tr>
            <td class="jq-lbl">夏普比率</td>
            <td class="jq-val">{{ fmtNum(M.sharpe_ratio) }}</td>
            <td class="jq-lbl">索提诺比率</td>
            <td class="jq-val">{{ fmtNum(M.sortino_ratio) }}</td>
            <td class="jq-lbl">信息比率</td>
            <td class="jq-val">{{ fmtNum(M.information_ratio) }}</td>
          </tr>
          <tr>
            <td class="jq-lbl">胜率</td>
            <td class="jq-val">{{ fmtPct(M.trade_win_rate, 1) }}</td>
            <td class="jq-lbl">盈亏比</td>
            <td class="jq-val">{{ fmtNum(M.profit_loss_ratio) }}</td>
            <td class="jq-lbl">最大回撤</td>
            <td class="jq-val val-green">{{ fmtPct(M.max_drawdown) }}</td>
          </tr>
          <tr>
            <td class="jq-lbl">日胜率</td>
            <td class="jq-val">{{ fmtPct(M.daily_win_rate, 1) }}</td>
            <td class="jq-lbl">盈利次数</td>
            <td class="jq-val val-red">{{ M.win_count ?? 0 }}</td>
            <td class="jq-lbl">亏损次数</td>
            <td class="jq-val val-green">{{ M.loss_count ?? 0 }}</td>
          </tr>
          <tr>
            <td class="jq-lbl">日均超额收益</td>
            <td class="jq-val" :class="pctCls(M.avg_daily_excess)">{{ fmtPct(M.avg_daily_excess, 3) }}</td>
            <td class="jq-lbl">超额收益最大回撤</td>
            <td class="jq-val val-green">{{ fmtPct(M.excess_max_drawdown) }}</td>
            <td class="jq-lbl">超额收益夏普比率</td>
            <td class="jq-val">{{ fmtNum(M.excess_sharpe_ratio) }}</td>
          </tr>
          <tr>
            <td class="jq-lbl">策略波动率</td>
            <td class="jq-val">{{ fmtPct(M.strategy_volatility) }}</td>
            <td class="jq-lbl">基准波动率</td>
            <td class="jq-val">{{ fmtPct(M.benchmark_volatility) }}</td>
            <td class="jq-lbl">最大回撤区间</td>
            <td class="jq-val jq-val-sm">{{ ddRange }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ═══════════  Tabs ═══════════ -->
    <el-tabs v-model="activeTab">

      <!-- Tab 1: 收益走势（累计收益 + 超额） -->
      <el-tab-pane label="收益走势" name="overview">
        <div ref="chartEl" class="chart-box"></div>
      </el-tab-pane>

      <!-- Tab 2: 每日盈亏 -->
      <el-tab-pane label="每日盈亏" name="daily_pnl">
        <div ref="pnlChartEl" class="chart-box"></div>
        <el-table :data="dailyPnlData" size="small" max-height="480" stripe style="margin-top: 8px">
          <el-table-column prop="date" label="日期" width="100" />
          <el-table-column label="策略净值" width="95" align="right">
            <template #default="{ row }">{{ N(row.nav).toFixed(4) }}</template>
          </el-table-column>
          <el-table-column label="基准净值" width="95" align="right">
            <template #default="{ row }">{{ N(row.benchmark_nav).toFixed(4) }}</template>
          </el-table-column>
          <el-table-column label="策略日收益" width="100" align="right">
            <template #default="{ row }">
              <span :class="pctCls(row.daily_return)">{{ ((row.daily_return ?? 0) * 100).toFixed(2) }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="基准日收益" width="100" align="right">
            <template #default="{ row }">
              <span :class="pctCls(row.benchmark_return)">{{ ((row.benchmark_return ?? 0) * 100).toFixed(2) }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="累计收益" width="100" align="right">
            <template #default="{ row }">
              <span :class="pctCls((row.nav ?? 1) - 1)">{{ (((row.nav ?? 1) - 1) * 100).toFixed(2) }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="总资产" width="130" align="right">
            <template #default="{ row }">{{ N(row.total_value).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}</template>
          </el-table-column>
          <el-table-column label="现金" width="130" align="right">
            <template #default="{ row }">{{ N(row.cash).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}</template>
          </el-table-column>
          <el-table-column label="持仓市值" width="130" align="right">
            <template #default="{ row }">{{ N(row.market_value).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Tab 3: 每日买卖 -->
      <el-tab-pane :label="'每日买卖(' + (info?.trades?.length || 0) + ')'" name="trades">
        <div ref="tradeChartEl" class="chart-box"></div>
        <el-table :data="info?.trades || []" size="small" max-height="480" stripe style="margin-top: 8px">
          <el-table-column prop="date" label="日期" width="100" />
          <el-table-column prop="code" label="代码" width="75" />
          <el-table-column prop="name" label="名称" width="85" show-overflow-tooltip />
          <el-table-column prop="direction" label="方向" width="55">
            <template #default="{ row }">
              <span :style="{ color: row.direction === 'buy' ? '#f56c6c' : '#67c23a', fontWeight: 600 }">
                {{ row.direction === 'buy' ? '买入' : '卖出' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="成交价" width="85" align="right">
            <template #default="{ row }">{{ N(row.price).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="数量(股)" width="90" align="right">
            <template #default="{ row }">{{ N(row.amount).toLocaleString() }}</template>
          </el-table-column>
          <el-table-column label="成交金额" width="110" align="right">
            <template #default="{ row }">{{ N(row.value || row.price * row.amount).toLocaleString('zh-CN', { maximumFractionDigits: 0 }) }}</template>
          </el-table-column>
          <el-table-column label="佣金" width="75" align="right">
            <template #default="{ row }">{{ N(row.commission || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="印花税" width="75" align="right">
            <template #default="{ row }">{{ N(row.tax || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="滑点" width="75" align="right">
            <template #default="{ row }">{{ N(row.slippage_cost || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="平仓盈亏" width="110" align="right">
            <template #default="{ row }">
              <span v-if="row.direction === 'sell'" :class="pctCls(row.close_profit)">
                {{ (row.close_profit ?? 0) >= 0 ? '+' : '' }}{{ N(row.close_profit || 0).toFixed(2) }}
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="收益率" width="85" align="right">
            <template #default="{ row }">
              <span v-if="row.direction === 'sell'" :class="pctCls(row.return_rate)">
                {{ (row.return_rate ?? 0) >= 0 ? '+' : '' }}{{ N(row.return_rate || 0).toFixed(2) }}%
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Tab 4: 每日持仓 -->
      <el-tab-pane label="每日持仓" name="positions">
        <div style="margin-bottom: 10px" v-if="info?.positions?.length">
          <el-select v-model="selectedPosDate" size="small" style="width: 160px" placeholder="选择日期">
            <el-option v-for="p in info.positions" :key="p.date" :label="p.date" :value="p.date" />
          </el-select>
        </div>
        <el-table :data="selectedPositions" size="small" max-height="600" stripe>
          <el-table-column prop="code" label="代码" width="75" />
          <el-table-column prop="name" label="名称" width="85" show-overflow-tooltip />
          <el-table-column label="持仓(股)" width="90" align="right">
            <template #default="{ row }">{{ N(row.amount).toLocaleString() }}</template>
          </el-table-column>
          <el-table-column label="成本价" width="85" align="right">
            <template #default="{ row }">{{ N(row.avg_cost).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="现价" width="85" align="right">
            <template #default="{ row }">{{ N(row.price).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="市值" width="110" align="right">
            <template #default="{ row }">{{ N(row.value).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}</template>
          </el-table-column>
          <el-table-column label="盈亏" width="100" align="right">
            <template #default="{ row }">
              <span :class="pctCls(row.profit)">{{ (row.profit ?? 0) >= 0 ? '+' : '' }}{{ N(row.profit ?? 0).toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="盈亏比例" width="90" align="right">
            <template #default="{ row }">
              <span :class="pctCls(row.profit_rate)">{{ (row.profit_rate ?? 0) >= 0 ? '+' : '' }}{{ N(row.profit_rate ?? 0).toFixed(2) }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="仓位占比" width="90" align="right">
            <template #default="{ row }">{{ N(row.weight).toFixed(1) }}%</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Tab 5: 运行日志 -->
      <el-tab-pane :label="'日志(' + (info?.logs?.length || 0) + ')'" name="logs">
        <div class="log-box">
          <div v-for="(l, i) in (info?.logs || []).slice(-300)" :key="i" class="log-line">{{ l }}</div>
          <div v-if="!info?.logs?.length" class="log-empty">暂无日志</div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, onActivated, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getPortfolioBacktestDetail } from '@/api/stock'
import * as echarts from 'echarts'

const route = useRoute()
const btId = computed(() => Number(route.params.id))
const info = ref<any>(null)
const loading = ref(false)
const activeTab = ref('overview')
const selectedPosDate = ref('')
let lastLoadedId = 0   // 记录上次加载的回测ID，用于 keep-alive 激活时判断是否需要重新加载

const chartEl = ref<HTMLElement>()
const pnlChartEl = ref<HTMLElement>()
const tradeChartEl = ref<HTMLElement>()
let chart: echarts.ECharts | null = null
let pnlChart: echarts.ECharts | null = null
let tradeChart: echarts.ECharts | null = null

// ── shortcuts ──
const N = Number
const M = computed(() => info.value?.metrics || {})

function fmtPct(v: number | undefined, digits = 2) {
  if (v == null) return '--'
  return `${v >= 0 ? '+' : ''}${N(v).toFixed(digits)}%`
}
function fmtNum(v: number | undefined, digits = 3) {
  if (v == null) return '--'
  return N(v).toFixed(digits)
}
function pctCls(v: number | undefined) {
  if (v == null || v === 0) return ''
  return v > 0 ? 'val-red' : 'val-green'
}

const ddRange = computed(() => {
  const m = M.value
  return (m.max_drawdown_start && m.max_drawdown_end)
    ? `${m.max_drawdown_start} ~ ${m.max_drawdown_end}` : '--'
})

const dailyPnlData = computed(() => info.value?.nav || [])

const selectedPositions = computed(() => {
  const pos = info.value?.positions
  if (!pos || pos.length === 0) return []
  if (!selectedPosDate.value) return pos[pos.length - 1].positions || []
  const found = pos.find((p: any) => p.date === selectedPosDate.value)
  return found ? found.positions : []
})

// ── lifecycle ──

/** 清理所有图表实例 */
function disposeAllCharts() {
  chart?.dispose(); chart = null
  pnlChart?.dispose(); pnlChart = null
  tradeChart?.dispose(); tradeChart = null
}

/** 加载回测详情数据 */
async function loadDetail() {
  const id = btId.value
  if (!id) return
  // 清理旧状态
  disposeAllCharts()
  info.value = null
  activeTab.value = 'overview'
  selectedPosDate.value = ''

  loading.value = true
  try {
    const res = await getPortfolioBacktestDetail(id) as any
    info.value = res?.code === 0 ? res.data : res?.data
    if (info.value?.positions?.length) {
      selectedPosDate.value = info.value.positions[info.value.positions.length - 1].date
    }
    lastLoadedId = id
    await nextTick()
    safeRender('overview')
  } finally {
    loading.value = false
  }
}

onMounted(() => loadDetail())

// keep-alive 激活时，检查路由参数是否变化，如有变化则重新加载
onActivated(() => {
  const id = btId.value
  if (id && id !== lastLoadedId) {
    loadDetail()
  }
})

// 同一组件激活期间，路由 :id 参数发生变化时也重新加载
watch(btId, (newId, oldId) => {
  if (newId && newId !== oldId && newId !== lastLoadedId) {
    loadDetail()
  }
})

const onResize = () => { chart?.resize(); pnlChart?.resize(); tradeChart?.resize() }
window.addEventListener('resize', onResize)
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  disposeAllCharts()
})

watch(activeTab, async (tab) => {
  await nextTick()
  safeRender(tab)
})

function safeRender(tab: string) {
  // el-tabs lazy: chart container may have 0 width on first paint
  const map: Record<string, () => void> = {
    overview: renderReturnChart,
    daily_pnl: renderPnlChart,
    trades: renderTradeChart,
  }
  const fn = map[tab]
  if (!fn) return
  setTimeout(() => fn(), 80)
}

// ═══════════════════════════════════════════════════
// Chart 1 — 收益走势（策略 vs 基准 + 超额）
// ═══════════════════════════════════════════════════
function renderReturnChart() {
  const el = chartEl.value
  if (!el || !info.value?.nav?.length) return
  if (el.clientWidth === 0) { setTimeout(renderReturnChart, 120); return }
  if (chart) chart.dispose()
  chart = echarts.init(el)

  const nav = info.value.nav as any[]
  const dates = nav.map(r => r.date)
  const stratRet = nav.map(r => +(((r.nav ?? 1) - 1) * 100).toFixed(2))
  const bmRet = nav.map(r => +(((r.benchmark_nav ?? 1) - 1) * 100).toFixed(2))
  const excessRet = nav.map((_r, i) => +(stratRet[i] - bmRet[i]).toFixed(2))
  const hasBm = bmRet.some(v => Math.abs(v) > 0.01)

  const legend = ['策略收益']
  const series: any[] = [
    {
      name: '策略收益', type: 'line', yAxisIndex: 0,
      data: stratRet, symbol: 'none',
      lineStyle: { width: 2, color: '#e6a23c' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(230,162,60,0.22)' },
          { offset: 1, color: 'rgba(230,162,60,0.01)' },
        ]),
      },
    },
  ]
  if (hasBm) {
    legend.push('基准收益', '超额收益')
    series.push(
      {
        name: '基准收益', type: 'line', yAxisIndex: 0,
        data: bmRet, symbol: 'none',
        lineStyle: { width: 1.5, type: 'dashed', color: '#909399' },
      },
      {
        name: '超额收益', type: 'line', yAxisIndex: 0,
        data: excessRet, symbol: 'none',
        lineStyle: { width: 1, color: '#67c23a' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(103,194,58,0.15)' },
            { offset: 1, color: 'rgba(103,194,58,0.01)' },
          ]),
        },
      },
    )
  }

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter(p: any) {
        let h = `<b>${p[0].axisValue}</b>`
        p.forEach((s: any) => {
          h += `<br/>${s.marker} ${s.seriesName}: ${s.value >= 0 ? '+' : ''}${s.value}%`
        })
        return h
      },
    },
    legend: { data: legend, top: 4, textStyle: { fontSize: 11 } },
    grid: { left: 55, right: 20, top: 38, bottom: 36 },
    dataZoom: [{ type: 'inside', start: 0, end: 100 }],
    xAxis: {
      type: 'category', data: dates, boundaryGap: false,
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '{value}%', fontSize: 10 },
      splitLine: { lineStyle: { type: 'dashed', color: '#eee' } },
    },
    series,
  })
}

// ═══════════════════════════════════════════════════
// Chart 2 — 每日盈亏 柱形图
// ═══════════════════════════════════════════════════
function renderPnlChart() {
  const el = pnlChartEl.value
  if (!el || !info.value?.nav?.length) return
  if (el.clientWidth === 0) { setTimeout(renderPnlChart, 120); return }
  if (pnlChart) pnlChart.dispose()
  pnlChart = echarts.init(el)

  const nav = info.value.nav as any[]
  const dates = nav.map(r => r.date)
  const dailyRet = nav.map(r => +((r.daily_return ?? 0) * 100).toFixed(3))
  // 每日盈亏金额
  const dailyPnl = nav.map((r: any, i: number) => {
    if (i === 0) return 0
    return +((r.total_value ?? 0) - (nav[i - 1].total_value ?? 0)).toFixed(2)
  })

  pnlChart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter(p: any) {
        const d = p[0].axisValue
        let h = `<b>${d}</b>`
        p.forEach((s: any) => {
          const unit = s.seriesIndex === 0 ? '%' : ' 元'
          h += `<br/>${s.marker} ${s.seriesName}: ${s.seriesIndex === 0 ? (s.value >= 0 ? '+' : '') : ''}${s.value}${unit}`
        })
        return h
      },
    },
    legend: { data: ['日收益率', '日盈亏金额'], top: 4, textStyle: { fontSize: 11 } },
    grid: { left: 60, right: 60, top: 38, bottom: 36 },
    dataZoom: [{ type: 'inside', start: 0, end: 100 }],
    xAxis: {
      type: 'category', data: dates, boundaryGap: true,
      axisLabel: { fontSize: 10 },
    },
    yAxis: [
      {
        type: 'value', name: '日收益率',
        axisLabel: { formatter: '{value}%', fontSize: 10 },
        splitLine: { lineStyle: { type: 'dashed', color: '#eee' } },
      },
      {
        type: 'value', name: '盈亏(元)',
        axisLabel: { fontSize: 10 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '日收益率', type: 'bar', yAxisIndex: 0,
        data: dailyRet,
        itemStyle: {
          color(p: any) { return p.value >= 0 ? '#f56c6c' : '#67c23a' },
        },
        barMaxWidth: 6,
      },
      {
        name: '日盈亏金额', type: 'line', yAxisIndex: 1,
        data: dailyPnl, symbol: 'none',
        lineStyle: { width: 1, color: '#409eff' },
      },
    ],
  })
}

// ═══════════════════════════════════════════════════
// Chart 3 — 每日买卖 (资金曲线 + 买卖标记)
// ═══════════════════════════════════════════════════
function renderTradeChart() {
  const el = tradeChartEl.value
  if (!el || !info.value?.nav?.length) return
  if (el.clientWidth === 0) { setTimeout(renderTradeChart, 120); return }
  if (tradeChart) tradeChart.dispose()
  tradeChart = echarts.init(el)

  const nav = info.value.nav as any[]
  const trades = (info.value.trades || []) as any[]
  const dates = nav.map(r => r.date)
  const totalVals = nav.map(r => +(N(r.total_value || 0)).toFixed(0))

  // 构建买入/卖出散点数据
  const dateIdx = new Map<string, number>()
  dates.forEach((d, i) => dateIdx.set(d, i))

  const buyPoints: any[] = []
  const sellPoints: any[] = []
  trades.forEach((t: any) => {
    const idx = dateIdx.get(t.date)
    if (idx == null) return
    const val = totalVals[idx]
    const point = [t.date, val, t.code, N(t.price).toFixed(2), N(t.amount).toLocaleString(), t.direction]
    if (t.direction === 'buy') buyPoints.push(point)
    else sellPoints.push(point)
  })

  tradeChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter(p: any) {
        if (p.seriesType === 'scatter') {
          const d = p.data
          return `<b>${d[0]}</b><br/>${d[5] === 'buy' ? '🔴 买入' : '🟢 卖出'} ${d[2]}<br/>价格: ${d[3]}&nbsp;&nbsp;数量: ${d[4]}`
        }
        return `<b>${p.name}</b><br/>${p.marker} 总资产: ${N(p.value).toLocaleString()} 元`
      },
    },
    legend: { data: ['总资产', '买入', '卖出'], top: 4, textStyle: { fontSize: 11 } },
    grid: { left: 70, right: 20, top: 38, bottom: 36 },
    dataZoom: [{ type: 'inside', start: 0, end: 100 }],
    xAxis: {
      type: 'category', data: dates, boundaryGap: false,
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: 'value', name: '总资产(元)',
      axisLabel: { fontSize: 10 },
      splitLine: { lineStyle: { type: 'dashed', color: '#eee' } },
      scale: true,
    },
    series: [
      {
        name: '总资产', type: 'line',
        data: totalVals, symbol: 'none',
        lineStyle: { width: 1.5, color: '#409eff' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64,158,255,0.15)' },
            { offset: 1, color: 'rgba(64,158,255,0.01)' },
          ]),
        },
      },
      {
        name: '买入', type: 'scatter',
        data: buyPoints, symbolSize: 12, symbol: 'triangle',
        itemStyle: { color: '#f56c6c' },
      },
      {
        name: '卖出', type: 'scatter',
        data: sellPoints, symbolSize: 12, symbol: 'diamond',
        itemStyle: { color: '#67c23a' },
      },
    ],
  })
}
</script>

<style scoped>
.bt-detail { padding: 16px 20px; }
.detail-header { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.detail-header h3 { margin: 0; font-size: 16px; }
.header-sub { color: #909399; font-size: 13px; }

/* ── 聚宽风格收益概述表格 ── */
.jq-summary {
  margin-bottom: 18px;
  border: 1px solid #ebeef5; border-radius: 6px; overflow: hidden;
}
.jq-table {
  width: 100%; border-collapse: collapse;
  font-size: 13px;
}
.jq-table td {
  padding: 9px 12px;
  border-bottom: 1px solid #f0f0f0;
}
.jq-table tr:last-child td { border-bottom: none; }
.jq-lbl {
  color: #909399; white-space: nowrap; width: 120px;
  background: #fafafa;
}
.jq-val {
  color: #303133; font-weight: 600; font-variant-numeric: tabular-nums;
  min-width: 90px;
}
.jq-val-sm { font-size: 12px; font-weight: 500; color: #606266; }
.val-red { color: #f56c6c !important; }
.val-green { color: #67c23a !important; }

/* ── Charts ── */
.chart-box { width: 100%; height: 380px; }

/* ── Logs ── */
.log-box {
  max-height: 500px; overflow-y: auto; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px;
  background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 4px;
}
.log-line { white-space: pre-wrap; line-height: 1.5; }
.log-empty { text-align: center; color: #606266; padding: 40px; }
</style>
